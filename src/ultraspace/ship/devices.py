"""Device behaviors: EPS (ata-24-eps.md §2) and data hardware (ata-42-data.md §9).

Devices stamp the electrical network each tick and update their state after
the solve. In-fiction failure is state (`tripped`), never an exception
(Iron Law 7). Command semantics return CommandResult; refusals cite manuals.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ultraspace.content.schemas import DeviceSpec, PartSpec
from ultraspace.kernel import EventLog, SimClock
from ultraspace.networks import DataBus, ElectricalNetwork
from ultraspace.ship.units import Unit

__all__ = [
    "Battery",
    "Breaker",
    "BusController",
    "BusJunction",
    "CommandResult",
    "Contactor",
    "DataDevice",
    "ElectricalDevice",
    "HarnessElement",
    "HarnessSegment",
    "Load",
    "Precharge",
    "RemoteTerminal",
    "build_device",
]


@dataclass(frozen=True, slots=True)
class CommandResult:
    ok: bool
    text: str


def refused(text: str) -> CommandResult:
    return CommandResult(False, f"REFUSED: {text}")


class ElectricalDevice:
    """Base: a two-terminal element attached to the electrical network."""

    #: SCL verbs this device answers, in the order a refusal should offer
    #: them. `read` is handled above the device (Simulation.execute) and is
    #: implied everywhere, so it is not listed here.
    verbs: tuple[str, ...] = ()

    #: Does this class accrue powered hours? False means `records` prints
    #: "not tracked" rather than 0.0 h — a zero would be a false instrument
    #: reading (failure-and-repair.md, MAINT v1).
    tracks_hours: bool = False

    def __init__(self, spec: DeviceSpec, part: PartSpec) -> None:
        self.id = spec.id
        self.spec = spec
        self.part = part
        self.last_i_a = 0.0  # solved branch current, read by current transducers
        self.state = "in-service"  # switchables/precharge override
        self.unit: Unit | None = None  # the serialized box in this position

    @property
    def operating(self) -> bool:
        """Is the fitted unit running right now? Drives hour accrual."""
        return False

    def stamp(self, net: ElectricalNetwork) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    def after_solve(self, net: ElectricalNetwork, log: EventLog, tick: int) -> None:
        pass

    def powers_w(self, net: ElectricalNetwork) -> tuple[float, float]:
        """(source_w, dissipated_w) for the conservation audit."""
        return (0.0, 0.0)

    def execute(self, verb: str, flags: set[str]) -> CommandResult:
        return self.unsupported(verb)

    def unsupported(self, verb: str) -> CommandResult:
        """Refuse a verb and say what this device *does* answer.

        A refusal that only says "not supported" teaches nothing, and the
        manuals promise otherwise (AGENTS.md writing style: error messages
        cite their sections). Guessing `close` at a precharge unit cost a
        playtester an inrush trip — 2026-09-12 note, friction 1.
        """
        offered = ", ".join((*self.verbs, "records", "read"))
        return refused(f"{self.id}: verb {verb!r} not supported (try: {offered})")

    def observe(self) -> str:
        """Physical panel observation (position/state), not telemetry."""
        return f"{self.id}: (no observable state)"

    def read_result(self) -> CommandResult:
        """The SCL `read` surface: panel observation by default; instruments
        and probe points override (rich readouts, interlocked refusals)."""
        return CommandResult(True, self.observe())


class Battery(ElectricalDevice):
    """EMF(SOC) behind internal resistance; coulomb-counting SOC."""

    def __init__(self, spec: DeviceSpec, part: PartSpec, dt_s: float) -> None:
        super().__init__(spec, part)
        self.soc = spec.params.get("soc_init", 1.0)
        self._emf_stamped_v = 0.0
        self._dt_s = dt_s
        p = part.params
        self._emf_full_v = p["emf_full_v"]
        self._emf_empty_v = p["emf_empty_v"]
        self._r_int_ohm = p["r_int_ohm"]
        self._capacity_c = p["capacity_c"]

    @property
    def emf_v(self) -> float:
        return self._emf_empty_v + (self._emf_full_v - self._emf_empty_v) * self.soc

    def stamp(self, net: ElectricalNetwork) -> None:
        pos, neg = self.spec.ports["pos"], self.spec.ports["neg"]
        g_s = 1.0 / self._r_int_ohm
        # EMF is frozen for the tick: current and the power audit must use the
        # value actually stamped, not the post-SOC-update one (conservation).
        self._emf_stamped_v = self.emf_v
        net.stamp_conductance(pos, neg, g_s)
        net.stamp_current_a(pos, self._emf_stamped_v * g_s)
        net.stamp_current_a(neg, -self._emf_stamped_v * g_s)

    def after_solve(self, net: ElectricalNetwork, log: EventLog, tick: int) -> None:
        dv = net.voltage_v(self.spec.ports["pos"]) - net.voltage_v(self.spec.ports["neg"])
        self.last_i_a = (self._emf_stamped_v - dv) / self._r_int_ohm  # discharge positive
        self.soc = min(1.0, max(0.0, self.soc - self.last_i_a * self._dt_s / self._capacity_c))

    def powers_w(self, net: ElectricalNetwork) -> tuple[float, float]:
        return (self._emf_stamped_v * self.last_i_a, self.last_i_a**2 * self._r_int_ohm)


class _Switch(ElectricalDevice):
    """Common contactor/breaker machinery: open/closed/tripped, overcurrent trip."""

    verbs = ("open", "close", "reset")

    kind = "switch"

    def __init__(self, spec: DeviceSpec, part: PartSpec) -> None:
        super().__init__(spec, part)
        self.state = "open"  # cold & dark convention (blueprint comment)
        self._stamped = False  # conducted this tick (audit key; state may trip post-solve)
        self._g_s = 1.0 / part.params["r_contact_ohm"]
        self._rating_a = part.params["rating_a"]

    def stamp(self, net: ElectricalNetwork) -> None:
        self._stamped = self.state == "closed"
        if self._stamped:
            net.stamp_conductance(self.spec.ports["a"], self.spec.ports["b"], self._g_s)

    def after_solve(self, net: ElectricalNetwork, log: EventLog, tick: int) -> None:
        if not self._stamped:
            self.last_i_a = 0.0
            return
        self.last_i_a = net.branch_current_a(self.spec.ports["a"], self.spec.ports["b"], self._g_s)
        if abs(self.last_i_a) > self._rating_a:
            self.state = "tripped"
            log.append(
                tick,
                self.id,
                "overcurrent-trip",
                {"current_a": round(abs(self.last_i_a), 3), "rating_a": self._rating_a},
            )

    def powers_w(self, net: ElectricalNetwork) -> tuple[float, float]:
        return (0.0, self.last_i_a**2 / self._g_s if self._stamped else 0.0)

    def observe(self) -> str:
        return f"{self.id}: {self.state.upper()}"

    # -- commands ----------------------------------------------------------

    def execute(self, verb: str, flags: set[str]) -> CommandResult:
        if verb == "open":
            return self._open()
        if verb == "close":
            return self._close(flags)
        if verb == "reset":
            return self._reset()
        if verb == "read":
            return CommandResult(True, self.observe())
        return self.unsupported(verb)

    def _open(self) -> CommandResult:
        if self.state == "tripped":
            return refused(f"{self.id} is TRIPPED; use reset")
        self.state = "open"
        return CommandResult(True, f"{self.id}: OPEN")

    def _reset(self) -> CommandResult:
        if self.state != "tripped":
            return refused(f"{self.id} is not tripped")
        self.state = "open"
        return CommandResult(True, f"{self.id}: reset, now OPEN")

    def _close(self, flags: set[str]) -> CommandResult:
        if self.state == "tripped":
            return refused(f"{self.id} is TRIPPED; reset before closing")
        self.state = "closed"
        return CommandResult(True, f"{self.id}: CLOSED")


class Breaker(_Switch):
    kind = "breaker"


class Contactor(_Switch):
    """Adds guarded close (--confirm) and analytic peak-inrush protection.

    The 100 ms backward-Euler step averages away closure transients, so the
    honest inrush peak is computed analytically from pre-closure voltages:
    I_peak = |V_a - V_b| / r_contact (ata-24-eps.md §3). Exceeding
    inrush_limit_a trips the contactor at closure — the precharge lesson.
    """

    kind = "contactor"

    def __init__(self, spec: DeviceSpec, part: PartSpec) -> None:
        super().__init__(spec, part)
        self._inrush_limit_a = part.params["inrush_limit_a"]
        self._net: ElectricalNetwork | None = None  # bound at assembly
        self._log: EventLog | None = None
        self._clock: SimClock | None = None

    def bind(self, net: ElectricalNetwork, log: EventLog, clock: SimClock) -> None:
        self._net = net
        self._log = log
        self._clock = clock

    def _close(self, flags: set[str]) -> CommandResult:
        if self.state == "tripped":
            return refused(f"{self.id} is TRIPPED; reset before closing (SOM 24-00-00 §3)")
        if "confirm" not in flags:
            return refused(f"{self.id}: guarded action, add --confirm (SOM 24-00-00 §3)")
        assert self._net is not None and self._log is not None and self._clock is not None
        dv_v = abs(
            self._net.voltage_v(self.spec.ports["a"]) - self._net.voltage_v(self.spec.ports["b"])
        )
        peak_a = dv_v * self._g_s
        if peak_a > self._inrush_limit_a:
            self.state = "tripped"
            # Command-time event: logged at the *current* tick, not the last
            # solved one — a stale tick here regresses the journal (kernel
            # ValueError escaping to the player; found in the 2026-07-14
            # cross-tie session).
            self._log.append(
                self._clock.tick_index,
                self.id,
                "inrush-trip",
                {"peak_a": round(peak_a, 1), "limit_a": self._inrush_limit_a},
            )
            return CommandResult(
                True,
                f"{self.id}: CLOSED... TRIPPED (inrush). See SOM 24-00-00 §3.",
            )
        self.state = "closed"
        return CommandResult(True, f"{self.id}: CLOSED")


class Precharge(ElectricalDevice):
    """Switched precharge resistor with auto-complete monitor."""

    verbs = ("start", "stop")

    def __init__(self, spec: DeviceSpec, part: PartSpec) -> None:
        super().__init__(spec, part)
        self.state = "idle"  # idle | charging | complete
        self._stamped = False
        self._g_s = 1.0 / part.params["r_ohm"]
        self._complete_dv_v = part.params["complete_dv_v"]
        self._interlock: _Switch | None = None  # resolved at assembly

    def bind_interlock(self, switch: _Switch) -> None:
        self._interlock = switch

    def stamp(self, net: ElectricalNetwork) -> None:
        self._stamped = self.state == "charging"
        if self._stamped:
            net.stamp_conductance(self.spec.ports["a"], self.spec.ports["b"], self._g_s)

    def after_solve(self, net: ElectricalNetwork, log: EventLog, tick: int) -> None:
        if not self._stamped:
            self.last_i_a = 0.0
            return
        a, b = self.spec.ports["a"], self.spec.ports["b"]
        self.last_i_a = net.branch_current_a(a, b, self._g_s)
        if abs(net.voltage_v(a) - net.voltage_v(b)) < self._complete_dv_v:
            self.state = "complete"
            log.append(tick, self.id, "precharge-complete", {})

    def powers_w(self, net: ElectricalNetwork) -> tuple[float, float]:
        return (0.0, self.last_i_a**2 / self._g_s if self._stamped else 0.0)

    def observe(self) -> str:
        return f"{self.id}: {self.state.upper()}"

    def execute(self, verb: str, flags: set[str]) -> CommandResult:
        if verb == "start":
            if self._interlock is not None and self._interlock.state != "open":
                return refused(f"interlock {self._interlock.id} must be OPEN (SOM 24-00-00 §3)")
            self.state = "charging"
            return CommandResult(True, f"{self.id}: precharge in progress")
        if verb == "stop":
            self.state = "idle"
            return CommandResult(True, f"{self.id}: precharge IDLE")
        if verb == "read":
            return CommandResult(True, self.observe())
        return self.unsupported(verb)


class Load(ElectricalDevice):
    """Constant-resistance equipment load (constant-power: M2)."""

    def __init__(self, spec: DeviceSpec, part: PartSpec) -> None:
        super().__init__(spec, part)
        self._g_s = 1.0 / part.params["r_ohm"]

    def stamp(self, net: ElectricalNetwork) -> None:
        net.stamp_conductance(self.spec.ports["pos"], self.spec.ports["neg"], self._g_s)

    def after_solve(self, net: ElectricalNetwork, log: EventLog, tick: int) -> None:
        self.last_i_a = net.branch_current_a(
            self.spec.ports["pos"], self.spec.ports["neg"], self._g_s
        )

    def powers_w(self, net: ElectricalNetwork) -> tuple[float, float]:
        return (0.0, self.last_i_a**2 / self._g_s)


class DataDevice(ElectricalDevice):
    """Base for bus-attached data hardware (ata-42-data.md §9): an electrical
    load whose *data function* gates on rail voltage (``min_v`` power gate).
    The electrical side is a constant-resistance load; the data side is driven
    by the ship's data task, after the electrical solve fixes rail truth."""

    tracks_hours = True

    def __init__(self, spec: DeviceSpec, part: PartSpec) -> None:
        super().__init__(spec, part)
        self._g_s = 1.0 / part.params["r_ohm"]
        self._min_v = part.params["min_v"]
        self.energized = False  # rail truth from the last solve

    @property
    def operating(self) -> bool:
        return self.energized

    def stamp(self, net: ElectricalNetwork) -> None:
        net.stamp_conductance(self.spec.ports["pos"], self.spec.ports["neg"], self._g_s)

    def after_solve(self, net: ElectricalNetwork, log: EventLog, tick: int) -> None:
        self.last_i_a = net.branch_current_a(
            self.spec.ports["pos"], self.spec.ports["neg"], self._g_s
        )
        self.energized = net.voltage_v(self.spec.ports["pos"]) >= self._min_v

    def powers_w(self, net: ElectricalNetwork) -> tuple[float, float]:
        return (0.0, self.last_i_a**2 / self._g_s)


