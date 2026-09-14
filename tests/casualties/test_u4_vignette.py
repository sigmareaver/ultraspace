"""The U4 story, end to end, through instruments only (simulation-depth.md).

The M2 acceptance vignette: a solar particle event arrives as a number on a
monitor, a terminal latches up on its own, the bus jams, the QRH stabilizes,
the FIM convicts, and MAINT puts a different board in the rack. Nothing here
reads simulation state — every fact comes from a panel, a table, or a refusal,
which is the whole claim this test exists to keep honest.

Emergent, not staged: the casualty is rolled by the stress model against the
scenario's own environment timeline. Seed 1553 fixes which terminal goes and
when (failure-and-repair.md, stress model v1).
"""

from __future__ import annotations

from ultraspace.content import ContentTree
from ultraspace.interaction import Dispatcher, run_procedure
from ultraspace.ship import Simulation
from ultraspace.world import ScenarioRun

SEED = 1553


def under_way(tree: ContentTree) -> Simulation:
    spec = tree.scenarios["core:spe-transit"]
    sim = Simulation(tree, spec.ship, master_seed=SEED)
    ScenarioRun(spec, sim)
    for procedure_id in ("core:som-24-30-01", "core:som-42-30-01"):
        result = run_procedure(sim, tree.procedures[procedure_id])
        assert result.passed, f"{procedure_id}: {result.failure_summary()}"
    return sim


def run_until(sim: Simulation, message: str, limit_ticks: int = 6000) -> int:
    for _ in range(limit_ticks):
        if message in sim.panel.active_messages():
            return sim.clock.tick_index
        sim.step(1)
    raise AssertionError(f"{message!r} never annunciated")


def test_u4_from_the_flux_reading_to_the_functional_test(tree: ContentTree) -> None:
    sim = under_way(tree)
    d = Dispatcher(sim)

    # Act 1 — the weather. The event announces itself as an instrument reading
    # and nothing else; a ship with no monitor gets the casualty unheralded.
    hazard_tick = run_until(sim, "SEU HAZARD")
    assert "p/cm2s" in d.execute_line("data.seu read").text

    # Act 2 — the casualty, rolled rather than scripted.
    failed_tick = run_until(sim, "DATA BUS A FAILED")
    assert failed_tick > hazard_tick, "the warning must precede the casualty"
    onsets = [e for e in sim.log if e.kind == "fault-onset"]
    assert onsets and onsets[0].payload["by"] == "stress"
    suspect = onsets[0].source

    # Act 3 — the QRH stabilizes and repairs nothing.
    qrh = run_procedure(sim, tree.procedures["core:qrh-42-01"])
    assert qrh.passed, qrh.failure_summary()
    assert "NO RESPONSE" in d.execute_line("data.db.a read").text
    assert not sim.panel.master_warning_new, "acknowledged: the panel can warn again"

    # Act 4 — the FIM convicts by cycling feeds, and service comes back.
    fim = run_procedure(sim, tree.procedures["core:fim-42-11"])
    assert fim.passed, fim.failure_summary()
    assert "HEALTHY" in d.execute_line("data.db.a read").text
    assert "DATA BUS A FAILED" not in sim.panel.active_messages()

    # Act 5 — MAINT 42-110-001, worked by hand with the NOTE 2 substitutions
    # (the task is printed for RT 12; the convicted board is whichever latched).
    address = f"data.db.a.{suspect}"
    assert "42-110-001" in d.execute_line(f"{address} records").text
    assert "on shelf" in d.execute_line("maint read").text
    before = d.execute_line(f"{address} read").text

    assert not d.execute_line(f"{address} remove").ok  # live bus: refused
    for line in ("eps cb.e2 open", "eps cb.a2 open", "eps cb.e3 open"):
        assert d.execute_line(line).ok
    sim.step(10)  # the rails bleed

    removed = d.execute_line(f"{address} remove")
    assert removed.ok and "position open" in removed.text
    assert "NOT FITTED" in d.execute_line(f"{address} read").text
    assert suspect in d.execute_line("maint read").text  # the only record of the hole

    installed = d.execute_line(f"{address} install")
    assert installed.ok and "installed from stores" in installed.text
    assert not d.execute_line(f"{address} install").ok  # the position is occupied now

    # Act 6 — the close-out: terminal feeds, then the controller, then a table.
    for line in ("eps cb.a2 close", "eps cb.e3 close", "eps cb.e2 close"):
        assert d.execute_line(line).ok
    sim.step(20)
    after = d.execute_line(f"{address} read").text
    assert after != before, "a swap that returns the same serial is a reseat"
    assert "HEALTHY" in d.execute_line("data.db.a read").text
    assert "NO SPARES" in d.execute_line("maint read").text  # stores are finite
