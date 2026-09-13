"""Ship simulation facade: assembles a vessel from content and runs it.

Owns the kernel primitives, the electrical network, devices, telemetry, and
annunciators. Registration/execution order derives from blueprint order
(determinism, ADR-0002 §3). Interaction layers drive this via `execute()`
(verbs on SCL addresses) and read via telemetry/observation only.
"""

from __future__ import annotations

from collections.abc import Callable

from ultraspace.content import ContentTree
from ultraspace.content.schemas import DeviceSpec, ShipSpec
from ultraspace.kernel import TICK_US, EventLog, Phase, RngHub, Scheduler, SimClock
from ultraspace.networks import DataBus, ElectricalNetwork
from ultraspace.ship.annunciators import AnnunciatorPanel
from ultraspace.ship.devices import (
    Battery,
    BusController,
    BusJunction,
    CommandResult,
    Contactor,
    DataDevice,
    ElectricalDevice,
    HarnessSegment,
    Precharge,
    RemoteTerminal,
    _Switch,
    build_device,
    refused,
)
from ultraspace.ship.telemetry import TelemetryItem, TelemetryStore

__all__ = ["Simulation"]

_ELECTRICAL = (
    "battery",
    "contactor",
    "breaker",
    "precharge",
    "load",
    "bc",
    "rt",
    "junction",
    "harness_seg",
)
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
            spec.id: DataBus(spec.id, spec.termination_ohm) for spec in self.ship.data_buses
        }
        self._bcs: dict[str, BusController] = {}  # bus id -> its controller
        self._rts_by_bus: dict[str, list[RemoteTerminal]] = {
            spec.id: [] for spec in self.ship.data_buses
        }

        harness: list[DeviceSpec] = []  # segment specs, wired in a second pass
        for spec in self.ship.devices:
            part = tree.parts[spec.part]
            if part.behavior in _ELECTRICAL:
                device = build_device(spec, part, DT_S)
                if isinstance(device, Contactor):
                    device.bind(self.net, self.log, self.clock)
                if spec.data_bus is not None:
                    self._attach_data_device(spec, device)
                    if isinstance(device, HarnessSegment):
                        harness.append(spec)
                self.devices[spec.id] = device
                self._electrical.append(device)
            elif part.behavior in _XDUCERS:
                self._xducers.append(spec)
            if spec.scl is not None:
                self.address_map.setdefault(spec.scl, []).append(spec.id)

        for segment_spec in harness:  # segments join members, so members go first
            self._wire_harness_segment(segment_spec)

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

    def _attach_data_device(self, spec: DeviceSpec, device: ElectricalDevice) -> None:
        """Register a data-bus device with its bus model (ata-42 §9).

        Harness and couplers bind a de-energized gate shared by the DMM and
        the repair verb: work requires a dead bus, real shop practice.
        """
        assert spec.data_bus is not None  # loader-validated
        bus = self.data_buses[spec.data_bus]
        if isinstance(device, BusController):
            device.bind(bus)
            bus.bind_bc(spec.id)
            self._bcs[spec.data_bus] = device
        elif isinstance(device, RemoteTerminal):
            bus.register_rt(device.address, spec.id)
            self._rts_by_bus[spec.data_bus].append(device)
            device.bind(self._de_energized_gate(spec.data_bus), self.log, self.clock)
        elif isinstance(device, BusJunction):
            bus.register_junction(spec.id)
            device.bind(bus, self._de_energized_gate(spec.data_bus), self.log, self.clock)
        elif isinstance(device, HarnessSegment):
            device.bind(bus, self._de_energized_gate(spec.data_bus), self.log, self.clock)

    def _wire_harness_segment(self, spec: DeviceSpec) -> None:
        """Second assembly pass: join two bus members with a harness run.

        Segments name their ends by device id, so every BC/RT/coupler must be
        registered first — otherwise blueprint *order* would decide whether a
        ship builds, and content that passes `validate` could still crash the
        builder (ata-42-data.md §9: harness errors are load-time, always).
        """
        assert spec.data_bus is not None  # loader-validated
        self.data_buses[spec.data_bus].add_segment(spec.id, spec.ends["a"], spec.ends["b"])

    def _de_energized_gate(self, bus_id: str) -> Callable[[], bool]:
        def de_energized() -> bool:
            members: list[DataDevice] = [self._bcs[bus_id], *self._rts_by_bus[bus_id]]
            return not any(member.energized for member in members)

        return de_energized

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
        A poll succeeds iff the RT is energized, alive, and *reachable*, and
        the medium carried the transaction: a stuck-dominant RT jams it
        (protocol), a trunk short kills it (electrical) — both bus-wide,
        computed from physical truth each tick.
        """
        for bus_id, bus in self.data_buses.items():
            bc = self._bcs.get(bus_id)
            if bc is None or not bc.energized:
                continue
            rts = self._rts_by_bus[bus_id]
            jammed = any(rt.stuck_dominant and rt.energized for rt in rts)
            medium_dead = bus.has_trunk_short()
            for rt in rts:
                answered = (
                    rt.energized
                    and not rt.dead
                    and not jammed
                    and not medium_dead
                    and bus.reachable(rt.id, bc.id)
                )
                bus.poll(rt.address, answered)

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
            parts = [
                self.devices[d].read_result() if d in self.devices else self._read_one(d)
                for d in device_ids
            ]
            return CommandResult(all(p.ok for p in parts), "\n".join(p.text for p in parts))
        actionable = [d for d in device_ids if d in self.devices]
        if len(actionable) != 1:
            return refused(f"{address}: verb {verb!r} not supported here")
        return self.devices[actionable[0]].execute(verb, flags)

    def _read_one(self, device_id: str) -> CommandResult:
        item = self.telemetry.read(device_id)
        if item is None:
            return CommandResult(True, f"{device_id}: --- NO DATA (no report yet)")
        age_s = (self.clock.tick_index - item.tick) * DT_S
        return CommandResult(
            True,
            f"{device_id}: {item.value:8.3f} {item.unit:<4} src: {item.source}  age {age_s:.1f} s",
        )

    def summary(self) -> str:
        lines = [f"{self.ship.name} — MET {self.clock.mission_elapsed_str()}"]
        caution = self.panel.active_messages()
        lines.append(f"MASTER CAUTION: {'ACTIVE — ' + ', '.join(caution) if caution else 'clear'}")
        lines.extend(self._read_one(t).text for t in self.telemetry.ids())
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
            # "not declared FAILED", not "answered the last poll": the count
            # tracks the BC's declaration (SOM 42-00-00 §3 — three consecutive
            # misses), so a terminal that just started missing still counts
            # here while the table already shows NO RESPONSE against it.
            lines.append(f"{bus_id}: {state} — {healthy}/{total} RTs healthy (bc {bc.id})")
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
