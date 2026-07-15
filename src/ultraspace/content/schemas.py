"""Pydantic schemas for authored content (`schema: <name>/<version>` files).

Content files use natural authoring units declared by schema-defined keys
(ADR-0004 §4); everything is converted to SI at the model boundary. All models
forbid unknown fields — typos are build errors, not silent defaults.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "REQUIRED_PARAMS",
    "REQUIRED_PORTS",
    "AnnunciatorSpec",
    "DeviceSpec",
    "NodeSpec",
    "PartSpec",
    "ProcedureSpec",
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
}


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


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
    docs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_params(self) -> PartSpec:
        missing = REQUIRED_PARAMS[self.behavior] - self.params.keys()
        if missing:
            raise ValueError(f"behavior {self.behavior!r} missing params: {sorted(missing)}")
        return self


class NodeSpec(_Model):
    """An electrical node (bus/terminal). Ground is the implicit reference `gnd`."""

    id: str
    c_f: float = Field(gt=0.0, description="node capacitance; >0 keeps the solve nonsingular")
    bus: bool = False  # distribution bus: gets a feeder tree in the WDM, named in manuals


class DeviceSpec(_Model):
    """A placed device instance."""

    id: str
    part: str  # pack-qualified part id, e.g. "core:ctr-30"
    ports: dict[str, str] = Field(default_factory=dict)  # port name -> node id
    measures: str | None = None  # xducer_v: node id; xducer_i/xducer_soc: device id
    scl: str | None = None  # SCL address (may be shared, e.g. V+I xducers)
    interlock_open: str | None = None  # device id that must be OPEN (precharge law)
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
    """`ship/1` — vessel blueprint (M1: electrical subset)."""

    schema_version: Literal["ship/1"] = Field(alias="schema")
    id: str
    name: str
    nodes: list[NodeSpec]
    devices: list[DeviceSpec]
    annunciators: list[AnnunciatorSpec] = Field(default_factory=list)


class StepSpec(_Model):
    """One procedure step: exactly one action; optional expected indication."""

    step: int
    scl: str | None = None
    wait_s: float | None = None
    expect_refusal: bool = False
    expect_telemetry: str | None = None  # transducer device id
    expect_min: float | None = None
    expect_max: float | None = None
    within_s: float = 5.0
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
        return self
