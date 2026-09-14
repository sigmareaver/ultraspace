"""Teletype mode: the flat line client (ui-presentation.md).

Turn-based at M1: sim time advances one tick per command, or explicitly via
``wait <seconds>`` — which is a watch, not a sleep: it ends early on a new
warning (interaction/watch.py). Output discipline: ``>`` echoes, ``*`` asynchronous events
(annunciators, trips), plain text for command results. This client is the
accessibility floor and the feature-parity contract for the TUI.
"""

from __future__ import annotations

from collections.abc import Callable

from ultraspace.interaction import Dispatcher, watch
from ultraspace.kernel import Event
from ultraspace.ship import Simulation

__all__ = ["EVENT_KINDS", "format_event", "run_teletype"]

EVENT_KINDS = (
    "annunciator-raise",
    "annunciator-clear",
    "overcurrent-trip",
    "inrush-trip",
    "precharge-complete",
)
"""FDR event kinds surfaced asynchronously to the operator (both clients)."""


def format_event(event: Event) -> str:
    """One-line operator rendering of an FDR event (shared with the TUI).

    An annunciation is rendered as the panel would say it — severity spelled
    out, because the flat line client has no color and the ranking is the
    whole point (ata-31-indicating.md §2).
    """
    met_s = event.tick / 10
    payload = dict(event.payload)
    severity = payload.get("severity")
    if isinstance(severity, str) and event.kind in ("annunciator-raise", "annunciator-clear"):
        verb = "RAISED" if event.kind == "annunciator-raise" else "clear"
        return f"[{met_s:8.1f}s] {severity.upper():<9} {payload['message']} {verb}"
    return f"[{met_s:8.1f}s] {event.source}: {event.kind} {dict(event.payload)}"


HELP = """\
ULTRASPACE teletype. Sim advances one tick (0.1 s) per command.
  <scl command>     e.g.: eps read | eps bus.e read | eps bat.1.contactor close --confirm
  wait <seconds>    advance sim time (stops early on a new WARNING)
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
            said = _do_wait(sim, line)
            # Events first, in the order they happened, then the summary line:
            # an operator told "INTERRUPTED by DATA BUS A FAILED" and only then
            # shown the raise that caused it is reading the transcript
            # backwards (2026-09-14 playtest).
            cursor = _flush_events(sim, output_fn, cursor)
            output_fn(said)
            continue
        result = dispatcher.execute_line(line)
        sim.step(1)  # operator actions take time; effects become observable
        output_fn(result.text)


def _do_wait(sim: Simulation, line: str) -> str:
    """``wait`` is a watch, not a sleep — the same primitive the runner uses.

    An operator who asks for ten minutes and gets them in full while a warning
    was lighting at second three has been failed by the console, not served by
    it. The wait stops, says what stopped it, and says what is left, so
    resuming is a decision the operator makes with the number in front of them.
    """
    parts = line.split()
    try:
        seconds = float(parts[1]) if len(parts) > 1 else 1.0
    except ValueError:
        return f"wait: not a duration: {parts[1]!r}"
    seconds = min(seconds, 3600.0)
    result = watch(sim, seconds)
    if not result.interrupted:
        return f"... {seconds:g} s pass. MET {sim.clock.mission_elapsed_str()}"
    sim.log.append(
        sim.clock.tick_index,
        "teletype",
        "wait-interrupted",
        {"remaining_s": result.remaining_s, "messages": result.warnings},
    )
    return (
        f"... {result.elapsed_s:g} s of {seconds:g} s pass. MET "
        f"{sim.clock.mission_elapsed_str()}\n"
        f"WAIT INTERRUPTED — WARNING: {', '.join(result.warnings)} "
        f"({result.remaining_s:g} s of the wait remaining; 'wait "
        f"{result.remaining_s:g}' resumes it)"
    )


def _flush_events(sim: Simulation, output_fn: Callable[[str], None], cursor: int) -> int:
    events = list(sim.log)[cursor:]
    for event in events:
        if event.kind in EVENT_KINDS:
            output_fn(f"* {format_event(event)}")
    return cursor + len(events)
