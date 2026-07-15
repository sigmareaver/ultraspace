"""SimClock: integer time, monotonicity, MET formatting."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ultraspace.kernel import TICK_US, TICKS_PER_S, SimClock


def test_constants_are_consistent() -> None:
    # 100 ms tick -> 10 ticks per second (simulation-kernel.md).
    assert TICK_US == 100_000
    assert TICKS_PER_S == 10
    assert TICK_US * TICKS_PER_S == 1_000_000


def test_time_starts_at_epoch() -> None:
    clock = SimClock()
    assert clock.tick_index == 0
    assert clock.now_us == 0


@given(st.lists(st.integers(min_value=1, max_value=10_000), max_size=50))
def test_time_is_tick_count_times_dt(advances: list[int]) -> None:
    """Integer time cannot drift: now_us is exactly tick_index * TICK_US."""
    clock = SimClock()
    for ticks in advances:
        clock.advance(ticks)
    assert clock.tick_index == sum(advances)
    assert clock.now_us == sum(advances) * TICK_US


def test_advance_rejects_non_positive() -> None:
    clock = SimClock()
    with pytest.raises(ValueError, match="forward only"):
        clock.advance(0)
    with pytest.raises(ValueError, match="forward only"):
        clock.advance(-5)


def test_now_s_matches_us() -> None:
    clock = SimClock()
    clock.advance(15)  # 15 ticks * 100_000 us = 1_500_000 us = 1.5 s
    assert clock.now_us == 1_500_000
    assert clock.now_s == pytest.approx(1.5)


def test_mission_elapsed_formatting() -> None:
    clock = SimClock()
    assert clock.mission_elapsed_str() == "000:00:00:00.0"

    # 1 day + 1 h + 3 min + 4.5 s = 86400 + 3600 + 180 + 4.5 = 90184.5 s
    # = 901_845 ticks at 10 ticks/s.
    clock.advance(901_845)
    assert clock.mission_elapsed_str() == "001:01:03:04.5"
