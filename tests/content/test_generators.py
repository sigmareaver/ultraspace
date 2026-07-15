"""WDM generator: correctness, determinism, and the no-drift gate."""

from __future__ import annotations

from ultraspace.content import ContentTree
from ultraspace.content.generators import generate_all, generate_ship_wdm, sync_generated


def test_committed_generated_output_is_current(tree: ContentTree) -> None:
    """THE staleness gate (ADR-0003 §4): a netlist/blueprint change without
    regenerated manuals fails here, exactly as it fails `generate --check` in CI."""
    stale = sync_generated(tree, check=True)
    assert stale == [], (
        f"stale generated manuals {stale}: run `uv run python -m ultraspace generate` "
        "and commit the result with the content change that caused it"
    )


def test_generation_is_deterministic(tree: ContentTree) -> None:
    assert generate_all(tree) == generate_all(tree)


def test_panel_table_binds_procedure_names_to_hardware(tree: ContentTree) -> None:
    wdm = generate_ship_wdm(tree, "core:tb-1")
    # Every switching device appears with SCL address, P/N, and endpoints.
    assert "| `eps.cb.e1` | cb.e1 | 24-120-005 | breaker | 5 A | bus.e | load.avionics.in |" in wdm
    assert "| `eps.bus.a.tie` | tie.a | 24-110-030 | contactor | 30 A | bus.e | bus.a |" in wdm
    assert "| `eps.bus.a.precharge` | pcu.a | 24-115-050 | precharge | 50 ohm" in wdm


def test_feeder_tree_follows_style_guide(tree: ContentTree) -> None:
    wdm = generate_ship_wdm(tree, "core:tb-1")
    assert "BUS E  [bus.e]  8 mF" in wdm
    assert "BUS A  [bus.a]  12 mF" in wdm
    # Two-hop chain: breaker -> feed node -> device ids (style guide rule 3).
    assert "→ load.avionics.in → load.avionics" in wdm
    # Tie stops at the far bus.
    assert "→ BUS A" in wdm
    # Last-branch glyph present; transducers never appear in trees.
    assert " └── " in wdm
    assert "mt.bus.e.v" not in wdm.split("## Wire list")[0].split("## Feeder trees")[1]


def test_wire_list_covers_every_node_and_ground(tree: ContentTree) -> None:
    wdm = generate_ship_wdm(tree, "core:tb-1")
    for node in tree.ships["core:tb-1"].nodes:
        assert f"| {node.id} |" in wdm
    assert "| gnd (ref) | - |" in wdm
    assert "bat1.neg" in wdm  # ground connections listed


def test_load_list_traces_protection(tree: ContentTree) -> None:
    wdm = generate_ship_wdm(tree, "core:tb-1")
    # 28/13.07 = 2.1 A; 28/5.23 = 5.4 A (style guide: one decimal).
    assert "| load.avionics | 24-190-060 |" in wdm and "| 2.1 A | cb.e1 |" in wdm
    assert "| load.cabin | 24-190-150 |" in wdm and "| 5.4 A | cb.a1 |" in wdm


def test_parts_list_is_sorted_with_quantities(tree: ContentTree) -> None:
    wdm = generate_ship_wdm(tree, "core:tb-1")
    parts_section = wdm.split("{#parts-list}")[1]
    rows = [r for r in parts_section.splitlines() if r.startswith("| 24-")]
    part_numbers = [r.split("|")[1].strip() for r in rows]
    assert part_numbers == sorted(part_numbers)
    assert "| 24-150-001 | Voltage transducer, DC bus | 2 |" in wdm  # qty aggregation


def test_width_constraint_enforced(tree: ContentTree) -> None:
    for text in generate_all(tree).values():
        assert all(len(line) <= 92 for line in text.splitlines())
