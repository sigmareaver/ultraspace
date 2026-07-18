"""Textual pilot smoke tests (testing.md §2): deliberately thin.

The TUI contains no logic worth deep testing (architecture rule), so these
prove the wiring exists: stations mount, annunciators render, the station-key
footer clicks through, the semantic color contract shows up as styles, and
the command bar round-trips SCL through the dispatcher (and therefore into
the FDR). Physics correctness lives in tests/conformance and tests/casualties.
"""

from __future__ import annotations

import pytest
from rich.style import Style as RichStyle
from rich.text import Text
from textual.content import Content
from textual.pilot import Pilot
from textual.style import Style as TextualStyle
from textual.widgets import ContentSwitcher, Footer, Input, OptionList, Static
from textual.widgets._footer import FooterKey  # only export path (textual 8.x)

from ultraspace.content import ContentTree, load_manual_pages
from ultraspace.interaction import Dispatcher, run_procedure
from ultraspace.presentation import UltraspaceApp
from ultraspace.presentation.tui.palette import (
    ADVISORY_STYLE,
    CAUTION_STYLE,
    LAMP_ACTIVE_STYLE,
    OFF_STYLE,
)
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


def _t_style(style: object) -> TextualStyle:
    """Normalize a span style (str / rich / textual) for equality checks.

    Widgets rewrite span styles into textual.style.Style on render; rich
    round-trips lose equality (color(214) → #ffaf00), textual's don't.
    """
    if isinstance(style, TextualStyle):
        return style
    if isinstance(style, RichStyle):
        return TextualStyle.from_rich_style(style)
    return TextualStyle.from_rich_style(RichStyle.parse(str(style)))


def span_styles_at(text: Text | Content, needle: str) -> list[set[TextualStyle]]:
    """Styles covering each occurrence of ``needle`` in a rendered Text."""
    found: list[set[TextualStyle]] = []
    start = 0
    while (at := text.plain.find(needle, start)) != -1:
        found.append({_t_style(span.style) for span in text.spans if span.start <= at < span.end})
        start = at + 1
    return found


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


@pytest.mark.asyncio
async def test_station_footer_is_a_clickable_key_bar(tree: ContentTree) -> None:
    app = make_app(tree)
    async with app.run_test(size=(132, 43)) as pilot:
        await pilot.pause()
        app.query_one(Footer)
        keys = {key.key: key for key in app.query(FooterKey)}
        assert {key: keys[key].description for key in keys} == {
            "f1": "SYS/EPS",
            "f7": "DOCS",
            "f8": "LOG",
        }
        switcher = app.query_one("#stations", ContentSwitcher)
        for key, station in (("f8", "log"), ("f7", "docs"), ("f1", "eps")):
            await pilot.click(keys[key])
            await pilot.pause()
            assert switcher.current == station
        assert app.query_one(Input).has_focus  # mouse never steals the keyboard


def test_eps_station_applies_the_semantic_color_contract(tree: ContentTree) -> None:
    """Every state color is glyph-redundant (style-guide mapping, palette.py)."""
    sim = Simulation(tree, "core:tb-1", master_seed=99)
    d = Dispatcher(sim)
    sim.step(1)
    # Cold & dark: off states are dim with the `·` glyph — a dark ship reads dark.
    text = render_eps(sim)
    assert span_styles_at(text, "MASTER CAUTION: clear") == [{_t_style(OFF_STYLE)}]
    open_cells = span_styles_at(text, "· OPEN")
    assert open_cells and all(styles == {_t_style(OFF_STYLE)} for styles in open_cells)

    # Advisory: an in-progress precharge is cyan `●`; CLOSED stays plain.
    d.execute_line("eps bat.1.contactor close --confirm")
    sim.step(10)
    d.execute_line("eps bus.a.precharge start")
    sim.step(1)
    text = render_eps(sim)
    charging = span_styles_at(text, "● CHARGING")
    assert charging and all(styles == {_t_style(ADVISORY_STYLE)} for styles in charging)
    assert span_styles_at(text, "CLOSED") == [set(), set()]  # panel row + tree branch

    # Caution: forcing the tie trips it (SOM 24-00-00 §3) — amber `▲` everywhere.
    d.execute_line("eps bus.a.tie close --confirm")
    sim.step(1)
    text = render_eps(sim)
    tripped = span_styles_at(text, "▲ TRIPPED")
    assert tripped and all(styles == {_t_style(CAUTION_STYLE)} for styles in tripped)


@pytest.mark.asyncio
async def test_caution_lights_lamp_row_and_station(tree: ContentTree) -> None:
    """The undervolt casualty (tests/casualties) experienced at the console."""
    app = make_app(tree)
    result = run_procedure(app.sim, tree.procedures["core:som-24-30-01"])  # powered ship
    assert result.passed, result.failure_summary()
    async with app.run_test(size=(132, 43)) as pilot:
        await submit(app, pilot, "eps bat.1.contactor open")
        await submit(app, pilot, "wait 2")  # bus caps drain through the loads
        row = app.query_one(AnnunciatorRow).render()
        assert isinstance(row, Content)  # Static renders our Text as Content
        assert "▲ MSTR CAUT" in row.plain and "▲ BUS E UNDERVOLT" in row.plain
        assert _t_style(LAMP_ACTIVE_STYLE) in {_t_style(span.style) for span in row.spans}
        station = app.query_one("#eps-text", Static).render()
        assert isinstance(station, Content)
        assert span_styles_at(station, "▲ MASTER CAUTION: ACTIVE") == [{_t_style(CAUTION_STYLE)}]
