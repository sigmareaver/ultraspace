"""Casualty: a solar particle event, experienced through the instruments.

Nothing is injected here — the only input is a scenario, and every assertion
below is something a player could have read off the panel or typed at the
teletype. The fault is emergent; the crew's warning is the flux monitor and
the clock (testing.md class 5, the hardest version of it).
"""

from __future__ import annotations

from ultraspace.content import ContentTree
from ultraspace.interaction import Dispatcher, run_procedure
from ultraspace.ship import Simulation
from ultraspace.world import ScenarioRun


def under_way(tree: ContentTree, scenario_id: str, seed: int) -> tuple[Simulation, Dispatcher]:
    spec = tree.scenarios[scenario_id]
    sim = Simulation(tree, spec.ship, master_seed=seed)
    ScenarioRun(spec, sim)
    for procedure_id in ("core:som-24-30-01", "core:som-42-30-01"):
        assert run_procedure(sim, tree.procedures[procedure_id]).passed
    return sim, Dispatcher(sim)


def test_the_crew_is_warned_before_anything_breaks(tree: ContentTree) -> None:
    """The monitor leads the casualty — the whole reason 42-30-02 is actionable."""
    sim, dispatcher = under_way(tree, "core:spe-transit", seed=1553)
    hazard_tick = None
    degraded_tick = None
    while sim.clock.tick_index < 6000:  # ten minutes of transit
        sim.step(1)
        active = sim.panel.active_messages()
        if hazard_tick is None and "SEU HAZARD" in active:
            hazard_tick = sim.clock.tick_index
        if degraded_tick is None and "DATA BUS A DEGRADED" in active:
            degraded_tick = sim.clock.tick_index
    assert hazard_tick is not None, "the event must annunciate"
    assert degraded_tick is not None, "a terminal must latch up at this flux"
    warning_s = (degraded_tick - hazard_tick) / 10
    assert warning_s > 120, f"only {warning_s:.0f} s of warning — 42-30-02 needs minutes"
    # And the reading the checklist gates on is on the teletype, in its own units.
    assert "p/cm2s" in dispatcher.execute_line("data.seu read").text


def test_the_bus_table_alone_cannot_tell_you_it_was_the_weather(tree: ContentTree) -> None:
    """FIM 42-11 §4: the symptom is identical; only the flux reading separates them."""
    sim, dispatcher = under_way(tree, "core:spe-transit", seed=1553)
    while "DATA BUS A DEGRADED" not in sim.panel.active_messages():
        sim.step(1)
    table = dispatcher.execute_line("data.db.a read").text
    assert "NO RESPONSE" in table
    assert "flux" not in table.lower() and "seu" not in table.lower()
    flux = dispatcher.execute_line("data.seu read").text
    assert float(flux.split()[1]) > 100.0  # the crew's only evidence of cause


def test_a_dark_ship_rides_out_the_same_event_untouched(tree: ContentTree) -> None:
    """An unpowered board cannot latch up (42-00-00 §10), at any flux."""
    spec = tree.scenarios["core:spe-transit"]
    sim = Simulation(tree, spec.ship, master_seed=1553)  # cold & dark, never powered
    ScenarioRun(spec, sim)
    sim.step(3000)  # the peak of the event
    assert sim.panel.active_messages() == ["SEU HAZARD"]  # the monitor still sees it
    sim.step(6000)
    assert [e for e in sim.log if e.kind == "fault-onset"] == []
    assert sim.panel.active_messages() == []  # event over, ship untouched
