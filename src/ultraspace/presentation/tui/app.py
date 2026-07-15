"""ULTRASPACE TUI: crew-station client over the headless core (ui-presentation.md).

Same operating contract as the teletype (feature parity is contractual):
turn-based at M1 — the sim advances one tick per SCL command, or explicitly
via ``wait <seconds>``. Every affordance emits SCL through the dispatcher, so
the FDR journal replays identically regardless of client. Persistent chrome:
annunciator row (top), command bar with last result + clock strip (bottom).
Stations switch on function keys; state persists per station.
"""

from __future__ import annotations

from typing import ClassVar

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.suggester import SuggestFromList
from textual.widgets import ContentSwitcher, Input, Static

from ultraspace.content.manuals import ManualPage
from ultraspace.interaction import Dispatcher
from ultraspace.kernel import Event
from ultraspace.presentation.teletype import EVENT_KINDS, format_event
from ultraspace.presentation.tui.stations import DocsStation, EpsStation, LogStation
from ultraspace.presentation.tui.widgets import AnnunciatorRow, ClockStrip
from ultraspace.ship import Simulation

__all__ = ["UltraspaceApp", "run_tui"]

HELP = """\
ULTRASPACE TUI. Sim advances one tick (0.1 s) per command.
  <scl command>     e.g.: eps read | eps bus.e read | eps bat.1.contactor close --confirm
  wait <seconds>    advance sim time (events land in the LOG station)
  met               show mission elapsed time
  help | quit
Stations: F1 SYS/EPS · F7 DOCS · F8 LOG"""

_MAX_WAIT_S = 3600.0


def _suggestions(sim: Simulation) -> list[str]:
    """Command-bar completion, generated from the loaded ship (command-language.md)."""
    out = ["help", "met", "quit", "wait 10"]
    roots = sorted({address.split(".")[0] for address in sim.address_map})
    out.extend(f"{root} read" for root in roots)
    for address in sorted(sim.address_map):
        root, _, rest = address.partition(".")
        spaced = f"{root} {rest}" if rest else address
        actionable = any(d in sim.devices for d in sim.address_map[address])
        out.append(spaced if actionable else f"{spaced} read")
    return out


class UltraspaceApp(App[None]):
    """The station client: chrome + ContentSwitcher of stations + command bar."""

    AUTO_FOCUS = "#command"
    CSS = """
    #annunciators { dock: top; height: 1; }
    #command-bar { dock: bottom; height: auto; }
    #result { max-height: 14; }
    #clock { height: 1; }
    #docs-list { width: 40%; max-width: 64; }
    """
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("f1", "station('eps')", "SYS/EPS"),
        Binding("f7", "station('docs')", "DOCS"),
        Binding("f8", "station('log')", "LOG"),
    ]

    def __init__(self, sim: Simulation, pages: list[ManualPage]) -> None:
        super().__init__()
        self.sim = sim
        self.title = f"ULTRASPACE — {sim.ship.name}"
        self._pages = pages
        self._dispatcher = Dispatcher(sim)
        self._log_cursor = 0

    def compose(self) -> ComposeResult:
        yield AnnunciatorRow(id="annunciators")
        with ContentSwitcher(initial="eps", id="stations"):
            yield EpsStation(self.sim, id="eps")
            yield DocsStation(self._pages, id="docs")
            yield LogStation(id="log")
        with Vertical(id="command-bar"):
            yield Static(id="result")
            yield ClockStrip(id="clock")
            yield Input(
                placeholder="SCL — 'help' for commands",
                suggester=SuggestFromList(_suggestions(self.sim), case_sensitive=True),
                id="command",
            )

    def on_mount(self) -> None:
        self.sim.step(1)  # instruments report before the first look (teletype parity)
        self._show(f"{self.sim.ship.name} — 'help' for commands. F1 EPS · F7 DOCS · F8 LOG.")

    # -- station switching -----------------------------------------------------

    def action_station(self, station: str) -> None:
        self.query_one("#stations", ContentSwitcher).current = station

    # -- command bar (the only mutation path: everything emits SCL) -------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        line = event.value.strip()
        event.input.value = ""
        if not line:
            return
        if line in ("quit", "exit"):
            self.exit()
            return
        if line == "help":
            self._show(HELP)
            return
        if line == "met":
            self._show(f"MET {self.sim.clock.mission_elapsed_str()}")
            return
        if line.startswith("wait"):
            self._show(self._do_wait(line))
            return
        result = self._dispatcher.execute_line(line)
        self.sim.step(1)  # operator actions take time; effects become observable
        self._show(f"> {line}\n{result.text}")

    def _do_wait(self, line: str) -> str:
        parts = line.split()
        try:
            seconds = float(parts[1]) if len(parts) > 1 else 1.0
        except ValueError:
            return f"wait: not a duration: {parts[1]!r}"
        seconds = min(seconds, _MAX_WAIT_S)
        self.sim.step_s(seconds)
        return f"... {seconds:g} s pass. MET {self.sim.clock.mission_elapsed_str()}"

    # -- per-turn refresh --------------------------------------------------------

    def _show(self, text: str) -> None:
        """Update the result line, flush FDR events, refresh chrome + stations."""
        lines = [text]
        lines.extend(f"* {format_event(e)}" for e in self._flush_events())
        self.query_one("#result", Static).update(Text("\n".join(lines)))
        self.query_one("#annunciators", AnnunciatorRow).refresh_from_sim(self.sim)
        self.query_one("#clock", ClockStrip).refresh_from_sim(self.sim)
        self.query_one("#eps", EpsStation).refresh_from_sim()

    def _flush_events(self) -> list[Event]:
        """Append new journal entries to LOG; return the operator-notable ones."""
        events = list(self.sim.log)[self._log_cursor :]
        self._log_cursor += len(events)
        station = self.query_one("#log", LogStation)
        notable: list[Event] = []
        for event in events:
            station.write(format_event(event))
            if event.kind in EVENT_KINDS:
                notable.append(event)
        return notable


def run_tui(sim: Simulation, pages: list[ManualPage]) -> None:
    """Blocking entry point (mirrors run_teletype; wired to `ultraspace run --tui`)."""
    UltraspaceApp(sim, pages).run()
