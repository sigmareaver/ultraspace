"""Raw-state inspection and fault injection for tests and dev tools — the
ONLY No-God-View bypass.

Importing this module from presentation/world/interaction is forbidden
(Iron Law 2; mechanical enforcement via tools/check_imports.py at M1+).
tests/casualties/ may import ONLY `inject_fault` — to insert the fault;
every assertion there stays on telemetry, SCL, and panel observation
(testing.md class 5: inject F, then experience it like a player).
"""

from __future__ import annotations

from ultraspace.ship.devices import ElectricalDevice
from ultraspace.ship.sim import Simulation

__all__ = ["inject_fault", "raw_bus_voltage_v", "raw_device", "raw_power_audit_w"]


def inject_fault(sim: Simulation, device_id: str, mode: str) -> None:
    """Fault-injection console: set fault state on a device and log it.

    A thin wrapper over `Simulation.apply_fault` — the same door the stress
    model and scenario scripts use (faults.py). What makes an injected fault
    an injected fault is the FDR issuer `testing`, nothing about the physics.

    Injection is journal-external (issuer `testing`, like an SCL command is
    `scl`) and never surfaces to the operator live — the player discovers
    the fault through symptoms; FDR review reconstructs the cause.
    """
    if device_id not in sim.devices:
        raise ValueError(f"unknown device {device_id!r}")
    sim.apply_fault(device_id, mode, by="testing")


def raw_bus_voltage_v(sim: Simulation, node: str) -> float:
    """True node voltage, bypassing instrumentation."""
    return sim.net.voltage_v(node)


def raw_device(sim: Simulation, device_id: str) -> ElectricalDevice:
    """Direct device handle (state, currents) for assertions."""
    return sim.devices[device_id]


def raw_power_audit_w(sim: Simulation) -> tuple[float, float, float]:
    """(source_w, dissipated_w, stored_w) from the last tick."""
    return sim.power_audit_w()
