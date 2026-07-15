"""ULTRASPACE command-line entry point.

M0 surface: ``selftest`` — assemble the kernel primitives, run a fixed
deterministic workload, and print the event-log digest. The digest is the
determinism canary: it must be identical on every run, machine, and platform
(pinned in tests/test_selftest.py; see ADR-0002).
"""

from __future__ import annotations

import argparse

from ultraspace import __version__
from ultraspace.kernel import TICK_US, EventLog, Phase, RngHub, Scheduler, SimClock

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

    args = parser.parse_args(argv)

    if args.command == "selftest":
        ticks = int(args.ticks)
        seed = int(args.seed)
        digest = run_selftest(ticks, seed)
        print("ULTRASPACE kernel selftest")
        print(f"  ticks={ticks} seed={seed} sim_time_s={ticks * TICK_US / 1_000_000:.1f}")
        print(f"  event-log digest: {digest}")
        return 0

    raise AssertionError(f"unhandled command: {args.command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
