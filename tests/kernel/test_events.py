"""EventLog: (tick, seq) ordering, canonicalization, digest oracle."""

from __future__ import annotations

import pytest

from ultraspace.kernel import EventLog


def test_seq_increments_within_tick_and_resets_across_ticks() -> None:
    log = EventLog()
    e0 = log.append(5, "eps.bus-a", "energized")
    e1 = log.append(5, "eps.bus-a", "load-step", {"amps": 21})
    e2 = log.append(6, "eps.bus-a", "load-step", {"amps": 22})

    assert (e0.tick, e0.seq) == (5, 0)
    assert (e1.tick, e1.seq) == (5, 1)
    assert (e2.tick, e2.seq) == (6, 0)
    assert len(log) == 3


def test_tick_regression_rejected() -> None:
    log = EventLog()
    log.append(10, "src", "kind")
    with pytest.raises(ValueError, match="regression"):
        log.append(9, "src", "kind")


def test_events_iterate_in_order() -> None:
    log = EventLog()
    log.append(1, "a", "x")
    log.append(1, "b", "y")
    log.append(2, "c", "z")
    assert [(e.tick, e.seq, e.source) for e in log] == [(1, 0, "a"), (1, 1, "b"), (2, 0, "c")]


def test_digest_is_content_determined() -> None:
    def build(amps: int) -> EventLog:
        log = EventLog()
        log.append(1, "eps.bus-a", "energized")
        log.append(2, "eps.bus-a", "load-step", {"amps": amps})
        return log

    assert build(21).digest() == build(21).digest()
    assert build(21).digest() != build(22).digest()


def test_payload_key_order_does_not_matter() -> None:
    """Canonicalization sorts keys: semantically equal payloads hash equally."""
    log_a = EventLog()
    log_a.append(1, "s", "k", {"x": 1, "y": 2})
    log_b = EventLog()
    log_b.append(1, "s", "k", {"y": 2, "x": 1})
    assert log_a.digest() == log_b.digest()


def test_non_json_payload_fails_loudly() -> None:
    """Non-serializable payloads are programmer bugs, caught at append time."""
    log = EventLog()
    with pytest.raises(TypeError):
        log.append(1, "s", "k", {"bad": object()})


def test_payload_is_copied_at_append() -> None:
    """Later mutation of the caller's dict must not alter the recorded event."""
    log = EventLog()
    payload = {"amps": 21}
    event = log.append(1, "s", "k", payload)
    payload["amps"] = 999
    assert event.payload["amps"] == 21
