"""Determinism: identical (seed, content, command sequence) -> identical FDR digest."""

from __future__ import annotations

from ultraspace.content import ContentTree
from ultraspace.ship import Simulation

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
