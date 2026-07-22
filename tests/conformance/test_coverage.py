"""Conformance coverage canary (testing.md class 6): every shipped procedure
must be claimed by exactly one chapter suite. Adding a procedure without
coverage fails the build.

Replaced by a generic parametrized runner (with declared preconditions)
when the procedure count grows further.
"""

from __future__ import annotations

from test_som_ch24 import COVERED as COVERED_24
from test_som_ch42 import COVERED as COVERED_42

from ultraspace.content import ContentTree

ALL_COVERED = COVERED_24 | COVERED_42


def test_every_shipped_procedure_is_covered(tree: ContentTree) -> None:
    assert set(tree.procedures) == ALL_COVERED


def test_chapter_suites_do_not_overlap() -> None:
    assert not (COVERED_24 & COVERED_42)