class RemoteTerminal(DataDevice):
    """RT: answers BC status polls while fitted, energized, alive, and reachable.

    Fault state (ata-42-data.md §6): `stuck_dominant` — the SEU latch-up
    signature; holds while powered, clears on power removal (FDR-logged).
    `dead` — a silent module failure; cleared only by replacing the box.

    A terminal is a line-replaceable unit (failure-and-repair.md, MAINT v1):
    it answers `remove` and `install` against the ship's finite stores, and an
    empty position is genuinely empty — no load stamped, no poll answered, and
    nothing to jam the bus with.
    """

    verbs = ("remove", "install")

    kind = "rt"

    def __init__(self, spec: DeviceSpec, part: PartSpec) -> None:
        super().__init__(spec, part)
        self.address = int(spec.params["rt_address"])  # loader-validated 0..31
        self.stuck_dominant = False
        self.dead = False
        self._de_energized: Callable[[], bool] | None = None
        self._swap: Callable[[str], CommandResult] | None = None
        self._log: EventLog | None = None
        self._clock: SimClock | None = None

    def bind(
        self,
        de_energized: Callable[[], bool],
        log: EventLog,
        clock: SimClock,
        swap: Callable[[str], CommandResult] | None = None,
    ) -> None:
        self._de_energized = de_energized
        self._log = log
        self._clock = clock
        self._swap = swap

    @property
    def fitted(self) -> bool:
        return self.unit is not None

    def stamp(self, net: ElectricalNetwork) -> None:
        """An empty rack draws nothing. The stub stays wired either way."""
        if self.fitted:
            super().stamp(net)

    def after_solve(self, net: ElectricalNetwork, log: EventLog, tick: int) -> None:
        if not self.fitted:
            self.last_i_a = 0.0
            self.energized = False
            return
        super().after_solve(net, log, tick)
        if self.stuck_dominant and not self.energized:
            self.stuck_dominant = False
            log.append(
                tick, self.id, "fault-cleared", {"mode": "stuck_dominant", "by": "power-removal"}
            )

    def observe(self) -> str:
        if self.unit is None:
            return f"{self.id}: NOT FITTED — position open (MAINT 42-110-001)"
        rail = "rail up" if self.energized else "rail down"
        return f"{self.id}: {self.unit.serial} fitted, {rail}"

    def execute(self, verb: str, flags: set[str]) -> CommandResult:
        if verb not in self.verbs:
            return self.unsupported(verb)
        assert self._de_energized is not None and self._swap is not None  # bound at assembly
        if not self._de_energized():
            bus_id = self.spec.data_bus
            return refused(
                f"{self.id}: de-energize {bus_id} before working on it (MAINT 42-110-001 §2)"
            )
        return self._swap(verb)

    def pulled(self) -> bool:
        """Clear the position's fault state and report what came off with it.

        The caller records the answer against the removed unit and the FDR; no
        player surface ever renders it, because nothing aboard tested the board
        (MAINT 00-00 §4).
        """
        found = self.dead or self.stuck_dominant
        self.dead = False
        self.stuck_dominant = False
        return found


