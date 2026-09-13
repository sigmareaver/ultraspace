"""Stress model v1: hazard arithmetic, rail gating, and stream discipline.

Unit level — these reach for raw device state deliberately (they are testing
the mechanism, not the experience). The player's view of a solar event is
tested in tests/casualties/test_ata42_stress.py.
"""

from __future__ import annotations

import pytest

from ultraspace.content import ContentTree
from ultraspace.content.schemas import HazardSpec
from ultraspace.ship import Simulation
from ultraspace.ship.devices import RemoteTerminal
from ultraspace.ship.environment import CM2_PER_M2, QUIET_FLUX_M2S, Environment
from ultraspace.ship.stress import Hazard
from ultraspace.testing import raw_device


def powered(tree: ContentTree, seed: int = 1553) -> Simulation:
    sim = Simulation(tree, "core:tb-1", master_seed=seed)
    for device_id in ("ctr.bat1", "tie.a", "cb.e2", "cb.e3", "cb.a2"):
        raw_device(sim, device_id).state = "closed"
    sim.step(5)
    return sim


def hazard_of(sim: Simulation, device_id: str) -> Hazard:
    return next(h for h in sim.stress.hazards if h.device.id == device_id)


def test_rate_scales_linearly_with_flux(tree: ContentTree) -> None:
    sim = powered(tree)
    hazard = hazard_of(sim, "rt.12")
    quiet = hazard.rate_per_s(Environment(QUIET_FLUX_M2S))
    assert quiet == pytest.approx(hazard.base_rate_per_s)
    # radiation exponent 1.0: a hundredfold flux is a hundredfold rate.
    loud = hazard.rate_per_s(Environment(100.0 * QUIET_FLUX_M2S))
    assert loud == pytest.approx(100.0 * quiet)


def test_an_unpowered_board_cannot_latch_up(tree: ContentTree) -> None:
    """The teachable of SOM 42-00-00 §10: a parasitic path needs a rail."""
    sim = Simulation(tree, "core:tb-1", master_seed=7)  # cold & dark
    sim.environment.flux_m2s = 1.0e9 * QUIET_FLUX_M2S  # absurd; rate would be 1.0
    hazard = hazard_of(sim, "rt.12")
    assert hazard.needs_rail
    assert hazard.rate_per_s(sim.environment) == 0.0
    sim.step(600)
    rt12 = raw_device(sim, "rt.12")
    assert isinstance(rt12, RemoteTerminal)
    assert not rt12.stuck_dominant


def test_probability_is_capped_below_certainty(tree: ContentTree) -> None:
    """No tick is ever a sure thing — the cap keeps dt out of the physics.

    At a flux where rate x dt would exceed 1, an uncapped model would latch
    every terminal on its first tick, which is dt leaking into the outcome.
    Capped at 0.5, roughly half of a spread of seeds survive tick one.
    """
    survivors = 0
    for seed in range(20):
        sim = powered(tree, seed=seed)
        assert hazard_of(sim, "rt.12").rate_per_s(Environment(1.0e12)) * 0.1 > 1.0
        sim.environment.flux_m2s = 1.0e12
        sim.step(1)
        rt12 = raw_device(sim, "rt.12")
        assert isinstance(rt12, RemoteTerminal)
        survivors += not rt12.stuck_dominant
    assert 4 <= survivors <= 16  # binomial(20, 0.5); an uncapped model gives 0


def test_every_hazard_draws_every_tick(tree: ContentTree) -> None:
    """Determinism (ADR-0002): the roll happens whether or not it can matter.

    A hazard whose rail is dead still consumes its stream, so powering a
    terminal up cannot shift another terminal's future.
    """
    sim = Simulation(tree, "core:tb-1", master_seed=42)  # all rails dead
    before = [sim.rng.stream(f"fault/{h.device.id}/{h.mode}").random() for h in sim.stress.hazards]
    sim.step(3)
    after = [sim.rng.stream(f"fault/{h.device.id}/{h.mode}").random() for h in sim.stress.hazards]
    assert before != after  # streams advanced despite every rate being zero


def test_a_part_without_a_hazard_block_never_fails(tree: ContentTree) -> None:
    sim = Simulation(tree, "core:tb-1", master_seed=1)
    hazard_devices = {h.device.id for h in sim.stress.hazards}
    assert "rt.12" in hazard_devices and "rt.5" in hazard_devices
    # Couplers, harness segments and breakers carry no hazard block yet: their
    # failures are authored, not emergent (failure-and-repair.md, stress v1).
    assert not hazard_devices & {"j1", "j2", "seg.bc-j1", "cb.a2", "bc.a"}


def test_onset_records_its_causal_factors(tree: ContentTree) -> None:
    sim = powered(tree)
    sim.environment.flux_m2s = 1.0e6 * CM2_PER_M2
    sim.step(200)
    onsets = [e for e in sim.log if e.kind == "fault-onset"]
    assert onsets, "a terminal should latch at 1e6 p/cm2s within 20 s"
    payload = onsets[0].payload
    assert payload["by"] == "stress"
    assert payload["mode"] == "stuck_dominant"
    assert payload["flux_cm2s"] == pytest.approx(1.0e6)
    assert float(str(payload["rate_per_s"])) > 0.0


def test_a_hazard_must_have_a_positive_rate() -> None:
    """A zero-rate hazard block is content that says nothing; say nothing instead."""
    with pytest.raises(ValueError):
        HazardSpec(rate_per_h=0.0)
