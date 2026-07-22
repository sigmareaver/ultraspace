"""Ship simulation facade: assembles a vessel from content and runs it.

Owns the kernel primitives, the electrical network, devices, telemetry, and
annunciators. Registration/execution order derives from blueprint order
(determinism, ADR-0002 §3). Interaction layers drive this via `execute()`
(verbs on SCL addresses) and read via telemetry/observation only.
"""

from __future__ import annotations

from ultraspace.content import ContentTree
from ultraspace.content.schemas import DeviceSpec, ShipSpec
from ultraspace.kernel import TICK_US, EventLog, Phase, RngHub, Scheduler, SimClock
from ultraspace.networks import DataBus, ElectricalNetwork
from ultraspace.ship.annunciators import AnnunciatorPanel
from ultraspace.ship.devices import (
    Battery,
    BusController,
    CommandResult,
    Contactor,
    ElectricalDevice,
    Precharge,
    RemoteTerminal,
    _Switch,
    build_device,
    refused,
)
from ultraspace.ship.telemetry import TelemetryItem, TelemetryStore

__all__ = ["Simulation"]

_ELECTRICAL = ("battery", "contactor", "breaker", "precharge", "load", "bc", "rt")
_XDUCERS = ("xducer_v", "xducer_i", "xducer_soc")
DT_S = TICK_US / 1_000_000


