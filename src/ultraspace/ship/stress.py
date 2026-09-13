"""The stress model: why things break here and now (failure-and-repair.md).

Each (device, fault mode) pair with a declared hazard owns one RNG stream,
`fault/<device>/<mode>`, and that stream is drawn **exactly once per tick,
unconditionally** — before anything is checked about whether the fault could
happen. Drawing only for eligible devices would let a breaker position shift
the sequence, and a recorded session would stop replaying. The world rolls its
dice whether or not they can matter; only the comparison afterwards cares.

v1 implements two factors and names the rest (each lands with the system that
produces its input):

    rate_per_s = base_rate_per_s * f_env * f_rail
    f_env  = (flux_m2s / QUIET_FLUX_M2S) ** radiation
    f_rail = 1.0 energized, 0.0 unpowered (declared per mode: a latch-up is a
             parasitic conduction path, and it needs a rail to conduct)
"""

from __future__ import annotations

from dataclasses import dataclass

from ultraspace.content.schemas import HazardSpec
from ultraspace.kernel import TICK_US, EventLog, RngHub
from ultraspace.ship.devices import DataDevice, ElectricalDevice
from ultraspace.ship.environment import CM2_PER_M2, QUIET_FLUX_M2S, Environment
from ultraspace.ship.faults import apply_fault

__all__ = ["Hazard", "StressModel"]

#: A tick's onset probability is capped well below 1: a rate that would fire
#: every tick is a content error, and silently saturating would hide it.
MAX_TICK_PROBABILITY = 0.5

_SECONDS_PER_HOUR = 3600.0
_DT_S = TICK_US / 1_000_000


@dataclass(frozen=True, slots=True)
class Hazard:
    """One device's susceptibility to one fault mode."""

    device: ElectricalDevice
    mode: str
    base_rate_per_s: float
    radiation: float
    needs_rail: bool

    @classmethod
    def build(cls, device: ElectricalDevice, mode: str, spec: HazardSpec) -> Hazard:
        return cls(
            device=device,
            mode=mode,
            base_rate_per_s=spec.rate_per_h / _SECONDS_PER_HOUR,
            radiation=spec.radiation,
            needs_rail=spec.needs_rail,
        )

    def rate_per_s(self, environment: Environment) -> float:
        """Hazard rate under current conditions, in per-second."""
        if self.needs_rail:
            # Schema-validated: `needs_rail` is only allowed on power-gated
            # behaviors (content.schemas.RAIL_GATED), which are DataDevices.
            assert isinstance(self.device, DataDevice)
            if not self.device.energized:
                return 0.0
        f_env = float((environment.flux_m2s / QUIET_FLUX_M2S) ** self.radiation)
        return self.base_rate_per_s * f_env


class StressModel:
    """Per-tick fault onset over a ship's hazards (Phase.FAULTS)."""

    def __init__(
        self,
        hazards: list[Hazard],
        rng: RngHub,
        environment: Environment,
        log: EventLog,
    ) -> None:
        self.hazards = hazards  # blueprint order (determinism, ADR-0002 §3)
        self._environment = environment
        self._log = log
        self._streams = [rng.stream(f"fault/{h.device.id}/{h.mode}") for h in hazards]

    def tick(self, tick: int) -> None:
        for hazard, stream in zip(self.hazards, self._streams, strict=True):
            roll = stream.random()  # unconditional: see the module docstring
            rate_per_s = hazard.rate_per_s(self._environment)
            probability = min(rate_per_s * _DT_S, MAX_TICK_PROBABILITY)
            if roll >= probability or not apply_fault(hazard.device, hazard.mode):
                continue
            self._log.append(
                tick,
                hazard.device.id,
                "fault-onset",
                {
                    # The causal chain, in full: a fault with no cause record
                    # is a bug, not a mystery (failure-and-repair.md).
                    "mode": hazard.mode,
                    "by": "stress",
                    "flux_cm2s": round(self._environment.flux_m2s / CM2_PER_M2, 4),
                    "rate_per_s": f"{rate_per_s:.3e}",
                    "roll": round(roll, 9),
                },
            )
