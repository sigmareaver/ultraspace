"""Data-network conservation law: causality over arbitrary traffic patterns.

Iron Law 4 / testing.md class 3, per ata-42-data.md §3: no reply is counted
that was never sent (rx <= tx, and replies land only against polls issued in
the same tick), declarations stay within the registry, and health is always a
fraction. A violation is a P0.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from ultraspace.networks.data import FAIL_AFTER_POLLS, DataBus

_ADDRESSES = (4, 12, 30)


@given(
    pattern=st.lists(
        st.lists(st.booleans(), min_size=len(_ADDRESSES), max_size=len(_ADDRESSES)),
        min_size=0,
        max_size=40,
    )
)
@settings(max_examples=80, deadline=None)
def test_causality_and_health_over_arbitrary_traffic(pattern: list[list[bool]]) -> None:
    """Each inner list is one tick: whether each RT (in registry order) answers."""
    bus = DataBus("db.a")
    for address in _ADDRESSES:
        bus.register_rt(address)
    previous_errors = dict.fromkeys(_ADDRESSES, 0)

    for answers in pattern:
        rx_before = bus.rx_total
        for address, answered in zip(_ADDRESSES, answers, strict=True):
            bus.poll(address, answered)
        # Causality: replies — total and this tick — never exceed polls sent.
        assert bus.rx_total <= bus.tx_total
        assert bus.rx_total - rx_before <= len(_ADDRESSES)
        for address in _ADDRESSES:
            rt = bus.rt(address)
            # Declaration rule: FAILED <=> 3+ consecutive timeouts, nothing else.
            assert rt.failed == (rt.consec_timeouts >= FAIL_AFTER_POLLS)
            # Error evidence is monotone (never rewinds).
            assert rt.error_total >= previous_errors[address]
            previous_errors[address] = rt.error_total

    assert 0.0 <= bus.health_frac() <= 1.0
    assert bus.degraded == (bus.health_frac() < 1.0)
