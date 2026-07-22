"""Manual conformance (ADR-0005): SOM Ch 42 procedures must pass headlessly.

A failing procedure here means the manual and the ship disagree — a P1
either way (workflow.md, `manual-wrong`). Fix the design ruling, not the
test. The checkout is written against TB-1; the Kestrel run proves the
chapter is true on the player ship too (same addresses, same truth).
"""

from __future__ import annotations

from ultraspace.content import ContentTree
from ultraspace.interaction import run_procedure
from ultraspace.ship import Simulation

COVERED = {"core:som-42-30-01"}


def test_som_42_30_01_checkout_conforms_tb1(tree: ContentTree) -> None:
    sim = Simulation(tree, "core:tb-1", master_seed=42)
    up = run_procedure(sim, tree.procedures["core:som-24-30-01"])
    assert up.passed, up.failure_summary()
    result = run_procedure(sim, tree.procedures["core:som-42-30-01"])
    assert result.passed, result.failure_summary()
    # Documented end state: bus healthy, no cautions anywhere.
    assert "MASTER CAUTION: clear" in sim.summary()


def test_som_42_30_01_checkout_conforms_kestrel(tree: ContentTree) -> None:
    sim = Simulation(tree, "core:uev-kestrel", master_seed=42)
    up = run_procedure(sim, tree.procedures["core:som-24-30-03"])
    assert up.passed, up.failure_summary()
    result = run_procedure(sim, tree.procedures["core:som-42-30-01"])
    assert result.passed, result.failure_summary()
    assert "MASTER CAUTION: clear" in sim.summary()


def test_som_42_30_01_conforms_across_seeds(tree: ContentTree) -> None:
    """The procedure must survive transducer noise, not one lucky seed."""
    for seed in (1, 7, 1337, 2026):
        sim = Simulation(tree, "core:tb-1", master_seed=seed)
        up = run_procedure(sim, tree.procedures["core:som-24-30-01"])
        assert up.passed, f"seed {seed} power-up: {up.failure_summary()}"
        result = run_procedure(sim, tree.procedures["core:som-42-30-01"])
        assert result.passed, f"seed {seed}: {result.failure_summary()}"
