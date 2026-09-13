"""Manual conformance (ADR-0005): SOM Ch 42 procedures must pass headlessly.

A failing procedure here means the manual and the ship disagree — a P1
either way (workflow.md, `manual-wrong`). Fix the design ruling, not the
test. The checkout is written against TB-1; the Kestrel run proves the
chapter is true on the player ship too (same addresses, same truth).
"""

from __future__ import annotations

from ultraspace.content import ContentTree
from ultraspace.interaction.procedures import ProcedureResult, run_procedure
from ultraspace.ship import Simulation
from ultraspace.world import ScenarioRun

COVERED = {"core:som-42-30-01", "core:som-42-30-02"}


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


def under_way(tree: ContentTree, scenario_id: str, seed: int) -> Simulation:
    """TB-1 powered up and on the bus, inside a scenario — a crew's starting state."""
    spec = tree.scenarios[scenario_id]
    sim = Simulation(tree, spec.ship, master_seed=seed)
    ScenarioRun(spec, sim)
    for procedure_id in ("core:som-24-30-01", "core:som-42-30-01"):
        result = run_procedure(sim, tree.procedures[procedure_id])
        assert result.passed, f"{procedure_id}: {result.failure_summary()}"
    return sim


def path(result: ProcedureResult) -> list[int]:
    """The steps the checklist actually walked — the branch tree is the content."""
    return [s.step for s in result.steps]


def test_som_42_30_02_declines_a_quiet_environment(tree: ContentTree) -> None:
    """The gate is the procedure's most important step: no event, no action."""
    sim = under_way(tree, "core:spe-minor", seed=42)  # t = 0: still quiet
    result = run_procedure(sim, tree.procedures["core:som-42-30-02"])
    assert result.passed, result.failure_summary()
    assert path(result) == [1, 8], "a quiet environment must exit at the gate"
    assert "12   OK" in sim.execute("data.db.a", "read", set()).text  # nothing was shed


def test_som_42_30_02_sheds_and_restores_through_a_minor_event(tree: ContentTree) -> None:
    sim = under_way(tree, "core:spe-minor", seed=24)
    while "SEU HAZARD" not in sim.panel.active_messages():
        sim.step(1)
    result = run_procedure(sim, tree.procedures["core:som-42-30-02"])
    assert result.passed, result.failure_summary()
    assert path(result) == [1, 2, 3, 4, 5, 6, 7], "the ride-out path"
    assert "DATA BUS A DEGRADED" not in sim.panel.active_messages()


def test_som_42_30_02_exits_to_the_fim_when_a_kept_terminal_latches(tree: ContentTree) -> None:
    """Seed 24 rides it out; seed 99 does not — same scenario, same checklist.

    RT 5 is on the essential bus and cannot be shed, so it takes the event at
    the full rate. When it latches, the procedure's restore step finds a bus
    that will not come back and hands off to FIM 42-11 (42-30-02 §3). Both
    outcomes are conformance: the checklist is right either way.
    """
    sim = under_way(tree, "core:spe-minor", seed=99)
    while "SEU HAZARD" not in sim.panel.active_messages():
        sim.step(1)
    result = run_procedure(sim, tree.procedures["core:som-42-30-02"])
    assert result.passed, result.failure_summary()
    assert path(result) == [1, 2, 3, 4, 5, 6, 10], "the hand-off path"
    onsets = [e for e in sim.log if e.kind == "fault-onset"]
    assert [e.source for e in onsets] == ["rt.5"]
    assert onsets[0].payload["by"] == "stress"


def test_som_42_30_02_holds_through_a_severe_event(tree: ContentTree) -> None:
    """A severe event outlasts the 600 s hold; the crew stays shed (exit 9)."""
    sim = under_way(tree, "core:spe-transit", seed=1553)
    while "SEU HAZARD" not in sim.panel.active_messages():
        sim.step(1)
    result = run_procedure(sim, tree.procedures["core:som-42-30-02"])
    assert result.passed, result.failure_summary()
    assert path(result) == [1, 2, 3, 4, 5, 9]
