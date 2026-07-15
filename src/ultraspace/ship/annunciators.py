"""Annunciator panel: threshold monitors on telemetry (ANNUNCIATORS phase).

Annunciators watch *measured* values only — a warning fires because the
monitored parameter crossed a threshold as instruments saw it, never because a
fault exists (failure-and-repair.md, observability). `arm_above` keeps alarms
quiet while cold & dark until the parameter first reaches normal range.
"""

from __future__ import annotations

from ultraspace.content.schemas import AnnunciatorSpec
from ultraspace.kernel import EventLog
from ultraspace.ship.telemetry import TelemetryStore

__all__ = ["Annunciator", "AnnunciatorPanel"]


class Annunciator:
    def __init__(self, spec: AnnunciatorSpec) -> None:
        self.spec = spec
        self.armed = spec.arm_above is None  # armed immediately if no arm gate
        self.active = False

    def scan(self, telemetry: TelemetryStore, log: EventLog, tick: int) -> None:
        item = telemetry.read(self.spec.telemetry)
        if item is None:
            return
        if not self.armed and self.spec.arm_above is not None and item.value > self.spec.arm_above:
            self.armed = True
        if not self.armed:
            return
        exceeded = (self.spec.low is not None and item.value < self.spec.low) or (
            self.spec.high is not None and item.value > self.spec.high
        )
        if exceeded and not self.active:
            self.active = True
            log.append(
                tick,
                self.spec.id,
                "annunciator-raise",
                {"message": self.spec.message, "value": round(item.value, 3)},
            )
        elif not exceeded and self.active:
            self.active = False
            log.append(tick, self.spec.id, "annunciator-clear", {"message": self.spec.message})


class AnnunciatorPanel:
    def __init__(self, specs: list[AnnunciatorSpec]) -> None:
        self.annunciators = [Annunciator(spec) for spec in specs]  # blueprint order

    def scan(self, telemetry: TelemetryStore, log: EventLog, tick: int) -> None:
        for ann in self.annunciators:
            ann.scan(telemetry, log, tick)

    def active_messages(self) -> list[str]:
        return [a.spec.message for a in self.annunciators if a.active]

    @property
    def master_caution(self) -> bool:
        return any(a.active for a in self.annunciators)