class Simulation:
    def __init__(self, tree: ContentTree, ship_id: str, master_seed: int) -> None:
        if not tree.ok:
            raise ValueError(f"content tree has errors: {tree.errors[0]}")
        self.ship: ShipSpec = tree.ships[ship_id]
        self.clock = SimClock()
        self.log = EventLog()
        self.rng = RngHub(master_seed)
        self.scheduler = Scheduler()
        self.telemetry = TelemetryStore()
        self.net = ElectricalNetwork([(n.id, n.c_f) for n in self.ship.nodes], DT_S)
        self.panel = AnnunciatorPanel(self.ship.annunciators)

        self.devices: dict[str, ElectricalDevice] = {}
        self._electrical: list[ElectricalDevice] = []  # blueprint order
        self._xducers: list[DeviceSpec] = []
        self.address_map: dict[str, list[str]] = {}  # scl address -> device ids
        self.data_buses: dict[str, DataBus] = {
            spec.id: DataBus(spec.id) for spec in self.ship.data_buses
        }
        self._bcs: dict[str, BusController] = {}  # bus id -> its controller
        self._rts_by_bus: dict[str, list[RemoteTerminal]] = {
            spec.id: [] for spec in self.ship.data_buses
        }

        for spec in self.ship.devices:
            part = tree.parts[spec.part]
            if part.behavior in _ELECTRICAL:
                device = build_device(spec, part, DT_S)
                if isinstance(device, Contactor):
                    device.bind(self.net, self.log, self.clock)
                if isinstance(device, BusController | RemoteTerminal):
                    assert spec.data_bus is not None  # loader-validated
                    bus = self.data_buses[spec.data_bus]
                    if isinstance(device, BusController):
                        device.bind(bus)
                        self._bcs[spec.data_bus] = device
                    else:
                        bus.register_rt(device.address)
                        self._rts_by_bus[spec.data_bus].append(device)
                self.devices[spec.id] = device
                self._electrical.append(device)
            elif part.behavior in _XDUCERS:
                self._xducers.append(spec)
            if spec.scl is not None:
                self.address_map.setdefault(spec.scl, []).append(spec.id)

        for spec in self.ship.devices:  # second pass: interlock references
            if spec.interlock_open is not None:
                device = self.devices[spec.id]
                target = self.devices[spec.interlock_open]
                if isinstance(device, Precharge) and isinstance(target, _Switch):
                    device.bind_interlock(target)

        self._xducer_parts = {spec.id: tree.parts[spec.part] for spec in self._xducers}

        self.scheduler.register(Phase.NETWORKS, "electrical", self._electrical_task)
        self.scheduler.register(Phase.NETWORKS, "data", self._data_task)
        self.scheduler.register(Phase.INSTRUMENTS, "instruments", self._instruments_task)
        self.scheduler.register(Phase.ANNUNCIATORS, "annunciators", self._annunciators_task)

    # -- tick tasks ----------------------------------------------------------

    def _electrical_task(self, tick: int) -> None:
        self.net.begin()
        for device in self._electrical:
            device.stamp(self.net)
        self.net.solve()
        for device in self._electrical:
            device.after_solve(self.net, self.log, tick)

    def _data_task(self, tick: int) -> None:
        """BC cyclic schedule: one status poll per registered RT (ata-42 §3).

        Runs after the electrical solve so rail truth (``energized``) is fresh.
        An unpowered BC issues no polls at all — the ledger stays untouched.
        """
        for bus_id, bus in self.data_buses.items():
            bc = self._bcs.get(bus_id)
            if bc is None or not bc.energized:
                continue
            for rt in self._rts_by_bus[bus_id]:
                bus.poll(rt.address, rt.answers_poll())

    def _instruments_task(self, tick: int) -> None:
        # M1: transducers are rig-powered (TB-1 is a breadboard); they move onto
        # ship buses + the data network at M2 (ata-24-eps.md §4).
        for spec in self._xducers:
            part = self._xducer_parts[spec.id]
            noise = self.rng.stream(f"sensor/{spec.id}/noise")
            assert spec.measures is not None  # loader-validated
            if part.behavior == "xducer_v":
                value = self.net.voltage_v(spec.measures) + noise.gauss(0.0, part.params["sigma_v"])
                unit = "V"
            elif part.behavior == "xducer_i":
                value = self.devices[spec.measures].last_i_a + noise.gauss(
                    0.0, part.params["sigma_a"]
                )
                unit = "A"
            else:  # xducer_soc
                battery = self.devices[spec.measures]
                assert isinstance(battery, Battery)
                value = battery.soc + noise.gauss(0.0, part.params["sigma_frac"])
                unit = "frac"
            self.telemetry.publish(
                TelemetryItem(spec.id, value, unit, f"{spec.id} ({part.part_number})", tick)
            )
        for bc in self._bcs.values():  # instruments are devices: unpowered = silent
            if bc.energized:
                self.telemetry.publish(
                    TelemetryItem(
                        bc.id,
                        bc.bus.health_frac(),
                        "frac",
                        f"{bc.id} ({bc.part.part_number})",
                        tick,
                    )
                )

    def _annunciators_task(self, tick: int) -> None:
        self.panel.scan(self.telemetry, self.log, tick)

    # -- run -----------------------------------------------------------------

    def step(self, ticks: int = 1) -> None:
        for _ in range(ticks):
            self.scheduler.run_tick(self.clock.tick_index)
            self.clock.advance()

    def step_s(self, seconds: float) -> None:
        self.step(max(1, round(seconds / DT_S)))

    # -- command surface (used by interaction/scl) ----------------------------

    def execute(self, address: str, verb: str, flags: set[str]) -> CommandResult:
        device_ids = self.address_map.get(address)
        if device_ids is None:
            return refused(f"unknown address {address!r}")
        if verb == "read":
            return CommandResult(True, "\n".join(self._read_one(d) for d in device_ids))
        actionable = [d for d in device_ids if d in self.devices]
        if len(actionable) != 1:
            return refused(f"{address}: verb {verb!r} not supported here")
        return self.devices[actionable[0]].execute(verb, flags)

    def _read_one(self, device_id: str) -> str:
        if device_id in self.devices:
            device = self.devices[device_id]
            if isinstance(device, BusController):
                return device.readout()  # the analyzer table, not just the one-liner
            return device.observe()  # panel observation
        item = self.telemetry.read(device_id)
        if item is None:
            return f"{device_id}: --- NO DATA (no report yet)"
        age_s = (self.clock.tick_index - item.tick) * DT_S
        return (
            f"{device_id}: {item.value:8.3f} {item.unit:<4} src: {item.source}  age {age_s:.1f} s"
        )

    def summary(self) -> str:
        lines = [f"{self.ship.name} — MET {self.clock.mission_elapsed_str()}"]
        caution = self.panel.active_messages()
        lines.append(f"MASTER CAUTION: {'ACTIVE — ' + ', '.join(caution) if caution else 'clear'}")
        lines.extend(self._read_one(t) for t in self.telemetry.ids())
        return "\n".join(lines)

    def summarize(self, root: str) -> str:
        """System-level `read` summary for an address root (SCL dispatcher)."""
        if root == "data":
            return self._data_summary()
        return self.summary()  # eps is the M1 default summary

    def _data_summary(self) -> str:
        lines = [f"{self.ship.name} — DATA — MET {self.clock.mission_elapsed_str()}"]
        for bus_id, bus in self.data_buses.items():
            bc = self._bcs.get(bus_id)
            if bc is None or not bc.energized:
                lines.append(f"{bus_id}: --- NO DATA (bus controller unpowered)")
                continue
            total = len(bus.rt_addresses())
            healthy = round(bus.health_frac() * total)
            state = "DEGRADED" if bus.degraded else "HEALTHY"
            lines.append(f"{bus_id}: {state} — {healthy}/{total} RTs responding (bc {bc.id})")
        if not self.data_buses:
            lines.append("(no data buses fitted)")
        return "\n".join(lines)

    # -- conservation audit (invariant tests; not a player surface) -----------

    def power_audit_w(self) -> tuple[float, float, float]:
        """(source_w, dissipated_w, stored_w) for the last solved tick."""
        source_w = 0.0
        dissipated_w = 0.0
        for device in self._electrical:
            src, dis = device.powers_w(self.net)
            source_w += src
            dissipated_w += dis
        return source_w, dissipated_w, self.net.capacitor_power_w()
