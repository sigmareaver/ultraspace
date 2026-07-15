"""Manual page index: frontmatter parsing over the real data/manuals tree."""

from __future__ import annotations

from pathlib import Path

from ultraspace.content import ContentTree, load_manual_pages


def test_real_manuals_load_with_frontmatter(tree: ContentTree) -> None:
    pages = load_manual_pages(tree.root)
    by_key = {(p.manual, p.section): p for p in pages}

    page = by_key[("som", "24-30-01")]
    assert page.title.startswith("Electrical Power Up")
    assert page.procedure == "som-24-30-01"  # page links to its executable spec
    assert not page.generated
    assert "precharge" in page.body and not page.body.startswith("---")
    assert page.label == "SOM 24-30-01 — Electrical Power Up — Cold and Dark to Buses Powered"


def test_generated_and_frontmatterless_pages_are_indexed(tree: ContentTree) -> None:
    pages = load_manual_pages(tree.root)
    generated = {p.rel_path for p in pages if p.generated}
    assert "wdm/24/generated/tb-1.md" in generated
    # style-guide.md has no frontmatter: metadata is inferred, never a crash.
    style = next(p for p in pages if p.rel_path == "style-guide.md")
    assert style.title == "Manual Diagram & Table Style Guide"  # first heading
    assert (
        sorted(pages, key=lambda p: (p.manual, p.section, p.rel_path)) == pages
    )  # deterministic shelf order


def test_missing_manuals_dir_is_an_empty_shelf(tmp_path: Path) -> None:
    assert load_manual_pages(tmp_path) == []
