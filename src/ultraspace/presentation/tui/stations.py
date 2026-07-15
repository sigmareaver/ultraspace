"""Station widgets: SYS/EPS, DOCS, LOG (ui-presentation.md station table).

Stations render exclusively from sanctioned surfaces: the telemetry store,
the annunciator panel, panel observations via the command surface (``read``),
and the FDR event log. The EPS feeder tree uses the same diagram grammar as
the generated WDM sheets (blueprint order, `→` tails) with live annotations —
one grammar for manual pages and live screens.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Markdown, OptionList, RichLog, Static

from ultraspace.content.manuals import ManualPage
from ultraspace.ship import Simulation
from ultraspace.ship.sim import DT_S

__all__ = ["DocsStation", "EpsStation", "LogStation", "render_eps"]

_STALE_AGE_S = 1.0  # older than this gets the visible `?` tag (No God View)

_DOCS_WELCOME = """\
# DOCS

Select a page from the index (arrow keys, Enter). `F1` returns to SYS/EPS.
"""


# -- SYS/EPS ------------------------------------------------------------------


def _device_states(sim: Simulation) -> dict[str, str]:
    """Panel observations (device id -> state) via the ``read`` command surface.

    Reads are panel observations, not operator actions; they bypass the FDR
    journal deliberately (a display refresh is not a replay input).
    """
    states: dict[str, str] = {}
    for address in sorted(sim.address_map):
        if not any(d in sim.devices for d in sim.address_map[address]):
            continue  # telemetry-only address; the measurements table owns it
        for line in sim.execute(address, "read", set()).text.splitlines():
            device_id, sep, state = line.partition(": ")
            if sep:
                states[device_id] = state
    return states


def _measurement_lines(sim: Simulation) -> list[str]:
    lines = ["MEASUREMENTS"]
    ids = sim.telemetry.ids()
    if not ids:
        lines.append("  --- NO DATA (instruments cold)")
    for telemetry_id in ids:
        item = sim.telemetry.read(telemetry_id)
        assert item is not None  # ids() only lists published items
        age_s = (sim.clock.tick_index - item.tick) * DT_S
        stale = "  ?" if age_s > _STALE_AGE_S else ""
        lines.append(
            f"  {telemetry_id:<14} {item.value:9.3f} {item.unit:<4}"
            f" src {item.source}  age {age_s:4.1f} s{stale}"
        )
    return lines


def _panel_lines(sim: Simulation, states: dict[str, str]) -> list[str]:
    lines = ["PANEL — protection & switching (SCL address · device · state)"]
    for address in sorted(sim.address_map):
        for device_id in sim.address_map[address]:
            if device_id in states:
                lines.append(f"  {address:<24} {device_id:<10} {states[device_id]}")
    return lines


def _feeder_tree_lines(sim: Simulation, states: dict[str, str]) -> list[str]:
    """Live feeder trees: WDM diagram grammar + telemetry/panel annotations."""
    node_v: dict[str, float] = {}
    for spec in sim.ship.devices:  # map measured node -> latest voltage report
        item = sim.telemetry.read(spec.id)
        if spec.measures is not None and item is not None and item.unit == "V":
            node_v[spec.measures] = item.value
    on_node: dict[str, list[tuple[str, str]]] = {}  # node -> [(device id, other node)]
    for spec in sim.ship.devices:
        for port, node in spec.ports.items():
            others = [n for p, n in spec.ports.items() if p != port]
            on_node.setdefault(node, []).append((spec.id, others[0] if len(others) == 1 else ""))

    lines = ["FEEDER TREES — live (voltages are transducer reports)"]
    for bus in sim.ship.nodes:
        if not bus.bus:
            continue
        volts = node_v.get(bus.id)
        volts_txt = f"{volts:6.2f} V" if volts is not None else "--- ?  (no report)"
        lines.append(f"  {bus.id.replace('.', ' ').upper()}  [{bus.id}]  {volts_txt}")
        attached = on_node.get(bus.id, [])  # blueprint order (style guide rule 2)
        width = max((len(device_id) for device_id, _ in attached), default=0)
        for i, (device_id, other) in enumerate(attached):
            branch = "└──" if i == len(attached) - 1 else "├──"
            state = states.get(device_id, "·")
            tail = f"  → {other}" if other else ""
            lines.append(f"   {branch} {device_id:<{width}}  {state:<12}{tail}")
    return lines


def render_eps(sim: Simulation) -> str:
    """The SYS/EPS station text: caution line, measurements, panel, feeder trees."""
    caution = sim.panel.active_messages()
    states = _device_states(sim)
    sections = [
        [f"MASTER CAUTION: {'ACTIVE — ' + ', '.join(caution) if caution else 'clear'}"],
        _measurement_lines(sim),
        _panel_lines(sim, states),
        _feeder_tree_lines(sim, states),
    ]
    return "\n\n".join("\n".join(lines) for lines in sections)


class EpsStation(VerticalScroll):
    """F1 — bus diagram, breaker panel, measurement table."""

    def __init__(self, sim: Simulation, *, id: str | None = None) -> None:  # noqa: A002 - textual convention
        super().__init__(id=id)
        self._sim = sim

    def compose(self) -> ComposeResult:
        yield Static(id="eps-text")

    def refresh_from_sim(self) -> None:
        self.query_one("#eps-text", Static).update(Text(render_eps(self._sim)))


# -- DOCS ----------------------------------------------------------------------


class DocsStation(Horizontal):
    """F7 — manual reader: page index + Markdown view."""

    def __init__(self, pages: list[ManualPage], *, id: str | None = None) -> None:  # noqa: A002
        super().__init__(id=id)
        self.pages = pages

    def compose(self) -> ComposeResult:
        yield OptionList(*[page.label for page in self.pages], id="docs-list")
        with VerticalScroll(id="docs-view"):
            yield Markdown(_DOCS_WELCOME, id="docs-page")

    async def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        page = self.pages[event.option_index]
        await self.query_one("#docs-page", Markdown).update(f"# {page.label}\n\n{page.body}")


# -- LOG -----------------------------------------------------------------------


class LogStation(RichLog):
    """F8 — FDR review v1: every event, appended as the journal grows."""

    def __init__(self, *, id: str | None = None) -> None:  # noqa: A002 - textual convention
        super().__init__(id=id, wrap=False, highlight=False, markup=False, auto_scroll=True)
