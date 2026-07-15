# data/ — game content tree

Arrives at M1 with the content pipeline. Layout is specified in
[docs/engineering/data-model.md](../docs/engineering/data-model.md):

```
parts/  ships/  manuals/  procedures/  comms/  scenarios/  packs/
```

Rules that apply from the first file onward:

- Every file declares `schema: <name>/<version>`; `ultraspace validate` must pass.
- Content IDs are forever (kebab-case, pack-namespaced). Renames = new ID + alias.
- Generated manual blocks (pinouts, breaker tables, ...) are never hand-edited.
- In-game manual prose lives here (it is game content), not in `docs/`.
