# Architecture Decision Records

Any decision that (a) had real alternatives and (b) will be expensive to reverse gets an
ADR. ADRs are immutable once Accepted; reversals are new ADRs that supersede.

## Index

| # | Title | Status |
|---|---|---|
| [0001](0001-language-and-ui.md) | Python + Textual over headless core | Accepted |
| [0002](0002-determinism.md) | Fixed-tick, integer-time, seeded-stream determinism | Accepted |
| [0003](0003-content-format.md) | YAML + pydantic schemas, versioned, generated manual tables | Accepted |
| [0004](0004-units-policy.md) | SI floats with unit-suffixed names; no units library in sim loop | Accepted |
| [0005](0005-manual-driven-development.md) | Manual-Driven Development (manuals as executable specs) | Accepted |
| [0006](0006-diegetic-displays.md) | Diegetic displays: MFCs as simulated parts, panes as consoles | Proposed |

## Template

```markdown
# ADR-NNNN: Title

Status: Proposed | Accepted | Superseded by ADR-XXXX
Date: YYYY-MM-DD
Deciders: ...

## Context
What forces are at play; what problem demands a decision.

## Decision
The choice, stated imperatively.

## Consequences
What becomes easier/harder; costs accepted knowingly.

## Alternatives considered
Each with the honest reason for rejection.

## Revisit triggers
Concrete, observable conditions under which this ADR should be reopened.
```

The **Revisit triggers** section is mandatory: decisions rot silently without tripwires.
