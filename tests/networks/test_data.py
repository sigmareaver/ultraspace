"""Data bus ledger: timeout accounting, FAILED declarations, health, causality.

Hand-computed expectations: TB-1 has one RT (address 12) on DB-A; FAILED is
declared at the 3rd consecutive timeout (FAIL_AFTER_POLLS).
"""

from __future__ import annotations

import pytest

from ultraspace.networks.data import FAIL_AFTER_POLLS, DataBus


def test_healthy_rt_answers_and_health_stays_full() -> None:
    bus = DataBus("db.a")
    bus.register_rt(12)
    for _ in range(5):
        bus.poll(12, answered=True)
    assert bus.rt(12).answered_last
    assert bus.health_frac() == 1.0
    assert not bus.degraded
    assert bus.tx_total == 5 and bus.rx_total == 5  # causality ledger


def test_rt_declared_failed_after_three_consecutive_timeouts() -> None:
    bus = DataBus("db.a")
    bus.register_rt(12)
    for tick in range(FAIL_AFTER_POLLS):
        assert not bus.rt(12).failed  # not yet: declaration at the 3rd miss
        bus.poll(12, answered=False)
        assert bus.rt(12).consec_timeouts == tick + 1
    assert bus.rt(12).failed
    assert bus.degraded
    assert bus.health_frac() == 0.0
    assert bus.rt(12).error_total == FAIL_AFTER_POLLS  # monotone counter
    assert bus.tx_total == FAIL_AFTER_POLLS and bus.rx_total == 0


def test_single_miss_does_not_degrade_but_error_counter_remains() -> None:
    bus = DataBus("db.a")
    bus.register_rt(12)
    bus.poll(12, answered=False)  # one transient miss
    bus.poll(12, answered=True)  # recovers
    assert bus.rt(12).consec_timeouts == 0 and not bus.rt(12).failed
    assert bus.rt(12).error_total == 1  # evidence never rewinds
    assert bus.health_frac() == 1.0


def test_failed_rt_recovers_on_first_good_reply() -> None:
    bus = DataBus("db.a")
    bus.register_rt(12)
    for _ in range(FAIL_AFTER_POLLS + 2):
        bus.poll(12, answered=False)
    assert bus.health_frac() == 0.0
    bus.poll(12, answered=True)
    assert not bus.rt(12).failed
    assert bus.rt(12).answered_last
    assert bus.health_frac() == 1.0
    assert bus.rt(12).error_total == FAIL_AFTER_POLLS + 2


def test_health_fraction_counts_only_failed_rts() -> None:
    bus = DataBus("db.a")
    for address in (4, 12, 30):
        bus.register_rt(address)
    # RT 12 fails hard; RT 4 misses once (transient); RT 30 healthy.
    for _ in range(FAIL_AFTER_POLLS):
        bus.poll(4, answered=False)
        bus.poll(12, answered=False)
        bus.poll(30, answered=True)
    bus.poll(4, answered=True)  # transient recovers
    assert bus.rt(12).failed and not bus.rt(4).failed
    assert bus.health_frac() == 2 / 3
    assert bus.degraded


def test_empty_bus_is_vacuously_healthy() -> None:
    bus = DataBus("db.b")
    assert bus.health_frac() == 1.0
    assert not bus.degraded


def test_duplicate_rt_address_is_a_build_error() -> None:
    bus = DataBus("db.a")
    bus.register_rt(12)
    with pytest.raises(ValueError, match="duplicate RT address"):
        bus.register_rt(12)
