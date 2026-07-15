"""SCL v1: parsing, longest-prefix dispatch, journaling."""

from __future__ import annotations

from ultraspace.interaction import Dispatcher
from ultraspace.ship import Simulation


def test_space_and_dot_forms_are_equivalent(tb1: Simulation) -> None:
    d = Dispatcher(tb1)
    tb1.step(1)
    r1 = d.execute_line("eps bat.1.contactor close --confirm")
    assert r1.ok, r1.text
    r2 = d.execute_line("eps.bat.1.contactor open")
    assert r2.ok, r2.text


def test_flags_position_independent(tb1: Simulation) -> None:
    d = Dispatcher(tb1)
    tb1.step(1)
    assert d.execute_line("--confirm eps bat.1.contactor close").ok


def test_system_level_read_gives_summary(tb1: Simulation) -> None:
    d = Dispatcher(tb1)
    tb1.step(2)
    result = d.execute_line("eps read")
    assert result.ok
    assert "MASTER CAUTION" in result.text


def test_telemetry_read_via_scl(tb1: Simulation) -> None:
    d = Dispatcher(tb1)
    tb1.step(2)
    result = d.execute_line("eps bus.e read")
    assert result.ok and "src: mt.bus.e.v" in result.text


def test_refusals_and_errors(tb1: Simulation) -> None:
    d = Dispatcher(tb1)
    tb1.step(1)
    assert not d.execute_line("").ok
    assert not d.execute_line("nonsense verb").ok
    assert not d.execute_line("eps bus.a.tie").ok  # missing verb
    assert not d.execute_line("eps launch").ok  # undefined system verb
    refusal = d.execute_line("eps bat.1.contactor close")  # missing --confirm
    assert not refusal.ok and "--confirm" in refusal.text


def test_every_command_is_journaled(tb1: Simulation) -> None:
    d = Dispatcher(tb1)
    tb1.step(1)
    d.execute_line("eps bat.1.contactor close --confirm")
    d.execute_line("bogus command")
    commands = [e for e in tb1.log if e.kind == "command" and e.source == "scl"]
    assert len(commands) == 2
    assert commands[0].payload["ok"] is True
    assert commands[1].payload["ok"] is False
