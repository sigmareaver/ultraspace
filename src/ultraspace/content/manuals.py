"""Manual page index: Markdown + YAML frontmatter under ``data/manuals/``.

The in-game DOCS reader renders the same files the printed binder is built
from (single source of truth, ADR-0003). Pages are Markdown with a YAML
frontmatter block (data-model.md §"Manual page"); generated sheets and the
style guide carry no frontmatter and get their metadata inferred from path
and first heading. Load order is sorted path order (determinism-friendly,
same convention as the YAML content loader).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

__all__ = ["ManualPage", "load_manual_pages"]

_GENERATED_MARK = "<!-- GENERATED FILE"


@dataclass(frozen=True, slots=True)
class ManualPage:
    manual: str  # "som" | "wdm" | ... ("misc" when inferred)
    section: str  # "24-30-01"; file stem when inferred
    title: str
    rel_path: str  # relative to data/manuals/, POSIX separators
    body: str  # Markdown body (frontmatter stripped)
    generated: bool  # lives under a generated/ dir; never hand-edited
    procedure: str | None  # linked executable ProcedureSpec id, if any

    @property
    def label(self) -> str:
        """One-line listing label for reader indexes."""
        return f"{self.manual.upper()} {self.section} — {self.title}"


def _split_frontmatter(text: str) -> tuple[dict[str, object], str]:
    """(frontmatter dict, body). No frontmatter -> ({}, whole text)."""
    if not text.startswith("---\n"):
        return {}, text
    closing = text.find("\n---\n", 4)
    if closing < 0:
        return {}, text
    meta = yaml.safe_load(text[4:closing])
    body = text[closing + 5 :]
    return (meta if isinstance(meta, dict) else {}), body


def _first_heading(body: str) -> str | None:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def _load_page(manuals_root: Path, path: Path) -> ManualPage:
    rel = path.relative_to(manuals_root)
    meta, body = _split_frontmatter(path.read_text(encoding="utf-8"))
    manual = str(meta.get("manual", rel.parts[0] if len(rel.parts) > 1 else "misc"))
    section = str(meta.get("section", path.stem))
    title = str(meta.get("title") or _first_heading(body) or path.stem)
    procedure = meta.get("procedure")
    return ManualPage(
        manual=manual,
        section=section,
        title=title,
        rel_path=rel.as_posix(),
        body=body,
        generated="generated" in rel.parts or body.lstrip().startswith(_GENERATED_MARK),
        procedure=str(procedure) if procedure is not None else None,
    )


def load_manual_pages(data_root: Path) -> list[ManualPage]:
    """Every ``*.md`` under ``<data_root>/manuals``, sorted by (manual, section).

    Missing manuals directory yields an empty list (a ship can fly without a
    library; the DOCS reader shows an empty shelf).
    """
    manuals_root = data_root / "manuals"
    if not manuals_root.is_dir():
        return []
    pages = [_load_page(manuals_root, p) for p in sorted(manuals_root.rglob("*.md"))]
    return sorted(pages, key=lambda p: (p.manual, p.section, p.rel_path))
