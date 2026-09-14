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
from ultraspace.content.schemas import DataBusSpec, DeviceSpec, PartSpec, ShipSpec
from ultraspace.content.units import assign_serials

__all__ = [
    "generate_all",
    "generate_ship_ipc",
    "generate_ship_wdm",
    "generate_ship_wdm42",
    "sync_generated",
]

_SWITCHING = ("contactor", "breaker", "precharge")
_XDUCERS = ("xducer_v", "xducer_i", "xducer_soc")
_LOADS = ("load", "bc", "rt")  # constant-resistance electrical loads (ata-42 §9)
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
    if part.behavior in ("bc", "rt"):
        return f"data {part.behavior} {p['r_ohm']:g} ohm"
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


def _connection_items(ctx: _Ctx, node: str) -> tuple[str | None, list[str]]:
    """(shared-port prefix or None, connection items in blueprint order).

    device.port pairs; a homogeneous port factors out as a prefix
    (``neg: bat1, …``) — the 92-column budget wins over uniformity
    (style guide, wire list rule)."""
    conns = ctx.on_node.get(node, [])
    ports = {port for _, port in conns}
    if conns and len(ports) == 1:
        return ports.pop(), [d.id for d, _ in conns]
    return None, [f"{d.id}.{p}" for d, p in conns]


def _wire_rows(ctx: _Ctx, node: str, cap: str, *, label: str | None = None) -> list[str]:
    """Table rows for one node, splitting connections across continuation
    rows (marked ``↳``) at item boundaries when the budget demands — never
    mid-item (style guide, wire list rule)."""
    name = label if label is not None else node
    prefix, items = _connection_items(ctx, node)
    cell_prefix = f"{prefix}: " if prefix is not None else ""
    chunks: list[str] = []
    body = ""
    for item in items:
        candidate = f"{body}, {item}" if body else item
        if body and len(f"| {name} | {cap} | {cell_prefix}{candidate} |") > _MAX_WIDTH:
            chunks.append(body)
            body = item
        else:
            body = candidate
    chunks.append(body)
    rows = []
    for i, chunk in enumerate(chunks):
        row = f"| {name if i == 0 else f'{name} ↳'} | {cap} | {cell_prefix}{chunk} |"
        if len(row) > _MAX_WIDTH:
            raise ValueError(f"generated line exceeds {_MAX_WIDTH} cols: {row!r}")
        rows.append(row)
    return rows


def _wire_list(ctx: _Ctx) -> str:
    rows = ["## Wire list {#wire-list}", ""]
    rows.append("| Node | Capacitance | Connections (device.port) |")
    rows.append("|---|---|---|")
    for node in ctx.ship.nodes:
        rows.extend(_wire_rows(ctx, node.id, f"{node.c_f * 1000:g} mF"))
    rows.extend(_wire_rows(ctx, GROUND_NODE, "-", label="gnd (ref)"))
    return "\n".join(rows)


