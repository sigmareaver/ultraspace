"""Textual TUI package: the primary station client (presentation/tui only).

Everything here is display and input routing; game logic in a UI widget is a
defect (Iron Law 3). Reads come from telemetry, the annunciator panel, panel
observations, and the FDR; writes go through the SCL dispatcher exclusively.
"""

from ultraspace.presentation.tui.app import UltraspaceApp, run_tui

__all__ = ["UltraspaceApp", "run_tui"]
