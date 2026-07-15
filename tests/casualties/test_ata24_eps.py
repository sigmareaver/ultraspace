"""EPS casualty behavior, experienced strictly like a player.

Rule (testing.md class 5): telemetry, SCL responses, and panel observation
only — no `ultraspace.testing` imports in this directory, ever.
"""

from __future__ import annotations

from ultraspace.content import ContentTree
from ultraspace.interaction import Dispatcher, run_procedure
from ultraspace.ship import Simulation


def powered_tb1(tree: ContentTree, seed: int = 42) -> tuple[Simulation, Dispatcher]:
    sim = Simulation(tree, "core:tb-1", master_seed=seed)
    result = run_procedure(sim, tree.procedures["core:som-24-30-01"])
    assert result.passed, result.failure_summary()
    return sim, Dispatcher(sim)


def test_losing_the_battery_annunciates_undervolt(tree: ContentTree) -> None:
    sim, d = powered_tb1(tree)
    d.execute_line("eps bat.1.contactor open")
    sim.step_s(2.0)  # bus caps drain through connected loads
    summary = d.execute_line("eps read").text
    assert "MASTER CAUTION: ACTIVE" in summary
    assert "BUS E UNDERVOLT" in summary and "BUS A UNDERVOLT" in summary
    reading = d.execute_line("eps bus.e read").text
    # The player sees the bus dying through the transducer, provenance intact.
    assert "src: mt.bus.e.v" in reading


def test_tie_closed_onto_dead_bus_observable_consequences(tree: ContentTree) -> None:
    """The 24-30-01 CAUTION, violated: symptoms exactly as the SOM promises."""
    sim = Simulation(tree, "core:tb-1", master_seed=99)
    d = Dispatcher(sim)
    sim.step(1)
    d.execute_line("eps bat.1.contactor close --confirm")
    sim.step(10)
    response = d.execute_line("eps bus.a.tie close --confirm")  # skipping precharge
    assert "TRIPPED" in response.text and "SOM 24-30-01" in response.text
    sim.step(10)
    panel = d.execute_line("eps bus.a.tie read").text
    assert "TRIPPED" in panel  # panel observation
    bus_a = sim.telemetry.read("mt.bus.a.v")
    assert bus_a is not None and bus_a.value < 2.0  # bus never came up
    # Recovery path the manual prescribes: reset, then do it properly.
    assert d.execute_line("eps bus.a.tie reset").ok
    assert d.execute_line("eps bus.a.precharge start").ok
    sim.step_s(3.0)
    assert d.execute_line("eps bus.a.tie close --confirm").text.count("TRIPPED") == 0
