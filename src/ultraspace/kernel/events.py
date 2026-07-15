"""Append-only event log — the kernel of the FDR (simulation-kernel.md).

Events are totally ordered by ``(tick, seq)``; ``seq`` resets each tick. Each
event's canonical JSON is fixed at append time and feeds the log digest, which
serves as the determinism oracle for tests and the selftest canary.

Payloads must be JSON-serializable (enforced at append — a non-serializable
payload is a programmer bug and fails loudly, per the error philosophy in
architecture.md). Payload *values* must themselves be deterministic; that is
the emitting code's contract under ADR-0002.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass

__all__ = ["Event", "EventLog"]


@dataclass(frozen=True, slots=True)
class Event:
    tick: int
    seq: int
    source: str
    kind: str
    payload: Mapping[str, object]
    canonical: str
    """Canonical JSON of the full record; digest input, fixed at append time."""


class EventLog:
    """Append-only, (tick, seq)-ordered event record."""

    def __init__(self) -> None:
        self._events: list[Event] = []
        self._last_tick = -1
        self._next_seq = 0

    def append(
        self,
        tick: int,
        source: str,
        kind: str,
        payload: Mapping[str, object] | None = None,
    ) -> Event:
        """Record an event at ``tick``. Ticks must be non-decreasing."""
        if tick < self._last_tick:
            raise ValueError(f"event tick regression: got tick {tick} after tick {self._last_tick}")
        if tick > self._last_tick:
            self._last_tick = tick
            self._next_seq = 0
        payload_dict = dict(payload) if payload is not None else {}
        canonical = json.dumps(
            {
                "tick": tick,
                "seq": self._next_seq,
                "source": source,
                "kind": kind,
                "payload": payload_dict,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        event = Event(
            tick=tick,
            seq=self._next_seq,
            source=source,
            kind=kind,
            payload=payload_dict,
            canonical=canonical,
        )
        self._events.append(event)
        self._next_seq += 1
        return event

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self) -> Iterator[Event]:
        return iter(self._events)

    def digest(self) -> str:
        """blake2b hex digest over all canonical records — the determinism oracle."""
        hasher = hashlib.blake2b(digest_size=16)
        for event in self._events:
            hasher.update(event.canonical.encode())
            hasher.update(b"\n")
        return hasher.hexdigest()
