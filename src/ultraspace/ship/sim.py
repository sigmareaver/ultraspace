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
from ultraspace.ship.environment import CM2_PER_M2, Environment
from ultraspace.ship.faults import apply_fault
from ultraspace.ship.stress import Hazard, StressModel
from ultraspace.ship.telemetry import STALE_AFTER_TICKS, TelemetryItem, TelemetryStore
from ultraspace.ship.units import UnitRegistry

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
_XDUCERS = ("xducer_v", "xducer_i", "xducer_soc", "xducer_flux")
_SWITCHING = ("contactor", "breaker", "precharge")
DT_S = TICK_US / 1_000_000

#: The annunciator panel's SCL address. A *fixture*, not yet a device: it has
#: an address and verbs but no electrical ports, because the honest version
#: needs a feed and lamps that burn out (ata-31-indicating.md §5, §9).
ANNUNCIATOR_ADDRESS = "sys.annunciator"

#: Lamp test duration: long enough to look along the row and see a dark one.
LAMP_TEST_TICKS = 20

#: The maintenance stores sheet (failure-and-repair.md, MAINT v1). Like the
#: annunciator panel it is a fixture with an address and no electrical ports —
#: a shelf is not a device, but it is a thing the crew reads.
MAINT_ADDRESS = "maint.stores"

#: Addressable fixtures: they answer verbs but own no hardware.
FIXTURE_ADDRESSES = (ANNUNCIATOR_ADDRESS, MAINT_ADDRESS)

