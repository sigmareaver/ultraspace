"""Deterministic simulation kernel: time, scheduling, randomness, event log.

Spec: docs/engineering/simulation-kernel.md. Stdlib-only by law (architecture.md).
"""

from ultraspace.kernel.clock import TICK_US, TICKS_PER_S, SimClock
from ultraspace.kernel.events import Event, EventLog
from ultraspace.kernel.rng import RngHub
from ultraspace.kernel.scheduler import Phase, Scheduler, TickTask

__all__ = [
    "TICKS_PER_S",
    "TICK_US",
    "Event",
    "EventLog",
    "Phase",
    "RngHub",
    "Scheduler",
    "SimClock",
    "TickTask",
]
