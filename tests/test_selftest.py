"""Selftest determinism canary (ADR-0002).

The selftest workload is frozen; its digest is the M0 determinism oracle.
"""

from __future__ import annotations

from ultraspace.__main__ import DEFAULT_SEED, DEFAULT_TICKS, run_selftest

# Golden digest for (ticks=600, seed=42), obtained by running the selftest
# twice in-process and once via CLI on 2026-07-14 (CPython 3.14, Linux).
# If a kernel change legitimately alters this, update it in the same commit
# with a "determinism suite" justification per the PR checklist.
GOLDEN_DIGEST = "5c972ffed58129c48fd122a75d03e795"


def test_selftest_digest_matches_golden() -> None:
    assert run_selftest(DEFAULT_TICKS, DEFAULT_SEED) == GOLDEN_DIGEST


def test_selftest_repeatable_in_process() -> None:
    assert run_selftest() == run_selftest()


def test_selftest_sensitive_to_seed_and_length() -> None:
    assert run_selftest(master_seed=43) != GOLDEN_DIGEST
    assert run_selftest(ticks=601) != GOLDEN_DIGEST
