"""Export the manual binder as a printable HTML site (M1: `make binder`).

Single source of truth (ADR-0003/0005): the binder is built from the same
``data/manuals/`` pages the in-game DOCS reader renders, via the same
``load_manual_pages`` index — the printed book cannot diverge from the
in-game library. mkdocs-material does the rendering (tech-stack.md "Docs
build"); this script only *stages* pages and generates the nav, it never
writes manual content.

Usage: uv run python tools/export_binder.py [--data data] [--out build/binder]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from ultraspace.content import ManualPage, load_manual_pages  # noqa: E402

MANUAL_NAMES = {
    "som": "SOM — Ship Operating Manual",
    "wdm": "WDM — Wiring Data Manual",
    "misc": "General",
}


def stage(pages: list[ManualPage], docs_dir: Path) -> list[dict[str, object]]:
    """Copy page bodies into ``docs_dir``; return the mkdocs nav structure.

    Bodies are staged (frontmatter already stripped by the index) so the
    build needs no mkdocs frontmatter handling and the output carries the
    exact text the DOCS reader shows.
    """
    docs_dir.mkdir(parents=True, exist_ok=True)
    shelves: dict[str, list[dict[str, str]]] = {}
    lines = ["# Manual Binder", ""]
    for page in pages:
        target = docs_dir / page.rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page.body, encoding="utf-8")
        shelves.setdefault(page.manual, []).append({page.label: page.rel_path})
        lines.append(f"- [{page.label}]({page.rel_path})")
    lines += [
        "",
        "Built from the ship's content tree. If this book and the vessel",
        "disagree, file it — either way it is a P1 (workflow.md).",
        "",
    ]
    (docs_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")
    nav: list[dict[str, object]] = [{"Binder": "index.md"}]
    for manual in sorted(shelves):
        nav.append({MANUAL_NAMES.get(manual, manual.upper()): shelves[manual]})
    return nav


def write_config(build_dir: Path, nav: list[dict[str, object]]) -> Path:
    config = {
        "site_name": "ULTRASPACE Manual Binder",
        "docs_dir": "docs",
        "site_dir": "site",
        "use_directory_urls": False,  # printable, file://-friendly links
        "theme": {"name": "material", "palette": {"scheme": "default"}},
        "markdown_extensions": ["tables", "fenced_code", "attr_list"],
        "nav": nav,
    }
    path = build_dir / "mkdocs.yml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=REPO / "data")
    parser.add_argument("--out", type=Path, default=REPO / "build" / "binder")
    args = parser.parse_args(argv)

    # The binder is the crew's book: real manuals only. Pages without a
    # manual shelf ("misc": the diagram style guide and other authoring
    # docs) stay in the DOCS reader but out of the printed binder.
    pages = [p for p in load_manual_pages(Path(args.data)) if p.manual != "misc"]
    if not pages:
        print(f"no manual pages under {args.data}/manuals — nothing to bind")
        return 1
    build_dir = Path(args.out)
    if build_dir.exists():
        shutil.rmtree(build_dir)
    nav = stage(pages, build_dir / "docs")
    config = write_config(build_dir, nav)
    result = subprocess.run(
        ["mkdocs", "build", "--strict", "--config-file", str(config)],
        cwd=REPO,
        check=False,
    )
    if result.returncode != 0:
        return result.returncode
    print(f"binder: {build_dir / 'site' / 'index.html'} ({len(pages)} pages)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
