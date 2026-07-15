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
    where = f"ship {ship_id}"

    def err(message: str) -> None:
        tree.errors.append(ContentError(where, message))

    if len(node_ids) - 1 != len(ship.nodes):
        err("duplicate node ids")
    if len(device_ids) != len(ship.devices):
        err("duplicate device ids")

    for device in ship.devices:
        part = tree.parts.get(device.part)
        if part is None:
            err(f"device {device.id!r}: unknown part {device.part!r}")
            continue
        _validate_device_refs(err, device, part.behavior, node_ids, device_ids)

    for ann in ship.annunciators:
        if ann.telemetry not in device_ids:
            err(f"annunciator {ann.id!r}: unknown telemetry source {ann.telemetry!r}")


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
        xducer_ids = {d.id for d in ship.devices if d.measures is not None}
        for step in proc.steps:
            if step.expect_telemetry is not None and step.expect_telemetry not in xducer_ids:
                tree.errors.append(
                    ContentError(
                        pwhere,
                        f"step {step.step}: unknown telemetry {step.expect_telemetry!r}",
                    )
                )
