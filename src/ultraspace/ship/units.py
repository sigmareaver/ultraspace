"""Serialized units and the ship's stores (failure-and-repair.md, MAINT v1).

Every fitted box is a unit with a serial, a part number, a position, powered
hours and a history. The registry is the authority on what is fitted where;
devices hold a reference to their own unit so a position can render its
nameplate without reaching back through the ship.

What a unit records and what the crew may read are deliberately different. The
fault state that came off with a board is kept here and written to the FDR for
review — it is never rendered to a player surface, because no instrument on
this ship has tested that board (No God View; MAINT 00-00 §4).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ultraspace.content.schemas import PartSpec, ShipSpec
from ultraspace.content.units import assign_serials

__all__ = ["Unit", "UnitEvent", "UnitRegistry"]


@dataclass(frozen=True, slots=True)
class UnitEvent:
    """One line of a unit's logbook page."""

    tick: int
    what: str  # "fitted" | "removed" | "installed"
    position: str


@dataclass(slots=True)
class Unit:
    serial: str
    part_id: str  # pack-qualified, the effectivity match
    part_number: str
    name: str
    position: str | None = None  # device id, or None while on shelf/bench
    hours_s: float = 0.0
    #: What came off with it. FDR-visible, never player-visible.
    fault_found: bool = False
    history: list[UnitEvent] = field(default_factory=list)


class UnitRegistry:
    """Fitted units, stores, and the bench, for one ship.

    Serials come from the content layer so the generated IPC sheet and the
    running ship cannot disagree about what this vessel carries.
    """

    def __init__(self, ship: ShipSpec, parts: dict[str, PartSpec]) -> None:
        serials = assign_serials(ship, parts)
        self.units: dict[str, Unit] = {}
        self.fitted: dict[str, Unit] = {}  # device id -> unit
        self.stores: dict[str, list[Unit]] = {}  # part id -> shelf, lowest serial first
        #: part id -> (part number, name), so an emptied shelf still has a label
        self.store_parts: dict[str, tuple[str, str]] = {}
        self.bench: list[Unit] = []
        self.open_positions: dict[str, int] = {}  # device id -> tick it was emptied

        for device in ship.devices:
            part = parts.get(device.part)
            if part is None or device.id not in serials.fitted:
                continue
            unit = self._make(serials.fitted[device.id], device.part, part)
            unit.position = device.id
            unit.history.append(UnitEvent(0, "fitted", device.id))
            self.fitted[device.id] = unit
        for part_id, shelf in serials.stores.items():
            part = parts[part_id]
            self.store_parts[part_id] = (part.part_number, part.name)
            self.stores[part_id] = [self._make(serial, part_id, part) for serial in shelf]

    def _make(self, serial: str, part_id: str, part: PartSpec) -> Unit:
        unit = Unit(serial, part_id, part.part_number, part.name)
        self.units[serial] = unit
        return unit

    # -- queries -------------------------------------------------------------

    def unit_at(self, device_id: str) -> Unit | None:
        return self.fitted.get(device_id)

    def on_shelf(self, part_id: str) -> int:
        return len(self.stores.get(part_id, []))

    # -- maintenance actions -------------------------------------------------

    def remove(self, device_id: str, tick: int, *, fault_found: bool) -> Unit:
        """Pull the fitted unit to the bench. Caller has cleared the interlock."""
        unit = self.fitted.pop(device_id)
        unit.position = None
        unit.fault_found = fault_found
        unit.history.append(UnitEvent(tick, "removed", device_id))
        self.bench.append(unit)
        self.open_positions[device_id] = tick
        return unit

    def install(self, device_id: str, part_id: str, tick: int) -> Unit | None:
        """Fit the lowest-serial spare of `part_id`; None when the shelf is empty."""
        shelf = self.stores.get(part_id)
        if not shelf:
            return None
        unit = shelf.pop(0)
        unit.position = device_id
        unit.history.append(UnitEvent(tick, "installed", device_id))
        self.fitted[device_id] = unit
        self.open_positions.pop(device_id, None)
        return unit

    def accrue(self, device_id: str, dt_s: float) -> None:
        unit = self.fitted.get(device_id)
        if unit is not None:
            unit.hours_s += dt_s
