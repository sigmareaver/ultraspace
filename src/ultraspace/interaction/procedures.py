"""Procedure runner: one engine, three users (ADR-0005).

Executes procedure/1 specs against a Simulation via the SCL dispatcher —
exactly the surface a player types at. The CI conformance suite calls this
headlessly; the crew-AI and player-interactive modes (M3) wrap the same loop.
Expectations read telemetry only: the runner experiences the ship like a
player (No God View holds in CI too).
"""

from __future__ import annotations

from dataclasses import dataclass

from ultraspace.content.schemas import ProcedureSpec, StepSpec
from ultraspace.interaction.scl import Dispatcher
from ultraspace.ship import Simulation
from ultraspace.ship.sim import DT_S

__all__ = ["ProcedureResult", "StepResult", "run_procedure"]


@dataclass(frozen=True, slots=True)
class StepResult:
    step: int
    ok: bool
    detail: str


@dataclass(frozen=True, slots=True)
class ProcedureResult:
    procedure_id: str
    passed: bool
    steps: list[StepResult]

    def failure_summary(self) -> str:
        failed = [s for s in self.steps if not s.ok]
        return "; ".join(f"step {s.step}: {s.detail}" for s in failed) or "all steps passed"


def run_procedure(sim: Simulation, proc: ProcedureSpec) -> ProcedureResult:
    dispatcher = Dispatcher(sim)
    sim.log.append(sim.clock.tick_index, "procedure", "start", {"id": proc.id})
    results: list[StepResult] = []
    for step in proc.steps:
        result = _run_step(sim, dispatcher, step)
        results.append(result)
        if not result.ok:
            break  # a real checklist holds at the failed step
    passed = all(r.ok for r in results) and len(results) == len(proc.steps)
    sim.log.append(
        sim.clock.tick_index, "procedure", "complete" if passed else "failed", {"id": proc.id}
    )
    return ProcedureResult(proc.id, passed, results)


def _run_step(sim: Simulation, dispatcher: Dispatcher, step: StepSpec) -> StepResult:
    if step.wait_s is not None:
        sim.step_s(step.wait_s)
        detail = f"waited {step.wait_s} s"
    else:
        assert step.scl is not None  # schema-validated
        result = dispatcher.execute_line(step.scl)
        if step.expect_refusal:
            if result.ok:
                return StepResult(step.step, False, f"expected refusal, got: {result.text}")
            detail = f"refused as expected: {result.text}"
        elif not result.ok:
            return StepResult(step.step, False, result.text)
        else:
            detail = result.text

    if step.expect_telemetry is not None:
        return _await_indication(sim, step, detail)
    return StepResult(step.step, True, detail)


def _await_indication(sim: Simulation, step: StepSpec, detail: str) -> StepResult:
    """Poll the expected indication (via telemetry only) until it holds or times out."""
    assert step.expect_telemetry is not None
    deadline_ticks = max(1, round(step.within_s / DT_S))
    value = float("nan")
    for _ in range(deadline_ticks):
        sim.step(1)
        item = sim.telemetry.read(step.expect_telemetry)
        if item is None:
            continue
        value = item.value
        low_ok = step.expect_min is None or value >= step.expect_min
        high_ok = step.expect_max is None or value <= step.expect_max
        if low_ok and high_ok:
            return StepResult(step.step, True, f"{detail}; {step.expect_telemetry}={value:.3f}")
    return StepResult(
        step.step,
        False,
        f"indication not met within {step.within_s} s: {step.expect_telemetry}={value:.3f} "
        f"(expected [{step.expect_min}, {step.expect_max}])",
    )