class BusController(DataDevice):
    """BC: owns a bus's cyclic schedule. The ship's data task runs the polls;
    this device supplies the power gate, the telemetry surface (health
    fraction), and the operator read (the bus table — analyzer v1)."""

    kind = "bc"

    def __init__(self, spec: DeviceSpec, part: PartSpec) -> None:
        super().__init__(spec, part)
        self._bus: DataBus | None = None  # bound at assembly

    def bind(self, bus: DataBus) -> None:
        self._bus = bus

    @property
    def bus(self) -> DataBus:
        assert self._bus is not None  # bound at assembly
        return self._bus

    def observe(self) -> str:
        if not self.energized:
            return f"{self.id}: OFF (bus controller unpowered)"
        state = self.bus.state_word()
        return f"{self.id}: ON AIR — {self.bus.id} {state}"

    def execute(self, verb: str, flags: set[str]) -> CommandResult:
        return self.unsupported(verb)  # schedule control is firmware, not panel

    def read_result(self) -> CommandResult:
        return CommandResult(True, self.readout())

    def readout(self) -> str:
        """The analyzer surface: BC state + per-RT table (BC's own view only —
        an RT that does not answer is NO RESPONSE, never a root cause)."""
        if not self.energized:
            return f"{self.id}: --- NO DATA (bus controller unpowered)"
        assert self._bus is not None
        bus = self._bus
        lines = [self.observe(), "  RT   STATE             ERRORS"]
        for address in bus.rt_addresses():
            rt = bus.rt(address)
            if rt.answered_last:
                word = "OK"
            elif rt.consec_timeouts:
                word = f"NO RESPONSE ({rt.consec_timeouts}x)"
            else:
                word = "NO DATA"  # never polled (BC just energized)
            lines.append(f"  {address:<4} {word:<18} {rt.error_total}")
        return "\n".join(lines)


