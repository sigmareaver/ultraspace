"""Persistent chrome widgets: annunciator row and clock strip.

The annunciator row renders the modeled `AnnunciatorPanel` lamps — blueprint
order, the two masters first. Colors/glyphs are the semantic contract from
`palette.py` (colorblind-safe, ui-presentation.md): an active caution is a
backlit amber `▲`, a warning is red, an idle lamp is a dim `·`. A lamp whose
onset nobody has acknowledged carries a leading `!` — redundant with the
style, so the distinction survives a monochrome terminal
(ata-31-indicating.md §3). The clock strip shows MET and the M1 time
discipline (turn-based: one tick per command, `wait` to advance).
"""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

from ultraspace.presentation.tui.palette import (
    CAUTION_GLYPH,
    LAMP_ACTIVE_STYLE,
    OFF_GLYPH,
    OFF_STYLE,
    WARNING_LAMP_STYLE,
)
from ultraspace.ship import Simulation

__all__ = ["AnnunciatorRow", "ClockStrip"]


class AnnunciatorRow(Static):
    """Top-docked lamp row: the two masters + one tile per blueprint annunciator."""

    def refresh_from_sim(self, sim: Simulation) -> None:
        panel = sim.panel
        testing = panel.testing
        tiles = [
            self._tile(
                "MSTR WARN",
                testing or panel.master_warning,
                "warning",
                new=panel.master_warning_new,
            ),
            self._tile(
                "MSTR CAUT",
                testing or panel.master_caution,
                "caution",
                new=panel.master_caution_new,
            ),
        ]
        for lamp in panel.annunciators:
            tiles.append(
                self._tile(
                    lamp.spec.message,
                    testing or lamp.active,
                    lamp.spec.severity,
                    new=lamp.is_new,
                )
            )
        self.update(Text("│", style=OFF_STYLE).join(tiles))

    @staticmethod
    def _tile(message: str, active: bool, severity: str, *, new: bool) -> Text:
        if not active:
            return Text(f" {OFF_GLYPH} {message} ", style=OFF_STYLE)
        style = WARNING_LAMP_STYLE if severity == "warning" else LAMP_ACTIVE_STYLE
        mark = "!" if new else " "
        return Text(f"{mark}{CAUTION_GLYPH} {message} ", style=style)


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
