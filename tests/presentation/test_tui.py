"""Textual pilot smoke tests (testing.md §2): deliberately thin.

The TUI contains no logic worth deep testing (architecture rule), so these
prove the wiring exists: stations mount, annunciators render, and the command
bar round-trips SCL through the dispatcher (and therefore into the FDR).
Physics correctness lives in tests/conformance and tests/casualties.
"""

from __future__ import annotations

import pytest
from textual.pilot import Pilot
from textual.widgets import ContentSwitcher, Input, OptionList, Static

from ultraspace.content import ContentTree, load_manual_pages
from ultraspace.presentation import UltraspaceApp
from ultraspace.presentation.tui.stations import DocsStation, EpsStation, LogStation, render_eps
from ultraspace.presentation.tui.widgets import AnnunciatorRow
from ultraspace.ship import Simulation


def make_app(tree: ContentTree, seed: int = 42) -> UltraspaceApp:
    sim = Simulation(tree, "core:tb-1", master_seed=seed)
    return UltraspaceApp(sim, load_manual_pages(tree.root))


async def submit(app: UltraspaceApp, pilot: Pilot[None], line: str) -> None:
    """Type a line into the focused command bar and press enter."""
    app.query_one("#command", Input).value = line
    await pilot.press("enter")


@pytest.mark.asyncio
async def test_shell_mounts_with_chrome_and_stations(tree: ContentTree) -> None:
    app = make_app(tree)
    async with app.run_test(size=(132, 43)):
        assert app.query_one("#stations", ContentSwitcher).current == "eps"
        app.query_one(EpsStation)
        app.query_one(DocsStation)
        app.query_one(LogStation)
        row = app.query_one(AnnunciatorRow)
        rendered = row.render()
        assert "MSTR CAUT" in str(rendered)
        assert "BUS E UNDERVOLT" in str(rendered)  # blueprint lamp tiles present
        assert app.query_one(Input).has_focus  # command bar owns the keyboard


@pytest.mark.asyncio
async def test_station_switching_on_function_keys(tree: ContentTree) -> None:
    app = make_app(tree)
    async with app.run_test(size=(132, 43)) as pilot:
        switcher = app.query_one("#stations", ContentSwitcher)
        await pilot.press("f7")
        assert switcher.current == "docs"
        # DOCS index lists the real manual shelf, SOM and generated WDM included.
        options = app.query_one("#docs-list", OptionList)
        assert options.option_count == len(load_manual_pages(tree.root))
        await pilot.press("f8")
        assert switcher.current == "log"
        await pilot.press("f1")
        assert switcher.current == "eps"


@pytest.mark.asyncio
async def test_command_bar_round_trips_scl_into_the_fdr(tree: ContentTree) -> None:
    app = make_app(tree)
    async with app.run_test(size=(132, 43)) as pilot:
        ticks_before = app.sim.clock.tick_index
        await submit(app, pilot, "eps bat.1.contactor close --confirm")
        result = str(app.query_one("#result", Static).render())
        assert "> eps bat.1.contactor close --confirm" in result  # echo discipline
        assert "ctr.bat1: CLOSED" in result
        assert app.sim.clock.tick_index == ticks_before + 1  # turn-based: one tick
        journal = [e for e in app.sim.log if e.kind == "command" and e.source == "scl"]
        assert journal and journal[-1].payload["line"] == "eps bat.1.contactor close --confirm"


@pytest.mark.asyncio
async def test_wait_and_async_events_reach_result_and_log(tree: ContentTree) -> None:
    app = make_app(tree)
    async with app.run_test(size=(132, 43)) as pilot:
        for line in ("eps bat.1.contactor close --confirm", "eps bus.a.precharge start"):
            await submit(app, pilot, line)
        await submit(app, pilot, "wait 3")
        result = str(app.query_one("#result", Static).render())
        assert "... 3 s pass." in result
        assert "* [" in result and "precharge-complete" in result  # async event line
        await pilot.press("f8")  # RichLog renders once the LOG station is shown
        await pilot.pause()
        log_text = "\n".join(strip.text for strip in app.query_one(LogStation).lines)
        assert "precharge-complete" in log_text
        assert "scl: command" in log_text  # the FDR journal is on the LOG station


def test_eps_station_renders_from_sanctioned_surfaces_only(tree: ContentTree) -> None:
    sim = Simulation(tree, "core:tb-1", master_seed=42)
    sim.step(1)
    text = render_eps(sim)
    assert "MASTER CAUTION: clear" in text
    assert "mt.bus.e.v" in text  # measurements table
    assert "eps.bat.1.contactor" in text and "OPEN" in text  # panel observations
    assert "BUS E  [bus.e]" in text and "├──" in text  # live feeder tree grammar
    # Display refreshes are observations, not operator actions: journal untouched.
    assert not any(e.kind == "command" for e in sim.log)
