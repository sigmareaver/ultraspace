"""Annunciator panel: threshold monitors on telemetry (ANNUNCIATORS phase).

Annunciators watch *measured* values only — a warning fires because the
monitored parameter crossed a threshold as instruments saw it, never because a
fault exists (failure-and-repair.md, observability). `arm_above` keeps alarms
quiet while cold & dark until the parameter first reaches normal range.

A monitor asserts a *present-tense* fact about the ship, so it reads only
fresh telemetry (ata-42-data.md §5). A source that goes stale — its carrier
terminal dark, its controller unpowered — takes the monitor quiet and releases
any caution it was holding, the same as a source that never reported. The dark
lamp is then a statement about the instrument, not a clearance for the system;
SOM 42-00-00 §6 and §8 teach the crew to read it that way.

Every lamp carries two bits, not one (ata-31-indicating.md §3): whether the
condition holds *now*, and whether a human has seen this particular onset. The
second bit is what lets the panel get attention twice — the whole reason this
increment exists. Acknowledging never clears anything; it says only *I have
seen this*.
"""

from __future__ import annotations

from ultraspace.content.schemas import SEVERITY_RANK, AnnunciatorSpec
from ultraspace.kernel import EventLog
from ultraspace.ship.telemetry import TelemetryStore

__all__ = ["Annunciator", "AnnunciatorPanel"]


class Annunciator:
    def __init__(self, spec: AnnunciatorSpec) -> None:
        self.spec = spec
        self.armed = spec.arm_above is None  # armed immediately if no arm gate
        self.active = False
        self.acknowledged = False

    @property
    def is_new(self) -> bool:
        """Lit and unseen. Drives the flashing master and the recall marker."""
        return self.active and not self.acknowledged

    def _raise(self, log: EventLog, tick: int, value: float) -> None:
        self.active = True
        self.acknowledged = False  # every onset is new, including a re-raise
        log.append(
            tick,
            self.spec.id,
            "annunciator-raise",
            {
                "message": self.spec.message,
                "severity": self.spec.severity,
                "value": round(value, 3),
            },
        )

    def _clear(self, log: EventLog, tick: int, reason: str | None = None) -> None:
        self.active = False
        self.acknowledged = False
        payload: dict[str, object] = {
            "message": self.spec.message,
            "severity": self.spec.severity,
        }
        if reason is not None:
            payload["reason"] = reason
        log.append(tick, self.spec.id, "annunciator-clear", payload)

    def scan(self, telemetry: TelemetryStore, log: EventLog, tick: int) -> None:
        item = telemetry.fresh(self.spec.telemetry, tick)
        if item is None:  # no report, or one too old to be about now
            if self.active:
                self._clear(log, tick, reason="source stale")
            return
        if not self.armed and self.spec.arm_above is not None and item.value > self.spec.arm_above:
            self.armed = True
        if not self.armed:
            return
        exceeded = (self.spec.low is not None and item.value < self.spec.low) or (
            self.spec.high is not None and item.value > self.spec.high
        )
        if exceeded and not self.active:
            self._raise(log, tick, item.value)
        elif not exceeded and self.active:
            self._clear(log, tick)


class AnnunciatorPanel:
    def __init__(self, specs: list[AnnunciatorSpec]) -> None:
        self.annunciators = [Annunciator(spec) for spec in specs]  # blueprint order
        self.test_until_tick: int | None = None

    def scan(self, telemetry: TelemetryStore, log: EventLog, tick: int) -> None:
        for ann in self.annunciators:
            ann.scan(telemetry, log, tick)
        if self.test_until_tick is not None and tick >= self.test_until_tick:
            self.test_until_tick = None

    # -- crew actions --------------------------------------------------------

    def acknowledge(self, log: EventLog, tick: int) -> list[str]:
        """Mark every lit lamp seen; return the messages acknowledged."""
        seen = [a for a in self.annunciators if a.is_new]
        for ann in seen:
            ann.acknowledged = True
        messages = [a.spec.message for a in seen]
        log.append(
            tick,
            "sys.annunciator",
            "annunciator-ack",
            {"count": len(messages), "messages": messages},
        )
        return messages

    def lamp_test(self, log: EventLog, tick: int, ticks: int) -> None:
        """Light every lamp for ``ticks``. Acknowledges nothing, alerts nobody."""
        self.test_until_tick = tick + ticks
        log.append(
            tick,
            "sys.annunciator",
            "annunciator-test",
            {"lamps": [a.spec.message for a in self.annunciators]},
        )

    @property
    def testing(self) -> bool:
        return self.test_until_tick is not None

    # -- reads ---------------------------------------------------------------

    def recall(self) -> list[Annunciator]:
        """Lit lamps in the order the QRH tells the crew to work them.

        Severity, then new before acknowledged, then blueprint order — which is
        chapter order, and stable. Never recency (ata-31-indicating.md §5).
        """
        lit = [a for a in self.annunciators if a.active]
        return sorted(
            lit,
            key=lambda a: (SEVERITY_RANK[a.spec.severity], 0 if a.is_new else 1),
        )

    def active_messages(self) -> list[str]:
        return [a.spec.message for a in self.recall()]

    def _any(self, severity: str, *, new_only: bool = False) -> bool:
        return any(
            a.spec.severity == severity and (a.is_new if new_only else a.active)
            for a in self.annunciators
        )

    @property
    def master_warning(self) -> bool:
        return self._any("warning")

    @property
    def master_caution(self) -> bool:
        return self._any("caution")

    @property
    def master_warning_new(self) -> bool:
        """Flashing, not steady: something at this level has not been seen."""
        return self._any("warning", new_only=True)

    @property
    def master_caution_new(self) -> bool:
        return self._any("caution", new_only=True)