SECONDS_PER_HOUR = 3600.0


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
        self.environment = Environment()  # the world layer owns writes to this
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
        # Built before assembly: units are content-derived, so the registry is
        # the authority every position binds itself to (ship/units.py).
        self.units = UnitRegistry(self.ship, tree.parts)

        harness: list[DeviceSpec] = []  # segment specs, wired in a second pass
        for spec in self.ship.devices:
            part = tree.parts[spec.part]
            if part.behavior in _ELECTRICAL:
                device = build_device(spec, part, DT_S)
                device.unit = self.units.unit_at(spec.id)
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

        for fixture in FIXTURE_ADDRESSES:
            self.address_map.setdefault(fixture, []).append(fixture)

        for segment_spec in harness:  # segments join members, so members go first
            self._wire_harness_segment(segment_spec)
        self._bind_interlocks()

        self._feeders = self._find_feeders(tree)
        self._xducer_parts = {spec.id: tree.parts[spec.part] for spec in self._xducers}
        self._carriers = self._bind_carriers()
        self.stress = StressModel(self._build_hazards(tree), self.rng, self.environment, self.log)

        self.scheduler.register(Phase.NETWORKS, "electrical", self._electrical_task)
        self.scheduler.register(Phase.NETWORKS, "data", self._data_task)
        self.scheduler.register(Phase.DEVICES, "units", self._units_task)
        self.scheduler.register(Phase.FAULTS, "stress", self.stress.tick)
        self.scheduler.register(Phase.INSTRUMENTS, "instruments", self._instruments_task)
        self.scheduler.register(Phase.ANNUNCIATORS, "annunciators", self._annunciators_task)

    def _bind_interlocks(self) -> None:
        """Second assembly pass: precharge units name the tie they gate on."""
        for spec in self.ship.devices:
            if spec.interlock_open is None:
                continue
            device = self.devices[spec.id]
            target = self.devices[spec.interlock_open]
            if isinstance(device, Precharge) and isinstance(target, _Switch):
                device.bind_interlock(target)

    def _build_hazards(self, tree: ContentTree) -> list[Hazard]:
        """Every declared (device, mode) susceptibility, in blueprint order.

        A part with no `hazard` block contributes nothing and never fails on
        its own — the correct default for hardware nobody has characterised.
        """
        hazards: list[Hazard] = []
        for spec in self.ship.devices:
            part = tree.parts[spec.part]
            for mode in sorted(part.hazard):  # sorted: content order must not matter
                hazards.append(Hazard.build(self.devices[spec.id], mode, part.hazard[mode]))
        return hazards

    def apply_fault(self, device_id: str, mode: str, by: str) -> bool:
        """Put a device into a fault mode and record who did it.

        The one door for authored casualties (scenario scripts) and for the
        test-only injection console; the stress model uses the same
        application call with its own, richer FDR record (stress.py).
        """
        changed = apply_fault(self.devices[device_id], mode)
        self.log.append(
            self.clock.tick_index,
            device_id,
            "fault-onset" if changed else "fault-reasserted",
            {"mode": mode, "by": by},
        )
        return changed

    def _bind_carriers(self) -> dict[str, RemoteTerminal]:
        """Transducer id -> the RT that transports it; absent means panel-wired.

        Panel wiring is the default and the reason cold start works at all:
        SOM 24-30-01 reads BUS E before any data bus exists (ata-42 §4).
        """
        carriers: dict[str, RemoteTerminal] = {}
        for spec in self._xducers:
            if spec.carried_by is None:
                continue
            carrier = self.devices[spec.carried_by]
            assert isinstance(carrier, RemoteTerminal)  # loader-validated
            carriers[spec.id] = carrier
        return carriers

    def _attach_data_device(self, spec: DeviceSpec, device: ElectricalDevice) -> None:
        """Register a data-bus device with its bus model (ata-42 §9).

        Harness and couplers bind a de-energized gate shared by the DMM and
        the repair verb: work requires a dead bus, real shop practice.
        """
        assert spec.data_bus is not None  # loader-validated
        bus = self.data_buses[spec.data_bus]
        if isinstance(device, BusController):
            device.bind(bus, self.log, self.clock)
            bus.bind_bc(spec.id)
            self._bcs[spec.data_bus] = device
        elif isinstance(device, RemoteTerminal):
            bus.register_rt(device.address, spec.id)
            self._rts_by_bus[spec.data_bus].append(device)
            device.bind(
                self._de_energized_gate(spec.data_bus),
                self.log,
                self.clock,
                self._swap_gate(device),
            )
        elif isinstance(device, BusJunction):
            bus.register_junction(spec.id)
            device.bind(bus, self._de_energized_gate(spec.data_bus), self.log, self.clock)
        elif isinstance(device, HarnessSegment):
            device.bind(bus, self._de_energized_gate(spec.data_bus), self.log, self.clock)

    def _find_feeders(self, tree: ContentTree) -> dict[str, str]:
        """Device id -> the switching device that feeds it, by blueprint walk.

        The same upstream walk the WDM feeder trees are generated from, so a
        rewired ship cannot print a stale breaker id. Nothing here is a view
        into the sim: a breaker position is something the crew reads off a
        panel, and this only saves them the walk (ata-42-data.md §3).
        """
        on_node: dict[str, list[DeviceSpec]] = {}
        for spec in self.ship.devices:
            for node in spec.ports.values():
                on_node.setdefault(node, []).append(spec)
        feeders: dict[str, str] = {}
        for spec in self.ship.devices:
            feed = spec.ports.get("pos")
            if feed is None:
                continue
            for other in on_node.get(feed, []):
                if other.id != spec.id and tree.parts[other.part].behavior in _SWITCHING:
                    feeders[spec.id] = other.id
                    break
        return feeders

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

    # -- maintenance (failure-and-repair.md, MAINT v1) ------------------------

    def _swap_gate(self, rt: RemoteTerminal) -> Callable[[str], CommandResult]:
        """The terminal's `remove`/`install`, once its interlock has passed."""

        def swap(verb: str) -> CommandResult:
            return self._remove_unit(rt) if verb == "remove" else self._install_unit(rt)

        return swap

    def _remove_unit(self, rt: RemoteTerminal) -> CommandResult:
        if rt.unit is None:
            return refused(f"{rt.id}: position already open — nothing to remove")
        found = rt.pulled()  # the fault comes off with the box, silently
        unit = self.units.remove(rt.id, self.clock.tick_index, fault_found=found)
        rt.unit = None
        self.log.append(
            self.clock.tick_index,
            rt.id,
            "unit-removed",
            {"serial": unit.serial, "part_number": unit.part_number, "fault_found": found},
        )
        return CommandResult(
            True, f"{rt.id}: {unit.serial} removed — position open (MAINT 42-110-001)"
        )

    def _install_unit(self, rt: RemoteTerminal) -> CommandResult:
        if rt.unit is not None:
            return refused(
                f"{rt.id}: position occupied by {rt.unit.serial} — remove it first "
                f"(MAINT 42-110-001)"
            )
        unit = self.units.install(rt.id, rt.spec.part, self.clock.tick_index)
        if unit is None:
            pn = rt.part.part_number
            return refused(f"{rt.id}: no {pn} in stores (IPC {pn}; MAINT 00-00 §1)")
        rt.unit = unit
        rt.dead = False  # a unit off the shelf has no history on this ship
        rt.stuck_dominant = False
        self.log.append(
            self.clock.tick_index,
            rt.id,
            "unit-installed",
            {"serial": unit.serial, "part_number": unit.part_number},
        )
        return CommandResult(
            True, f"{rt.id}: {unit.serial} installed from stores — verify (SOM 42-30-01)"
        )

    def _records_one(self, device_id: str) -> CommandResult:
        """A nameplate and a logbook page — not a verdict (MAINT 00-00 §4)."""
        unit = self.units.unit_at(device_id)
        if unit is None:
            opened = self.units.open_positions.get(device_id)
            if opened is None:
                return CommandResult(True, f"{device_id}: no unit record")
            since = SimClock(opened).mission_elapsed_str()
            return CommandResult(True, f"{device_id}: NOT FITTED — position open since MET {since}")
        device = self.devices.get(device_id)
        hours = (
            f"{unit.hours_s / SECONDS_PER_HOUR:.2f} h"
            if device is not None and device.tracks_hours
            else "not tracked"
        )
        lines = [
            f"{device_id}: {unit.serial} — {unit.name}",
            f"   P/N {unit.part_number}   position {device_id}   hours {hours}",
        ]
        lines.extend(
            f"   MET {SimClock(event.tick).mission_elapsed_str()}  "
            f"{event.what:<10} {event.position}"
            for event in unit.history
        )
        return CommandResult(True, "\n".join(lines))

    def _fixture_command(self, address: str, verb: str) -> CommandResult:
        if address == ANNUNCIATOR_ADDRESS:
            return self._annunciator_command(verb)
        return self._maint_command(verb)

    def _maint_command(self, verb: str) -> CommandResult:
        if verb == "read":
            return CommandResult(True, self._maint_summary())
        return refused(f"{MAINT_ADDRESS}: verb {verb!r} not supported (try: read)")

    def _maint_summary(self) -> str:
        """Stores, bench, and open positions — the ship's own paperwork.

        The only place an emptied position is written down: the bus controller
        cannot see an empty rack and says NO RESPONSE either way (MAINT 00-00 §3).
        """
        lines = [f"{self.ship.name} — MAINT — MET {self.clock.mission_elapsed_str()}", "STORES"]
        if not self.units.stores:
            lines.append("  (no spares carried)")
        for part_id, shelf in self.units.stores.items():
            part_number, name = self.units.store_parts[part_id]
            count = f"{len(shelf)} on shelf" if shelf else "NO SPARES"
            lines.append(f"  {part_number:<12} {name:<42} {count}")
        lines.append("BENCH")
        if not self.units.bench:
            lines.append("  (nothing removed)")
        lines.extend(
            f"  {unit.serial}  off {unit.history[-1].position} at MET "
            f"{SimClock(unit.history[-1].tick).mission_elapsed_str()} — not bench-tested"
            for unit in self.units.bench
        )
        lines.append("OPEN POSITIONS")
        if not self.units.open_positions:
            lines.append("  (none)")
        lines.extend(
            f"  {device_id}  NOT FITTED since MET {SimClock(tick).mission_elapsed_str()}"
            for device_id, tick in self.units.open_positions.items()
        )
        return "\n".join(lines)

    # -- tick tasks ----------------------------------------------------------

    def _units_task(self, tick: int) -> None:
        """Accrue powered hours. Blueprint order; only where the gate is known."""
        for device_id, device in self.devices.items():
            if device.tracks_hours and device.operating:
                self.units.accrue(device_id, DT_S)

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

    def _delivered(self, xducer_id: str) -> bool:
        """Did this transducer's sample reach the store this tick?

        Panel-wired transducers always deliver — copper, no network (§4), and
        cold start depends on it. A carried one delivers only when its
        controller is powered *and* its terminal answered the poll issued this
        tick; ``answered_last`` alone would go stale the moment the BC stops
        polling, which is precisely the BC-unpowered case.
        """
        carrier = self._carriers.get(xducer_id)
        if carrier is None:
            return True
        assert carrier.spec.data_bus is not None  # loader-validated
        bc = self._bcs.get(carrier.spec.data_bus)
        if bc is None or not bc.energized:
            return False
        return bc.bus.rt(carrier.address).answered_last

    def _instruments_task(self, tick: int) -> None:
        """Sample every transducer; publish the ones whose transport delivered.

        The sensor keeps sensing whatever the bus is doing: the noise stream is
        drawn unconditionally, so a bus casualty can never shift the RNG
        sequence (ADR-0002). What a dark terminal costs is *delivery* — the
        store keeps the last item that got through and it ages (§4).
        """
        for spec in self._xducers:
            part = self._xducer_parts[spec.id]
            noise = self.rng.stream(f"sensor/{spec.id}/noise")
            if part.behavior == "xducer_v":
                assert spec.measures is not None  # loader-validated
                value = self.net.voltage_v(spec.measures) + noise.gauss(0.0, part.params["sigma_v"])
                unit = "V"
            elif part.behavior == "xducer_i":
                assert spec.measures is not None  # loader-validated
                value = self.devices[spec.measures].last_i_a + noise.gauss(
                    0.0, part.params["sigma_a"]
                )
                unit = "A"
            elif part.behavior == "xducer_soc":
                assert spec.measures is not None  # loader-validated
                battery = self.devices[spec.measures]
                assert isinstance(battery, Battery)
                value = battery.soc + noise.gauss(0.0, part.params["sigma_frac"])
                unit = "frac"
            else:  # xducer_flux — the environment monitor, reading its own face
                value = self.environment.flux_m2s / CM2_PER_M2 + noise.gauss(
                    0.0, part.params["sigma_cm2s"]
                )
                unit = "p/cm2s"
            if self._delivered(spec.id):
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
        if address in FIXTURE_ADDRESSES:
            return self._fixture_command(address, verb)
        device_ids = self.address_map.get(address)
        if device_ids is None:
            return refused(f"unknown address {address!r}")
        if verb == "read":
            parts = [
                self.devices[d].read_result() if d in self.devices else self._read_one(d)
                for d in device_ids
            ]
            return CommandResult(all(p.ok for p in parts), "\n".join(p.text for p in parts))
        if verb == "records":
            # Answered everywhere, like `read`: every box on the ship has a
            # nameplate, whether or not it has a verb (MAINT 00-00 §1).
            records = [self._records_one(d) for d in device_ids]
            return CommandResult(all(r.ok for r in records), "\n".join(r.text for r in records))
        actionable = [d for d in device_ids if d in self.devices]
        if len(actionable) != 1:
            return refused(f"{address}: verb {verb!r} not supported here")
        return self.devices[actionable[0]].execute(verb, flags)

    def _read_one(self, device_id: str) -> CommandResult:
        item = self.telemetry.read(device_id)
        if item is None:
            return CommandResult(True, f"{device_id}: --- NO DATA (no report yet)")
        age_ticks = self.clock.tick_index - item.tick
        age_s = age_ticks * DT_S
        # Teletype has no dim, so the word carries what the panel says with
        # style: past the horizon the reading is marked, not hidden (§4).
        tag = "  ? STALE" if age_ticks > STALE_AFTER_TICKS else ""
        return CommandResult(
            True,
            f"{device_id}: {item.value:8.3f} {item.unit:<4} "
            f"src: {item.source}  age {age_s:.1f} s{tag}",
        )

    def summary(self) -> str:
        lines = [f"{self.ship.name} — MET {self.clock.mission_elapsed_str()}"]
        lines.extend(self._master_lines())
        lines.extend(self._read_one(t).text for t in self.telemetry.ids())
        return "\n".join(lines)

    def _master_lines(self) -> list[str]:
        """The two master lights. The caution line always prints, lit or not.

        `MASTER CAUTION: clear` is the sentence the crew has been reading since
        M1 and it is still true; the warning line appears only when there is
        something at that level, because a permanently displayed "no warnings"
        is how a panel teaches people to stop looking.
        """
        lines = []
        for severity, lit, new in (
            ("WARNING", self.panel.master_warning, self.panel.master_warning_new),
            ("CAUTION", self.panel.master_caution, self.panel.master_caution_new),
        ):
            messages = [
                a.spec.message for a in self.panel.recall() if a.spec.severity.upper() == severity
            ]
            if not lit:
                if severity == "CAUTION":
                    lines.append("MASTER CAUTION: clear")
                continue
            mark = " (NEW)" if new else ""
            lines.append(f"MASTER {severity}: ACTIVE{mark} — {', '.join(messages)}")
        return lines

    def _annunciator_command(self, verb: str) -> CommandResult:
        """The panel's own verbs (ata-31-indicating.md §5)."""
        if verb == "read":
            return CommandResult(True, self._annunciator_summary())
        if verb == "ack":
            seen = self.panel.acknowledge(self.log, self.clock.tick_index)
            if not seen:
                return CommandResult(True, "sys.annunciator: nothing new to acknowledge")
            return CommandResult(
                True, f"sys.annunciator: {len(seen)} acknowledged — {', '.join(seen)}"
            )
        if verb == "test":
            self.panel.lamp_test(self.log, self.clock.tick_index, LAMP_TEST_TICKS)
            return CommandResult(
                True, f"sys.annunciator: lamp test, all lamps lit {LAMP_TEST_TICKS * DT_S:.0f} s"
            )
        return refused(f"{ANNUNCIATOR_ADDRESS}: verb {verb!r} not supported (try: read, ack, test)")

    def _annunciator_summary(self) -> str:
        """The recall list, in the order the QRH says to work it (QRH 00-00 §1)."""
        lines = [f"{self.ship.name} — ANNUNCIATORS — MET {self.clock.mission_elapsed_str()}"]
        if self.panel.testing:
            lines.append("PANEL TEST — every lamp lit")
            lines.extend(f"   TEST      {a.spec.message}" for a in self.panel.annunciators)
            return "\n".join(lines)
        lines.extend(self._master_lines())
        lit = self.panel.recall()
        if not lit:
            lines.append("(no annunciations)")
        lines.extend(
            f" {'!' if a.is_new else ' '} {a.spec.severity.upper():<9} {a.spec.message}"
            for a in lit
        )
        return "\n".join(lines)

    def summarize(self, root: str) -> str:
        """System-level `read` summary for an address root (SCL dispatcher)."""
        if root == "data":
            return self._data_summary()
        if root == "sys":
            return self._annunciator_summary()
        if root == "maint":
            return self._maint_summary()
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
            state = bus.state_word()
            # "not declared FAILED", not "answered the last poll": the count
            # tracks the BC's declaration (SOM 42-00-00 §3 — three consecutive
            # misses), so a terminal that just started missing still counts
            # here while the table already shows NO RESPONSE against it.
            lines.append(f"{bus_id}: {state} — {healthy}/{total} RTs healthy (bc {bc.id})")
            lines.extend(self._silent_terminal_lines(bus_id))
        if not self.data_buses:
            lines.append("(no data buses fitted)")
        lines.extend(self._seu_lines())
        return "\n".join(lines)

    def _silent_terminal_lines(self, bus_id: str) -> list[str]:
        """One line per terminal the bus has declared FAILED, annotated.

        The BC's table answers for the BC: a terminal that does not reply is
        NO RESPONSE and nothing more. This page is the *ship's*, and the ship
        knows two things the controller cannot — which feeder is open, and
        which position maintenance left empty. Both are facts the crew could
        read at another address; printing them here saves the walk and invents
        nothing. A bare NO RESPONSE therefore carries real information: the
        ship has no innocent explanation for this one (ata-42-data.md §3).
        """
        bus = self.data_buses[bus_id]
        lines = []
        for rt in self._rts_by_bus[bus_id]:
            if not bus.rt(rt.address).failed:
                continue
            lines.append(f"  RT {rt.address}: NO RESPONSE{self._silence_note(rt)}")
        return lines

    def _silence_note(self, rt: RemoteTerminal) -> str:
        if rt.unit is None:
            opened = self.units.open_positions.get(rt.id)
            since = SimClock(opened).mission_elapsed_str() if opened is not None else "assembly"
            return f" — NOT FITTED (position open since MET {since})"
        feeder = self._feeders.get(rt.id)
        switch = self.devices.get(feeder) if feeder is not None else None
        if isinstance(switch, _Switch) and switch.state != "closed":
            return f" — SHED ({feeder} {switch.state})"
        return ""

    def _seu_lines(self) -> list[str]:
        """The particle environment, as the monitor reports it (42-00-00 §9).

        Read from telemetry like everything else: with no monitor fitted there
        is no line, which is the honest answer — the ship does not know.
        """
        return [
            self._read_one(spec.id).text
            for spec in self._xducers
            if self._xducer_parts[spec.id].behavior == "xducer_flux"
        ]

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
