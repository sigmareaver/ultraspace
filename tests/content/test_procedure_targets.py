"""Procedure targets: one task, many identical positions (data-model.md).

A task written for one terminal is written for every identical terminal. The
schema's job is to make that promise checkable at load time, so a content
author cannot ship a placeholder no target fills or a target nobody uses.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ultraspace.content import ContentTree
from ultraspace.content.schemas import ProcedureSpec


def make_proc(steps: list[dict[str, object]], targets: list[dict[str, object]]) -> ProcedureSpec:
    return ProcedureSpec.model_validate(
        {
            "schema": "procedure/1",
            "id": "test-targets",
            "title": "Targets fixture",
            "manual_ref": "TEST 00-00",
            "ship": "core:tb-1",
            "steps": steps,
            "targets": targets,
        }
    )


ONE_STEP: list[dict[str, object]] = [{"step": 1, "scl": "data.db.a.{rt} records"}]
TWO_TARGETS: list[dict[str, object]] = [
    {"name": "rt.12", "values": {"rt": "rt.12"}},
    {"name": "rt.5", "values": {"rt": "rt.5"}},
]


def test_a_placeholder_with_no_targets_is_a_build_error() -> None:
    with pytest.raises(ValidationError, match="placeholders with no targets"):
        make_proc(ONE_STEP, [])


def test_a_target_that_does_not_fill_every_placeholder_is_a_build_error() -> None:
    with pytest.raises(ValidationError, match="defines no"):
        make_proc(ONE_STEP, [{"name": "rt.12", "values": {"cb": "cb.a2"}}])


def test_a_target_key_nobody_uses_is_a_build_error() -> None:
    """Dead substitutions are how a task quietly stops covering a position."""
    with pytest.raises(ValidationError, match="unused"):
        make_proc(ONE_STEP, [{"name": "rt.12", "values": {"rt": "rt.12", "cb": "cb.a2"}}])


def test_target_names_are_unique() -> None:
    with pytest.raises(ValidationError, match="unique"):
        make_proc(ONE_STEP, [TWO_TARGETS[0], TWO_TARGETS[0]])


def test_the_default_target_is_the_first_one() -> None:
    """The printed variant, and stable: order is authored, not hashed."""
    proc = make_proc(ONE_STEP, TWO_TARGETS)
    assert proc.target_names() == ["rt.12", "rt.5"]
    assert proc.target_values() == {"rt": "rt.12"}
    assert proc.target_values("rt.5") == {"rt": "rt.5"}


def test_an_unknown_target_is_an_error_not_a_default() -> None:
    proc = make_proc(ONE_STEP, TWO_TARGETS)
    with pytest.raises(KeyError, match=r"rt\.9"):
        proc.target_values("rt.9")
    with pytest.raises(KeyError, match="no targets"):
        make_proc([{"step": 1, "scl": "data.db.a read"}], []).target_values("rt.5")


def test_substitution_reaches_every_authored_field() -> None:
    proc = make_proc(
        [
            {
                "step": 1,
                "scl": "data.db.a.{rt} records",
                "note": "the nameplate on {rt}",
                "expect_text": "{rt} fitted",
            }
        ],
        TWO_TARGETS,
    )
    step = proc.steps[0].resolve(proc.target_values("rt.5"))
    assert step.scl == "data.db.a.rt.5 records"
    assert step.note == "the nameplate on rt.5"
    assert step.expect_text == "rt.5 fitted"
    assert proc.steps[0].scl == "data.db.a.{rt} records"  # the spec is not mutated


def test_the_maint_task_ships_both_terminals(tree: ContentTree) -> None:
    proc = tree.procedures["core:maint-42-110-001"]
    assert proc.target_names() == ["rt.12", "rt.5"]
    assert proc.steps[0].resolve(proc.target_values("rt.5")).scl == "data.db.a.rt.5 records"
