#!/usr/bin/env python3
"""Layer import checker — Iron Law 3 (architecture.md), mechanically enforced.

Rules:
1. Upward imports only: kernel < content < networks < ship < world <
   interaction < presentation. A module may import its own layer and lower.
2. `ultraspace.kernel` imports stdlib only (no third-party, no ultraspace).
3. `ultraspace.testing` may be imported by tests and dev tools ONLY — never
   from any layer in src/ (the No-God-View bypass stays outside the game).
4. Package-root modules (`__init__.py`, `__main__.py`) are the composition
   root and may import anything in the package.

Run: uv run python tools/check_imports.py   (wired into `make lint`)
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

LAYER_ORDER = ["kernel", "content", "networks", "ship", "world", "interaction", "presentation"]
LAYER_INDEX = {name: i for i, name in enumerate(LAYER_ORDER)}
SRC = Path(__file__).resolve().parents[1] / "src" / "ultraspace"


def ultraspace_imports(tree: ast.Module) -> list[str]:
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(a.name for a in node.names if a.name.startswith("ultraspace"))
        elif (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module
            and node.module.startswith("ultraspace")
        ):
            found.append(node.module)
    return found


def third_party_imports(tree: ast.Module) -> list[str]:
    stdlib = sys.stdlib_module_names
    found: list[str] = []
    for node in ast.walk(tree):
        roots: list[str] = []
        if isinstance(node, ast.Import):
            roots = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots = [node.module.split(".")[0]]
        found.extend(r for r in roots if r not in stdlib and r != "ultraspace")
    return found


def segment_of(module: str) -> str | None:
    """Layer segment of an `ultraspace.X...` module path, if any."""
    parts = module.split(".")
    return parts[1] if len(parts) > 1 else None


def check_file(path: Path) -> list[str]:
    rel = path.relative_to(SRC)
    segment = rel.parts[0] if len(rel.parts) > 1 else None  # None: package root
    tree = ast.parse(path.read_text(encoding="utf-8"))
    errors: list[str] = []

    for module in sorted(set(ultraspace_imports(tree))):
        target = segment_of(module)
        if target == "testing" and segment != "testing":
            errors.append(f"{rel}: imports ultraspace.testing (No-God-View bypass; tests only)")
        elif (
            segment in LAYER_INDEX
            and target in LAYER_INDEX
            and LAYER_INDEX[target] > LAYER_INDEX[segment]
        ):
            errors.append(f"{rel}: layer '{segment}' imports upward from '{target}'")

    if segment == "kernel":
        for name in sorted(set(ultraspace_imports(tree))):
            if segment_of(name) != "kernel":
                errors.append(f"{rel}: kernel imports {name} (kernel is self-contained)")
        for name in sorted(set(third_party_imports(tree))):
            errors.append(f"{rel}: kernel imports third-party '{name}' (stdlib only)")

    return errors


def main() -> int:
    errors: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        errors.extend(check_file(path))
    for error in errors:
        print(f"IMPORT-LAYERING {error}")
    print(f"check_imports: {'FAILED' if errors else 'ok'} ({len(errors)} error(s))")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
