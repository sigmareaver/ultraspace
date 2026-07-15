"""ULTRASPACE command-line entry point.

M0 surface: ``selftest`` — assemble the kernel primitives, run a fixed
deterministic workload, and print the event-log digest. The digest is the
determinism canary: it must be identical on every run, machine, and platform
(pinned in tests/test_selftest.py; see ADR-0002).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ultraspace import __version__
from ultraspace.content import ContentTree, load_manual_pages, load_tree
from ultraspace.content.generators import sync_generated
from ultraspace.kernel import TICK_US, EventLog, Phase, RngHub, Scheduler, SimClock
from ultraspace.presentation import run_teletype, run_tui
from ultraspace.ship import Simulation

__all__ = ["main", "run_selftest"]

DEFAULT_TICKS = 600  # 60 s of sim time at the 100 ms base tick
DEFAULT_SEED = 42


def run_selftest(ticks: int = DEFAULT_TICKS, master_seed: int = DEFAULT_SEED) -> str:
    """Run the deterministic kernel workload; return the event-log digest.

    The workload exercises every kernel primitive: two independent RNG streams,
    three rate groups across two phases, and ordered event emission. It is
    deliberately frozen — changing it invalidates the pinned digest and should
    only happen alongside a conscious golden-value update.
    """
    clock = SimClock()
    log = EventLog()
    hub = RngHub(master_seed)
    scheduler = Scheduler()

    noise_a = hub.stream("kernel/selftest.device-a/noise")
    noise_b = hub.stream("kernel/selftest.device-b/noise")
    accumulators = {"a": 0, "b": 0}
    next_threshold = [10_000]

    def device_a(_tick: int) -> None:
        accumulators["a"] += noise_a.randrange(1000)

    def device_b(tick: int) -> None:
        accumulators["b"] += noise_b.randrange(1000)
        log.append(
            tick,
            "selftest.device-b",
            "sample",
            {"a": accumulators["a"], "b": accumulators["b"]},
        )

    def annunciator(tick: int) -> None:
        if accumulators["a"] > next_threshold[0]:
            log.append(
                tick,
                "selftest.annunciator",
                "threshold-crossed",
                {"threshold": next_threshold[0]},
            )
            next_threshold[0] *= 2

    scheduler.register(Phase.DEVICES, "selftest.device-a", device_a)
    scheduler.register(Phase.DEVICES, "selftest.device-b", device_b, period_ticks=10)
    scheduler.register(Phase.ANNUNCIATORS, "selftest.annunciator", annunciator, period_ticks=5)

    for _ in range(ticks):
        scheduler.run_tick(clock.tick_index)
        clock.advance()

    log.append(
        clock.tick_index,
        "selftest",
        "complete",
        {
            "ticks": ticks,
            "sim_time_us": clock.now_us,
            "met": clock.mission_elapsed_str(),
            "a": accumulators["a"],
            "b": accumulators["b"],
        },
    )
    return log.digest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ultraspace",
        description="ULTRASPACE — the ultra-in-depth spaceship simulation.",
    )
    parser.add_argument("--version", action="version", version=f"ultraspace {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    selftest = subparsers.add_parser(
        "selftest", help="run the deterministic kernel self-test and print its digest"
    )
    selftest.add_argument("--ticks", type=int, default=DEFAULT_TICKS)
    selftest.add_argument("--seed", type=int, default=DEFAULT_SEED)

    validate = subparsers.add_parser("validate", help="validate the content tree")
    validate.add_argument("--root", type=Path, default=Path("data"))

    run = subparsers.add_parser("run", help="run a ship (teletype by default; --tui for stations)")
    run.add_argument("--ship", default="core:tb-1")
    run.add_argument("--seed", type=int, default=DEFAULT_SEED)
    run.add_argument("--root", type=Path, default=Path("data"))
    run.add_argument(
        "--tui", action="store_true", help="Textual station client instead of teletype"
    )

    generate = subparsers.add_parser(
        "generate", help="regenerate manual tables/diagrams from content"
    )
    generate.add_argument("--root", type=Path, default=Path("data"))
    generate.add_argument(
        "--check", action="store_true", help="fail if committed output is stale (CI gate)"
    )

    args = parser.parse_args(argv)
    handlers = {
        "selftest": _cmd_selftest,
        "validate": _cmd_validate,
        "run": _cmd_run,
        "generate": _cmd_generate,
    }
    return handlers[str(args.command)](args)


def _load_or_report(root: Path) -> ContentTree | None:
    tree = load_tree(root)
    if not tree.ok:
        for error in tree.errors:
            print(f"ERROR {error}")
        return None
    return tree


def _cmd_generate(args: argparse.Namespace) -> int:
    tree = _load_or_report(Path(args.root))
    if tree is None:
        return 1
    stale = sync_generated(tree, check=bool(args.check))
    if args.check:
        for rel in stale:
            print(f"STALE manuals/{rel} — run: uv run python -m ultraspace generate")
        print(f"generated content: {'STALE' if stale else 'up to date'}")
        return 1 if stale else 0
    for rel in stale:
        print(f"wrote manuals/{rel}")
    print(f"generated content: {len(stale)} file(s) updated")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    tree = _load_or_report(Path(args.root))
    if tree is None:
        return 1
    sim = Simulation(tree, str(args.ship), master_seed=int(args.seed))
    try:
        if args.tui:
            run_tui(sim, load_manual_pages(Path(args.root)))
        else:
            run_teletype(sim, input, print)
    except KeyboardInterrupt:
        print()
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    tree = load_tree(Path(args.root))
    for error in tree.errors:
        print(f"ERROR {error}")
    print(
        f"content: {len(tree.parts)} parts, {len(tree.ships)} ships, "
        f"{len(tree.procedures)} procedures — {'OK' if tree.ok else 'FAILED'}"
    )
    return 0 if tree.ok else 1


def _cmd_selftest(args: argparse.Namespace) -> int:
    ticks = int(args.ticks)
    seed = int(args.seed)
    digest = run_selftest(ticks, seed)
    print("ULTRASPACE kernel selftest")
    print(f"  ticks={ticks} seed={seed} sim_time_s={ticks * TICK_US / 1_000_000:.1f}")
    print(f"  event-log digest: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
