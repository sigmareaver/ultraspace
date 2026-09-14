"""Annunciator discipline: severity, acknowledgement, recall order (ATA 31).

Unit level. The player's experience of the same machinery — a second casualty
arriving under an already-lit lamp — is in
tests/casualties/test_ata31_second_casualty.py.
"""

from __future__ import annotations

import pytest

from ultraspace.content import ContentTree
from ultraspace.content.schemas import AnnunciatorSpec
from ultraspace.kernel import EventLog
from ultraspace.ship import Simulation
from ultraspace.ship.annunciators import AnnunciatorPanel
from ultraspace.ship.telemetry import TelemetryItem, TelemetryStore


def panel(*specs: dict[str, object]) -> tuple[AnnunciatorPanel, TelemetryStore, EventLog]:
    built = [AnnunciatorSpec.model_validate(s) for s in specs]
    return AnnunciatorPanel(built), TelemetryStore(), EventLog()


def publish(store: TelemetryStore, telemetry_id: str, value: float, tick: int) -> None:
    store.publish(TelemetryItem(telemetry_id, value, "V", telemetry_id, tick))


def lamp(severity: str, **kwargs: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": f"ann.{severity}",
        "telemetry": f"mt.{severity}",
        "message": severity.upper(),
        "severity": severity,
        "low": 1.0,
    }
    return base | kwargs


def test_severity_defaults_to_caution() -> None:
    """The level that means 'real, and you have time to think'."""
    spec = AnnunciatorSpec.model_validate({"id": "a", "telemetry": "t", "message": "M", "low": 1.0})
    assert spec.severity == "caution"


def test_a_raised_lamp_is_new_until_acknowledged() -> None:
    board, store, log = panel(lamp("caution"))
    publish(store, "mt.caution", 0.0, 0)
    board.scan(store, log, 0)
    only = board.annunciators[0]
    before = (only.active, only.is_new, board.master_caution, board.master_caution_new)
    assert before == (True, True, True, True)
    assert board.acknowledge(log, 1) == ["CAUTION"]
    after = (only.active, only.is_new, board.master_caution, board.master_caution_new)
    assert after == (True, False, True, False), "acknowledging is seeing, not clearing"


def test_a_lamp_that_clears_and_re_raises_is_new_again() -> None:
    """Told twice, because it happened twice (ata-31-indicating.md §3)."""
    board, store, log = panel(lamp("caution"))
    publish(store, "mt.caution", 0.0, 0)
    board.scan(store, log, 0)
    board.acknowledge(log, 0)
    publish(store, "mt.caution", 5.0, 1)
    board.scan(store, log, 1)
    assert not board.annunciators[0].active
    publish(store, "mt.caution", 0.0, 2)
    board.scan(store, log, 2)
    assert board.annunciators[0].is_new


def test_advisories_never_drive_a_master() -> None:
    """That is what makes them advisories."""
    board, store, log = panel(lamp("advisory"))
    publish(store, "mt.advisory", 0.0, 0)
    board.scan(store, log, 0)
    assert board.annunciators[0].active
    assert not board.master_warning and not board.master_caution


def test_recall_ranks_severity_then_new_then_blueprint_order() -> None:
    board, store, log = panel(
        lamp("advisory"),
        lamp("caution", id="ann.c1", telemetry="mt.c1", message="CAUTION ONE"),
        lamp("caution", id="ann.c2", telemetry="mt.c2", message="CAUTION TWO"),
        lamp("warning"),
    )
    for telemetry_id in ("mt.advisory", "mt.c1", "mt.c2", "mt.warning"):
        publish(store, telemetry_id, 0.0, 0)
    board.scan(store, log, 0)
    board.acknowledge(log, 0)
    # CAUTION TWO clears and comes back: newest, but still not first.
    publish(store, "mt.c2", 5.0, 1)
    board.scan(store, log, 1)
    publish(store, "mt.c2", 0.0, 2)
    board.scan(store, log, 2)
    assert [a.spec.message for a in board.recall()] == [
        "WARNING",  # severity outranks everything
        "CAUTION TWO",  # new before acknowledged, within its level
        "CAUTION ONE",
        "ADVISORY",
    ]


def test_recall_is_never_ordered_by_recency() -> None:
    """The newest problem is often a consequence of the worst one."""
    board, store, log = panel(
        lamp("warning"),
        lamp("advisory"),
    )
    publish(store, "mt.warning", 0.0, 0)
    board.scan(store, log, 0)
    board.acknowledge(log, 0)
    publish(store, "mt.advisory", 0.0, 5)  # much newer, and unacknowledged
    board.scan(store, log, 5)
    assert [a.spec.message for a in board.recall()] == ["WARNING", "ADVISORY"]


def test_acknowledging_an_empty_panel_is_not_an_error(tb1: Simulation) -> None:
    result = tb1.execute("sys.annunciator", "ack", set())
    assert result.ok and "nothing new" in result.text


def test_lamp_test_lights_everything_and_releases(tb1: Simulation) -> None:
    tb1.step(2)
    before = tb1.panel.testing
    result = tb1.execute("sys.annunciator", "test", set())
    during = tb1.panel.testing
    assert result.ok
    assert (before, during) == (False, True)
    assert "PANEL TEST" in tb1.execute("sys.annunciator", "read", set()).text
    tb1.step(25)
    assert not tb1.panel.testing
    # A test acknowledges nothing and raises nothing.
    assert not [e for e in tb1.log if e.kind == "annunciator-raise"]
    assert not [e for e in tb1.log if e.kind == "annunciator-ack"]


def test_the_panel_answers_only_its_own_verbs(tb1: Simulation) -> None:
    result = tb1.execute("sys.annunciator", "close", set())
    assert not result.ok and "read, ack, test" in result.text


def test_every_shipped_annunciator_declares_a_severity(tree: ContentTree) -> None:
    """Content check: a chapter that declares everything a warning declares nothing."""
    for ship_id in ("core:tb-1", "core:uev-kestrel"):
        specs = tree.ships[ship_id].annunciators
        assert specs, f"{ship_id} has no annunciators"
        warnings = [s for s in specs if s.severity == "warning"]
        assert warnings, f"{ship_id} declares no warning at all"
        assert len(warnings) < len(specs), f"{ship_id} declares everything a warning"


@pytest.mark.parametrize("ship_id", ["core:tb-1", "core:uev-kestrel"])
def test_data_bus_annunciation_is_graded(tree: ContentTree, ship_id: str) -> None:
    """DEGRADED cannot fire twice, so the last terminal needs its own lamp."""
    by_message = {s.message: s for s in tree.ships[ship_id].annunciators}
    degraded = by_message["DATA BUS A DEGRADED"]
    failed = by_message["DATA BUS A FAILED"]
    assert degraded.severity == "caution" and failed.severity == "warning"
    assert degraded.telemetry == failed.telemetry  # same measurement, two statements
    assert failed.low is not None and degraded.low is not None
    assert failed.low < degraded.low  # the harder threshold is the louder lamp
