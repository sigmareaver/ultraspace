"""Raw-state inspection and fault injection for tests and dev tools — the
ONLY No-God-View bypass.

Importing this module from presentation/world/interaction is forbidden
(Iron Law 2; mechanical enforcement via tools/check_imports.py at M1+).
tests/casualties/ may import ONLY `inject_fault` — to insert the fault;
every assertion there stays on telemetry, SCL, and panel observation
(testing.md class 5: inject F, then experience it like a player).
"""

from __future__ import annotations

from ultraspace.ship.devices import ElectricalDevice, HarnessElement, RemoteTerminal
from ultraspace.ship.sim import Simulation

__all__ = ["inject_fault", "raw_bus_voltage_v", "raw_device", "raw_power_audit_w"]

#: Fault modes the console knows (ata-42-data.md §6; grows with the stress model).
_FAULT_MODES = ("stuck_dominant", "dead", "open", "short")


def inject_fault(sim: Simulation, device_id: str, mode: str) -> None:
    """Fault-injection console: set fault state on a device and log it.

    Injection is journal-external (issuer `testing`, like an SCL command is
    `scl`) and never surfaces to the operator live — the player discovers
    the fault through symptoms; FDR review reconstructs the cause.
    """
    if mode not in _FAULT_MODES:
        raise ValueError(f"unknown fault mode {mode!r} (have {sorted(_FAULT_MODES)})")
    if device_id not in sim.devices:
        raise ValueError(f"unknown device {device_id!r}")
    device = sim.devices[device_id]
    if mode in ("open", "short"):
        if not isinstance(device, HarnessElement):
            raise ValueError(f"{device_id!r}: {mode} targets harness hardware (coupler/segment)")
        device.state = mode
    elif not isinstance(device, RemoteTerminal):
        raise ValueError(f"{device_id!r}: {mode} targets a remote terminal")
    elif mode == "stuck_dominant":
        device.stuck_dominant = True
    else:  # dead
        device.dead = True
    sim.log.append(
        sim.clock.tick_index,
        "testing",
        "fault-injected",
        {"device": device_id, "mode": mode},
    )


def raw_bus_voltage_v(sim: Simulation, node: str) -> float:
    """True node voltage, bypassing instrumentation."""
    return sim.net.voltage_v(node)


def raw_device(sim: Simulation, device_id: str) -> ElectricalDevice:
    """Direct device handle (state, currents) for assertions."""
    return sim.devices[device_id]


def raw_power_audit_w(sim: Simulation) -> tuple[float, float, float]:
    """(source_w, dissipated_w, stored_w) from the last tick."""
    return sim.power_audit_w()
