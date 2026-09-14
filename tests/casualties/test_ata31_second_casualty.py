"""Casualty: the second thing to go wrong, under a lamp that is already lit.

This is the 2026-09-13 playtest finding, frozen. The crew shed a terminal on
purpose, which lit DATA BUS A DEGRADED; four minutes later the terminal they
could not shed latched up and the panel said nothing, because a lamp does not
light twice. Every assertion here is something the crew could read.
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


def test_a_casualty_under_an_acknowledged_lamp_still_gets_a_voice(
    tree: ContentTree,
) -> None:
    """The finding, inverted into a guarantee."""
    sim, dispatcher = under_way(tree, "core:spe-minor", seed=99)
    while "SEU HAZARD" not in sim.panel.active_messages():
        sim.step(1)
    dispatcher.execute_line("sys.annunciator ack")

    # Shed RT 12 per SOM 42-30-02 and acknowledge the lamp we lit ourselves.
    dispatcher.execute_line("eps cb.a2 open")
    sim.step(15)
    assert "DATA BUS A DEGRADED" in sim.panel.active_messages()
    dispatcher.execute_line("sys.annunciator ack")
    quiet = (sim.panel.master_caution_new, sim.panel.master_warning)
    assert quiet == (False, False), "the panel is steady and there is no warning"

    # Now ride the event out. RT 5 is on the essential bus and cannot be shed.
    while not sim.panel.master_warning and sim.clock.tick_index < 4000:
        sim.step(1)

    alerted = (sim.panel.master_warning, sim.panel.master_warning_new)
    assert alerted == (True, True), "the kept terminal latches and the panel says so"
    recall = dispatcher.execute_line("sys.annunciator read").text
    assert recall.index("DATA BUS A FAILED") < recall.index("DATA BUS A DEGRADED")
    assert "! WARNING" in recall


def test_the_chosen_degradation_stays_acknowledged_underneath(tree: ContentTree) -> None:
    """Ranking, not replacement: the panel says two true things at once."""
    sim, dispatcher = under_way(tree, "core:spe-minor", seed=99)
    dispatcher.execute_line("eps cb.a2 open")
    sim.step(15)
    dispatcher.execute_line("sys.annunciator ack")
    while not sim.panel.master_warning and sim.clock.tick_index < 4000:
        sim.step(1)
    lit = {a.spec.message: a for a in sim.panel.recall()}
    assert lit["DATA BUS A FAILED"].is_new
    assert not lit["DATA BUS A DEGRADED"].is_new  # still lit, still seen


def test_acknowledging_never_silences_the_condition(tree: ContentTree) -> None:
    sim, dispatcher = under_way(tree, "core:spe-minor", seed=99)
    dispatcher.execute_line("eps cb.a2 open")
    sim.step(15)
    dispatcher.execute_line("sys.annunciator ack")
    sim.step(50)
    assert "DATA BUS A DEGRADED" in sim.panel.active_messages()
    assert sim.panel.master_caution  # steady, but still very much on
