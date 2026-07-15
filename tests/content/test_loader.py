"""Content loader: real tree loads clean; broken content fails with context."""

from __future__ import annotations

from pathlib import Path

from ultraspace.content import load_tree

DATA_ROOT = Path(__file__).parents[2] / "data"


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


MINIMAL_PART = """
schema: part/1
id: r-1
part_number: "24-000-001"
name: "Test load"
ata: 24
tech_level: 0
mass_kg: 1.0
behavior: load
params: {r_ohm: 10.0}
"""


def test_repo_content_tree_is_valid() -> None:
    tree = load_tree(DATA_ROOT)
    assert tree.ok, "\n".join(str(e) for e in tree.errors)
    assert "core:tb-1" in tree.ships
    assert "core:bat-28-40" in tree.parts


def test_unknown_schema_reported(tmp_path: Path) -> None:
    write(tmp_path, "bad.yaml", "schema: nonsense/9\nid: x\n")
    tree = load_tree(tmp_path)
    assert not tree.ok
    assert "unknown schema" in str(tree.errors[0])


def test_missing_behavior_params_reported(tmp_path: Path) -> None:
    write(tmp_path, "part.yaml", MINIMAL_PART.replace("{r_ohm: 10.0}", "{}"))
    tree = load_tree(tmp_path)
    assert not tree.ok
    assert "missing params" in str(tree.errors[0])


def test_dangling_part_and_node_refs_reported(tmp_path: Path) -> None:
    write(tmp_path, "part.yaml", MINIMAL_PART)
    write(
        tmp_path,
        "ship.yaml",
        """
schema: ship/1
id: s-1
name: "Bad ship"
nodes: [{id: n1, c_f: 0.001}]
devices:
  - {id: d1, part: "core:nope", ports: {pos: n1, neg: gnd}}
  - {id: d2, part: "core:r-1", ports: {pos: ghost, neg: gnd}}
""",
    )
    tree = load_tree(tmp_path)
    messages = "\n".join(str(e) for e in tree.errors)
    assert "unknown part 'core:nope'" in messages
    assert "unknown node 'ghost'" in messages


def test_wrong_ports_for_behavior_reported(tmp_path: Path) -> None:
    write(tmp_path, "part.yaml", MINIMAL_PART)
    write(
        tmp_path,
        "ship.yaml",
        """
schema: ship/1
id: s-2
name: "Bad ports"
nodes: [{id: n1, c_f: 0.001}]
devices:
  - {id: d1, part: "core:r-1", ports: {a: n1, b: gnd}}
""",
    )
    tree = load_tree(tmp_path)
    assert any("ports" in str(e) and "required" in str(e) for e in tree.errors)


def test_duplicate_ids_reported(tmp_path: Path) -> None:
    write(tmp_path, "a.yaml", MINIMAL_PART)
    write(tmp_path, "b.yaml", MINIMAL_PART)
    tree = load_tree(tmp_path)
    assert any("duplicate id" in str(e) for e in tree.errors)


def test_procedure_refs_validated(tmp_path: Path) -> None:
    write(
        tmp_path,
        "proc.yaml",
        """
schema: procedure/1
id: p-1
title: "Ghost procedure"
manual_ref: "SOM 00-00-00"
ship: "core:ghost-ship"
steps:
  - {step: 1, scl: "eps read"}
""",
    )
    tree = load_tree(tmp_path)
    assert any("unknown ship" in str(e) for e in tree.errors)
