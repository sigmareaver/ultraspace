"""Persistent chrome widgets: annunciator row and clock strip.

The annunciator row renders the modeled `AnnunciatorPanel` lamps — blueprint
order, master caution first. Color is semantic and redundant with glyphs
(colorblind-safe, ui-presentation.md): active caution is amber `▲`, an idle
lamp is a dim `·`. The clock strip shows MET and the M1 time discipline
(turn-based: one tick per command, `wait` to advance).
"""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

from ultraspace.ship import Simulation

__all__ = ["AnnunciatorRow", "ClockStrip"]

_ACTIVE = "bold black on yellow"
_IDLE = "dim"


class AnnunciatorRow(Static):
    """Top-docked lamp row: MSTR CAUT tile + one tile per blueprint annunciator."""

    def refresh_from_sim(self, sim: Simulation) -> None:
        master = sim.panel.master_caution
        tiles = [Text(f" {'▲' if master else '·'} MSTR CAUT ", style=_ACTIVE if master else _IDLE)]
        for lamp in sim.panel.annunciators:
            glyph = "▲" if lamp.active else "·"
            tiles.append(
                Text(f" {glyph} {lamp.spec.message} ", style=_ACTIVE if lamp.active else _IDLE)
            )
        self.update(Text("│", style="dim").join(tiles))


class ClockStrip(Static):
    """MET + tick + time-compression state (turn-based at M1)."""

    def refresh_from_sim(self, sim: Simulation) -> None:
        self.update(
            Text(
                f" MET {sim.clock.mission_elapsed_str()} │ tick {sim.clock.tick_index}"
                f" │ turn-based: 1 tick per command, 'wait <s>' to advance",
                style="dim",
            )
        )
