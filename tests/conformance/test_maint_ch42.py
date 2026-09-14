"""MAINT conformance (ADR-0005, testing.md class 6): the swap task must be
walkable headlessly and must close itself out.

A maintenance task is the other half of a verdict (failure-and-repair.md,
MAINT v1). These tests hold MAINT 42-110-001 to the two promises its manual
makes: it refuses *before* the bus is down when it cannot be finished, and it
ends with an instrument saying the function is back — not with a board in a
rack.
"""

from __future__ import annotations

import pytest

from ultraspace.content import ContentTree
from ultraspace.interaction import Dispatcher, run_procedure
from ultraspace.interaction.procedures import ProcedureResult
from ultraspace.ship import Simulation
from ultraspace.testing import inject_fault

COVERED = {"core:maint-42-110-001"}

#: Every position MAINT 42-110-001 claims. Both are walked end to end.
TARGETS = {"rt.12", "rt.5"}


def convicted(tree: ContentTree, position: str = "rt.12") -> Simulation:
    """TB-1 up, the named terminal dead and declared — FIM 42-12's exit state."""
    sim = Simulation(tree, "core:tb-1", master_seed=42)
    for proc_id in ("core:som-24-30-01", "core:som-42-30-01"):
        result = run_procedure(sim, tree.procedures[proc_id])
        assert result.passed, result.failure_summary()
    inject_fault(sim, position, "dead")
    sim.step(4)
    return sim


def path(result: ProcedureResult) -> list[int]:
    return [s.step for s in result.steps]


@pytest.mark.parametrize("target", sorted(TARGETS))
def test_maint_42_110_001_restores_the_terminal(tree: ContentTree, target: str) -> None:
    """One task card, every identical position. The page is printed for RT 12;
    a variant nobody executes is a variant nobody can trust."""
    sim = convicted(tree, target)
    assert "DATA BUS A DEGRADED" in sim.panel.active_messages()
    result = run_procedure(sim, tree.procedures["core:maint-42-110-001"], target)
    assert result.passed, result.failure_summary()
    assert result.target == target
    assert path(result) == list(range(1, 16))
    assert "HEALTHY" in sim.execute("data.db.a", "read", set()).text
    assert "DATA BUS A DEGRADED" not in sim.panel.active_messages()
    # The counters belonged to the board that came out; a fresh board must not
    # inherit them (2026-09-14 playtest).
    assert "TOTAL 0 errors" in sim.execute("data.db.a", "read", set()).text


def test_every_target_the_task_claims_is_executed(tree: ContentTree) -> None:
    """The canary for the parametrization above: adding a target to the YAML
    without a position to run it at fails here, not in the field."""
    assert set(tree.procedures["core:maint-42-110-001"].target_names()) == TARGETS


def test_the_board_that_went_in_is_not_the_board_that_came_out(tree: ContentTree) -> None:
    """Identity is the point: a swap that reseats the same serial is a reseat."""
    sim = convicted(tree)
    before = sim.units.unit_at("rt.12")
    assert before is not None
    run_procedure(sim, tree.procedures["core:maint-42-110-001"])
    after = sim.units.unit_at("rt.12")
    assert after is not None and after.serial != before.serial
    assert before in sim.units.bench and before.fault_found  # the fault came off with it
    assert sim.units.on_shelf("core:rt-1553") == 0  # stores are finite


def test_the_task_refuses_before_the_bus_comes_down(tree: ContentTree) -> None:
    """Step 2 is the safety: an empty shelf holds the checklist with the ship
    still whole, rather than halfway through a swap it cannot finish."""
    sim = convicted(tree)
    first = run_procedure(sim, tree.procedures["core:maint-42-110-001"])
    assert first.passed, first.failure_summary()
    inject_fault(sim, "rt.5", "dead")
    sim.step(4)
    second = run_procedure(sim, tree.procedures["core:maint-42-110-001"])
    assert not second.passed
    assert path(second) == [1, 2]  # held at stores, nothing opened
    assert "NO SPARES" in second.steps[-1].detail
    assert sim.execute("data.db.a", "read", set()).text.count("OK") == 1  # RT 12 still up


def test_the_interlock_holds_on_a_live_bus(tree: ContentTree) -> None:
    """You do not pull a board out of a powered rack (MAINT 00-00 §2)."""
    sim = convicted(tree)
    d = Dispatcher(sim)
    refusal = d.execute_line("data.db.a.rt.12 remove")
    assert not refusal.ok and "de-energize" in refusal.text
    assert sim.units.unit_at("rt.12") is not None
