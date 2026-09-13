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

COVERED = {"core:fim-42-11", "core:fim-42-12"}


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


# -- FIM 42-12: the harness tree, against each injected medium/module fault --
#
# The documented tree de-energizes the bus (with a bleed wait — an open
# breaker is not a dead rail) and lets the DMM decide. Each fault must walk
# to its own verdict; the step list is the trace. Expected paths cite the
# procedure's branch steps; editing the FIM without understanding it fails
# here — that is the point of the suite.

FIM_42_12_PATHS: dict[tuple[str, str], list[int]] = {
    # -- one terminal dark: the stub tree, then the coupler, then the board --
    ("stub.j2-rt12", "open"): [1, 2, 4, 5, 6, 7, 8, 9, 44, 45, 46, 47],
    ("stub.j2-rt12", "short"): [1, 2, 4, 5, 6, 7, 8, 10, 9, 44, 45, 46, 47],
    ("stub.j1-rt5", "open"): [1, 2, 3, 16, 17, 18, 19, 20, 21, 44, 45, 46, 47],
    ("stub.j1-rt5", "short"): [1, 2, 3, 16, 17, 18, 19, 20, 22, 21, 44, 45, 46, 47],
    ("seg.j1-j2", "open"): [1, 2, 4, 5, 6, 7, 8, 10, 11, 12, 44, 45, 46, 47],
    # An open coupler reads clean at itself: J2's break shows as OL from J1 (13).
    ("j2", "open"): [1, 2, 4, 5, 6, 7, 8, 10, 11, 13, 14, 44, 45, 46, 47],
    # Same walk, everything clean — only then is the module convicted (15/23).
    ("rt.12", "dead"): [1, 2, 4, 5, 6, 7, 8, 10, 11, 13, 15, 44, 45, 46, 47],
    ("rt.5", "dead"): [1, 2, 3, 16, 17, 18, 19, 20, 22, 23, 44, 45, 46, 47],
    # -- every terminal dark: the trunk tree --
    ("seg.bc-j1", "open"): [1, 24, 25, 26, 27, 28, 29, 44, 45, 46, 47],
    ("seg.bc-j1", "short"): [1, 24, 25, 26, 27, 28, 30, 31, 29, 44, 45, 46, 47],
    # ~0 both ways at one probe point is the coupler itself (31 → 32).
    ("j1", "short"): [1, 24, 25, 26, 27, 28, 30, 31, 32, 44, 45, 46, 47],
    # Clean both ways at J1: its own break is only visible from J2 (49 → 50).
    ("j1", "open"): [1, 24, 25, 26, 27, 28, 30, 33, 49, 50, 44, 45, 46, 47],
    # The interval ladder: ohms cannot split "run" from "coupler at its end",
    # so the run goes first and the verify (37) decides. Short run: done there.
    ("seg.j1-j2", "short"): [1, 24, 25, 26, 27, 28, 30, 33, 34, 35, 36, 37],
    # Shorted J2: the run swap does not restore the bus, and the ladder walks
    # back out to the coupler — the whole point of having the ladder.
    ("j2", "short"): [
        *[1, 24, 25, 26, 27, 28, 30, 33, 34, 35, 36, 37],
        *[38, 39, 40, 41, 42, 43, 44, 45, 46, 47],
    ],
}

#: Fault modes the harness tree owns. `stuck_dominant` belongs to FIM 42-11.
_HARNESS_MODES = {"junction": ("open", "short"), "harness_seg": ("open", "short"), "rt": ("dead",)}


def test_every_injectable_harness_fault_has_a_documented_path(tree: ContentTree) -> None:
    """Coverage canary: fitting new harness hardware (or a new fault mode)
    without a verdict path in the tree fails the build. The gap this closes
    was real — coupler faults shipped unwalked, and the tree convicted
    innocent parts for them (review, 2026-09-12).
    """
    ship = tree.ships["core:tb-1"]
    expected = {
        (device.id, mode)
        for device in ship.devices
        if (part := tree.parts[device.part]).behavior in _HARNESS_MODES
        for mode in _HARNESS_MODES[part.behavior]
    }
    assert set(FIM_42_12_PATHS) == expected


def test_fim_42_12_convicts_each_harness_fault(tree: ContentTree) -> None:
    for (target, mode), expected_path in FIM_42_12_PATHS.items():
        sim = Simulation(tree, "core:tb-1", master_seed=42)
        for proc_id in ("core:som-24-30-01", "core:som-42-30-01"):
            result = run_procedure(sim, tree.procedures[proc_id])
            assert result.passed, (target, result.failure_summary())
        inject_fault(sim, target, mode)
        sim.step(4)  # the symptom declares
        result = run_procedure(sim, tree.procedures["core:fim-42-12"])
        path = [r.step for r in result.steps]
        assert result.passed, f"{target}/{mode}: {result.failure_summary()}"
        assert path == expected_path, f"{target}/{mode}: walked {path}"
        assert "MASTER CAUTION: clear" in sim.summary(), (target, mode)  # the bus is whole


def test_fim_42_12_rejects_a_live_bus_for_ohms_checks(tree: ContentTree) -> None:
    """The interlock the NOTE teaches: probing a live bus is refused."""
    sim = Simulation(tree, "core:tb-1", master_seed=42)
    for proc_id in ("core:som-24-30-01", "core:som-42-30-01"):
        result = run_procedure(sim, tree.procedures[proc_id])
        assert result.passed, result.failure_summary()
    d = Dispatcher(sim)
    refusal = d.execute_line("data.db.a.j1 read")
    assert not refusal.ok and "de-energize" in refusal.text
