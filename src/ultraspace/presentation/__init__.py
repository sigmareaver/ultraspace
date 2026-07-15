"""Presentation layer: teletype (flat) client at M1; Textual TUI follows.

May import interaction (SCL) and read telemetry/FDR surfaces only
(architecture.md Iron Law 2/3).
"""

from ultraspace.presentation.teletype import run_teletype

__all__ = ["run_teletype"]
