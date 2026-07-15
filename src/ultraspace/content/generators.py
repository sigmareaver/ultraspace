"""Generated manual content: WDM tables and feeder trees (ADR-0003 §4).

Single source of truth machinery: these artifacts are derived from the same
blueprint/parts data the simulation loads, so the WDM cannot state a
mechanical fact the ship disagrees with. Output is committed under
``data/manuals/*/generated/`` and diff-checked in CI
(``ultraspace generate --check``); a hand edit or a stale table fails the
build. Formatting rules: data/manuals/style-guide.md.
"""

from __future__ import annotations

from ultraspace.content.loader import GROUND_NODE, ContentTree
from ultraspace.content.schemas import DeviceSpec, PartSpec, ShipSpec

__all__ = ["generate_all", "generate_ship_wdm", "sync_generated"]

_SWITCHING = ("contactor", "breaker", "precharge")
_XDUCERS = ("xducer_v", "xducer_i", "xducer_soc")
_MAX_WIDTH = 92  # style-guide print constraint

_HEADER = """\
<!-- GENERATED FILE — DO NOT EDIT (ultraspace generate). -->
<!-- Source: ships/{ship_dir}/blueprint.yaml + the part catalog. -->
<!-- Style: data/manuals/style-guide.md. Hand edits fail CI. -->
"""


class _Ctx:
    """Resolved lookup helpers for one ship (blueprint order preserved)."""

    def __init__(self, tree: ContentTree, ship: ShipSpec) -> None:
        self.ship = ship
        self.part_of = {d.id: tree.parts[d.part] for d in ship.devices}
        self.bus_ids = [n.id for n in ship.nodes if n.bus]
        # node id -> [(device, port)] in blueprint order
        self.on_node: dict[str, list[tuple[DeviceSpec, str]]] = {}
        for device in ship.devices:
            for port, node in device.ports.items():
                self.on_node.setdefault(node, []).append((device, port))

    def bus_name(self, node_id: str) -> str:
        return node_id.replace(".", " ").upper()

    def other_node(self, device: DeviceSpec, port: str) -> str | None:
        others = [n for p, n in device.ports.items() if p != port]
        return others[0] if len(others) == 1 else None


def _rating(part: PartSpec) -> str:
    p = part.params
    if part.behavior in ("contactor", "breaker"):
        return f"{part.behavior} {p['rating_a']:g} A"
    if part.behavior == "precharge":
        return f"precharge {p['r_ohm']:g} ohm"
    if part.behavior == "battery":
        return f"battery {p['emf_full_v']:g} V"
    if part.behavior == "load":
        return f"load {p['r_ohm']:g} ohm"
    return part.behavior


def generate_ship_wdm(tree: ContentTree, ship_qid: str) -> str:
    ship = tree.ships[ship_qid]
    ctx = _Ctx(tree, ship)
    sections = [
        _HEADER.format(ship_dir=ship.id),
        f"# WDM 24 — Generated Data Sheets — {ship.name} ({ship_qid})",
        _panel_table(ctx),
        _feeder_trees(ctx),
        _wire_list(ctx),
        _load_list(ctx),
        _instrumentation(ctx),
        _parts_list(ctx),
    ]
    text = "\n\n".join(sections) + "\n"
    for line in text.splitlines():
        if len(line) > _MAX_WIDTH:
            raise ValueError(f"generated line exceeds {_MAX_WIDTH} cols: {line!r}")
    return text


def _panel_table(ctx: _Ctx) -> str:
    rows = ["## Panel: protection & switching {#breaker-table}", ""]
    rows.append("| SCL address | Device | P/N | Type | Rating | From | To |")
    rows.append("|---|---|---|---|---|---|---|")
    for device in ctx.ship.devices:
        part = ctx.part_of[device.id]
        if part.behavior not in _SWITCHING:
            continue
        kind, _, rating = _rating(part).partition(" ")
        rows.append(
            f"| `{device.scl or '-'}` | {device.id} | {part.part_number} | {kind} "
            f"| {rating} | {device.ports['a']} | {device.ports['b']} |"
        )
    return "\n".join(rows)


def _feeder_trees(ctx: _Ctx) -> str:
    out = ["## Feeder trees {#feeder-trees}", "", "```"]
    for bus_id in ctx.bus_ids:
        node = next(n for n in ctx.ship.nodes if n.id == bus_id)
        out.append(f"{ctx.bus_name(bus_id)}  [{bus_id}]  {node.c_f * 1000:g} mF")
        attached = ctx.on_node.get(bus_id, [])  # blueprint order (style guide rule 2)
        width = max((len(d.id) for d, _ in attached), default=0)
        for i, (device, port) in enumerate(attached):
            part = ctx.part_of[device.id]
            branch = "└──" if i == len(attached) - 1 else "├──"
            line = f" {branch} {device.id:<{width}}  {part.part_number}  {_rating(part):<18}"
            out.append((line + _tail(ctx, device, port)).rstrip())
        out.append("")
    if out[-1] == "":
        out.pop()
    out.append("```")
    return "\n".join(out)


