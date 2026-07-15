"""Deterministic rate-group scheduler with fixed phase order (simulation-kernel.md).

Per tick, phases execute in the fixed order defined by :class:`Phase`; within a
phase, tasks execute in registration order. Registration order must itself be
deterministic — it derives from content traversal at ship assembly (data-model.md),
never from iteration over unordered collections (Iron Law 1).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum

__all__ = ["Phase", "Scheduler", "TickTask"]

TickTask = Callable[[int], None]
"""A per-tick task; receives the current tick index."""


class Phase(IntEnum):
    """Fixed per-tick execution phases, in canonical order."""

    COMMANDS = 0
    NETWORKS = 1
    DEVICES = 2
    FAULTS = 3
    INSTRUMENTS = 4
    ANNUNCIATORS = 5
    WORLD = 6
    TELEMETRY = 7


@dataclass(frozen=True, slots=True)
class _Registration:
    name: str
    task: TickTask
    period_ticks: int
    offset_ticks: int

    def due(self, tick_index: int) -> bool:
        return (
            tick_index >= self.offset_ticks
            and (tick_index - self.offset_ticks) % self.period_ticks == 0
        )


class Scheduler:
    """Registers tasks into (phase, rate group) slots and runs one tick at a time."""

    def __init__(self) -> None:
        # Keyed access only; iteration always goes through `for phase in Phase`
        # (enum definition order), never dict order.
        self._registrations: dict[Phase, list[_Registration]] = {phase: [] for phase in Phase}
        self._names: set[str] = set()  # membership checks only, never iterated

    def register(
        self,
        phase: Phase,
        name: str,
        task: TickTask,
        *,
        period_ticks: int = 1,
        offset_ticks: int = 0,
    ) -> None:
        """Register ``task`` to run every ``period_ticks`` starting at ``offset_ticks``.

        ``name`` must be unique across the scheduler: names make execution
        traces greppable and force callers to think about identity, which is
        where scheduling determinism bugs hide.
        """
        if period_ticks < 1:
            raise ValueError(f"period_ticks must be >= 1, got {period_ticks}")
        if offset_ticks < 0:
            raise ValueError(f"offset_ticks must be >= 0, got {offset_ticks}")
        if name in self._names:
            raise ValueError(f"duplicate task name: {name!r}")
        self._names.add(name)
        registration = _Registration(
            name=name, task=task, period_ticks=period_ticks, offset_ticks=offset_ticks
        )
        self._registrations[phase].append(registration)

    def run_tick(self, tick_index: int) -> None:
        """Execute all due tasks for ``tick_index`` in canonical phase/registration order."""
        for phase in Phase:
            for registration in self._registrations[phase]:
                if registration.due(tick_index):
                    registration.task(tick_index)
