"""Data-device physics: the stuck-dominant fault and the bus jam.

The jam is computed from physical truth each tick (any energized babbling
RT jams its medium); a latch-up holds while powered and clears on power
removal (ata-42-data.md §6). Raw state is fair game in tests/ship.
"""

from __future__ import annotations

import pytest

from ultraspace.content import ContentTree
from ultraspace.ship import Simulation
from ultraspace.ship.devices import BusController, RemoteTerminal
from ultraspace.testing import inject_fault, raw_device


def powered_data_sim(tree: ContentTree) -> Simulation:
    """TB-1 with the battery and all data feeds forced on (testing bypass)."""
    sim = Simulation(tree, "core:tb-1", master_seed=42)
    for device_id in ("ctr.bat1", "tie.a", "cb.e2", "cb.e3", "cb.a2"):
        raw_device(sim, device_id).state = "closed"
    sim.step(5)  # rails settle; BC publishes health
    return sim


def test_stuck_dominant_jams_every_transaction(tree: ContentTree) -> None:
    sim = powered_data_sim(tree)
    bus = sim.data_buses["db.a"]
    assert bus.health_frac() == 1.0
    inject_fault(sim, "rt.12", "stuck_dominant")
    sim.step(1)
    # Both terminals fail while the babbling one is powered — the jam
    # signature, distinct from a one-dark power loss.
    assert not bus.rt(12).answered_last and not bus.rt(5).answered_last
    sim.step(2)
    assert bus.rt(12).failed and bus.rt(5).failed
    assert bus.health_frac() == 0.0


def test_opening_the_babbling_feed_unjams_then_closing_clears(tree: ContentTree) -> None:
    sim = powered_data_sim(tree)
    bus = sim.data_buses["db.a"]
    inject_fault(sim, "rt.12", "stuck_dominant")
    sim.step(3)
    # Feed open: the babbler loses power, the jam dies with it — RT 5 answers.
    raw_device(sim, "cb.a2").state = "open"
    sim.step(1)
    assert bus.rt(5).answered_last
    assert not bus.rt(12).answered_last  # still dark (no power)
    # Feed closed: power removal cleared the latch-up — it answers cleanly.
    raw_device(sim, "cb.a2").state = "closed"
    sim.step(1)
    assert bus.rt(12).answered_last
    rt12 = raw_device(sim, "rt.12")
    assert isinstance(rt12, RemoteTerminal) and not rt12.stuck_dominant
    cleared = [e for e in sim.log if e.kind == "fault-cleared" and e.source == "rt.12"]
    assert cleared and cleared[-1].payload["mode"] == "stuck_dominant"
    assert cleared[-1].payload["by"] == "power-removal"
    sim.step(2)
    assert bus.health_frac() == 1.0


def test_injection_is_logged_and_validated(tree: ContentTree) -> None:
    sim = powered_data_sim(tree)
    inject_fault(sim, "rt.5", "stuck_dominant")
    # Injection goes through the one fault door; only the issuer marks it as
    # an injection (faults.py), so the FDR record is the ordinary onset record.
    injected = [e for e in sim.log if e.kind == "fault-onset" and e.source == "rt.5"]
    assert injected[-1].payload == {"mode": "stuck_dominant", "by": "testing"}
    with pytest.raises(ValueError, match="unknown fault mode"):
        inject_fault(sim, "rt.5", "explode")
    with pytest.raises(ValueError, match="unknown device"):
        inject_fault(sim, "rt.99", "stuck_dominant")
    with pytest.raises(ValueError, match="remote terminal"):
        inject_fault(sim, "bc.a", "stuck_dominant")


def test_bc_publishes_health_only_while_energized(tree: ContentTree) -> None:
    sim = Simulation(tree, "core:tb-1", master_seed=42)
    sim.step(2)
    assert sim.telemetry.read("bc.a") is None  # cold & dark: silent
    for device_id in ("ctr.bat1", "tie.a", "cb.e2", "cb.e3", "cb.a2"):
        raw_device(sim, device_id).state = "closed"
    sim.step(5)
    item = sim.telemetry.read("bc.a")
    assert item is not None and item.value == 1.0 and item.unit == "frac"
    bc = raw_device(sim, "bc.a")
    assert isinstance(bc, BusController) and bc.energized