def _tail(ctx: _Ctx, device: DeviceSpec, port: str) -> str:
    other = ctx.other_node(device, port)
    if other is None:
        return ""
    if other == GROUND_NODE:
        return "  → GND"
    if other in ctx.bus_ids:
        return f"  → {ctx.bus_name(other)}"
    hop = [d.id for d, _ in ctx.on_node.get(other, []) if d.id != device.id]
    if not hop:
        return f"  → {other}"
    return f"  → {other} → {', '.join(hop)}"  # ids only: style guide rule 3


def _wire_list(ctx: _Ctx) -> str:
    rows = ["## Wire list {#wire-list}", ""]
    rows.append("| Node | Capacitance | Connections (device.port) |")
    rows.append("|---|---|---|")
    for node in ctx.ship.nodes:
        conns = ", ".join(f"{d.id}.{p}" for d, p in ctx.on_node.get(node.id, []))
        rows.append(f"| {node.id} | {node.c_f * 1000:g} mF | {conns} |")
    gnd = ", ".join(f"{d.id}.{p}" for d, p in ctx.on_node.get(GROUND_NODE, []))
    rows.append(f"| gnd (ref) | - | {gnd} |")
    return "\n".join(rows)


def _load_list(ctx: _Ctx) -> str:
    rows = ["## Load list {#load-list}", ""]
    rows.append("| Device | P/N | Name | R | I @ 28 V | Protected by |")
    rows.append("|---|---|---|---|---|---|")
    for device in ctx.ship.devices:
        part = ctx.part_of[device.id]
        if part.behavior != "load":
            continue
        r_ohm = part.params["r_ohm"]
        feeder = _protector(ctx, device)
        rows.append(
            f"| {device.id} | {part.part_number} | {part.name} | {r_ohm:g} ohm "
            f"| {28.0 / r_ohm:.1f} A | {feeder} |"
        )
    return "\n".join(rows)


def _protector(ctx: _Ctx, load: DeviceSpec) -> str:
    feed_node = load.ports["pos"]
    for device, _port in ctx.on_node.get(feed_node, []):
        if device.id != load.id and ctx.part_of[device.id].behavior in _SWITCHING:
            return device.id
    return "(unprotected)"


def _instrumentation(ctx: _Ctx) -> str:
    rows = ["## Instrumentation {#instrumentation}", ""]
    rows.append("| Telemetry ID | P/N | Measures | Unit | SCL |")
    rows.append("|---|---|---|---|---|")
    units = {"xducer_v": "V", "xducer_i": "A", "xducer_soc": "frac"}
    for device in ctx.ship.devices:
        part = ctx.part_of[device.id]
        if part.behavior not in _XDUCERS:
            continue
        rows.append(
            f"| {device.id} | {part.part_number} | {device.measures} "
            f"| {units[part.behavior]} | `{device.scl or '-'}` |"
        )
    return "\n".join(rows)


def _parts_list(ctx: _Ctx) -> str:
    rows = ["## Parts list (IPC extract) {#parts-list}", ""]
    rows.append("| P/N | Name | Qty | Unit mass |")
    rows.append("|---|---|---|---|")
    counts: dict[str, int] = {}
    parts: dict[str, PartSpec] = {}
    for device in ctx.ship.devices:
        part = ctx.part_of[device.id]
        counts[part.part_number] = counts.get(part.part_number, 0) + 1
        parts[part.part_number] = part
    for pn in sorted(counts):
        part = parts[pn]
        rows.append(f"| {pn} | {part.name} | {counts[pn]} | {part.mass_kg:g} kg |")
    return "\n".join(rows)


def generate_all(tree: ContentTree) -> dict[str, str]:
    """{relative path under data/manuals: content} for every ship, sorted."""
    return {
        f"wdm/24/generated/{tree.ships[qid].id}.md": generate_ship_wdm(tree, qid)
        for qid in sorted(tree.ships)
    }


def sync_generated(tree: ContentTree, *, check: bool) -> list[str]:
    """Write (or, with check=True, only detect) stale generated files.

    Returns the list of stale/updated relative paths; CI fails on non-empty
    in check mode (the ADR-0003 no-drift gate).
    """
    manuals_root = tree.root / "manuals"
    stale: list[str] = []
    for rel, text in generate_all(tree).items():
        path = manuals_root / rel
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != text:
            stale.append(rel)
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
    return stale
