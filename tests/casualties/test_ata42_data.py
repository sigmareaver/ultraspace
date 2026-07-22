"""Data-bus casualty behavior, experienced strictly like a player.

Rule (testing.md class 5): `inject_fault` is the only permitted
`ultraspace.testing` import here — it inserts the fault; every assertion
then reads telemetry, SCL responses, or panel observation, never raw state.
Scope (ata-42-data.md §6): consequence physics and the injected
stuck-dominant — the BC's view, never the root cause.
"""

from __future__ import annotations

from ultraspace.content import ContentTree
from ultraspace.interaction import Dispatcher, run_procedure
from ultraspace.ship import Simulation
from ultraspace.testing import inject_fault


def powered_tb1_with_data(tree: ContentTree, seed: int = 42) -> tuple[Simulation, Dispatcher]:
    """EPS per SOM 24-30-01, then data hardware on line (SOM 42-30-01 order:
    both RT feeds before the BC, so the bus comes up HEALTHY)."""
    sim = Simulation(tree, "core:tb-1", master_seed=seed)
    result = run_procedure(sim, tree.procedures["core:som-24-30-01"])
    assert result.passed, result.failure_summary()
    d = Dispatcher(sim)
    d.execute_line("eps cb.a2 close")
    d.execute_line("eps cb.e3 close")
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


def test_stuck_dominant_shows_the_jam_signature_not_one_dark(tree: ContentTree) -> None:
    """The U4 fault, as the player meets it: *every* terminal dark at once —
    the analyzer's split from a one-terminal power loss (42-00-00 §3)."""
    sim, d = powered_tb1_with_data(tree)
    inject_fault(sim, "rt.12", "stuck_dominant")
    sim.step(4)  # the BC misses, then declares, both terminals
    table = d.execute_line("data.db.a read").text
    rt_rows = [line for line in table.splitlines() if "NO RESPONSE" in line]
    assert len(rt_rows) == 2  # RT 5 and RT 12 both — the jam signature
    assert "DEGRADED" in table
    assert "DATA BUS A DEGRADED" in d.execute_line("eps read").text


def test_power_cycling_the_babbling_terminal_restores_the_bus(tree: ContentTree) -> None:
    """FIM 42-11's cure, experienced by hand: cycle the suspect's feed; the
    latch-up clears on power removal — the error counters keep the evidence."""
    sim, d = powered_tb1_with_data(tree)
    inject_fault(sim, "rt.12", "stuck_dominant")
    sim.step(4)
    # Cycle the suspect's feed: OPEN — the jam dies with the babbler's power.
    d.execute_line("eps cb.a2 open")
    sim.step(2)
    table = d.execute_line("data.db.a read").text
    rt5_row = next(line for line in table.splitlines() if " 5 " in line)
    assert "OK" in rt5_row  # RT 5 answers again while RT 12 is dark
    # CLOSE — the terminal is back, and the latch-up is gone with the outage.
    d.execute_line("eps cb.a2 close")
    sim.step(2)
    table = d.execute_line("data.db.a read").text
    rt12_row = next(line for line in table.splitlines() if " 12 " in line)
    assert "OK" in rt12_row
    assert "DATA BUS A DEGRADED" not in d.execute_line("eps read").text
    # Evidence remains: both terminals carry error counts from the episode.
    assert " 0" not in rt12_row.split("OK")[-1]


def test_bc_up_before_rt_feeds_annunciates_then_recovers(tree: ContentTree) -> None:
    """Wrong order from SOM 42-30-01's NOTE: BC on with dark RTs degrades
    the bus within three polls — the honest cost of skipping the note."""
    sim = Simulation(tree, "core:tb-1", master_seed=42)
    result = run_procedure(sim, tree.procedures["core:som-24-30-01"])
    assert result.passed, result.failure_summary()
    d = Dispatcher(sim)
    d.execute_line("eps cb.e2 close")  # BC first — both RT feeds still open
    sim.step(4)  # 3 misses to FAILED + the annunciator scan
    assert "DATA BUS A DEGRADED" in d.execute_line("eps read").text
    d.execute_line("eps cb.a2 close")
    d.execute_line("eps cb.e3 close")
    sim.step(2)
    assert "DATA BUS A DEGRADED" not in d.execute_line("eps read").text
