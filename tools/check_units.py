#!/usr/bin/env python3
"""Units-suffix heuristic lint — ADR-0004, mechanically assisted.

Flags identifiers in model code (kernel/content/networks/ship/world) whose
names *sound* dimensioned (contain a physics keyword) but lack a unit suffix.
Heuristic by design: it catches the common sins cheaply; review remains the
final authority. Extend KEYWORDS/SUFFIXES as new physical domains land.

Run: uv run python tools/check_units.py   (wired into `make lint`)
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "ultraspace"
MODEL_LAYERS = ("kernel", "content", "networks", "ship", "world")

#: name-substring -> the mistake it usually marks
KEYWORDS = (
    "voltage",
    "current",
    "temperature",
    "pressure",
    "power",
    "energy",
    "resistance",
    "capacitance",
    "duration",
    "flow",
    "torque",
    "force",
)

SUFFIXES = (
    "_v", "_a", "_w", "_k", "_pa", "_kg", "_j", "_s", "_us",
    "_rad", "_ohm", "_f", "_c", "_n", "_nm", "_kg_s", "_frac",
)  # fmt: skip

#: names that sound dimensioned but aren't (or are annotated at declaration)
ALLOWLIST = frozenset({"powers_w"})  # methods returning tuples keep a single suffix


def flag_name(name: str) -> bool:
    lowered = name.lower().strip("_")
    if name in ALLOWLIST or not any(k in lowered for k in KEYWORDS):
        return False
    return not lowered.endswith(SUFFIXES)


def names_in(tree: ast.Module) -> set[tuple[int, str]]:
    found: set[tuple[int, str]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name | ast.arg):
            ident = node.id if isinstance(node, ast.Name) else node.arg
            found.add((node.lineno, ident))
        elif isinstance(node, ast.Attribute):
            found.add((node.lineno, node.attr))
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            found.add((node.lineno, node.name))
    return found


def main() -> int:
    errors: list[str] = []
    for layer in MODEL_LAYERS:
        for path in sorted((SRC / layer).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for lineno, name in sorted(names_in(tree)):
                if flag_name(name):
                    errors.append(
                        f"{path.relative_to(SRC)}:{lineno}: {name!r} looks dimensioned "
                        f"but has no unit suffix (ADR-0004)"
                    )
    for error in errors:
        print(f"UNITS {error}")
    print(f"check_units: {'FAILED' if errors else 'ok'} ({len(errors)} error(s))")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
