"""RngHub: named streams, reproducibility, independence (ADR-0002 laws)."""

from __future__ import annotations

import pytest

from ultraspace.kernel import RngHub


def draws(hub: RngHub, name: str, n: int = 8) -> list[int]:
    stream = hub.stream(name)
    return [stream.randrange(1_000_000) for _ in range(n)]


def test_same_seed_same_name_same_sequence() -> None:
    a = draws(RngHub(1234), "fault/pump-p201/bearing")
    b = draws(RngHub(1234), "fault/pump-p201/bearing")
    assert a == b


def test_different_names_differ() -> None:
    hub = RngHub(1234)
    assert draws(hub, "fault/pump-p201/bearing") != draws(hub, "fault/pump-p202/bearing")


def test_different_seeds_differ() -> None:
    assert draws(RngHub(1), "fault/pump-p201/bearing") != draws(
        RngHub(2), "fault/pump-p201/bearing"
    )


def test_stream_is_stateful_singleton() -> None:
    """Repeated stream() calls return the same generator, continuing its sequence."""
    hub = RngHub(99)
    first = draws(hub, "world/traffic/departures", 4)
    resumed = draws(hub, "world/traffic/departures", 4)
    fresh = draws(RngHub(99), "world/traffic/departures", 8)
    assert first + resumed == fresh


def test_perturbation_independence() -> None:
    """Iron Law: draws on one stream never affect another stream's sequence.

    Adding a device (and its draws) to a ship must not reshuffle when an
    unrelated component fails.
    """
    reference = draws(RngHub(7), "fault/pdu2.a2.u4/latchup")

    noisy_hub = RngHub(7)
    draws(noisy_hub, "fault/other-device/wear", 1000)  # unrelated traffic first
    assert draws(noisy_hub, "fault/pdu2.a2.u4/latchup") == reference


def test_golden_sequence_pinned_cross_platform() -> None:
    """Golden values: seed 42, stream 'kernel/test/golden', randrange(1000).

    Obtained by running exactly that (2026-07-14, CPython 3.14, Linux). blake2b
    seed derivation and the Mersenne Twister core are platform/version stable;
    if this test ever fails, seed derivation changed — that is save-breaking
    (ADR-0002) and must be a conscious, versioned decision.
    """
    stream = RngHub(42).stream("kernel/test/golden")
    assert [stream.randrange(1000) for _ in range(5)] == [50, 670, 46, 189, 51]


@pytest.mark.parametrize("bad", ["", "noslash", "two/segments", "a//c", "/b/c", "a/b/"])
def test_stream_name_discipline(bad: str) -> None:
    """Names must be domain/entity/purpose (>= 3 non-empty segments)."""
    with pytest.raises(ValueError, match="segments"):
        RngHub(0).stream(bad)


def test_deeper_names_allowed() -> None:
    RngHub(0).stream("world/traffic/meridian/departures")  # 4 segments is fine
