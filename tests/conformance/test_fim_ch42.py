"""FIM conformance (ADR-0005, testing.md class 6): the documented isolation
tree must terminate at the injected fault — verdict correct, every time.

The procedure runner walks FIM 42-11 against each injected stuck-dominant;
the executed step list is the tree's trace, and each suspect must produce
its own path. A deliberately wrong FIM edit fails this suite — that is the
point of the suite.
"""

from __future__ import annotations

from ultraspace.content import ContentTree
from ultraspace.interaction import Dispatcher, run_procedure
from ultraspace.interaction.procedures import ProcedureResult
from ultraspace.ship import Simulation
from ultraspace.testing import inject_fault

COVERED = {"core:fim-42-11"}


def _run_fim(tree: ContentTree, suspect: str) -> tuple[Simulation, ProcedureResult]:
    """Data hardware up per SOM, the fault injected and declared, then the
    documented tree, headless — exactly as a player would work it."""
    sim = Simulation(tree, "core:tb-1", master_seed=42)
    up = run_procedure(sim, tree.procedures["core:som-24-30-01"])
    assert up.passed, up.failure_summary()
    checkout = run_procedure(sim, tree.procedures["core:som-42-30-01"])
    assert checkout.passed, checkout.failure_summary()
    inject_fault(sim, suspect, "stuck_dominant")
    sim.step(4)  # the BC misses, then declares — the symptom is on
    return sim, run_procedure(sim, tree.procedures["core:fim-42-11"])


def test_fim_42_11_convicts_rt12(tree: ContentTree) -> None:
    sim, result = _run_fim(tree, "rt.12")
    assert result.passed, result.failure_summary()
    # The bus recovered when RT 12's feed was cycled — RT 5 never touched.
    assert [r.step for r in result.steps] == [1, 2, 3, 4, 10]
    assert "MASTER CAUTION: clear" in sim.summary()  # service restored


def test_fim_42_11_convicts_rt5(tree: ContentTree) -> None:
    sim, result = _run_fim(tree, "rt.5")
    assert result.passed, result.failure_summary()
    # RT 12's cycle did not recover it; RT 5's did — the tree branched on.
    assert [r.step for r in result.steps] == [1, 2, 3, 4, 5, 6, 7, 10]
    assert "MASTER CAUTION: clear" in sim.summary()


def test_fim_42_11_routes_one_dark_out_of_the_jam_tree(tree: ContentTree) -> None:
    """A plain power loss is not the jam: the tree must exit at the §2
    boundary, not cycle innocent feeds."""
    sim = Simulation(tree, "core:tb-1", master_seed=42)
    for proc_id in ("core:som-24-30-01", "core:som-42-30-01"):
        result = run_procedure(sim, tree.procedures[proc_id])
        assert result.passed, result.failure_summary()
    d = Dispatcher(sim)
    d.execute_line("eps cb.a2 open")  # RT 12 dark — one-dark power loss
    sim.step(4)
    result = run_procedure(sim, tree.procedures["core:fim-42-11"])
    assert result.passed, result.failure_summary()
    assert [r.step for r in result.steps] == [1, 8]  # boundary exit, no cycling
