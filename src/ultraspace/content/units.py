"""Serial-number assignment for fitted hardware and stores (MAINT v1).

Identity is *derived*, not authored: ``<part number>/<NNNN>`` numbered per part
number in blueprint order, with spares continuing the same sequence — serials
are issued at manufacture, not at fitting. Deriving costs no authoring and no
content churn, at one known price: inserting a device earlier in a blueprint
renumbers the ones after it, which "IDs are forever" (ADR-0001) does not permit
for saved campaigns. The escape hatch is an authored serial on the blueprint
with this as the fallback, and it lands with persistence (failure-and-repair.md,
MAINT v1).

This lives in the content layer because the generated IPC sheet and the ship's
unit registry must agree by construction, and the sheet is built without a ship.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ultraspace.content.schemas import PartSpec, ShipSpec

__all__ = ["ShipSerials", "assign_serials", "format_serial"]


def format_serial(part_number: str, index: int) -> str:
    """``42-110-001`` + 3 -> ``42-110-001/0003`` (1-based, zero-padded)."""
    return f"{part_number}/{index:04d}"


@dataclass(frozen=True, slots=True)
class ShipSerials:
    """Every serial this blueprint issues, fitted and on the shelf."""

    fitted: dict[str, str] = field(default_factory=dict)  # device id -> serial
    stores: dict[str, list[str]] = field(default_factory=dict)  # part id -> serials


def assign_serials(ship: ShipSpec, parts: dict[str, PartSpec]) -> ShipSerials:
    """Blueprint order for fitted units, then the stores lines in order.

    A device whose part is unknown is skipped rather than guessed at: the
    loader has already reported it, and a serial invented here would outlive
    the error message.
    """
    issued: dict[str, int] = {}  # part number -> last index used
    fitted: dict[str, str] = {}
    for device in ship.devices:
        part = parts.get(device.part)
        if part is None:
            continue
        issued[part.part_number] = issued.get(part.part_number, 0) + 1
        fitted[device.id] = format_serial(part.part_number, issued[part.part_number])

    stores: dict[str, list[str]] = {}
    for spare in ship.spares:
        part = parts.get(spare.part)
        if part is None:
            continue
        serials = stores.setdefault(spare.part, [])
        for _ in range(spare.qty):
            issued[part.part_number] = issued.get(part.part_number, 0) + 1
            serials.append(format_serial(part.part_number, issued[part.part_number]))
    return ShipSerials(fitted, stores)
