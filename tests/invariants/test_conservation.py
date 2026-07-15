"""Conservation invariant: source power = dissipation + capacitive storage.

Iron Law 4 / testing.md class 3. Runs TB-1 through arbitrary switch
configurations; a violation is a P0.
"""

from __future__ import annotations

from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from ultraspace.content import ContentTree, load_tree
from ultraspace.ship import Simulation
from ultraspace.testing import raw_device, raw_power_audit_w

_TREE: ContentTree = load_tree(Path(__file__).parents[2] / "data")

SWITCHES = ["ctr.bat1", "tie.a", "cb.e1", "cb.a1"]


@given(
    closed=st.lists(st.booleans(), min_size=4, max_size=4),
    precharging=st.booleans(),
    ticks=st.integers(min_value=1, max_value=30),
)
@settings(max_examples=60, deadline=None)
def test_power_balance_over_arbitrary_configurations(
    closed: list[bool], precharging: bool, ticks: int
) -> None:
    sim = Simulation(_TREE, "core:tb-1", master_seed=7)
    # Force states directly (testing bypass): physics must balance in ANY
    # configuration, including ones the interlocks would refuse.
    for device_id, is_closed in zip(SWITCHES, closed, strict=True):
        raw_device(sim, device_id).state = "closed" if is_closed else "open"
    if precharging:
        raw_device(sim, "pcu.a").state = "charging"

    for _ in range(ticks):
        sim.step(1)
        source_w, dissipated_w, stored_w = raw_power_audit_w(sim)
        residual_w = source_w - dissipated_w - stored_w
        assert abs(residual_w) < 1e-6 * max(1.0, abs(source_w)), (
            f"conservation violated: src={source_w} dis={dissipated_w} sto={stored_w}"
        )
