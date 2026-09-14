"""A timed wait is a watch, not a sleep (command-language.md).

A crew member holding a stopwatch does not stop being a crew member. These
tests hold the runner to that: warnings interrupt a wait and say what is left,
cautions do not, a lamp already lit when the clock started does not, and the
one step that must finish anyway says so out loud.
"""

from __future__ import annotations

import pytest

from ultraspace.content import ContentTree
from ultraspace.content.schemas import ProcedureSpec
from ultraspace.interaction import run_procedure
from ultraspace.interaction.procedures import ProcedureResult
from ultraspace.ship import Simulation
from ultraspace.ship.devices import RemoteTerminal
from ultraspace.testing import inject_fault, raw_device


@pytest.fixture
def flying(tree: ContentTree) -> Simulation:
    sim = Simulation(tree, "core:tb-1", master_seed=42)
    for proc_id in ("core:som-24-30-01", "core:som-42-30-01"):
        result = run_procedure(sim, tree.procedures[proc_id])
        assert result.passed, result.failure_summary()
    return sim


def wait_proc(seconds: float, *, hold: bool = False) -> ProcedureSpec:
    return ProcedureSpec.model_validate(
        {
            "schema": "procedure/1",
            "id": "test-wait",
            "title": "Wait fixture",
            "manual_ref": "TEST 00-00",
            "ship": "core:tb-1",
            "steps": [{"step": 1, "wait_s": seconds, "hold_through_warning": hold}],
        }
    )


def wait(sim: Simulation, seconds: float, *, hold: bool = False) -> ProcedureResult:
    return run_procedure(sim, wait_proc(seconds, hold=hold))


def jam(sim: Simulation) -> None:
    """A babbling terminal takes the whole bus down: DATA BUS A FAILED."""
    inject_fault(sim, "rt.12", "stuck_dominant")


def test_a_warning_ends_the_wait_and_says_what_is_left(flying: Simulation) -> None:
    jam(flying)
    result = wait(flying, 30.0)
    detail = result.steps[0].detail
    assert result.passed  # interrupted is not failed: the ship talked, that is its right
    assert "INTERRUPTED by WARNING: DATA BUS A FAILED" in detail
    assert "of the wait remaining" in detail
    assert flying.clock.tick_index < 300  # it stopped the clock; it did not run 30 s


def test_the_interruption_is_in_the_fdr(flying: Simulation) -> None:
    jam(flying)
    wait(flying, 30.0)
    events = [e for e in flying.log if e.kind == "wait-interrupted"]
    assert len(events) == 1
    assert events[0].payload["messages"] == ["DATA BUS A FAILED"]
    remaining_s = events[0].payload["remaining_s"]
    assert isinstance(remaining_s, float) and remaining_s > 0.0


def test_a_caution_does_not_interrupt(flying: Simulation) -> None:
    """A checklist that stopped for every caution would never finish a start."""
    inject_fault(flying, "rt.12", "dead")
    before = flying.clock.tick_index
    result = wait(flying, 2.0)
    assert "DATA BUS A DEGRADED" in flying.panel.active_messages()
    assert result.steps[0].detail == "waited 2.0 s"
    assert flying.clock.tick_index - before == 20


def test_a_warning_already_lit_does_not_interrupt(flying: Simulation) -> None:
    """The wait reacts to an onset, not to a standing condition — otherwise no
    checklist could be run while anything at all was wrong."""
    jam(flying)
    flying.step(10)
    assert flying.panel.master_warning_new  # lit and unseen, and still not an onset
    before = flying.clock.tick_index
    assert wait(flying, 2.0).steps[0].detail == "waited 2.0 s"
    assert flying.clock.tick_index - before == 20


def test_a_second_onset_of_the_same_lamp_interrupts_again(flying: Simulation) -> None:
    jam(flying)
    flying.step(10)
    board = raw_device(flying, "rt.12")
    assert isinstance(board, RemoteTerminal)
    board.stuck_dominant = False
    flying.step(10)
    assert "DATA BUS A FAILED" not in flying.panel.active_messages()
    jam(flying)
    assert "INTERRUPTED" in wait(flying, 30.0).steps[0].detail


def test_a_step_may_hold_through_a_warning_and_must_say_so(flying: Simulation) -> None:
    """The bleed-down case: the only thing between you and energized hardware
    is that second, and no lamp is worth reaching into a rack for."""
    jam(flying)
    before = flying.clock.tick_index
    detail = wait(flying, 2.0, hold=True).steps[0].detail
    assert detail == "waited 2.0 s — held through WARNING: DATA BUS A FAILED (step NOTE)"
    assert flying.clock.tick_index - before == 20
    assert not [e for e in flying.log if e.kind == "wait-interrupted"]


def test_hold_through_warning_needs_a_wait(tree: ContentTree) -> None:
    with pytest.raises(ValueError, match="applies to a wait step"):
        ProcedureSpec.model_validate(
            {
                "schema": "procedure/1",
                "id": "test-hold",
                "title": "Bad hold",
                "manual_ref": "TEST 00-00",
                "ship": "core:tb-1",
                "steps": [{"step": 1, "scl": "data.db.a read", "hold_through_warning": True}],
            }
        )
