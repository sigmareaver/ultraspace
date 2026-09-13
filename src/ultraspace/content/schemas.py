"""Pydantic schemas for authored content (`schema: <name>/<version>` files).

Content files use natural authoring units declared by schema-defined keys
(ADR-0004 §4); everything is converted to SI at the model boundary. All models
forbid unknown fields — typos are build errors, not silent defaults.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "HAZARD_MODES",
    "REQUIRED_PARAMS",
    "REQUIRED_PORTS",
    "AnnunciatorSpec",
    "DataBusSpec",
    "DeviceSpec",
    "EnvironmentPointSpec",
    "HazardSpec",
    "NodeSpec",
    "PartSpec",
    "ProcedureSpec",
    "ScenarioSpec",
    "ScheduledFaultSpec",
    "ShipSpec",
    "StepSpec",
]

Behavior = Literal[
    "battery",
    "contactor",
    "breaker",
    "precharge",
    "load",
    "xducer_v",
    "xducer_i",
    "xducer_soc",
    "xducer_flux",
    "bc",
    "rt",
    "junction",
    "harness_seg",
]

#: Required `params` keys per behavior (units in key names, ADR-0004).
REQUIRED_PARAMS: dict[str, frozenset[str]] = {
    "battery": frozenset({"emf_full_v", "emf_empty_v", "r_int_ohm", "capacity_c"}),
    "contactor": frozenset({"r_contact_ohm", "rating_a", "inrush_limit_a"}),
    "breaker": frozenset({"r_contact_ohm", "rating_a"}),
    "precharge": frozenset({"r_ohm", "complete_dv_v"}),
    "load": frozenset({"r_ohm"}),
    "xducer_v": frozenset({"sigma_v"}),
    "xducer_i": frozenset({"sigma_a"}),
    "xducer_soc": frozenset({"sigma_frac"}),
    "xducer_flux": frozenset({"sigma_cm2s"}),
    "bc": frozenset({"r_ohm", "min_v"}),
    "rt": frozenset({"r_ohm", "min_v"}),
    "junction": frozenset(),
    "harness_seg": frozenset(),
}

#: Required electrical `ports` per behavior (transducers attach via `measures`).
REQUIRED_PORTS: dict[str, frozenset[str]] = {
    "battery": frozenset({"pos", "neg"}),
    "contactor": frozenset({"a", "b"}),
    "breaker": frozenset({"a", "b"}),
    "precharge": frozenset({"a", "b"}),
    "load": frozenset({"pos", "neg"}),
    "xducer_v": frozenset(),
    "xducer_i": frozenset(),
    "xducer_soc": frozenset(),
    "xducer_flux": frozenset(),
    "bc": frozenset({"pos", "neg"}),
    "rt": frozenset({"pos", "neg"}),
    "junction": frozenset(),
    "harness_seg": frozenset(),
}


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


#: Fault modes a `hazard` block may declare, per behavior. A mode the device
#: cannot actually enter would be a hazard that never fires — a content lie.
HAZARD_MODES: dict[str, frozenset[str]] = {
    "rt": frozenset({"stuck_dominant", "dead"}),
    "junction": frozenset({"open", "short"}),
    "harness_seg": frozenset({"open", "short"}),
}

#: Behaviors with a rail-voltage power gate, and so the only ones whose
#: hazards may be declared `needs_rail` (failure-and-repair.md: `f_power`).
RAIL_GATED = frozenset({"bc", "rt"})


class HazardSpec(_Model):
    """One fault mode's susceptibility (failure-and-repair.md, stress model v1).

    `rate_per_h` is the mode's base rate at the quiet reference environment,
    written per hour because that is the unit a reliability figure is quoted
    in; the loader converts to SI. `radiation` is the exponent on the flux
    ratio — 0.0 means the mode does not care about the particle environment,
    which is the correct default for anything mechanical.
    """

    rate_per_h: float = Field(gt=0.0)
    radiation: float = Field(default=0.0, ge=0.0)
    needs_rail: bool = False  # the mode needs a live rail to happen at all


class PartSpec(_Model):
    """`part/1` — a purchasable/instantiable part type."""

    schema_version: Literal["part/1"] = Field(alias="schema")
    id: str
    part_number: str
    name: str
    ata: int
    tech_level: int
    mass_kg: float
    behavior: Behavior
    params: dict[str, float]
    hazard: dict[str, HazardSpec] = Field(default_factory=dict)  # fault mode -> rate
    docs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_params(self) -> PartSpec:
        missing = REQUIRED_PARAMS[self.behavior] - self.params.keys()
        if missing:
            raise ValueError(f"behavior {self.behavior!r} missing params: {sorted(missing)}")
        allowed = HAZARD_MODES.get(self.behavior, frozenset())
        for mode in sorted(self.hazard):
            if mode not in allowed:
                raise ValueError(
                    f"behavior {self.behavior!r} cannot enter fault mode {mode!r} "
                    f"(have {sorted(allowed)})"
                )
            if self.hazard[mode].needs_rail and self.behavior not in RAIL_GATED:
                raise ValueError(
                    f"hazard {mode!r}: 'needs_rail' requires a rail-gated behavior, "
                    f"not {self.behavior!r}"
                )
        return self


class NodeSpec(_Model):
    """An electrical node (bus/terminal). Ground is the implicit reference `gnd`."""

    id: str
    c_f: float = Field(gt=0.0, description="node capacitance; >0 keeps the solve nonsingular")
    bus: bool = False  # distribution bus: gets a feeder tree in the WDM, named in manuals


class DataBusSpec(_Model):
    """A data bus segment (ata-42-data.md). BC/RT devices attach via `data_bus`."""

    id: str
    name: str  # display name, e.g. "DB-A"
    termination_ohm: float = Field(default=78.0, gt=0.0)  # both ends, per 1553B


class DeviceSpec(_Model):
    """A placed device instance."""

    id: str
    part: str  # pack-qualified part id, e.g. "core:ctr-30"
    ports: dict[str, str] = Field(default_factory=dict)  # port name -> node id
    measures: str | None = None  # xducer_v: node id; xducer_i/xducer_soc: device id
    scl: str | None = None  # SCL address (may be shared, e.g. V+I xducers)
    interlock_open: str | None = None  # device id that must be OPEN (precharge law)
    data_bus: str | None = None  # bc/rt: data bus id this device attaches to
    ends: dict[str, str] = Field(default_factory=dict)  # harness_seg: {a, b} bus-member ids
    carried_by: str | None = None  # xducer: RT device id that transports it (None = panel-wired)
    params: dict[str, float] = Field(default_factory=dict)  # instance overrides (soc_init)


class AnnunciatorSpec(_Model):
    """Threshold monitor on one telemetry item (ANNUNCIATORS phase)."""

    id: str
    telemetry: str  # transducer device id
    message: str
    low: float | None = None
    high: float | None = None
    arm_above: float | None = None  # arms after value first exceeds this (cold&dark quiet)

    @model_validator(mode="after")
    def _check_thresholds(self) -> AnnunciatorSpec:
        if self.low is None and self.high is None:
            raise ValueError("annunciator needs at least one of low/high")
        return self


class ShipSpec(_Model):
    """`ship/1` — vessel blueprint (M1 electrical + M2 data-bus subset)."""

    schema_version: Literal["ship/1"] = Field(alias="schema")
    id: str
    name: str
    nodes: list[NodeSpec]
    devices: list[DeviceSpec]
    data_buses: list[DataBusSpec] = Field(default_factory=list)
    annunciators: list[AnnunciatorSpec] = Field(default_factory=list)


class StepSpec(_Model):
    """One procedure step: exactly one action; optional expected indication.

    Expectations come in two kinds: `expect_telemetry` (an instrument reading
    within bounds) or `expect_text` (a substring of the command output — how
    DMM readings and table rows branch). Branching (FIM/QRH trees): when the
    expectation is met, `on_pass_goto` jumps; when it is not, `on_fail_goto`
    jumps instead of holding. Targets are step numbers in the same procedure;
    ``0`` ends the procedure (a verdict step — nothing further to check).
    """

    step: int
    scl: str | None = None
    wait_s: float | None = None
    expect_refusal: bool = False
    expect_telemetry: str | None = None  # transducer device id
    expect_min: float | None = None
    expect_max: float | None = None
    expect_text: str | None = None  # substring expected in the command output
    within_s: float = 5.0
    on_pass_goto: int | None = None
    on_fail_goto: int | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _check_action(self) -> StepSpec:
        if (self.scl is None) == (self.wait_s is None):
            raise ValueError("step needs exactly one of scl/wait_s")
        if self.expect_refusal and self.scl is None:
            raise ValueError("expect_refusal requires an scl action")
        if self.expect_telemetry is not None and (
            self.expect_min is None and self.expect_max is None
        ):
            raise ValueError("expect_telemetry needs expect_min and/or expect_max")
        if self.expect_text is not None:
            if self.scl is None:
                raise ValueError("expect_text requires an scl action")
            if self.expect_telemetry is not None:
                raise ValueError("one expectation kind per step (telemetry xor text)")
        if (self.on_pass_goto is not None or self.on_fail_goto is not None) and (
            self.expect_telemetry is None and self.expect_text is None
        ):
            raise ValueError("branch targets require an expectation (telemetry or text)")
        return self


class ProcedureSpec(_Model):
    """`procedure/1` — executable checklist (rendered in manuals, run in CI)."""

    schema_version: Literal["procedure/1"] = Field(alias="schema")
    id: str
    title: str
    manual_ref: str  # e.g. "SOM 24-30-01"
    ship: str  # pack-qualified ship id it is written against
    steps: list[StepSpec]

    @model_validator(mode="after")
    def _check_step_numbers(self) -> ProcedureSpec:
        numbers = [s.step for s in self.steps]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError("steps must be numbered 1..N in order")
        for step in self.steps:
            for target in (step.on_pass_goto, step.on_fail_goto):
                if target is not None and (
                    target == step.step or (target != 0 and target not in numbers)
                ):
                    raise ValueError(f"step {step.step}: invalid branch target {target}")
        return self


class EnvironmentPointSpec(_Model):
    """One point on a scenario's environment timeline.

    Authored in the conventional instrument unit (particles per cm² per
    second); the loader converts to SI (ADR-0004 §4). Points are held in
    order and interpolated linearly between — a solar particle event ramps
    over minutes and decays over hours, and a step function would be a lie
    the monitor could see.
    """

    at_s: float = Field(ge=0.0)
    flux_cm2s: float = Field(ge=0.0)


class ScheduledFaultSpec(_Model):
    """A fault the scenario author places by hand, at a time.

    Scripted faults enter the ship through the same call the stress model
    uses, so a drill and an emergent casualty are indistinguishable to
    everything downstream — including the player.
    """

    at_s: float = Field(ge=0.0)
    device: str
    mode: str


class ScenarioSpec(_Model):
    """`scenario/1` — an authored situation (data-model.md, M2 subset).

    Implemented now: ship, seed, the environment timeline and scripted faults.
    Wear deltas, crew, world state, goals and debrief criteria arrive with the
    systems that give them meaning; unknown keys are build errors until then,
    so a scenario written against the full schema fails loudly rather than
    being quietly half-honoured.
    """

    schema_version: Literal["scenario/1"] = Field(alias="schema")
    id: str
    name: str
    ship: str  # pack-qualified ship id
    seed: int
    environment: list[EnvironmentPointSpec] = Field(default_factory=list)
    faults: list[ScheduledFaultSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_timeline(self) -> ScenarioSpec:
        times_s = [point.at_s for point in self.environment]
        if times_s != sorted(times_s) or len(set(times_s)) != len(times_s):
            raise ValueError("environment points must be in strictly increasing time order")
        fault_times_s = [fault.at_s for fault in self.faults]
        if fault_times_s != sorted(fault_times_s):
            raise ValueError("scheduled faults must be in non-decreasing time order")
        return self
