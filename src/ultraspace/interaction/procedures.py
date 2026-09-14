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
from ultraspace.interaction.watch import watch
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
    target: str | None = None

    def failure_summary(self) -> str:
        failed = [s for s in self.steps if not s.ok]
        return "; ".join(f"step {s.step}: {s.detail}" for s in failed) or "all steps passed"


def run_procedure(
    sim: Simulation, proc: ProcedureSpec, target: str | None = None
) -> ProcedureResult:
    values = proc.target_values(target)
    if target is None and proc.targets:
        target = proc.targets[0].name  # the printed variant, named in the FDR
    dispatcher = Dispatcher(sim)
    sim.log.append(sim.clock.tick_index, "procedure", "start", {"id": proc.id, "target": target})
    results: list[StepResult] = []
    max_jumps = 2 * len(proc.steps)  # branch-loop guard: a tree, not a hamster wheel
    jumps = 0
    index = 0
    while 0 <= index < len(proc.steps):
        step = proc.steps[index].resolve(values)
        result, goto = _run_step(sim, dispatcher, step)
        results.append(result)
        if not result.ok:
            break  # a real checklist holds at the failed step
        if goto is None:
            index += 1
            continue
        jumps += 1
        if jumps > max_jumps:
            results.append(StepResult(step.step, False, "branch-loop guard tripped"))
            break
        if goto == 0:
            break  # verdict step: the tree terminated the checklist
        index = goto - 1  # steps are numbered 1..N in order (schema-validated)
    passed = bool(results) and all(r.ok for r in results)
    sim.log.append(
        sim.clock.tick_index,
        "procedure",
        "complete" if passed else "failed",
        {"id": proc.id, "target": target},
    )
    return ProcedureResult(proc.id, passed, results, target)


def _run_step(
    sim: Simulation, dispatcher: Dispatcher, step: StepSpec
) -> tuple[StepResult, int | None]:
    """Run one step; return its result and an optional branch target."""
    if step.wait_s is not None:
        detail = _watch(sim, step)
    else:
        assert step.scl is not None  # schema-validated
        result = dispatcher.execute_line(step.scl)
        if step.expect_refusal:
            if result.ok:
                return StepResult(step.step, False, f"expected refusal, got: {result.text}"), None
            detail = f"refused as expected: {result.text}"
        elif not result.ok:
            return StepResult(step.step, False, result.text), None
        else:
            detail = result.text

    if step.expect_text is not None:
        met = step.expect_text in detail
        indication = StepResult(
            step.step,
            met,
            f"{detail}\n[expect {step.expect_text!r}: {'met' if met else 'NOT MET'}]",
        )
    elif step.expect_telemetry is not None:
        indication = _await_indication(sim, step, detail)
    else:
        return StepResult(step.step, True, detail), None

    def label(target: int) -> str:
        return "end" if target == 0 else f"step {target}"

    if indication.ok and step.on_pass_goto is not None:
        target = step.on_pass_goto
        return (
            StepResult(step.step, True, f"{indication.detail}; branch to {label(target)}"),
            target,
        )
    if not indication.ok and step.on_fail_goto is not None:
        # The tree worked as designed: record the unmet indication as a
        # taken branch, not a hold.
        target = step.on_fail_goto
        return (
            StepResult(step.step, True, f"branch to {label(target)}: {indication.detail}"),
            target,
        )
    return indication, None


def _watch(sim: Simulation, step: StepSpec) -> str:
    """Run out a timed wait, watching (interaction/watch.py).

    Being interrupted is not a failed step — it is the ship talking over the
    checklist, which is its right. The next step is still offered; what changes
    is that the crew has been told, in the step result and in the FDR.
    """
    assert step.wait_s is not None
    result = watch(sim, step.wait_s, hold=step.hold_through_warning)
    said = ", ".join(result.warnings)
    if not result.interrupted:
        if result.warnings:
            return f"waited {step.wait_s} s — held through WARNING: {said} (step NOTE)"
        return f"waited {step.wait_s} s"
    sim.log.append(
        sim.clock.tick_index,
        "procedure",
        "wait-interrupted",
        {
            "step": step.step,
            "remaining_s": result.remaining_s,
            "messages": result.warnings,
        },
    )
    return (
        f"waited {result.elapsed_s:.1f} s of {step.wait_s} s — INTERRUPTED by "
        f"WARNING: {said} ({result.remaining_s:.1f} s of the wait remaining)"
    )


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
