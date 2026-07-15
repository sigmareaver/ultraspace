"""Teletype mode: the flat line client (ui-presentation.md).

Turn-based at M1: sim time advances one tick per command, or explicitly via
``wait <seconds>``. Output discipline: ``>`` echoes, ``*`` asynchronous events
(annunciators, trips), plain text for command results. This client is the
accessibility floor and the feature-parity contract for the TUI.
"""

from __future__ import annotations

from collections.abc import Callable

from ultraspace.interaction import Dispatcher
from ultraspace.ship import Simulation

__all__ = ["run_teletype"]

_EVENT_KINDS = (
    "annunciator-raise",
    "annunciator-clear",
    "overcurrent-trip",
    "inrush-trip",
    "precharge-complete",
)

HELP = """\
ULTRASPACE teletype. Sim advances one tick (0.1 s) per command.
  <scl command>     e.g.: eps read | eps bus.e read | eps bat.1.contactor close --confirm
  wait <seconds>    advance sim time (events print as they occur)
  met               show mission elapsed time
  help | quit"""


def run_teletype(
    sim: Simulation,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
) -> None:
    """REPL loop; injectable I/O so tests and ssh wrappers share the code path."""
    dispatcher = Dispatcher(sim)
    cursor = len(sim.log)
    output_fn(f"{sim.ship.name} — teletype mode. 'help' for commands.")
    sim.step(1)

    while True:
        cursor = _flush_events(sim, output_fn, cursor)
        try:
            line = input_fn("> ").strip()
        except EOFError:
            return
        if not line:
            continue
        if line in ("quit", "exit"):
            return
        if line == "help":
            output_fn(HELP)
            continue
        if line == "met":
            output_fn(f"MET {sim.clock.mission_elapsed_str()}")
            continue
        if line.startswith("wait"):
            _do_wait(sim, output_fn, line)
            continue
        result = dispatcher.execute_line(line)
        sim.step(1)  # operator actions take time; effects become observable
        output_fn(result.text)


def _do_wait(sim: Simulation, output_fn: Callable[[str], None], line: str) -> None:
    parts = line.split()
    try:
        seconds = float(parts[1]) if len(parts) > 1 else 1.0
    except ValueError:
        output_fn(f"wait: not a duration: {parts[1]!r}")
        return
    seconds = min(seconds, 3600.0)
    sim.step_s(seconds)
    output_fn(f"... {seconds:g} s pass. MET {sim.clock.mission_elapsed_str()}")


def _flush_events(sim: Simulation, output_fn: Callable[[str], None], cursor: int) -> int:
    events = list(sim.log)[cursor:]
    for event in events:
        if event.kind in _EVENT_KINDS:
            met_s = event.tick / 10
            output_fn(f"* [{met_s:8.1f}s] {event.source}: {event.kind} {dict(event.payload)}")
    return cursor + len(events)
