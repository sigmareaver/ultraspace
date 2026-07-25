"""Content tree loader and cross-reference validator.

Load-time failure philosophy (architecture.md): every content problem is
reported with file context here; nothing content-related may fail at tick time.
Files are visited in sorted path order (determinism: content hash and load
order are stable).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import ValidationError

from ultraspace.content.schemas import (
    REQUIRED_PORTS,
    DeviceSpec,
    PartSpec,
    ProcedureSpec,
    ShipSpec,
)

__all__ = ["ContentError", "ContentTree", "load_tree"]

PACK = "core"  # M1: single built-in pack; packs/ namespacing lands with mod support
GROUND_NODE = "gnd"

#: Behaviors that publish telemetry without a `measures` field (BC health).
_TELEMETRY_BEHAVIORS = ("bc",)

_SCHEMAS: dict[str, type[PartSpec] | type[ShipSpec] | type[ProcedureSpec]] = {
    "part/1": PartSpec,
    "ship/1": ShipSpec,
    "procedure/1": ProcedureSpec,
}


@dataclass(frozen=True, slots=True)
class ContentError:
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


@dataclass(slots=True)
class ContentTree:
    root: Path
    parts: dict[str, PartSpec] = field(default_factory=dict)
    ships: dict[str, ShipSpec] = field(default_factory=dict)
    procedures: dict[str, ProcedureSpec] = field(default_factory=dict)
    errors: list[ContentError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def load_tree(root: Path) -> ContentTree:
    """Load and validate every ``*.yaml`` content file under ``root``."""
    tree = ContentTree(root=root)
    for path in sorted(root.rglob("*.yaml")):
        _load_file(tree, path)
    _validate_refs(tree)
    return tree


def _load_file(tree: ContentTree, path: Path) -> None:
    rel = str(path.relative_to(tree.root))
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        tree.errors.append(ContentError(rel, f"YAML parse error: {exc}"))
        return
    if not isinstance(raw, dict) or "schema" not in raw:
        tree.errors.append(ContentError(rel, "missing top-level 'schema' key"))
        return
    schema = raw["schema"]
    if schema not in _SCHEMAS:
        tree.errors.append(ContentError(rel, f"unknown schema {schema!r}"))
        return
    try:
        spec: PartSpec | ShipSpec | ProcedureSpec = _SCHEMAS[schema].model_validate(raw)
    except ValidationError as exc:
        tree.errors.append(ContentError(rel, f"schema violation: {exc}"))
        return

    qualified = f"{PACK}:{spec.id}"
    duplicate = False
    if isinstance(spec, PartSpec):
        duplicate = qualified in tree.parts
        tree.parts.setdefault(qualified, spec)
    elif isinstance(spec, ShipSpec):
        duplicate = qualified in tree.ships
        tree.ships.setdefault(qualified, spec)
    else:
        duplicate = qualified in tree.procedures
        tree.procedures.setdefault(qualified, spec)
    if duplicate:
        tree.errors.append(ContentError(rel, f"duplicate id {qualified!r}"))


def _validate_refs(tree: ContentTree) -> None:
    for ship_id, ship in sorted(tree.ships.items()):
        _validate_ship_refs(tree, ship_id, ship)
    _validate_procedure_refs(tree)


def _validate_ship_refs(tree: ContentTree, ship_id: str, ship: ShipSpec) -> None:
    node_ids = {node.id for node in ship.nodes} | {GROUND_NODE}
    device_ids = {device.id for device in ship.devices}
    bus_ids = {bus.id for bus in ship.data_buses}
    where = f"ship {ship_id}"

    def err(message: str) -> None:
        tree.errors.append(ContentError(where, message))

    if len(node_ids) - 1 != len(ship.nodes):
        err("duplicate node ids")
    if len(device_ids) != len(ship.devices):
        err("duplicate device ids")
    if len(bus_ids) != len(ship.data_buses):
        err("duplicate data bus ids")

    for device in ship.devices:
        part = tree.parts.get(device.part)
        if part is None:
            err(f"device {device.id!r}: unknown part {device.part!r}")
            continue
        _validate_device_refs(err, device, part.behavior, node_ids, device_ids)

    _validate_data_bus_refs(err, ship, bus_ids, tree)

    for ann in ship.annunciators:
        if ann.telemetry not in device_ids:
            err(f"annunciator {ann.id!r}: unknown telemetry source {ann.telemetry!r}")


_DATA_BEHAVIORS = ("bc", "rt", "junction", "harness_seg")


@dataclass
class _DataBusAcc:
    """Accumulators for data-bus cross-validation (per-bus keyed dicts)."""

    bcs_per_bus: dict[str, int]
    rt_addresses: dict[str, set[int]]
    members: dict[str, dict[str, str]]
    segments: dict[str, list[tuple[str, str]]]


def _validate_data_bus_refs(
    err: Callable[[str], None],
    ship: ShipSpec,
    bus_ids: set[str],
    tree: ContentTree,
) -> None:
    """ata-42-data.md §9: one BC per bus; RT addresses unique per bus, 0-31;
    harness ends resolve to bus members; every member reachable from the BC."""
    acc = _DataBusAcc(
        bcs_per_bus=dict.fromkeys(bus_ids, 0),
        rt_addresses={bus_id: set() for bus_id in bus_ids},
        members={bus_id: {} for bus_id in bus_ids},
        segments={bus_id: [] for bus_id in bus_ids},
    )
    for device in ship.devices:
        part = tree.parts.get(device.part)
        if part is None:
            continue  # unknown part already reported
        _accumulate_data_device(err, device, part, bus_ids, acc)
    for bus_id in sorted(bus_ids):
        count = acc.bcs_per_bus[bus_id]
        if count != 1:
            err(f"data bus {bus_id!r}: needs exactly one BC, has {count}")
        _validate_bus_connectivity(err, bus_id, acc.members[bus_id], acc.segments[bus_id])


def _accumulate_data_device(
    err: Callable[[str], None],
    device: DeviceSpec,
    part: PartSpec,
    bus_ids: set[str],
    acc: _DataBusAcc,
) -> None:
    if part.behavior not in _DATA_BEHAVIORS:
        if device.data_bus is not None:
            err(f"device {device.id!r}: 'data_bus' invalid for behavior {part.behavior}")
        return
    if device.data_bus is None:
        err(f"device {device.id!r} ({part.behavior}): missing 'data_bus'")
        return
    if device.data_bus not in bus_ids:
        err(f"device {device.id!r}: unknown data bus {device.data_bus!r}")
        return
    acc.members[device.data_bus][device.id] = part.behavior
    if part.behavior == "bc":
        acc.bcs_per_bus[device.data_bus] += 1
    elif part.behavior == "rt":
        _validate_rt_address(err, device, acc.rt_addresses[device.data_bus])
    elif part.behavior == "junction":
        if device.ends:
            err(f"junction {device.id!r}: couplers take no 'ends'")
    elif set(device.ends) != {"a", "b"}:  # harness_seg
        err(f"harness {device.id!r}: needs ends {{a, b}}")
    else:
        acc.segments[device.data_bus].append((device.ends["a"], device.ends["b"]))


def _validate_rt_address(err: Callable[[str], None], device: DeviceSpec, seen: set[int]) -> None:
    raw_address = device.params.get("rt_address")
    if raw_address is None or not raw_address.is_integer() or not 0 <= raw_address <= 31:
        err(f"rt {device.id!r}: params.rt_address must be an integer in 0..31")
        return
    address = int(raw_address)
    if address in seen:
        err(f"rt {device.id!r}: address {address} already used on {device.data_bus}")
    seen.add(address)


def _validate_bus_connectivity(
    err: Callable[[str], None],
    bus_id: str,
    members: dict[str, str],
    segments: list[tuple[str, str]],
) -> None:
    adjacency: dict[str, set[str]] = {}
    for a, b in segments:
        for end in (a, b):
            if end not in members:
                err(f"harness end {end!r} is not a member of data bus {bus_id!r}")
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)
    bcs = sorted(d for d, behavior in members.items() if behavior == "bc")
    rts = sorted(d for d, behavior in members.items() if behavior == "rt")
    for bc in bcs:
        seen = {bc}
        stack = [bc]
        while stack:
            here = stack.pop()
            for other in adjacency.get(here, ()):
                if other not in seen:
                    seen.add(other)
                    stack.append(other)
        for rt in rts:
            if rt not in seen:
                err(f"rt {rt!r} is not reachable from bc {bc!r} on data bus {bus_id!r}")


def _validate_device_refs(
    err: Callable[[str], None],
    device: DeviceSpec,
    behavior: str,
    node_ids: set[str],
    device_ids: set[str],
) -> None:
    required_ports = REQUIRED_PORTS[behavior]
    if set(device.ports) != set(required_ports):
        err(
            f"device {device.id!r} ({behavior}): ports {sorted(device.ports)} "
            f"!= required {sorted(required_ports)}"
        )
    for port, node in sorted(device.ports.items()):
        if node not in node_ids:
            err(f"device {device.id!r} port {port!r}: unknown node {node!r}")
    if behavior == "xducer_v":
        if device.measures not in node_ids:
            err(f"xducer {device.id!r}: measures unknown node {device.measures!r}")
    elif behavior in ("xducer_i", "xducer_soc"):
        if device.measures not in device_ids:
            err(f"xducer {device.id!r}: measures unknown device {device.measures!r}")
    elif device.measures is not None:
        err(f"device {device.id!r}: 'measures' invalid for behavior {behavior}")
    if device.interlock_open is not None and device.interlock_open not in device_ids:
        err(f"device {device.id!r}: interlock_open references unknown {device.interlock_open!r}")


def _validate_procedure_refs(tree: ContentTree) -> None:
    for proc_id, proc in sorted(tree.procedures.items()):
        pwhere = f"procedure {proc_id}"
        ship = tree.ships.get(proc.ship)
        if ship is None:
            tree.errors.append(ContentError(pwhere, f"unknown ship {proc.ship!r}"))
            continue
        source_ids = {
            device.id
            for device in ship.devices
            if device.measures is not None
            or (
                (part := tree.parts.get(device.part)) is not None
                and part.behavior in _TELEMETRY_BEHAVIORS
            )
        }
        for step in proc.steps:
            if step.expect_telemetry is not None and step.expect_telemetry not in source_ids:
                tree.errors.append(
                    ContentError(
                        pwhere,
                        f"step {step.step}: unknown telemetry {step.expect_telemetry!r}",
                    )
                )
