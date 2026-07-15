# ULTRASPACE *(working title)*

**The ultra-in-depth spaceship simulation.** Text-driven. A study sim where the
spacecraft is modeled down to the boards in its avionics bays, operating it *actively
requires* the manual, and the radio discipline is as real as the bus voltages.

> BUS A tie: OPEN. · `DATA BUS A DEGRADED` · "Kestrel, readback correct, cleared corridor three."

- Depth is real: every gauge reading has a physical cause. No scripted malfunctions.
- Knowledge is the progression system: manuals, notebooks, and crew skill — no XP bars.
- No God View: you see instruments, and instruments are simulated components that lie.
- Space is crewed: ATC-style traffic control, phraseology, closed-loop crew orders.
- Tech levels from 2020s aerospace (solder it yourself) to archeotech (appease it).

**Status: M0 — Foundations.** Design corpus and deterministic sim kernel; the first
playable vertical slice (EPS "First Light") is next. See
[docs/process/roadmap.md](docs/process/roadmap.md).

## Orientation

| You want | Go to |
|---|---|
| The pitch & pillars | [docs/vision.md](docs/vision.md) |
| All specifications | [docs/README.md](docs/README.md) (index) |
| How development works | [docs/process/workflow.md](docs/process/workflow.md) |
| Agent/contributor operational guide | [AGENTS.md](AGENTS.md) |

## Quickstart (development)

Requires [uv](https://docs.astral.sh/uv/) and Python ≥ 3.12.

```bash
make setup      # create venv, install dev deps
make check      # lint + types + fast tests
make selftest   # run the deterministic kernel self-test
```

## License

TBD (decided before first public release).
