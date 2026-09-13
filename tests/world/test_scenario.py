"""Scenario playback: the environment timeline and authored faults."""

from __future__ import annotations

import pytest

from ultraspace.content import ContentTree
from ultraspace.content.schemas import ScenarioSpec
from ultraspace.ship import Simulation
from ultraspace.ship.environment import CM2_PER_M2, QUIET_FLUX_M2S
from ultraspace.world import ScenarioRun


def scenario(**kwargs: object) -> ScenarioSpec:
    base: dict[str, object] = {
        "schema": "scenario/1",
        "id": "unit",
        "name": "unit test",
        "ship": "core:tb-1",
        "seed": 1,
    }
    return ScenarioSpec.model_validate(base | kwargs)


def flux_cm2s(sim: Simulation) -> float:
    return sim.environment.flux_m2s / CM2_PER_M2


def test_the_timeline_interpolates_between_its_points(tb1: Simulation) -> None:
    spec = scenario(
        environment=[
            {"at_s": 0.0, "flux_cm2s": 10.0},
            {"at_s": 100.0, "flux_cm2s": 110.0},
        ]
    )
    ScenarioRun(spec, tb1)
    assert flux_cm2s(tb1) == pytest.approx(10.0)
    tb1.step(500)  # 50 s in
    assert flux_cm2s(tb1) == pytest.approx(59.9, abs=0.11)  # one tick of documented lag


def test_the_timeline_holds_flat_past_its_last_point(tb1: Simulation) -> None:
    spec = scenario(environment=[{"at_s": 0.0, "flux_cm2s": 5.0}, {"at_s": 10.0, "flux_cm2s": 7.0}])
    ScenarioRun(spec, tb1)
    tb1.step(1000)
    assert flux_cm2s(tb1) == pytest.approx(7.0)


def test_no_timeline_leaves_the_quiet_background(tb1: Simulation) -> None:
    ScenarioRun(scenario(), tb1)
    tb1.step(100)
    assert tb1.environment.flux_m2s == pytest.approx(QUIET_FLUX_M2S)


def test_a_scheduled_fault_fires_once_at_its_time(tb1: Simulation) -> None:
    spec = scenario(faults=[{"at_s": 5.0, "device": "rt.12", "mode": "dead"}])
    ScenarioRun(spec, tb1)
    tb1.step(40)
    assert [e for e in tb1.log if e.kind == "fault-onset"] == []
    tb1.step(20)
    onsets = [e for e in tb1.log if e.kind == "fault-onset"]
    assert len(onsets) == 1
    assert onsets[0].source == "rt.12"
    assert onsets[0].payload == {"mode": "dead", "by": "scenario"}
    tb1.step(100)
    assert len([e for e in tb1.log if e.kind == "fault-onset"]) == 1  # not re-fired


def test_faults_sharing_a_time_all_fire_on_the_same_tick(tb1: Simulation) -> None:
    spec = scenario(
        faults=[
            {"at_s": 1.0, "device": "rt.12", "mode": "dead"},
            {"at_s": 1.0, "device": "rt.5", "mode": "dead"},
        ]
    )
    ScenarioRun(spec, tb1)
    tb1.step(20)
    onsets = [e for e in tb1.log if e.kind == "fault-onset"]
    assert [e.source for e in onsets] == ["rt.12", "rt.5"]
    assert len({e.tick for e in onsets}) == 1


def test_the_timeline_must_move_forward() -> None:
    """Content that goes back in time is a content error, not a runtime surprise."""
    with pytest.raises(ValueError):
        scenario(environment=[{"at_s": 10.0, "flux_cm2s": 1.0}, {"at_s": 5.0, "flux_cm2s": 2.0}])
    with pytest.raises(ValueError):
        scenario(
            faults=[
                {"at_s": 10.0, "device": "rt.12", "mode": "dead"},
                {"at_s": 5.0, "device": "rt.5", "mode": "dead"},
            ]
        )


def test_shipped_scenarios_load(tree: ContentTree) -> None:
    assert {"core:spe-transit", "core:spe-minor"} <= set(tree.scenarios)
