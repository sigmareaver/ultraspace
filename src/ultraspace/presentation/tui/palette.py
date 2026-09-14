"""The semantic color & glyph contract — one definition for all TUI chrome.

Contract (ui-presentation.md §rendering language): color is semantic and
*redundant with glyphs* — nothing is color-only (colorblind-safe; the
accessibility commitments). The player-facing mapping is documented in
`data/manuals/style-guide.md`; this module is its executable form. If the
two disagree, one of them is wrong — fix deliberately, not silently.

| Meaning               | Glyph | Style        | M1 raisers |
|-----------------------|-------|--------------|------------|
| caution — act/aware   | ▲     | amber        | active annunciator lamp, TRIPPED switch |
| advisory — transition | ●     | cyan         | precharge CHARGING |
| off / de-energized    | ·     | dim          | OPEN/IDLE states, idle lamps, clear caution |
| stale / no report     | ?     | dim          | aged telemetry, unreported bus voltage |
| warning — immediate   | ▲     | red          | warning-severity lamp (ata-31-indicating.md §2) |
| new / unacknowledged  | !     | reverse       | a lamp raised and not yet acknowledged |
"""

from __future__ import annotations

__all__ = [
    "ADVISORY_GLYPH",
    "ADVISORY_STYLE",
    "CAUTION_GLYPH",
    "CAUTION_STYLE",
    "LAMP_ACTIVE_STYLE",
    "OFF_GLYPH",
    "OFF_STYLE",
    "STALE_GLYPH",
    "STALE_STYLE",
    "WARNING_LAMP_STYLE",
    "WARNING_STYLE",
    "state_annotation",
]

CAUTION_GLYPH = "▲"
ADVISORY_GLYPH = "●"
OFF_GLYPH = "·"
STALE_GLYPH = "?"

CAUTION_STYLE = "bold color(214)"  # amber on a 256-color floor (tech-stack.md)
ADVISORY_STYLE = "cyan"
OFF_STYLE = "dim"
STALE_STYLE = "dim"
LAMP_ACTIVE_STYLE = "bold black on color(214)"  # backlit caution lamp
WARNING_STYLE = "bold red"
WARNING_LAMP_STYLE = "bold white on red"  # backlit warning lamp

# Panel-observed state word -> (glyph prefix, style). Words not listed render
# plain: CLOSED/COMPLETE are the normal end states, not things to notice.
_STATE_ANNOTATIONS: dict[str, tuple[str, str]] = {
    "TRIPPED": (CAUTION_GLYPH, CAUTION_STYLE),
    "CHARGING": (ADVISORY_GLYPH, ADVISORY_STYLE),
    "OPEN": (OFF_GLYPH, OFF_STYLE),
    "IDLE": (OFF_GLYPH, OFF_STYLE),
}


def state_annotation(state: str) -> tuple[str, str]:
    """(glyph, style) for a panel-observed state word; ``("", "")`` = plain.

    The glyph is a prefix, never a replacement: the state word always stays
    (no color-only or glyph-only information).
    """
    return _STATE_ANNOTATIONS.get(state, ("", ""))