def _load_list(ctx: _Ctx) -> str:
    rows = ["## Load list {#load-list}", ""]
    rows.append("| Device | P/N | Name | R | I @ 28 V | Protected by |")
    rows.append("|---|---|---|---|---|---|")
    for device in ctx.ship.devices:
        part = ctx.part_of[device.id]
        if part.behavior not in _LOADS:
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
    rows.append("| Telemetry ID | P/N | Measures | Unit | SCL | Reported via |")
    rows.append("|---|---|---|---|---|---|")
    units = {"xducer_v": "V", "xducer_i": "A", "xducer_soc": "frac"}
    for device in ctx.ship.devices:
        part = ctx.part_of[device.id]
        if part.behavior not in _XDUCERS:
            continue
        # Carriage is wiring, so it belongs on the wiring sheet: it is the
        # difference between a reading that can go stale and one that cannot
        # (ata-42-data.md §4, FIM 42-14).
        via = f"`{device.carried_by}`" if device.carried_by else "panel-wired"
        rows.append(
            f"| {device.id} | {part.part_number} | {device.measures} "
            f"| {units[part.behavior]} | `{device.scl or '-'}` | {via} |"
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


def generate_ship_wdm42(tree: ContentTree, ship_qid: str) -> str:
    """WDM 42 — data-harness sheet: trunk order, stub taps, probe points.

    This is the isolation map FIM 42-12 references; connectivity is always
    generated truth (style guide), walked from the same blueprint the sim
    assembles.
    """
    ship = tree.ships[ship_qid]
    sections = [
        _HEADER.format(ship_dir=ship.id),
        f"# WDM 42 — Generated Data Sheets — {ship.name} ({ship_qid})",
        *(_bus_sheet(tree, ship, bus) for bus in ship.data_buses),
    ]
    text = "\n\n".join(sections) + "\n"
    for line in text.splitlines():
        if len(line) > _MAX_WIDTH:
            raise ValueError(f"generated line exceeds {_MAX_WIDTH} cols: {line!r}")
    return text


def _bus_sheet(tree: ContentTree, ship: ShipSpec, bus: DataBusSpec) -> str:
    members: dict[str, str] = {}  # device id -> behavior
    segments: list[tuple[str, str, str]] = []  # (segment id, end a, end b)
    for device in ship.devices:
        if device.data_bus != bus.id:
            continue
        part = tree.parts[device.part]
        members[device.id] = part.behavior
        if part.behavior == "harness_seg":
            segments.append((device.id, device.ends["a"], device.ends["b"]))
    bc = next(d for d, behavior in members.items() if behavior == "bc")
    junctions = sorted(d for d, behavior in members.items() if behavior == "junction")

    chain = [bc]  # trunk walk: BC outward, trunk segments only (linear by §9)
    done: set[str] = set()
    here = bc
    while True:
        onward = [
            (seg, b if a == here else a)
            for seg, a, b in segments
            if seg not in done and here in (a, b) and members[b if a == here else a] != "rt"
        ]
        if not onward:
            break
        seg, here = onward[0]
        done.add(seg)
        chain.extend([seg, here])

    def rt_label(rt_id: str) -> str:
        device = next(d for d in ship.devices if d.id == rt_id)
        return f"RT {device.params['rt_address']:g} ({rt_id})"

    taps = [
        f"{j} → {seg} → {rt_label(rt)}"
        for seg, a, b in segments
        for rt, j in ((a, b), (b, a))
        if members.get(rt) == "rt"
    ]
    lines = [
        f"## Data bus {bus.name} {{#bus-{bus.id}}}",
        "",
        f"Termination: {bus.termination_ohm:g} ohm at both ends (BC end and far end).",
        "Stubs: transformer-coupled — a stub fault is contained to its terminal.",
        "",
        "```",
        f"Trunk order (from the BC): {' — '.join(chain)} — (end)",
        f"Stub taps: {'; '.join(taps)}",
        f"DMM probe points (de-energized bus only): {', '.join(junctions)}",
        "```",
    ]
    return "\n".join(lines)


def generate_ship_ipc(tree: ContentTree, ship_qid: str) -> str:
    """IPC — what is fitted where, by serial, and what is on the shelf.

    The catalog MAINT refuses against (failure-and-repair.md, MAINT v1). It is
    generated from the same blueprint the registry serializes, so the sheet
    cannot promise a spare the ship does not carry, and the serial printed here
    is the serial the crew reads off the nameplate.
    """
    ship = tree.ships[ship_qid]
    serials = assign_serials(ship, tree.parts)
    sections = [
        _HEADER.format(ship_dir=ship.id),
        f"# IPC — Generated Parts Catalog — {ship.name} ({ship_qid})",
        _fitted_units(tree, ship, serials.fitted),
        _stores(tree, ship, serials.stores),
        _part_numbers(tree, ship),
    ]
    text = "\n\n".join(sections) + "\n"
    for line in text.splitlines():
        if len(line) > _MAX_WIDTH:
            raise ValueError(f"generated line exceeds {_MAX_WIDTH} cols: {line!r}")
    return text


def _fitted_units(tree: ContentTree, ship: ShipSpec, fitted: dict[str, str]) -> str:
    rows = ["## Fitted units {#fitted}", ""]
    rows.append("| Position | SCL | P/N | Serial |")
    rows.append("|---|---|---|---|")
    for device in ship.devices:
        part = tree.parts[device.part]
        rows.append(
            f"| {device.id} | `{device.scl or '-'}` | {part.part_number} | {fitted[device.id]} |"
        )
    return "\n".join(rows)


def _stores(tree: ContentTree, ship: ShipSpec, stores: dict[str, list[str]]) -> str:
    """Shelf contents as a serial *range*: a stocked kit must never wrap."""
    rows = ["## Stores {#stores}", ""]
    if not ship.spares:
        return "\n".join([*rows, "No spares carried."])
    rows.append("| P/N | Name | On shelf | Serials |")
    rows.append("|---|---|---|---|")
    for spare in ship.spares:
        part = tree.parts[spare.part]
        serials = stores[spare.part]
        span = serials[0] if len(serials) == 1 else f"{serials[0]} .. /{serials[-1].split('/')[1]}"
        rows.append(f"| {part.part_number} | {part.name} | {len(serials)} | {span} |")
    return "\n".join(rows)


def _part_numbers(tree: ContentTree, ship: ShipSpec) -> str:
    rows = ["## Part numbers {#part-numbers}", ""]
    rows.append("| P/N | Name | ATA | TL | Unit mass | Fitted | Spare |")
    rows.append("|---|---|---|---|---|---|---|")
    fitted_counts: dict[str, int] = {}
    parts: dict[str, PartSpec] = {}
    for device in ship.devices:
        part = tree.parts[device.part]
        fitted_counts[part.part_number] = fitted_counts.get(part.part_number, 0) + 1
        parts[part.part_number] = part
    spare_counts: dict[str, int] = {}
    for spare in ship.spares:
        part = tree.parts[spare.part]
        spare_counts[part.part_number] = spare_counts.get(part.part_number, 0) + spare.qty
        parts.setdefault(part.part_number, part)
    for pn in sorted(parts):
        part = parts[pn]
        rows.append(
            f"| {pn} | {part.name} | {part.ata} | {part.tech_level} | {part.mass_kg:g} kg "
            f"| {fitted_counts.get(pn, 0)} | {spare_counts.get(pn, 0)} |"
        )
    return "\n".join(rows)


def generate_all(tree: ContentTree) -> dict[str, str]:
    """{relative path under data/manuals: content} for every ship, sorted."""
    out: dict[str, str] = {}
    for qid in sorted(tree.ships):
        ship = tree.ships[qid]
        out[f"wdm/24/generated/{ship.id}.md"] = generate_ship_wdm(tree, qid)
        if ship.data_buses:
            out[f"wdm/42/generated/{ship.id}.md"] = generate_ship_wdm42(tree, qid)
        out[f"ipc/generated/{ship.id}.md"] = generate_ship_ipc(tree, qid)
    return out


def sync_generated(tree: ContentTree, *, check: bool) -> list[str]:
    """Write (or, with check=True, only detect) stale generated files.

    Returns the list of stale/updated relative paths; CI fails on non-empty
    in check mode (the ADR-0003 no-drift gate).
    """
    manuals_root = tree.root / "manuals"
    stale: list[str] = []
    for rel, text in generate_all(tree).items():
        path = manuals_root / rel
        existing = path.read_text(encoding="utf-8") if path.exists() else None
        if existing != text:
            stale.append(rel)
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
    return stale
