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
    # Nothing answers at all, so the analyzer and the panel both say FAILED —
    # they must never disagree in front of the crew (ata-31-indicating.md §4).
    assert "db.a FAILED" in table
    panel = d.execute_line("eps read").text
    assert "DATA BUS A FAILED" in panel and "DATA BUS A DEGRADED" in panel


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


def _de_energize_db_a(d: Dispatcher, sim: Simulation) -> None:
    for line in ("eps cb.e2 open", "eps cb.e3 open", "eps cb.a2 open"):
        d.execute_line(line)
        sim.step(1)


def _re_energize_db_a(d: Dispatcher, sim: Simulation) -> None:
    for line in ("eps cb.a2 close", "eps cb.e3 close", "eps cb.e2 close"):
        d.execute_line(line)
        sim.step(1)
    sim.step(2)


def test_dmm_refuses_on_a_live_bus(tree: ContentTree) -> None:
    """Real shop practice: no ohms checks on a live bus (FIM 42-12's NOTE)."""
    sim, d = powered_tb1_with_data(tree)
    result = d.execute_line("data.db.a.j2 read")
    assert not result.ok and "de-energize" in result.text
    _de_energize_db_a(d, sim)
    assert "2.1 ohm" in d.execute_line("data.db.a.j2 read").text


def test_trunk_open_partitions_the_dark_zone_contiguously(tree: ContentTree) -> None:
    """A break between the couplers: everything beyond goes dark from the
    BC's chair, the near side keeps answering — and the DMM points at it."""
    sim, d = powered_tb1_with_data(tree)
    inject_fault(sim, "seg.j1-j2", "open")
    sim.step(4)
    table = d.execute_line("data.db.a read").text
    rt5_row = next(line for line in table.splitlines() if " 5 " in line)
    rt12_row = next(line for line in table.splitlines() if " 12 " in line)
    assert "OK" in rt5_row and "NO RESPONSE" in rt12_row  # contiguous suffix
    _de_energize_db_a(d, sim)
    dmm = d.execute_line("data.db.a.j2 read").text
    assert "seg.j1-j2 (toward j1): OL" in dmm
    assert "stub.j2-rt12 (toward rt.12): 2.1 ohm" in dmm  # stub is innocent
    d.execute_line("data.db.a.seg.j1-j2 repair")
    _re_energize_db_a(d, sim)
    assert "HEALTHY" in d.execute_line("data.db.a read").text


def test_trunk_short_kills_the_bus_and_no_power_cycle_helps(tree: ContentTree) -> None:
    """The other all-dark: like a jam, but cycling every feed restores
    nothing — that is the tell — and the trunk reads ~0 ohm."""
    sim, d = powered_tb1_with_data(tree)
    inject_fault(sim, "seg.bc-j1", "short")
    sim.step(4)
    assert (
        len(
            [
                line
                for line in d.execute_line("data.db.a read").text.splitlines()
                if "NO RESPONSE" in line
            ]
        )
        == 2
    )
    # The 42-11 cure, honestly attempted: cycle each feed. Nothing.
    for line in ("eps cb.a2 open", "eps cb.a2 close", "eps cb.e3 open", "eps cb.e3 close"):
        d.execute_line(line)
        sim.step(2)
    assert "db.a FAILED" in d.execute_line("data.db.a read").text
    _de_energize_db_a(d, sim)
    dmm = d.execute_line("data.db.a.j1 read").text
    assert "seg.bc-j1 (toward bc.a): 0.0 ohm" in dmm
    d.execute_line("data.db.a.seg.bc-j1 repair")
    _re_energize_db_a(d, sim)
    assert "HEALTHY" in d.execute_line("data.db.a read").text


def test_stub_short_is_contained_and_the_dmm_says_where(tree: ContentTree) -> None:
    """Transformer coupling earns its keep: a shorted stub takes down only
    its own terminal, and the coupler tap reads ~0 while the trunk reads 78."""
    sim, d = powered_tb1_with_data(tree)
    inject_fault(sim, "stub.j2-rt12", "short")
    sim.step(4)
    table = d.execute_line("data.db.a read").text
    rt5_row = next(line for line in table.splitlines() if " 5 " in line)
    rt12_row = next(line for line in table.splitlines() if " 12 " in line)
    assert "OK" in rt5_row and "NO RESPONSE" in rt12_row
    _de_energize_db_a(d, sim)
    dmm = d.execute_line("data.db.a.j2 read").text
    assert "stub.j2-rt12 (toward rt.12): 0.0 ohm" in dmm
    assert "seg.j1-j2 (toward j1): 78.0 ohm" in dmm
    d.execute_line("data.db.a.stub.j2-rt12 repair")
    _re_energize_db_a(d, sim)
    assert "HEALTHY" in d.execute_line("data.db.a read").text