class HarnessElement(ElectricalDevice):
    """Passive data-harness hardware (couplers, twinax runs): no electrical
    stamp. Fault state lives in the bus model — the medium is the truth —
    and the device is the operator surface: probe points and the `repair`
    verb (ata-42-data.md §6). Field-form repair; MAINT attaches cost later.

    `repair` replaces the run or coupler whatever its state, and reports the
    same either way. Refusing "nothing to repair" on a sound part would hand
    the player a verdict no instrument gave them (No God View); replacing a
    good cable is a wasted part, which is the honest cost of a guess. Whether
    a fault was actually there goes to the FDR, for review afterwards.
    """

    verbs = ("repair",)

    def __init__(self, spec: DeviceSpec, part: PartSpec) -> None:
        # Attribute assignments must precede super().__init__: the base
        # assigns self.state, which delegates to the (not yet bound) bus.
        self._bus: DataBus | None = None
        self._de_energized: Callable[[], bool] | None = None
        self._log: EventLog | None = None
        self._clock: SimClock | None = None
        super().__init__(spec, part)

    def bind(
        self,
        bus: DataBus,
        de_energized: Callable[[], bool],
        log: EventLog,
        clock: SimClock,
    ) -> None:
        self._bus = bus
        self._de_energized = de_energized
        self._log = log
        self._clock = clock

    def stamp(self, net: ElectricalNetwork) -> None:
        pass  # no electrical presence

    @property
    def state(self) -> str:
        raise NotImplementedError  # junction/segment delegate to the medium

    @state.setter
    def state(self, value: str) -> None:
        raise NotImplementedError

    def execute(self, verb: str, flags: set[str]) -> CommandResult:
        if verb != "repair":
            return self.unsupported(verb)
        assert self._bus is not None and self._de_energized is not None
        assert self._log is not None and self._clock is not None
        if not self._de_energized():
            return refused(
                f"{self.id}: de-energize {self._bus.id} before working on it (FIM 42-12)"
            )
        found = self.state != "ok"
        self.state = "ok"
        self._log.append(
            self._clock.tick_index, self.id, "repair", {"result": "replaced", "fault_found": found}
        )
        return CommandResult(True, f"{self.id}: replaced — verify (FIM 42-12 §4)")


