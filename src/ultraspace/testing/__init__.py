"""Raw-state inspection for tests and dev tools — the ONLY No-God-View bypass.

Importing this module from presentation/world/interaction is forbidden
(Iron Law 2; mechanical enforcement via tools/check_imports.py at M1+).
tests/casualties/ must not use it either: those tests experience faults
through telemetry, like a player.
"""

from __future__ import annotations

from ultraspace.ship.devices import ElectricalDevice
from ultraspace.ship.sim import Simulation

__all__ = ["raw_bus_voltage_v", "raw_device", "raw_power_audit_w"]


def raw_bus_voltage_v(sim: Simulation, node: str) -> float:
    """True node voltage, bypassing instrumentation."""
    return sim.net.voltage_v(node)


def raw_device(sim: Simulation, device_id: str) -> ElectricalDevice:
    """Direct device handle (state, currents) for assertions."""
    return sim.devices[device_id]


def raw_power_audit_w(sim: Simulation) -> tuple[float, float, float]:
    """(source_w, dissipated_w, stored_w) from the last tick."""
    return sim.power_audit_w()
