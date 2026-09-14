"""Bus analyzer v1.1: zeroing the evidence, and the ship's own honest page.

Two surfaces that must not be confused (ata-42-data.md §3). The BC's table
answers for the BC and says NO RESPONSE, full stop. The `data read` summary is
the ship's page, and the ship knows two things the controller cannot: which
feeder is open and which position is empty. Zeroing is maintenance on the
analyzer — it moves counters and nothing else.
"""

from __future__ import annotations

import pytest

from ultraspace.content import ContentTree
from ultraspace.interaction import Dispatcher, run_procedure
from ultraspace.ship import Simulation
from ultraspace.testing import inject_fault


@pytest.fixture
def flying(tree: ContentTree) -> Simulation:
    """TB-1 up and checked out — which now includes zeroing the counters."""
    sim = Simulation(tree, "core:tb-1", master_seed=42)
    for proc_id in ("core:som-24-30-01", "core:som-42-30-01"):
        result = run_procedure(sim, tree.procedures[proc_id])
        assert result.passed, result.failure_summary()
    return sim


@pytest.fixture
def unchecked(tree: ContentTree) -> Simulation:
    """Buses up, bus energized by hand: counters never zeroed."""
    sim = Simulation(tree, "core:tb-1", master_seed=42)
    result = run_procedure(sim, tree.procedures["core:som-24-30-01"])
    assert result.passed, result.failure_summary()
    d = Dispatcher(sim)
    for line in ("eps cb.a2 close", "eps cb.e3 close", "eps cb.e2 close"):
        d.execute_line(line)
    sim.step(20)
    return sim


def errors(sim: Simulation) -> int:
    return sim.data_buses["db.a"].error_total()


def dirty(sim: Simulation) -> Simulation:
    """A bus with a history: RT 12 dark long enough to be declared."""
    Dispatcher(sim).execute_line("eps cb.a2 open")
    sim.step(40)
    return sim


# -- zeroing -----------------------------------------------------------------


def test_zero_is_guarded_because_the_evidence_does_not_come_back(flying: Simulation) -> None:
    dirty(flying)
    assert errors(flying) > 0
    refusal = Dispatcher(flying).execute_line("data.db.a zero")
    assert not refusal.ok
    assert "read it first" in refusal.text and "SOM 42-30-01" in refusal.text
    assert errors(flying) > 0  # refused means refused


def test_a_dark_controller_has_nothing_to_zero(tree: ContentTree) -> None:
    sim = Simulation(tree, "core:tb-1", master_seed=42)
    refusal = Dispatcher(sim).execute_line("data.db.a zero --confirm")
    assert not refusal.ok and "unpowered" in refusal.text


def test_zero_clears_the_totals_and_reports_what_it_discarded(flying: Simulation) -> None:
    dirty(flying)
    before = errors(flying)
    result = Dispatcher(flying).execute_line("data.db.a zero --confirm")
    assert result.ok and f"{before} errors discarded" in result.text
    assert errors(flying) == 0


def test_zero_moves_counters_and_nothing_else(flying: Simulation) -> None:
    """Not a system reset: the terminal is still dark and still declared, and
    the lamp that says so is still lit. Erasing the count is not a repair."""
    dirty(flying)
    Dispatcher(flying).execute_line("data.db.a zero --confirm")
    rt12 = flying.data_buses["db.a"].rt(12)
    assert rt12.failed and rt12.consec_timeouts >= 3
    assert "DATA BUS A DEGRADED" in flying.panel.active_messages()
    assert "DEGRADED" in flying.execute("data.db.a", "read", set()).text


def test_the_discarded_totals_go_to_the_fdr(flying: Simulation) -> None:
    dirty(flying)
    before = errors(flying)
    Dispatcher(flying).execute_line("data.db.a zero --confirm")
    zeroed = [e for e in flying.log if e.kind == "analyzer-zeroed"]
    assert zeroed[-1].payload["bus"] == "db.a"  # [0] is the checkout's own zero
    discarded = zeroed[-1].payload["discarded"]
    assert isinstance(discarded, dict)
    assert sum(int(n) for n in discarded.values()) == before


def test_the_table_says_when_the_counters_started_over(unchecked: Simulation) -> None:
    """A total is only evidence if you know what span it covers."""
    assert "TOTAL 0 errors since power-up" in unchecked.execute("data.db.a", "read", set()).text
    dirty(unchecked)
    assert "TOTAL 40 errors since power-up" in unchecked.execute("data.db.a", "read", set()).text
    Dispatcher(unchecked).execute_line("data.db.a zero --confirm")
    assert "TOTAL 0 errors since MET " in unchecked.execute("data.db.a", "read", set()).text


# -- the ship's own page -----------------------------------------------------


def test_a_shed_terminal_is_named_with_its_own_breaker(flying: Simulation) -> None:
    dirty(flying)
    summary = flying.summarize("data")
    assert "RT 12: NO RESPONSE — SHED (cb.a2 open)" in summary
    assert "SHED" not in flying.execute("data.db.a", "read", set()).text  # the BC's view is pure


def test_an_empty_position_says_so_and_says_when(flying: Simulation) -> None:
    d = Dispatcher(flying)
    for line in ("eps cb.e2 open", "eps cb.a2 open", "eps cb.e3 open"):
        d.execute_line(line)
    flying.step(10)
    assert d.execute_line("data.db.a.rt.12 remove").ok
    for line in ("eps cb.a2 close", "eps cb.e3 close", "eps cb.e2 close"):
        d.execute_line(line)
    flying.step(40)
    summary = flying.summarize("data")
    assert "RT 12: NO RESPONSE — NOT FITTED (position open since MET " in summary


def test_a_dark_board_gets_no_excuse(flying: Simulation) -> None:
    """The point of the annotations is the line that has none: the ship has no
    innocent explanation for this terminal, which is isolation data."""
    inject_fault(flying, "rt.12", "dead")
    flying.step(10)
    assert "RT 12: NO RESPONSE\n" in flying.summarize("data") + "\n"
    assert "SHED" not in flying.summarize("data")


def test_a_healthy_bus_lists_no_terminals(flying: Simulation) -> None:
    """Only the silent ones get a line — a page that lists everything is a page
    nobody reads."""
    summary = flying.summarize("data")
    assert "HEALTHY" in summary and "NO RESPONSE" not in summary
