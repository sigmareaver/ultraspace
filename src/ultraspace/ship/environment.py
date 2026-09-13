"""The ship's surroundings, as the ship experiences them.

The environment is an *input* to ship physics, written from above (the world
layer walks a scenario's timeline) and read below (the stress model). Keeping
it here rather than in `world` is what lets the ship compute hazard without
importing upward, and it matches how the ship actually knows about the
weather: not by being told, but by measuring it.

Everything here is SI (ADR-0004). Instruments convert to their calibrated
unit at the boundary — a particle monitor reads p/cm²·s because that is what
its face is printed in, and the conversion lives at the transducer.
"""

from __future__ import annotations

__all__ = ["CM2_PER_M2", "QUIET_FLUX_CM2S", "QUIET_FLUX_M2S", "Environment"]

#: 1 m² = 10⁴ cm². The single conversion factor for flux (ADR-0004 §6).
CM2_PER_M2 = 1.0e4

#: Galactic background: always there, effectively constant, very low.
#: A solar particle event runs three to five orders of magnitude above it,
#: which is why the hazard model needs no fudge factor to make one dramatic.
QUIET_FLUX_CM2S = 0.1
QUIET_FLUX_M2S = QUIET_FLUX_CM2S * CM2_PER_M2


class Environment:
    """Ambient conditions at the ship. Mutable; the world layer owns writes."""

    __slots__ = ("flux_m2s",)

    def __init__(self, flux_m2s: float = QUIET_FLUX_M2S) -> None:
        self.flux_m2s = flux_m2s
