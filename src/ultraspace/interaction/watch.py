"""A timed wait is a watch, not a sleep (command-language.md).

One primitive behind both surfaces that let a human ask for time to pass: the
teletype's ``wait`` and the procedure runner's wait step. They must behave
identically — feature parity is contractual (ui-presentation.md), and "the
checklist stopped but the console did not" is exactly the kind of difference
that teaches a crew to trust neither.

A crew member holding a stopwatch does not stop being a crew member. The watch
ends the moment an annunciation at *warning* severity goes new, and reports how
much of it was left. Cautions do not interrupt: warning means now, caution
means when you can, and a wait that stopped for every caution would never run
out. Neither does a lamp that was already lit when the clock started — the
watch reacts to an onset, the same bit the flashing master reacts to.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ultraspace.ship import Simulation
from ultraspace.ship.sim import DT_S

__all__ = ["WatchResult", "new_warnings", "watch"]


@dataclass(frozen=True, slots=True)
class WatchResult:
    requested_s: float
    elapsed_s: float
    #: Warning messages whose onset fell inside the watch, in panel order.
    warnings: list[str] = field(default_factory=list)
    #: True iff those onsets ended the watch early.
    interrupted: bool = False

    @property
    def remaining_s(self) -> float:
        return round(self.requested_s - self.elapsed_s, 3)


def new_warnings(sim: Simulation) -> dict[str, str]:
    """Lit-and-unseen warnings in panel recall order: lamp id -> message."""
    return {
        a.spec.id: a.spec.message
        for a in sim.panel.recall()
        if a.spec.severity == "warning" and a.is_new
    }


def watch(sim: Simulation, seconds: float, *, hold: bool = False) -> WatchResult:
    """Advance the sim up to ``seconds``, stopping on a warning onset.

    ``hold`` runs the full duration anyway and still reports what was seen —
    for the handful of waits where stopping is the wrong act (a bleed-down
    before touching hardware finishes, because walking away mid-bleed is how
    people get hurt). It is per step, spelled in the procedure, never a default.
    """
    ticks = max(1, round(seconds / DT_S))
    prev = new_warnings(sim)
    seen: list[str] = []
    for elapsed in range(1, ticks + 1):
        sim.step(1)
        now = new_warnings(sim)
        fresh = [m for lamp, m in now.items() if lamp not in prev]
        prev = now
        if not fresh:
            continue
        seen.extend(m for m in fresh if m not in seen)
        if not hold:
            return WatchResult(seconds, elapsed * DT_S, fresh, interrupted=True)
    return WatchResult(seconds, ticks * DT_S, seen)
