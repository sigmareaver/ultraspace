"""Data-bus casualty behavior, experienced strictly like a player.

Rule (testing.md class 5): telemetry, SCL responses, and panel observation
only — no `ultraspace.testing` imports in this directory, ever.
Increment-1 scope (ata-42-data.md §6): consequence physics only — the BC's
view of a power loss, never the root cause.
"""

from __future__ import annotations

from ultraspace.content import ContentTree
from ultraspace.interaction import Dispatcher, run_procedure
from ultraspace.ship import Simulation


def powered_tb1_with_data(tree: ContentTree, seed: int = 42) -> tuple[Simulation, Dispatcher]:
    """EPS per SOM 24-30-01, then data hardware on line (SOM 42-30-01 order:
    the RT feed before the BC, so the bus comes up HEALTHY)."""
    sim = Simulation(tree, "core:tb-1", master_seed=seed)
    result = run_procedure(sim, tree.procedures["core:som-24-30-01"])
    assert result.passed, result.failure_summary()
    d = Dispatcher(sim)
    d.execute_line("eps cb.a2 close")
    sim.step(1)
    d.execute_line("eps cb.e2 close")
    sim.step(2)
    return sim, d


def test_rt_power_loss_degrades_bus_and_annunciates(tree: ContentTree) -> None:
    sim, d = powered_tb1_with_data(tree)
    assert "HEALTHY" in d.execute_line("data.db.a read").text

    # Kill the RT feed: the BC scores misses, declares at the third, and the
    # lamp follows the BC's declaration — not the breaker.
    d.execute_line("eps cb.a2 open")
    sim.step(1)
    early = d.execute_line("data.db.a read").text
    assert "NO RESPONSE (1x)" in early
    assert "DATA BUS A DEGRADED" not in d.execute_line("eps read").text
    sim.step(3)  # misses 2, 3, 4: FAILED at 3 consecutive
    late = d.execute_line("data.db.a read").text
    assert "NO RESPONSE (4x)" in late and "DEGRADED" in late
    summary = d.execute_line("eps read").text
    assert "DATA BUS A DEGRADED" in summary

    # Restore: the first good reply clears the declaration and the lamp —
    # but the error counter keeps the evidence.
    d.execute_line("eps cb.a2 close")
    sim.step(2)
    recovered = d.execute_line("data.db.a read").text
    rt_row = next(line for line in recovered.splitlines() if " 12 " in line)
    assert "OK" in rt_row and rt_row.rstrip().endswith("4")
    assert "DATA BUS A DEGRADED" not in d.execute_line("eps read").text


def test_losing_the_bc_silences_the_bus_honestly(tree: ContentTree) -> None:
    sim, d = powered_tb1_with_data(tree)
    d.execute_line("eps cb.e2 open")
    sim.step(2)
    # A dead instrument is silent, not lying: NO DATA, and no annunciator.
    assert "NO DATA" in d.execute_line("data.db.a read").text
    assert "NO DATA" in d.execute_line("data read").text
    assert "DATA BUS A DEGRADED" not in d.execute_line("eps read").text
    assert "MASTER CAUTION: clear" in d.execute_line("eps read").text


def test_bc_up_before_rt_feed_annunciates_then_recovers(tree: ContentTree) -> None:
    """Wrong order from SOM 42-30-01's NOTE: BC on with a dark RT degrades
    the bus within three polls — the honest cost of skipping the note."""
    sim = Simulation(tree, "core:tb-1", master_seed=42)
    result = run_procedure(sim, tree.procedures["core:som-24-30-01"])
    assert result.passed, result.failure_summary()
    d = Dispatcher(sim)
    d.execute_line("eps cb.e2 close")  # BC first — the RT feed is still open
    sim.step(4)  # 3 misses to FAILED + the annunciator scan
    assert "DATA BUS A DEGRADED" in d.execute_line("eps read").text
    d.execute_line("eps cb.a2 close")
    sim.step(2)
    assert "DATA BUS A DEGRADED" not in d.execute_line("eps read").text
