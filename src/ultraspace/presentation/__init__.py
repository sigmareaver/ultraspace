"""Presentation layer: teletype (flat) client + Textual TUI station client.

May import interaction (SCL) and read telemetry/FDR/panel-observation
surfaces only (architecture.md Iron Law 2/3). Feature parity between the two
clients is contractual (ui-presentation.md).
"""

from ultraspace.presentation.teletype import run_teletype
from ultraspace.presentation.tui import UltraspaceApp, run_tui

__all__ = ["UltraspaceApp", "run_teletype", "run_tui"]