def test_stub_open_and_dead_module_differ_only_in_the_stub(tree: ContentTree) -> None:
    """Same symptom (one terminal dark, powered), same table — the coupler
    tap splits them: OL for the broken stub, 2.1 ohm for the dead board."""
    sim, d = powered_tb1_with_data(tree)
    inject_fault(sim, "stub.j1-rt5", "open")
    sim.step(4)
    table = d.execute_line("data.db.a read").text
    rt5_row = next(line for line in table.splitlines() if " 5 " in line)
    rt12_row = next(line for line in table.splitlines() if " 12 " in line)
    assert "NO RESPONSE" in rt5_row and "OK" in rt12_row
    _de_energize_db_a(d, sim)
    dmm = d.execute_line("data.db.a.j1 read").text
    assert "stub.j1-rt5 (toward rt.5): OL" in dmm
    d.execute_line("data.db.a.stub.j1-rt5 repair")
    _re_energize_db_a(d, sim)
    assert "HEALTHY" in d.execute_line("data.db.a read").text

    inject_fault(sim, "rt.12", "dead")
    sim.step(4)
    assert "NO RESPONSE" in next(
        line for line in d.execute_line("data.db.a read").text.splitlines() if " 12 " in line
    )
    _de_energize_db_a(d, sim)
    dmm = d.execute_line("data.db.a.j2 read").text
    assert "stub.j2-rt12 (toward rt.12): 2.1 ohm" in dmm  # stub good: the board
    d.execute_line("data.db.a.rt.12 repair")
    _re_energize_db_a(d, sim)
    assert "HEALTHY" in d.execute_line("data.db.a read").text


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


def test_replacing_a_sound_part_gives_the_player_no_free_verdict(tree: ContentTree) -> None:
    """A refusal that said "nothing to repair" would tell the player the part
    is good — a verdict no DMM reading gave them (No God View). Replacing a
    sound run succeeds and reads exactly like replacing a broken one; only
    re-energizing and reading the table settles it.
    """
    sim, d = powered_tb1_with_data(tree)
    inject_fault(sim, "seg.j1-j2", "short")
    sim.step(4)
    _de_energize_db_a(d, sim)

    innocent = d.execute_line("data.db.a.stub.j1-rt5 repair")  # a sound stub
    guilty = d.execute_line("data.db.a.seg.j1-j2 repair")  # the actual short
    assert innocent.ok and guilty.ok
    assert innocent.text.split(":", 1)[1] == guilty.text.split(":", 1)[1]

    _re_energize_db_a(d, sim)
    assert "HEALTHY" in d.execute_line("data.db.a read").text


def _carried(d: Dispatcher, address: str) -> str:
    return d.execute_line(f"{address} read").text


def test_a_dark_carrier_freezes_its_reading_while_the_load_is_fine(tree: ContentTree) -> None:
    """The U4 step-3 vignette (simulation-depth.md): the *display* is what is
    wrong. RT 12 goes dark, the cabin ammeter it carries stops being refreshed
    and marks itself stale — while the cabin load keeps drawing, BUS A stays
    at voltage, and the avionics ammeter on the other terminal stays live.
    """
    sim, d = powered_tb1_with_data(tree)
    assert "? STALE" not in _carried(d, "eps.load.cabin")
    before = _carried(d, "eps.load.cabin")

    d.execute_line("eps cb.a2 open")  # RT 12 loses its feed; load.cabin does not
    sim.step_s(3.0)

    frozen = _carried(d, "eps.load.cabin")
    assert "? STALE" in frozen and "age 3.1 s" in frozen
    # The value did not change — it is the last reading that got through, and
    # it is still roughly right, which is exactly what makes it dangerous.
    assert frozen.split("src:")[0] == before.split("src:")[0]

    # Everything that is not carried by RT 12 is untouched: the twin on RT 5,
    # the bus the cabin load sits on, and the load's own breaker.
    assert "? STALE" not in _carried(d, "eps.load.avionics")
    assert "? STALE" not in _carried(d, "eps.bus.a")
    assert "cb.a1: CLOSED" in d.execute_line("eps cb.a1 read").text

    # And it comes back when the terminal does.
    d.execute_line("eps cb.a2 close")
    sim.step_s(1.5)
    assert "? STALE" not in _carried(d, "eps.load.cabin")


def test_a_stale_source_takes_its_caution_quiet(tree: ContentTree) -> None:
    """SOM 42-00-00 §6/§8: silence is not health. With the controller dark
    there is no health report to monitor, so DATA BUS A DEGRADED must drop —
    including a caution it was already holding — and every carried reading
    must say stale rather than pretend to be current.
    """
    sim, d = powered_tb1_with_data(tree)
    d.execute_line("eps cb.a2 open")  # RT 12 dark: the lamp latches on
    sim.step_s(1.0)
    assert "DATA BUS A DEGRADED" in d.execute_line("eps read").text

    d.execute_line("eps cb.e2 open")  # now the controller itself
    sim.step_s(3.0)

    assert "NO DATA (bus controller unpowered)" in d.execute_line("data.db.a read").text
    assert "DATA BUS A DEGRADED" not in d.execute_line("eps read").text
    for address in ("eps.load.cabin", "eps.load.avionics"):
        assert "? STALE" in _carried(d, address)
    # The panel-wired instruments never blink: that asymmetry is the whole
    # point of keeping them off the bus.
    assert "? STALE" not in _carried(d, "eps.bus.e")


def test_a_transport_casualty_leaves_every_other_instrument_untouched(tree: ContentTree) -> None:
    """Losing a reading must cost exactly that reading. A stub break is
    electrically inert — the harness carries no load — so every panel-wired
    instrument has to read identically, tick for tick, against the same seed.
    A transport fault that perturbed the rest of the panel would be a
    determinism leak dressed up as a casualty.
    """

    def bus_readings(*, break_the_stub: bool) -> list[str]:
        sim, d = powered_tb1_with_data(tree)
        if break_the_stub:
            inject_fault(sim, "stub.j2-rt12", "open")
        readings = []
        for _ in range(20):
            sim.step(1)
            for address in ("eps.bus.e", "eps.bus.a", "eps.bat.1"):
                readings.append(d.execute_line(f"{address} read").text.split("src:")[0])
        return readings

    healthy = bus_readings(break_the_stub=False)
    broken = bus_readings(break_the_stub=True)
    assert healthy == broken
