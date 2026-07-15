"""Teletype client: scripted transcript over the injectable I/O seam."""

from __future__ import annotations

from ultraspace.content import ContentTree
from ultraspace.presentation import run_teletype
from ultraspace.ship import Simulation


def transcript(tree: ContentTree, commands: list[str], seed: int = 42) -> str:
    sim = Simulation(tree, "core:tb-1", master_seed=seed)
    feed = iter(commands)
    lines: list[str] = []

    def input_fn(_prompt: str) -> str:
        try:
            return next(feed)
        except StopIteration:
            raise EOFError from None

    run_teletype(sim, input_fn, lines.append)
    return "\n".join(lines)


def test_cold_start_fragment_plays(tree: ContentTree) -> None:
    out = transcript(
        tree,
        [
            "help",
            "eps read",
            "eps bat.1.contactor close --confirm",
            "eps bus.a.precharge start",
            "wait 3",
            "eps bus.a.tie close --confirm",
            "met",
            "quit",
        ],
    )
    assert "teletype mode" in out
    assert "MASTER CAUTION: clear" in out
    assert "ctr.bat1: CLOSED" in out
    assert "precharge in progress" in out
    assert "* [" in out and "precharge-complete" in out  # async event line
    assert "tie.a: CLOSED" in out and "TRIPPED" not in out
    assert "MET 000:00:00" in out


def test_violating_the_caution_is_audible(tree: ContentTree) -> None:
    out = transcript(
        tree,
        [
            "eps bat.1.contactor close --confirm",
            "wait 1",
            "eps bus.a.tie close --confirm",  # no precharge: SOM 24-30-01 CAUTION
            "quit",
        ],
    )
    assert "inrush-trip" in out and "SOM 24-00-00" in out


def test_wait_parses_garbage_politely(tree: ContentTree) -> None:
    out = transcript(tree, ["wait pancakes", "quit"])
    assert "not a duration" in out
