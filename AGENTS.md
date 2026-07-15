# AGENTS.md — Operational guide for AI agents (and forgetful humans)

ULTRASPACE: text-driven, ultra-deep spaceship simulation. Headless deterministic sim
core; Textual TUI + teletype clients; in-game manuals are executable specifications.
Read [docs/vision.md](docs/vision.md) before designing anything.

## Commands

```bash
make setup        # uv sync (creates .venv, installs dev deps)
make check        # fast gate: ruff + mypy --strict + unit tests   (keep green ALWAYS)
make test         # full pytest suite
make lint         # ruff check + format check
make types        # mypy --strict
make selftest     # deterministic kernel self-test, prints state digest
uv run pytest tests/kernel/test_rng.py -k stream   # run a single test file/pattern
```

Always `uv run ...` — never bare `python`/`pip`. Runtime deps are currently **zero**
(kernel is stdlib-only); adding a dependency requires justification per
[docs/engineering/tech-stack.md](docs/engineering/tech-stack.md).

## Repo map

```
docs/            specs: design/ engineering/ process/ adr/  — index at docs/README.md
data/            game content (parts, ships, manuals, procedures, scenarios) [M1+]
src/ultraspace/  kernel/ → networks/ → ship/ → world/ → interaction/ → presentation/
tests/           mirrors src/; plus invariants/ determinism/ casualties/ conformance/
tools/           repo scripts (validators, generators, lints)
```

## The Iron Laws (violations are review-blocking; changes need an ADR)

1. **Determinism**: fixed 100 ms tick; integer-µs sim time; ALL randomness via
   `RngHub.stream("domain/entity/purpose")`; no wall clock, no module-level `random`,
   no ordering from unordered collections in model code. Same (seed, content, journal)
   → same state hash, forever.
2. **No God View**: player-facing data flows only through simulated instruments.
   `presentation/`, `world/`, `interaction/` never import raw sim state; the only
   bypass is `ultraspace.testing` (tests + dev tools).
3. **Layering**: `kernel ← networks ← ship ← world ← interaction ← presentation`.
   Upward imports only. Game logic in a UI widget is a defect.
4. **Physics is conserved**: new network/solver code ships with conservation +
   tier-consistency property tests. A conservation violation is a P0.
5. **Units**: SI everywhere in model code; every dimensioned identifier suffixed
   (`_v _a _w _k _pa _kg _j _s _us _rad`); kelvin not Celsius; no units libraries in
   the sim loop. (ADR-0004)
6. **Manual-Driven Development**: gameplay features start with their in-game manual
   content (SOM/QRH/FIM + procedure spec); procedures must pass the headless
   conformance runner; mechanical manual tables are generated, never hand-edited.
   If sim and manual disagree, it's a P1 either way. (ADR-0005)
7. **Failures are state, not exceptions**: in-fiction breakage is data (`Fault`
   records, `NoReport` values). Exceptions crossing layers are bugs.
8. **IDs are forever**: content IDs and SCL addresses never change meaning; renames
   are new IDs + deprecation aliases.

## Feature workflow (agents follow it too — no shortcuts)

SPEC (docs delta / ADR) → MANUAL (data/manuals + procedures) → TESTS (conformance,
casualty, invariants) → BUILD → VERIFY (`make test`) → PLAY (note in PR) → SYNC docs.
Details: [docs/process/workflow.md](docs/process/workflow.md). Definition of Done
checklist lives there; walk it before declaring anything finished.

## Writing style for specs & manuals

- Canonical vocabulary from [docs/glossary.md](docs/glossary.md) — no synonyms
  (Device/Block/LRU/SRU/annunciator mean exactly what the glossary says).
- Every doc: status line + Related links. Decisions with alternatives → ADR
  (template: [docs/adr/README.md](docs/adr/README.md)); mandatory Revisit-triggers.
- In-game manual voice: dry techwriter precision; WARNING/CAUTION/NOTE used honestly.
  Manuals teach the *why* (SOM explains its interlocks; error messages cite sections).
- Tests: hand-computed expected values cite their arithmetic in comments.

## Things that look fine but are wrong here

- `datetime.now()` / `time.time()` anywhere below presentation (use injected SimClock).
- A "quick debug print of the actual temperature" wired into a display (No God View
  — add an instrument or use `ultraspace.testing` in tests only).
- Asserting sim internals in `tests/casualties/` (those tests must experience faults
  through telemetry, like a player).
- Fixing a failing conformance test by editing the manual to match broken code (or
  vice versa) without a design ruling — check the spec, then decide which is wrong.
- Hand-editing a generated manual table (regenerate via `tools/` instead) [M1+].
- Celsius, degrees, PSI, or unsuffixed dimensioned variables in model code.
- Catching exceptions inside a tick to "keep the sim alive" (the tick guard owns that).

## Current state (update this section as milestones land)

- **M0 complete**: docs corpus v0.2; kernel (clock/rng/scheduler/events) implemented
  and tested; CI + Makefile operational.
- **M1 in progress**: EPS design spec (`docs/design/systems/ata-24-eps.md`), content
  pipeline (part/ship/procedure schemas + validate CLI), electrical solver, TB-1
  devices/telemetry/annunciators, SCL v1 + procedure runner, SOM Ch 24 + conformance
  + casualty suites, teletype client (`uv run python -m ultraspace run`). Runtime
  deps now: pydantic, PyYAML.
- **M1 remaining**: Textual TUI (EPS station, DOCS reader, annunciator row), WDM
  generated tables + diagram style guide, Kestrel blueprint (EPS subset), manual
  binder HTML export, `tools/check_imports.py` + `tools/check_units.py`.
- Git: remote `origin` → github.com/sigmareaver/ultraspace.

## Git discipline

- **Commit every feature, fix, and change/tweak as its own commit** (project rule —
  history is the regression-bisection and creative-direction ledger; details in
  [docs/process/workflow.md](docs/process/workflow.md) "Commit discipline").
- Conventional commits: `feat(ata24): ...`, `fix(kernel): ...`, `docs(process): ...`,
  `content(kestrel): ...`. Scope = ATA chapter or package name.
- Commit only at green (`make check`; full `make test` when models/content/determinism-
  adjacent code changed). One logical change per commit; spec deltas ride with the code
  they govern; golden-value updates are justified in the commit body.
