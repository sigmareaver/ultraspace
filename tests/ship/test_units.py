"""Serialized units, finite stores, and the swap verbs (MAINT v1).

Unit level. The crew's experience of the same machinery — a verdict, a board
out, a board in, a functional test — is in tests/conformance/test_maint_ch42.py
and tests/casualties/test_u4_vignette.py.
"""

from __future__ import annotations

from ultraspace.content import ContentTree, assign_serials
from ultraspace.interaction import Dispatcher, run_procedure
from ultraspace.ship import Simulation
from ultraspace.ship.devices import RemoteTerminal
from ultraspace.testing import inject_fault, raw_device

RT_PART = "core:rt-1553"


def on_the_bus(tree: ContentTree) -> tuple[Simulation, Dispatcher]:
    sim = Simulation(tree, "core:tb-1", master_seed=42)
    for proc_id in ("core:som-24-30-01", "core:som-42-30-01"):
        result = run_procedure(sim, tree.procedures[proc_id])
        assert result.passed, result.failure_summary()
    return sim, Dispatcher(sim)


def de_energized(tree: ContentTree) -> tuple[Simulation, Dispatcher]:
    sim, d = on_the_bus(tree)
    for line in ("eps cb.e2 open", "eps cb.a2 open", "eps cb.e3 open"):
        d.execute_line(line)
    sim.step(5)
    return sim, d


def test_serials_follow_blueprint_order_and_spares_continue_it(tree: ContentTree) -> None:
    """Identity is derived, so stocking a part costs one content line."""
    ship = tree.ships["core:tb-1"]
    serials = assign_serials(ship, tree.parts)
    assert serials.fitted["rt.12"] == "42-110-001/0001"  # rt.12 is fitted first
    assert serials.fitted["rt.5"] == "42-110-001/0002"
    assert serials.stores[RT_PART] == ["42-110-001/0003"]


def test_every_ship_serializes_every_fitted_device(tree: ContentTree) -> None:
    for ship_id in ("core:tb-1", "core:uev-kestrel"):
        ship = tree.ships[ship_id]
        serials = assign_serials(ship, tree.parts)
        assert len(serials.fitted) == len(ship.devices)
        assert len(set(serials.fitted.values())) == len(ship.devices), "serials are unique"


def test_an_empty_position_draws_nothing_and_answers_nothing(tree: ContentTree) -> None:
    sim, d = de_energized(tree)
    assert d.execute_line("data.db.a.rt.12 remove").ok
    for line in ("eps cb.a2 close", "eps cb.e3 close", "eps cb.e2 close"):
        d.execute_line(line)
    sim.step(10)
    empty = raw_device(sim, "rt.12")
    assert isinstance(empty, RemoteTerminal)
    assert empty.last_i_a == 0.0 and not empty.energized  # no box, no load
    table = d.execute_line("data.db.a read").text
    assert "NO RESPONSE" in table, "the controller cannot see an empty rack"
    assert "NOT FITTED" not in table, "and must not pretend it can (ata-42 §6)"
    assert "NOT FITTED" in d.execute_line("data.db.a.rt.12 read").text


def test_pulling_the_babbling_terminal_cures_the_bus(tree: ContentTree) -> None:
    """A real repair and a real trap: the bus is whole, the function is gone."""
    sim, d = on_the_bus(tree)
    inject_fault(sim, "rt.12", "stuck_dominant")
    sim.step(4)
    assert "DATA BUS A FAILED" in sim.panel.active_messages()
    for line in ("eps cb.e2 open", "eps cb.a2 open", "eps cb.e3 open"):
        d.execute_line(line)
    sim.step(5)
    assert d.execute_line("data.db.a.rt.12 remove").ok
    for line in ("eps cb.a2 close", "eps cb.e3 close", "eps cb.e2 close"):
        d.execute_line(line)
    sim.step(10)
    assert "5    OK" in d.execute_line("data.db.a read").text  # traffic passes again
    assert "DATA BUS A DEGRADED" in sim.panel.active_messages()  # at the cost of RT 12


