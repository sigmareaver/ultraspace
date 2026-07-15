"""Scheduler: canonical phase order, rate groups, registration determinism."""

from __future__ import annotations

import pytest

from ultraspace.kernel import Phase, Scheduler


def test_phase_order_is_canonical() -> None:
    """Phases run in spec order regardless of registration order."""
    scheduler = Scheduler()
    trace: list[str] = []

    # Register in scrambled phase order on purpose.
    scheduler.register(Phase.TELEMETRY, "t", lambda _: trace.append("telemetry"))
    scheduler.register(Phase.COMMANDS, "c", lambda _: trace.append("commands"))
    scheduler.register(Phase.FAULTS, "f", lambda _: trace.append("faults"))
    scheduler.register(Phase.NETWORKS, "n", lambda _: trace.append("networks"))

    scheduler.run_tick(0)
    assert trace == ["commands", "networks", "faults", "telemetry"]


def test_registration_order_within_phase_preserved() -> None:
    scheduler = Scheduler()
    trace: list[str] = []
    scheduler.register(Phase.DEVICES, "first", lambda _: trace.append("first"))
    scheduler.register(Phase.DEVICES, "second", lambda _: trace.append("second"))
    scheduler.register(Phase.DEVICES, "third", lambda _: trace.append("third"))

    scheduler.run_tick(0)
    assert trace == ["first", "second", "third"]


def test_rate_groups_period_and_offset() -> None:
    scheduler = Scheduler()
    ran_at: list[int] = []
    scheduler.register(Phase.DEVICES, "slow", ran_at.append, period_ticks=3, offset_ticks=1)

    for tick in range(10):
        scheduler.run_tick(tick)

    # offset 1, period 3 -> ticks 1, 4, 7 within [0, 10).
    assert ran_at == [1, 4, 7]


def test_task_not_due_before_offset() -> None:
    scheduler = Scheduler()
    ran_at: list[int] = []
    scheduler.register(Phase.WORLD, "late", ran_at.append, period_ticks=1, offset_ticks=5)
    for tick in range(8):
        scheduler.run_tick(tick)
    assert ran_at == [5, 6, 7]


def test_duplicate_names_rejected() -> None:
    scheduler = Scheduler()
    scheduler.register(Phase.DEVICES, "pump", lambda _: None)
    with pytest.raises(ValueError, match="duplicate"):
        scheduler.register(Phase.NETWORKS, "pump", lambda _: None)


def test_invalid_registration_parameters() -> None:
    scheduler = Scheduler()
    with pytest.raises(ValueError, match="period_ticks"):
        scheduler.register(Phase.DEVICES, "bad-period", lambda _: None, period_ticks=0)
    with pytest.raises(ValueError, match="offset_ticks"):
        scheduler.register(Phase.DEVICES, "bad-offset", lambda _: None, offset_ticks=-1)
