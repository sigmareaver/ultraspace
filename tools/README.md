# tools/ — repo maintenance scripts (not shipped)

Planned inventory (created at the milestone that needs them):

| Tool | Milestone | Purpose |
|---|---|---|
| `check_imports.py` | M1 | Enforce layer import rules (architecture.md) |
| `check_units.py` | M1 | Heuristic lint for unsuffixed dimensioned identifiers (ADR-0004) |

Manual-table generation lives in the package (`ultraspace generate`), not here — the
in-game DOCS reader uses the same code (data-model.md "Generators").
| `replay_bisect.py` | M2 | Bisect FDR journals to first divergent tick |
| `coverage_matrix.py` | M2 | Failure modes × casualty tests; manual sections × conformance |