class BusJunction(HarnessElement):
    """Bus coupler: trunk feed-through + stub taps, and the DMM probe point.
    `read` is an ohms check per direction (ata-42 §6), interlocked on a
    de-energized bus — real shop practice."""

    kind = "junction"

    @property
    def state(self) -> str:
        assert self._bus is not None  # bound at assembly
        return self._bus.junction_state(self.id)

    @state.setter
    def state(self, value: str) -> None:
        if self._bus is not None:  # pre-bind assignment (base __init__) drops
            self._bus.set_junction_state(self.id, value)  # type: ignore[arg-type]

    def observe(self) -> str:
        return f"{self.id}: coupler (DMM probe point — WDM 42)"

    def read_result(self) -> CommandResult:
        assert self._bus is not None and self._de_energized is not None
        if not self._de_energized():
            return refused(f"{self.id}: de-energize {self._bus.id} before ohms checks (FIM 42-12)")
        lines = [f"{self.id}: {self._bus.id} coupler — DMM across the pair (bus de-energized)"]
        for seg_id, other, ohms in self._bus.ohms_at(self.id):
            reading = "OL" if ohms is None else f"{ohms:.1f} ohm"
            lines.append(f"  {seg_id} (toward {other}): {reading}")
        return CommandResult(True, "\n".join(lines))


