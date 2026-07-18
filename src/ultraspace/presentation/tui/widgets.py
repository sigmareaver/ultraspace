"""Persistent chrome widgets: annunciator row and clock strip.

The annunciator row renders the modeled `AnnunciatorPanel` lamps — blueprint
order, master caution first. Colors/glyphs are the semantic contract from
`palette.py` (colorblind-safe, ui-presentation.md): an active caution is a
backlit amber `▲`, an idle lamp is a dim `·`. The clock strip shows MET and
the M1 time discipline (turn-based: one tick per command, `wait` to advance).
"""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

from ultraspace.presentation.tui.palette import (
    CAUTION_GLYPH,
    LAMP_ACTIVE_STYLE,
    OFF_GLYPH,
    OFF_STYLE,
)
from ultraspace.ship import Simulation

__all__ = ["AnnunciatorRow", "ClockStrip"]


class AnnunciatorRow(Static):
    """Top-docked lamp row: MSTR CAUT tile + one tile per blueprint annunciator."""

    def refresh_from_sim(self, sim: Simulation) -> None:
        master = sim.panel.master_caution
        tiles = [self._tile("MSTR CAUT", master)]
        for lamp in sim.panel.annunciators:
            tiles.append(self._tile(lamp.spec.message, lamp.active))
        self.update(Text("│", style=OFF_STYLE).join(tiles))

    @staticmethod
    def _tile(message: str, active: bool) -> Text:
        glyph = CAUTION_GLYPH if active else OFF_GLYPH
        style = LAMP_ACTIVE_STYLE if active else OFF_STYLE
        return Text(f" {glyph} {message} ", style=style)


class ClockStrip(Static):
    """MET + tick + time-compression state (turn-based at M1)."""

    def refresh_from_sim(self, sim: Simulation) -> None:
        self.update(
            Text(
                f" MET {sim.clock.mission_elapsed_str()} │ tick {sim.clock.tick_index}"
                f" │ turn-based: 1 tick per command, 'wait <s>' to advance",
                style=OFF_STYLE,
            )
        )
