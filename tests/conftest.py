"""Shared fixtures: the real content tree and fresh TB-1 simulations."""

from __future__ import annotations

from pathlib import Path

import pytest

from ultraspace.content import ContentTree, load_tree
from ultraspace.ship import Simulation

DATA_ROOT = Path(__file__).parents[1] / "data"


@pytest.fixture(scope="session")
def tree() -> ContentTree:
    loaded = load_tree(DATA_ROOT)
    assert loaded.ok, "\n".join(str(e) for e in loaded.errors)
    return loaded


@pytest.fixture
def tb1(tree: ContentTree) -> Simulation:
    return Simulation(tree, "core:tb-1", master_seed=42)
