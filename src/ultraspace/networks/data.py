"""Data bus network: 1553-flavored command/response, quasi-static per tick
(spec: docs/design/systems/ata-42-data.md §3).

A 1 Mbps bus completes a status transaction in ~100 µs — four orders below
the 100 ms tick — so a poll and its reply land in the tick that schedules
them. The bus owns the *medium* and the *transaction ledger*: the harness
graph (junctions, trunk/stub segments, terminators) with located fault
state, and the BC's accounting. The ship layer drives the schedule and
supplies the physical truth (power, transceiver state). Causality is the
conservation law: a reply is counted only for a poll issued in the same
tick, and received never exceeds transmitted.

The illusion contract (spec §1): no waveform, no bits, no timing — graph
reachability and equivalent-resistance arithmetic. Trunk faults partition or
kill the medium; stub faults are contained (transformer coupling).
"""

from __future__ import annotations

from typing import Literal

__all__ = [
    "FAIL_AFTER_POLLS",
    "STUB_WINDING_OHM",
    "DataBus",
    "MemberState",
    "RtHealth",
]

MemberState = Literal["ok", "open", "short"]

#: Consecutive timeouts before the BC declares an RT FAILED (300 ms at tick).
FAIL_AFTER_POLLS = 3

#: DMM continuity reading across a healthy transformer-coupled stub tap.
STUB_WINDING_OHM = 2.1


class RtHealth:
    """The BC's view of one remote terminal: counters and declaration state."""

    __slots__ = ("address", "answered_last", "consec_timeouts", "error_total", "failed")

    def __init__(self, address: int) -> None:
        self.address = address
        self.answered_last = False  # answered the most recent poll
        self.consec_timeouts = 0
        self.error_total = 0  # monotone; the analyzer's evidence
        self.failed = False  # declared after FAIL_AFTER_POLLS consecutive timeouts


class _Member:
    __slots__ = ("id", "state")

    def __init__(self, member_id: str) -> None:
        self.id = member_id
        self.state: MemberState = "ok"


class _Segment:
    __slots__ = ("a", "b", "id", "state")

    def __init__(self, seg_id: str, a: str, b: str) -> None:
        self.id = seg_id
        self.a = a
        self.b = b
        self.state: MemberState = "ok"