def test_the_interlock_and_the_position_state_gate_both_verbs(tree: ContentTree) -> None:
    sim, d = on_the_bus(tree)
    live = d.execute_line("data.db.a.rt.12 remove")
    assert not live.ok and "MAINT 42-110-001" in live.text
    for line in ("eps cb.e2 open", "eps cb.a2 open", "eps cb.e3 open"):
        d.execute_line(line)
    sim.step(5)
    occupied = d.execute_line("data.db.a.rt.12 install")
    assert not occupied.ok and "occupied" in occupied.text
    assert d.execute_line("data.db.a.rt.12 remove").ok
    twice = d.execute_line("data.db.a.rt.12 remove")
    assert not twice.ok and "nothing to remove" in twice.text


def test_an_empty_shelf_refuses_and_cites_the_catalog(tree: ContentTree) -> None:
    sim, d = de_energized(tree)
    d.execute_line("data.db.a.rt.12 remove")
    assert d.execute_line("data.db.a.rt.12 install").ok  # the one spare
    d.execute_line("data.db.a.rt.5 remove")
    refusal = d.execute_line("data.db.a.rt.5 install")
    assert not refusal.ok
    assert "no 42-110-001 in stores" in refusal.text and "IPC" in refusal.text
    assert sim.units.on_shelf(RT_PART) == 0


def test_the_fault_comes_off_with_the_board_and_stays_off_the_readout(
    tree: ContentTree,
) -> None:
    """The FDR keeps the truth; no player surface does (MAINT 00-00 §4)."""
    sim, d = on_the_bus(tree)
    inject_fault(sim, "rt.12", "dead")
    sim.step(4)
    for line in ("eps cb.e2 open", "eps cb.a2 open", "eps cb.e3 open"):
        d.execute_line(line)
    sim.step(5)
    removed = d.execute_line("data.db.a.rt.12 remove")
    position = raw_device(sim, "rt.12")
    assert isinstance(position, RemoteTerminal)
    assert not position.dead, "the position is clean; the box is not"
    unit = sim.units.bench[-1]
    assert unit.fault_found
    events = [e for e in sim.log if e.kind == "unit-removed"]
    assert events and events[-1].payload == {
        "serial": unit.serial,
        "part_number": "42-110-001",
        "fault_found": True,
    }
    surfaces = removed.text + d.execute_line("maint read").text
    assert "fault" not in surfaces.lower() and "dead" not in surfaces.lower()


def test_hours_accrue_on_the_rail_and_nowhere_else(tree: ContentTree) -> None:
    sim, d = on_the_bus(tree)
    sim.step(100)  # 10 s powered
    records = d.execute_line("data.db.a.rt.12 records").text
    assert "hours 0.00 h" in records  # 10 s rounds to two decimals of an hour
    unit = sim.units.unit_at("rt.12")
    assert unit is not None and unit.hours_s > 9.0
    powered_s = unit.hours_s
    d.execute_line("eps cb.a2 open")
    sim.step(100)
    assert unit.hours_s == powered_s, "a dark box ages, but it does not run"
    assert "hours not tracked" in d.execute_line("eps.cb.a2 records").text


def test_records_answer_at_every_address_including_instruments(tree: ContentTree) -> None:
    """Every box has a nameplate, verbs or no verbs (MAINT 00-00 §1)."""
    sim, d = on_the_bus(tree)
    xducer = d.execute_line("data.seu records").text
    assert "42-160-001/0001" in xducer and "hours not tracked" in xducer
    # A shared address lists every box on it, the way `read` does.
    shared = sim.execute("eps.bat.1", "records", set()).text
    assert "24-150-002/0001" in shared and "24-150-003/0001" in shared


def test_the_stores_sheet_is_the_only_record_of_an_open_position(tree: ContentTree) -> None:
    _, d = de_energized(tree)
    quiet = d.execute_line("maint read").text
    assert "(nothing removed)" in quiet and "(none)" in quiet
    d.execute_line("data.db.a.rt.5 remove")
    sheet = d.execute_line("maint read").text
    assert "not bench-tested" in sheet  # on the bench, untested, and staying that way
    assert "rt.5  NOT FITTED since MET" in sheet
    assert "1 on shelf" in sheet
