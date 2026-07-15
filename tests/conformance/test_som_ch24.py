"""Manual conformance (ADR-0005): SOM Ch 24 procedures must pass headlessly.

A failing procedure here means the manual and the ship disagree — a P1
either way (workflow.md, `manual-wrong`). Fix the design ruling, not the
test.
"""

from __future__ import annotations

from ultraspace.content import ContentTree
from ultraspace.interaction import run_procedure
from ultraspace.ship import Simulation

COVERED = {"core:som-24-30-01", "core:som-24-30-02"}


def test_som_24_30_01_power_up_conforms(tree: ContentTree) -> None:
    sim = Simulation(tree, "core:tb-1", master_seed=42)
    result = run_procedure(sim, tree.procedures["core:som-24-30-01"])
    assert result.passed, result.failure_summary()
    # Documented end state: no cautions with buses powered.
    assert "MASTER CAUTION: clear" in sim.summary()


def test_som_24_30_01_conforms_across_seeds(tree: ContentTree) -> None:
    """The procedure must survive transducer noise, not one lucky seed."""
    for seed in (1, 7, 1337, 2026):
        sim = Simulation(tree, "core:tb-1", master_seed=seed)
        result = run_procedure(sim, tree.procedures["core:som-24-30-01"])
        assert result.passed, f"seed {seed}: {result.failure_summary()}"


def test_som_24_30_02_power_down_conforms_after_power_up(tree: ContentTree) -> None:
    sim = Simulation(tree, "core:tb-1", master_seed=42)
    up = run_procedure(sim, tree.procedures["core:som-24-30-01"])
    assert up.passed, up.failure_summary()
    down = run_procedure(sim, tree.procedures["core:som-24-30-02"])
    assert down.passed, down.failure_summary()


def test_every_shipped_procedure_is_covered(tree: ContentTree) -> None:
    """Canary: adding a procedure without conformance coverage fails the build.

    Replaced by a generic parametrized runner (with declared preconditions)
    when the procedure count grows — M2.
    """
    assert set(tree.procedures) == COVERED
