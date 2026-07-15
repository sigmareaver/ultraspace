"""Simulation clock: fixed tick, integer-microsecond time (ADR-0002).

Sim time is an integer count of microseconds since mission epoch. Floats never
represent absolute time; ``now_s`` exists only for presentation and local math.
Time compression is *more ticks per wall second*, never a larger dt — the kernel
has no concept of wall time at all.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["TICKS_PER_S", "TICK_US", "SimClock"]

TICK_US: int = 100_000
"""Base tick length: 100 ms of sim time."""

TICKS_PER_S: int = 1_000_000 // TICK_US
"""Ticks per sim second (10)."""


@dataclass(slots=True)
class SimClock:
    """Monotonic fixed-tick simulation clock."""

    tick_index: int = 0

    @property
    def now_us(self) -> int:
        """Sim time in integer microseconds since mission epoch."""
        return self.tick_index * TICK_US

    @property
    def now_s(self) -> float:
        """Sim time in float seconds. Presentation/local math only — never state."""
        return self.now_us / 1_000_000

    def advance(self, ticks: int = 1) -> None:
        """Advance the clock by ``ticks`` base ticks (monotonic; ticks >= 1)."""
        if ticks < 1:
            raise ValueError(f"clock advances forward only: ticks must be >= 1, got {ticks}")
        self.tick_index += ticks

    def mission_elapsed_str(self) -> str:
        """Format sim time as ``DDD:HH:MM:SS.d`` (MET display convention)."""
        total_ds = self.now_us // 100_000  # deciseconds: exact at any tick boundary
        ds = total_ds % 10
        total_s = total_ds // 10
        sec = total_s % 60
        minute = (total_s // 60) % 60
        hour = (total_s // 3600) % 24
        day = total_s // 86_400
        return f"{day:03d}:{hour:02d}:{minute:02d}:{sec:02d}.{ds}"
