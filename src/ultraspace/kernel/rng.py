"""Named deterministic RNG streams (ADR-0002).

Every consumer of randomness owns a named stream obtained from :class:`RngHub`.
Stream seeds derive from ``blake2b(master_seed, stream_name)``, so:

- the same (seed, name) yields the same sequence on any platform;
- streams are independent: draws on one never perturb another, so adding a
  device to a ship cannot reshuffle when an unrelated pump fails
  (perturbation-independence law, enforced by tests/kernel/test_rng.py).

Stream names follow ``domain/entity/purpose`` with at least three segments,
e.g. ``fault/pdu2.a2.u4/latchup`` or ``world/traffic/meridian/departures`` —
grep-ability of draws is the point (coding-standards.md).
"""

from __future__ import annotations

import hashlib
import random

__all__ = ["RngHub"]

_MIN_NAME_SEGMENTS = 3


def _validate_stream_name(name: str) -> None:
    segments = name.split("/")
    if len(segments) < _MIN_NAME_SEGMENTS or any(not s for s in segments):
        raise ValueError(
            f"RNG stream name must have >= {_MIN_NAME_SEGMENTS} non-empty '/'-separated "
            f"segments (domain/entity/purpose), got {name!r}"
        )


class RngHub:
    """Factory and registry for named deterministic random streams."""

    def __init__(self, master_seed: int) -> None:
        self._master_seed = master_seed
        self._streams: dict[str, random.Random] = {}  # lookup only, never iterated

    @property
    def master_seed(self) -> int:
        return self._master_seed

    def stream(self, name: str) -> random.Random:
        """Return the stream for ``name``, creating it on first use.

        Streams are stateful: repeated calls return the *same* generator, which
        continues its sequence. State therefore depends only on (master seed,
        name, number of prior draws on this stream).
        """
        _validate_stream_name(name)
        existing = self._streams.get(name)
        if existing is not None:
            return existing
        digest = hashlib.blake2b(
            f"{self._master_seed}\x00{name}".encode(),
            digest_size=8,
        ).digest()
        rng = random.Random(int.from_bytes(digest, "little"))
        self._streams[name] = rng
        return rng
