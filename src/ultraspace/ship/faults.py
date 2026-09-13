"""Fault application: the one door every fault comes through.

The stress model, scenario scripts, and the test-only injection console all
call the same function, so an emergent casualty and an authored one are
indistinguishable downstream — to the physics, to the instruments, and to the
player. The FDR is the only place they differ, and only because it records
*who* opened the door (failure-and-repair.md: zero unexplainable faults).
"""

from __future__ import annotations

from ultraspace.ship.devices import ElectricalDevice, HarnessElement, RemoteTerminal

__all__ = ["FAULT_MODES", "apply_fault"]

#: Fault modes the ship knows (ata-42-data.md §6; grows with the stress model).
FAULT_MODES = ("stuck_dominant", "dead", "open", "short")


def apply_fault(device: ElectricalDevice, mode: str) -> bool:
    """Put ``device`` into fault ``mode``; return whether the state changed.

    Re-applying a mode the device is already in is a no-op, not an error: a
    hazard that fires twice on a latched board has simply not learned anything
    new, and the ledger should not pretend otherwise.
    """
    if mode not in FAULT_MODES:
        raise ValueError(f"unknown fault mode {mode!r} (have {sorted(FAULT_MODES)})")
    if mode in ("open", "short"):
        if not isinstance(device, HarnessElement):
            raise ValueError(f"{device.id!r}: {mode} targets harness hardware (coupler/segment)")
        changed = device.state != mode
        device.state = mode
        return changed
    if not isinstance(device, RemoteTerminal):
        raise ValueError(f"{device.id!r}: {mode} targets a remote terminal")
    if mode == "stuck_dominant":
        changed = not device.stuck_dominant
        device.stuck_dominant = True
        return changed
    changed = not device.dead
    device.dead = True
    return changed