class HarnessSegment(HarnessElement):
    """A run of twinax (trunk or stub): the fault-capable medium itself."""

    kind = "harness_seg"

    @property
    def state(self) -> str:
        assert self._bus is not None  # bound at assembly
        return self._bus.segment_state(self.id)

    @state.setter
    def state(self, value: str) -> None:
        if self._bus is not None:  # pre-bind assignment (base __init__) drops
            self._bus.set_segment_state(self.id, value)  # type: ignore[arg-type]

    def observe(self) -> str:
        return f"{self.id}: harness run {self.spec.ends['a']}-{self.spec.ends['b']} (WDM 42)"


def build_device(spec: DeviceSpec, part: PartSpec, dt_s: float) -> ElectricalDevice:
    """Instantiate the behavior class for an electrical device spec."""
    if part.behavior == "battery":
        return Battery(spec, part, dt_s)
    builders: dict[str, Callable[[DeviceSpec, PartSpec], ElectricalDevice]] = {
        "contactor": Contactor,
        "breaker": Breaker,
        "precharge": Precharge,
        "load": Load,
        "bc": BusController,
        "rt": RemoteTerminal,
        "junction": BusJunction,
        "harness_seg": HarnessSegment,
    }
    builder = builders.get(part.behavior)
    if builder is None:
        raise ValueError(f"not an electrical behavior: {part.behavior}")
    return builder(spec, part)