class DataBus:
    """One data bus: the harness graph + the BC's transaction ledger.

    Members are junctions (couplers), the BC, and RTs; segments join them
    (trunk runs between junctions/BC, stub runs to RTs). Trunk degree is
    enforced linear (BC: 1, junction: ≤2) so ohm walks are unambiguous.
    """

    def __init__(self, bus_id: str, termination_ohm: float = 78.0) -> None:
        self.id = bus_id
        self.termination_ohm = termination_ohm
        self.tx_total = 0  # polls transmitted
        self.rx_total = 0  # replies received; invariant: rx_total <= tx_total
        self.errors_zeroed_tick = 0  # when the totals below last started over
        self._bc_id: str | None = None
        self._junctions: dict[str, _Member] = {}
        self._segments: dict[str, _Segment] = {}
        self._links: dict[str, list[tuple[str, str]]] = {}  # member -> [(segment, other)]
        self._rts: dict[int, RtHealth] = {}
        self._rt_ids: dict[str, int] = {}  # device id -> address

    # -- topology (assembly-time) -------------------------------------------

    def bind_bc(self, device_id: str) -> None:
        self._bc_id = device_id

    def register_junction(self, junction_id: str) -> None:
        if junction_id in self._junctions:
            raise ValueError(f"{self.id}: duplicate junction {junction_id}")
        self._junctions[junction_id] = _Member(junction_id)

    def register_rt(self, address: int, device_id: str) -> None:
        if address in self._rts:
            raise ValueError(f"{self.id}: duplicate RT address {address}")
        self._rts[address] = RtHealth(address)
        self._rt_ids[device_id] = address

    def add_segment(self, seg_id: str, a: str, b: str) -> None:
        """Wire a trunk or stub run between two members (bc/junction/RT ids)."""
        members = set(self._junctions) | set(self._rt_ids) | {self._bc_id}
        for end in (a, b):
            if end not in members:
                raise ValueError(f"{self.id}: segment {seg_id} end {end!r} is not a bus member")
        if seg_id in self._segments:
            raise ValueError(f"{self.id}: duplicate segment {seg_id}")
        self._segments[seg_id] = _Segment(seg_id, a, b)
        self._links.setdefault(a, []).append((seg_id, b))
        self._links.setdefault(b, []).append((seg_id, a))
        for end in (a, b):
            if end in self._rt_ids and len(self._links[end]) > 1:
                raise ValueError(f"{self.id}: RT {end} has more than one stub")
            if end not in self._rt_ids:
                trunk = [s for s, o in self._links[end] if o not in self._rt_ids]
                limit = 1 if end == self._bc_id else 2
                if len(trunk) > limit:
                    raise ValueError(f"{self.id}: {end} trunk degree > {limit} (linear bus)")

    # -- fault state ---------------------------------------------------------

    def set_junction_state(self, junction_id: str, state: MemberState) -> None:
        self._junctions[junction_id].state = state

    def set_segment_state(self, seg_id: str, state: MemberState) -> None:
        self._segments[seg_id].state = state

    def junction_state(self, junction_id: str) -> MemberState:
        return self._junctions[junction_id].state

    def segment_state(self, seg_id: str) -> MemberState:
        return self._segments[seg_id].state

    def is_stub(self, seg_id: str) -> bool:
        seg = self._segments[seg_id]
        return seg.a in self._rt_ids or seg.b in self._rt_ids

    def has_trunk_short(self) -> bool:
        """A short on the trunk (or in a coupler) kills the whole medium;
        a stub short is contained by transformer coupling (spec §6)."""
        return any(
            seg.state == "short" and not self.is_stub(seg_id)
            for seg_id, seg in self._segments.items()
        ) or any(j.state == "short" for j in self._junctions.values())

    def reachable(self, target_id: str, from_id: str) -> bool:
        """Path of ok segments through unopened junctions from ``from_id``."""
        visited = {from_id}
        stack = [from_id]
        while stack:
            here = stack.pop()
            for seg_id, other in self._links.get(here, []):
                if self._segments[seg_id].state != "ok" or other in visited:
                    continue
                visited.add(other)
                if other in self._junctions and self._junctions[other].state == "open":
                    continue  # coupler feed-through broken: nothing beyond it
                stack.append(other)
        return target_id in visited

    # -- the DMM -------------------------------------------------------------

    def ohms_at(self, junction_id: str) -> list[tuple[str, str, float | None]]:
        """DMM at a coupler, per adjacent segment: (segment, toward, reading).

        Reading is the far terminator through an unbroken path, None for OL
        (open), ~0 for a short; stub taps read the coupling-winding
        continuity. Bus must be de-energized (interlock lives ship-side).

        The probed coupler's own state colors the trunk readings: a shorted
        coupler is a short *across the pair at the probe point*, so every
        trunk direction reads ~0 (spec §6 — a shorted coupler is a trunk
        short, and the meter must say so where it is). An open coupler is a
        broken feed-through *between* its two trunk faces: both faces still
        read their own way out, which is exactly why a coupler break is
        confirmed from the neighbouring coupler, not from this one.
        """
        own_short = self._junctions[junction_id].state == "short"
        readings = []
        for seg_id, other in self._links.get(junction_id, []):
            state = self._segments[seg_id].state
            if other in self._rt_ids:  # stub tap: the winding, not the trunk
                reading = {"ok": STUB_WINDING_OHM, "open": None, "short": 0.0}[state]
            elif own_short:
                reading = 0.0
            else:
                reading = self._trunk_ohms(junction_id, seg_id, other)
            readings.append((seg_id, other, reading))
        return readings

    def _trunk_ohms(self, from_id: str, seg_id: str, to_id: str) -> float | None:
        state = self._segments[seg_id].state
        if state == "open":
            return None
        if state == "short":
            return 0.0
        if to_id == self._bc_id:
            return self.termination_ohm
        junction = self._junctions[to_id]
        if junction.state == "short":
            return 0.0
        onward = (
            [(s, o) for s, o in self._links[to_id] if s != seg_id and o not in self._rt_ids]
            if junction.state == "ok"
            else []
        )
        if not onward:  # open coupler blocks; a dead end is the far terminator
            return None if junction.state == "open" else self.termination_ohm
        next_seg, next_id = onward[0]  # linear trunk (degree enforced)
        return self._trunk_ohms(to_id, next_seg, next_id)

    # -- the ledger (increments 1-2) -------------------------------------------

    def rt_addresses(self) -> list[int]:
        """Registered RT addresses in registration (blueprint) order."""
        return list(self._rts)

    def rt(self, address: int) -> RtHealth:
        return self._rts[address]

    def poll(self, address: int, answered: bool) -> None:
        """Record one status transaction this tick.

        ``answered`` is the physical truth the ship layer supplies (the RT
        was powered, alive, and reachable, and the medium carried the
        transaction). The ledger counts a reply only against a poll issued
        now — causality (spec §3).
        """
        rt = self._rts[address]
        self.tx_total += 1
        if answered:
            self.rx_total += 1
            rt.answered_last = True
            rt.consec_timeouts = 0
            rt.failed = False
        else:
            rt.answered_last = False
            rt.consec_timeouts += 1
            rt.error_total += 1
            if rt.consec_timeouts >= FAIL_AFTER_POLLS:
                rt.failed = True

    def zero_error_totals(self, tick: int) -> dict[int, int]:
        """Start the analyzer's evidence over; return what was discarded.

        A maintenance act on the *analyzer*, not on the bus: the per-RT totals
        go to zero and nothing else moves — not the consecutive-timeout
        counters, not a FAILED declaration, not a fault. The totals are
        monotone between zeroings, which is what makes them evidence
        (ata-42-data.md §3).
        """
        discarded = {address: rt.error_total for address, rt in self._rts.items()}
        for rt in self._rts.values():
            rt.error_total = 0
        self.errors_zeroed_tick = tick
        return discarded

    def error_total(self) -> int:
        """Errors on this bus since the counters were last zeroed."""
        return sum(rt.error_total for rt in self._rts.values())

    def health_frac(self) -> float:
        """Fraction of registered RTs not declared FAILED (1.0 when none)."""
        if not self._rts:
            return 1.0
        healthy = sum(1 for rt in self._rts.values() if not rt.failed)
        return healthy / len(self._rts)

    @property
    def degraded(self) -> bool:
        return any(rt.failed for rt in self._rts.values())

    @property
    def failed(self) -> bool:
        """No registered terminal is answering at all.

        A distinct word from `degraded`, because the annunciator panel makes
        the same distinction and the two surfaces must not disagree in front
        of the crew (ata-31-indicating.md §4): DATA BUS A FAILED lit over an
        analyzer still calling the bus DEGRADED is how a player stops trusting
        both.
        """
        return bool(self._rts) and all(rt.failed for rt in self._rts.values())

    def state_word(self) -> str:
        """HEALTHY | DEGRADED | FAILED — the analyzer's and the panel's word."""
        if self.failed:
            return "FAILED"
        return "DEGRADED" if self.degraded else "HEALTHY"
