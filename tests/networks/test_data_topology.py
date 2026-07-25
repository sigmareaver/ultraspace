"""Bus harness topology: reachability, medium death, and the DMM.

Fixture graph, mirroring TB-1 (ata-42-data.md §2):

        seg.bc-j1       seg.j1-j2
  bc.a ────────── j1 ────────── j2 ── (78 ohm end terminator)
                   │             │
                stub.j1-rt5   stub.j2-rt12

Ohm expectations are the equivalent resistance seen looking along each
direction: 78 ohm to a terminator, OL for an open, 0.0 for a short, and
STUB_WINDING_OHM across a healthy stub tap.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ultraspace.networks.data import STUB_WINDING_OHM, DataBus


def tb1_bus() -> DataBus:
    bus = DataBus("db.a")  # termination 78 ohm
    bus.bind_bc("bc.a")
    bus.register_junction("j1")
    bus.register_junction("j2")
    bus.register_rt(5, "rt.5")
    bus.register_rt(12, "rt.12")
    bus.add_segment("seg.bc-j1", "bc.a", "j1")
    bus.add_segment("seg.j1-j2", "j1", "j2")
    bus.add_segment("stub.j1-rt5", "j1", "rt.5")
    bus.add_segment("stub.j2-rt12", "j2", "rt.12")
    return bus


def test_healthy_bus_is_fully_reachable_and_reads_terminators() -> None:
    bus = tb1_bus()
    assert bus.reachable("rt.5", "bc.a") and bus.reachable("rt.12", "bc.a")
    assert not bus.has_trunk_short()
    j1 = {seg: (other, ohms) for seg, other, ohms in bus.ohms_at("j1")}
    assert j1["seg.bc-j1"] == ("bc.a", 78.0)  # toward the BC terminator
    assert j1["seg.j1-j2"] == ("j2", 78.0)  # toward the far-end terminator
    assert j1["stub.j1-rt5"] == ("rt.5", STUB_WINDING_OHM)
    j2 = {seg: (other, ohms) for seg, other, ohms in bus.ohms_at("j2")}
    assert j2["seg.j1-j2"] == ("j1", 78.0)
    assert j2["stub.j2-rt12"] == ("rt.12", STUB_WINDING_OHM)


def test_trunk_open_partitions_the_dark_zone_contiguously() -> None:
    bus = tb1_bus()
    bus.set_segment_state("seg.j1-j2", "open")
    # Beyond the break: dark from the BC's chair. Near side: fine.
    assert bus.reachable("rt.5", "bc.a")
    assert not bus.reachable("rt.12", "bc.a")
    # And the DMM tells you where: OL toward the break, terminator behind.
    j1 = {seg: ohms for seg, _, ohms in bus.ohms_at("j1")}
    assert j1["seg.j1-j2"] is None and j1["seg.bc-j1"] == 78.0
    j2 = {seg: ohms for seg, _, ohms in bus.ohms_at("j2")}
    assert j2["seg.j1-j2"] is None  # OL looking back at the break, too


def test_trunk_short_kills_the_medium_and_ohms_near_zero() -> None:
    bus = tb1_bus()
    bus.set_segment_state("seg.j1-j2", "short")
    assert bus.has_trunk_short()
    j1 = {seg: ohms for seg, _, ohms in bus.ohms_at("j1")}
    assert j1["seg.j1-j2"] == 0.0
    j2 = {seg: ohms for seg, _, ohms in bus.ohms_at("j2")}
    assert j2["seg.j1-j2"] == 0.0  # visible from both sides


def test_stub_short_is_contained_by_transformer_coupling() -> None:
    bus = tb1_bus()
    bus.set_segment_state("stub.j2-rt12", "short")
    assert not bus.has_trunk_short()  # the bus does not care
    assert bus.reachable("rt.5", "bc.a")
    assert not bus.reachable("rt.12", "bc.a")  # only its own tap is dead
    j2 = {seg: ohms for seg, _, ohms in bus.ohms_at("j2")}
    assert j2["stub.j2-rt12"] == 0.0


def test_stub_open_shows_ol_at_the_coupler_only() -> None:
    bus = tb1_bus()
    bus.set_segment_state("stub.j1-rt5", "open")
    assert bus.reachable("rt.12", "bc.a") and not bus.reachable("rt.5", "bc.a")
    j1 = {seg: ohms for seg, _, ohms in bus.ohms_at("j1")}
    assert j1["stub.j1-rt5"] is None
    assert j1["seg.bc-j1"] == 78.0 and j1["seg.j1-j2"] == 78.0


def test_failed_couplers_partition_and_kill_like_the_trunk_they_are() -> None:
    bus = tb1_bus()
    bus.set_junction_state("j1", "open")
    assert not bus.reachable("rt.5", "bc.a")  # its own tap is cut
    assert not bus.reachable("rt.12", "bc.a")  # and everything beyond
    assert not bus.has_trunk_short()
    bus.set_junction_state("j1", "short")
    assert bus.has_trunk_short()  # a shorted coupler is a trunk short


def test_topology_validation_is_build_time() -> None:
    bus = tb1_bus()
    with pytest.raises(ValueError, match="not a bus member"):
        bus.add_segment("seg.bogus", "j1", "nowhere")
    with pytest.raises(ValueError, match="more than one stub"):
        bus.add_segment("stub.extra", "j1", "rt.5")
    with pytest.raises(ValueError, match="trunk degree"):
        bus.add_segment("seg.j2-j1-again", "j2", "j1")
    bus2 = DataBus("db.b")
    bus2.register_rt(3, "rt.3")
    with pytest.raises(ValueError, match="duplicate RT address"):
        bus2.register_rt(3, "rt.9")


# -- harness invariants (testing.md class 3, ata-42-data.md §10) --------------

_SEGMENTS = ["seg.bc-j1", "seg.j1-j2", "stub.j1-rt5", "stub.j2-rt12"]
_TRUNK = ["seg.bc-j1", "seg.j1-j2"]
# Unique linear paths from the BC to each RT: (segments, junctions passed).
_PATHS = {
    "rt.5": (["seg.bc-j1", "stub.j1-rt5"], ["j1"]),
    "rt.12": (["seg.bc-j1", "seg.j1-j2", "stub.j2-rt12"], ["j1", "j2"]),
}


@given(short_seg=st.sampled_from(_SEGMENTS))
@settings(max_examples=20, deadline=None)
def test_a_trunk_short_is_always_bus_wide_a_stub_short_never(short_seg: str) -> None:
    bus = tb1_bus()
    bus.set_segment_state(short_seg, "short")
    assert bus.has_trunk_short() == (short_seg in _TRUNK)


@given(
    faults=st.lists(
        st.tuples(st.sampled_from(_SEGMENTS), st.sampled_from(["open", "short"])),
        max_size=4,
    ),
    junction_fault=st.sampled_from(["ok", "open"]),
)
@settings(max_examples=60, deadline=None)
def test_reachability_only_through_ok_paths(
    faults: list[tuple[str, str]], junction_fault: str
) -> None:
    bus = tb1_bus()
    for seg_id, state in faults:
        bus.set_segment_state(seg_id, state)  # type: ignore[arg-type]
    if junction_fault == "open":
        bus.set_junction_state("j1", "open")
    for rt_id, (path, junctions) in _PATHS.items():
        expected = all(bus.segment_state(s) == "ok" for s in path) and all(
            bus.junction_state(j) != "open" for j in junctions
        )
        assert bus.reachable(rt_id, "bc.a") == expected
