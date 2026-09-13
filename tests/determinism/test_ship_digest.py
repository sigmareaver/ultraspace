"""Determinism: identical (seed, content, command sequence) -> identical FDR digest."""

from __future__ import annotations

from ultraspace.content import ContentTree
from ultraspace.interaction import run_procedure
from ultraspace.ship import Simulation
from ultraspace.world import ScenarioRun

SCRIPT: list[tuple[str, str, frozenset[str]]] = [
    ("eps.bat.1.contactor", "close", frozenset({"confirm"})),
    ("eps.cb.e1", "close", frozenset()),
    ("eps.bus.a.precharge", "start", frozenset()),
    ("eps.bus.a.tie", "close", frozenset({"confirm"})),  # too early: inrush lesson
    ("eps.cb.a1", "close", frozenset()),
]


def run_script(tree: ContentTree, seed: int) -> str:
    sim = Simulation(tree, "core:tb-1", master_seed=seed)
    for address, verb, flags in SCRIPT:
        sim.step(10)
        result = sim.execute(address, verb, set(flags))
        sim.log.append(
            sim.clock.tick_index,
            "scl",
            "command",
            {
                "address": address,
                "verb": verb,
                "ok": result.ok,
            },
        )
    sim.step(50)
    return sim.log.digest()


def test_same_seed_same_digest(tree: ContentTree) -> None:
    assert run_script(tree, 42) == run_script(tree, 42)


def test_procedure_run_is_deterministic(tree: ContentTree) -> None:
    """The conformance path itself must replay bit-identically."""

    def digest(seed: int) -> str:
        sim = Simulation(tree, "core:tb-1", master_seed=seed)
        run_procedure(sim, tree.procedures["core:som-24-30-01"])
        sim.step(50)
        return sim.log.digest()

    assert digest(42) == digest(42)


def test_different_seed_different_digest(tree: ContentTree) -> None:
    # Different sensor noise draws land in annunciator/telemetry-driven events?
    # Not necessarily — noise may not change any *event*. Digest equality across
    # seeds is therefore allowed; what must differ is the raw noise stream.
    sim_a = Simulation(tree, "core:tb-1", master_seed=1)
    sim_b = Simulation(tree, "core:tb-1", master_seed=2)
    sim_a.step(5)
    sim_b.step(5)
    item_a = sim_a.telemetry.read("mt.bus.e.v")
    item_b = sim_b.telemetry.read("mt.bus.e.v")
    assert item_a is not None and item_b is not None
    assert item_a.value != item_b.value


def run_event(tree: ContentTree, seed: int, shed: str | None = None) -> str:
    """A full solar event, optionally with one terminal shed before it starts."""
    spec = tree.scenarios["core:spe-transit"]
    sim = Simulation(tree, spec.ship, master_seed=seed)
    ScenarioRun(spec, sim)
    for procedure_id in ("core:som-24-30-01", "core:som-42-30-01"):
        assert run_procedure(sim, tree.procedures[procedure_id]).passed
    if shed is not None:
        sim.execute(shed, "open", set())
    sim.step(6000)
    return sim.log.digest()


def test_a_scenario_replays_bit_identically(tree: ContentTree) -> None:
    assert run_event(tree, 1553) == run_event(tree, 1553)


def test_a_different_seed_is_a_different_event(tree: ContentTree) -> None:
    """The stress model must actually consume the seed, not just exist."""
    assert run_event(tree, 1553) != run_event(tree, 24)


def onset_ticks(tree: ContentTree, seed: int, shed: str | None) -> dict[str, int]:
    spec = tree.scenarios["core:spe-transit"]
    sim = Simulation(tree, spec.ship, master_seed=seed)
    ScenarioRun(spec, sim)
    for procedure_id in ("core:som-24-30-01", "core:som-42-30-01"):
        assert run_procedure(sim, tree.procedures[procedure_id]).passed
    if shed is not None:
        sim.execute(shed, "open", set())
    sim.step(6000)
    return {e.source: e.tick for e in sim.log if e.kind == "fault-onset"}


def test_shedding_one_terminal_does_not_move_the_others_onset(tree: ContentTree) -> None:
    """Stream isolation (ADR-0002): every hazard draws every tick, so a crew
    action on RT 12 cannot shift when RT 5 latches. Without the unconditional
    draw this test fails, and the whole replay story with it."""
    kept = onset_ticks(tree, 1553, shed=None)
    shed = onset_ticks(tree, 1553, shed="eps.cb.a2")
    assert "rt.5" in kept, "the reference run must contain the casualty being compared"
    assert shed.get("rt.5") == kept["rt.5"]
    assert "rt.12" not in shed  # shed before the event: an unpowered board cannot latch
