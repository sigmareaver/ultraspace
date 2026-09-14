"""Manual conformance (ADR-0005): QRH Ch 42 checklists must pass headlessly.

The QRH stabilizes; it does not diagnose (ata-31-indicating.md §7). These
tests hold it to that: the checklist must be walkable in the state its entry
condition describes, and must leave by the door it promises rather than by
starting a repair.
"""

from __future__ import annotations

from ultraspace.content import ContentTree
from ultraspace.interaction.procedures import ProcedureResult, run_procedure
from ultraspace.ship import Simulation
from ultraspace.testing import inject_fault, raw_device

COVERED = {"core:qrh-42-01"}


def jammed(tree: ContentTree) -> Simulation:
    """TB-1 on the bus with a babbling terminal: every RT dark, bus FAILED."""
    sim = Simulation(tree, "core:tb-1", master_seed=42)
    up = run_procedure(sim, tree.procedures["core:som-24-30-01"])
    assert up.passed, up.failure_summary()
    checkout = run_procedure(sim, tree.procedures["core:som-42-30-01"])
    assert checkout.passed, checkout.failure_summary()
    inject_fault(sim, "rt.12", "stuck_dominant")
    sim.step(5)
    return sim


def path(result: ProcedureResult) -> list[int]:
    return [s.step for s in result.steps]


def test_qrh_42_01_conforms_against_a_jammed_bus(tree: ContentTree) -> None:
    sim = jammed(tree)
    assert "DATA BUS A FAILED" in sim.panel.active_messages()
    result = run_procedure(sim, tree.procedures["core:qrh-42-01"])
    assert result.passed, result.failure_summary()
    assert path(result) == [1, 2, 3, 4, 5, 6]


def test_qrh_42_01_acknowledges_before_anything_else(tree: ContentTree) -> None:
    """Step 1 is the whole reason the panel can still warn you at step 6."""
    sim = jammed(tree)
    new_before = sim.panel.master_warning_new
    assert new_before
    run_procedure(sim, tree.procedures["core:qrh-42-01"])
    lit_after, new_after = sim.panel.master_warning, sim.panel.master_warning_new
    assert lit_after  # still lit: acknowledging is not clearing
    assert not new_after  # but steady, and able to flash again
    acks = [e for e in sim.log if e.kind == "annunciator-ack"]
    assert acks
    messages = acks[0].payload["messages"]
    assert isinstance(messages, list) and "DATA BUS A FAILED" in messages


def test_qrh_42_01_leaves_by_the_controller_door_when_the_bc_is_dark(
    tree: ContentTree,
) -> None:
    """A dark controller and a failed bus sound identical and are not the same work."""
    sim = jammed(tree)
    raw_device(sim, "cb.e2").state = "open"  # pull the controller feed
    sim.step(15)
    result = run_procedure(sim, tree.procedures["core:qrh-42-01"])
    assert result.passed, result.failure_summary()
    assert path(result) == [1, 2, 7]


def test_qrh_42_01_does_not_repair_anything(tree: ContentTree) -> None:
    """Stabilization, not diagnosis: the bus is exactly as broken at the end."""
    sim = jammed(tree)
    before = sim.execute("data.db.a", "read", set()).text
    run_procedure(sim, tree.procedures["core:qrh-42-01"])
    assert "NO RESPONSE" in sim.execute("data.db.a", "read", set()).text
    assert "NO RESPONSE" in before
