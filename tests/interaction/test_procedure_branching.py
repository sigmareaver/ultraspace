"""Procedure-runner branching (FIM/QRH trees): on_pass_goto / on_fail_goto.

Branching is how a manual's decision tree stays executable (data-model.md,
procedure/1). A taken branch is recorded, not held; skipped steps do not
count against the verdict; a loop guard bounds the walk.
"""

from __future__ import annotations

import pytest

from ultraspace.content import ContentTree
from ultraspace.content.schemas import ProcedureSpec
from ultraspace.interaction import run_procedure
from ultraspace.ship import Simulation


def make_proc(steps: list[dict[str, object]]) -> ProcedureSpec:
    return ProcedureSpec.model_validate(
        {
            "schema": "procedure/1",
            "id": "test-branch",
            "title": "Branching fixture",
            "manual_ref": "TEST 00-00",
            "ship": "core:tb-1",
            "steps": steps,
        }
    )


def test_on_fail_goto_is_taken_and_recorded(tree: ContentTree) -> None:
    sim = Simulation(tree, "core:tb-1", master_seed=42)
    sim.step(1)  # cold & dark: mt.bus.e.v ~0.03 V
    proc = make_proc(
        [
            {
                "step": 1,
                "scl": "eps bus.e read",
                "expect_telemetry": "mt.bus.e.v",
                "expect_min": 25.0,  # unmet on a dead bus
                "within_s": 0.3,
                "on_fail_goto": 3,
            },
            {"step": 2, "scl": "eps bus.a read"},
            {"step": 3, "wait_s": 0.1},
        ]
    )
    result = run_procedure(sim, proc)
    assert result.passed, result.failure_summary()
    assert [r.step for r in result.steps] == [1, 3]  # step 2 skipped by the branch
    assert "branch to step 3" in result.steps[0].detail


def test_on_pass_goto_is_taken_and_recorded(tree: ContentTree) -> None:
    sim = Simulation(tree, "core:tb-1", master_seed=42)
    sim.step(1)
    proc = make_proc(
        [
            {
                "step": 1,
                "scl": "eps bus.e read",
                "expect_telemetry": "mt.bus.e.v",
                "expect_max": 1.0,  # met on a dead bus
                "within_s": 0.3,
                "on_pass_goto": 3,
            },
            {"step": 2, "scl": "eps bus.a read"},
            {"step": 3, "wait_s": 0.1},
        ]
    )
    result = run_procedure(sim, proc)
    assert result.passed, result.failure_summary()
    assert [r.step for r in result.steps] == [1, 3]
    assert "branch to step 3" in result.steps[0].detail


def test_unmet_indication_without_branch_still_holds(tree: ContentTree) -> None:
    sim = Simulation(tree, "core:tb-1", master_seed=42)
    sim.step(1)
    proc = make_proc(
        [
            {
                "step": 1,
                "scl": "eps bus.e read",
                "expect_telemetry": "mt.bus.e.v",
                "expect_min": 25.0,
                "within_s": 0.3,
            },
            {"step": 2, "wait_s": 0.1},
        ]
    )
    result = run_procedure(sim, proc)
    assert not result.passed
    assert [r.step for r in result.steps] == [1]  # held at the failed step


def test_branch_loop_guard_trips(tree: ContentTree) -> None:
    sim = Simulation(tree, "core:tb-1", master_seed=42)
    sim.step(1)
    always = {"expect_telemetry": "mt.bus.e.v", "expect_max": 1.0, "within_s": 0.2}
    proc = make_proc(
        [
            {"step": 1, "scl": "eps bus.e read", **always, "on_pass_goto": 2},
            {"step": 2, "scl": "eps bus.e read", **always, "on_pass_goto": 1},
        ]
    )
    result = run_procedure(sim, proc)
    assert not result.passed
    assert "branch-loop guard" in result.steps[-1].detail


def test_branch_targets_are_schema_validated() -> None:
    with pytest.raises(ValueError, match="invalid branch target"):
        make_proc(
            [
                {
                    "step": 1,
                    "scl": "eps read",
                    "expect_telemetry": "mt.bus.e.v",
                    "expect_min": 1.0,
                    "on_pass_goto": 7,
                }
            ]
        )
    with pytest.raises(ValueError, match="invalid branch target"):
        make_proc(
            [
                {
                    "step": 1,
                    "scl": "eps read",
                    "expect_telemetry": "mt.bus.e.v",
                    "expect_min": 1.0,
                    "on_pass_goto": 1,
                }
            ]
        )
    with pytest.raises(ValueError, match="branch targets require an expectation"):
        make_proc([{"step": 1, "scl": "eps read", "on_pass_goto": 1}])
    with pytest.raises(ValueError, match="one expectation kind per step"):
        make_proc(
            [
                {
                    "step": 1,
                    "scl": "eps read",
                    "expect_telemetry": "mt.bus.e.v",
                    "expect_min": 1.0,
                    "expect_text": "V",
                }
            ]
        )
