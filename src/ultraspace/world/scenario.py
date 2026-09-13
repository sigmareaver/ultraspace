"""Scenario playback: the authored situation, walked one tick at a time.

A scenario is ordinary content (`scenario/1`, data-model.md): an environment
timeline and any faults the author places by hand. This module is the only
thing that writes the ship's environment, and it does so in the WORLD phase —
*after* the ship has read it for this tick. The ship therefore acts on the
environment as of the previous tick, a deliberate 100 ms lag that keeps the
layering honest (the world never reaches down into a half-finished tick) and
is four orders of magnitude below anything a solar event does.

Scripted faults enter through `Simulation.apply_fault`, the same door the
stress model uses. A drill and an emergent casualty are indistinguishable to
the physics, the instruments and the player; only the FDR knows which it was.
"""

from __future__ import annotations

from itertools import pairwise

from ultraspace.content.schemas import ScenarioSpec
from ultraspace.kernel import Phase
from ultraspace.ship import Simulation
from ultraspace.ship.environment import CM2_PER_M2, QUIET_FLUX_M2S

__all__ = ["ScenarioRun"]


class ScenarioRun:
    """One scenario bound to one simulation."""

    def __init__(self, spec: ScenarioSpec, sim: Simulation) -> None:
        self.spec = spec
        self._sim = sim
        self._points_m2s = [(p.at_s, p.flux_cm2s * CM2_PER_M2) for p in spec.environment]
        self._next_fault = 0
        sim.environment.flux_m2s = self._flux_at_m2s(0.0)
        sim.scheduler.register(Phase.WORLD, f"scenario/{spec.id}", self._tick)

    def _flux_at_m2s(self, elapsed_s: float) -> float:
        """Linear interpolation over the timeline; flat outside its ends.

        A step function would be a lie the monitor could see: real events ramp
        over minutes and decay over hours, and the ramp is what gives the crew
        the chance to act that the whole procedure depends on.
        """
        points = self._points_m2s
        if not points:
            return QUIET_FLUX_M2S
        if elapsed_s <= points[0][0]:
            return points[0][1]
        for (t0_s, flux0_m2s), (t1_s, flux1_m2s) in pairwise(points):
            if elapsed_s <= t1_s:
                span_s = t1_s - t0_s
                fraction = (elapsed_s - t0_s) / span_s if span_s > 0.0 else 1.0
                return flux0_m2s + fraction * (flux1_m2s - flux0_m2s)
        return points[-1][1]

    def _tick(self, tick: int) -> None:
        elapsed_s = self._sim.clock.now_s
        self._sim.environment.flux_m2s = self._flux_at_m2s(elapsed_s)
        while self._next_fault < len(self.spec.faults):
            fault = self.spec.faults[self._next_fault]
            if fault.at_s > elapsed_s:
                break
            self._next_fault += 1
            self._sim.apply_fault(fault.device, fault.mode, by="scenario")
