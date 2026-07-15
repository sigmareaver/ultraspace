"""TB-1 assembly and EPS operating behavior (hand-computed expectations)."""

from __future__ import annotations

from ultraspace.ship import Simulation
from ultraspace.testing import raw_bus_voltage_v, raw_device


def read_value(sim: Simulation, telemetry_id: str) -> float:
    item = sim.telemetry.read(telemetry_id)
    assert item is not None
    return item.value


def test_cold_and_dark_reads_zero(tb1: Simulation) -> None:
    tb1.step(5)
    assert abs(read_value(tb1, "mt.bus.e.v")) < 0.3  # noise floor only
    assert abs(read_value(tb1, "mt.bus.a.v")) < 0.3
    assert not tb1.panel.master_caution  # undervolt annunciators not yet armed


def test_battery_contactor_energizes_bus_e(tb1: Simulation) -> None:
    tb1.step(2)
    result = tb1.execute("eps.bat.1.contactor", "close", {"confirm"})
    assert result.ok, result.text
    tb1.step(10)
    # No load path (cb.e1 open): bus.e settles at EMF(0.75) = 26.8 V.
    assert abs(raw_bus_voltage_v(tb1, "bus.e") - 26.8) < 1e-3
    result = tb1.execute("eps.cb.e1", "close", set())
    assert result.ok
    tb1.step(10)
    # Loaded: I = 26.8/(0.05+0.02+0.05+13.07) = 2.0318 A
    # V_bus.e = 26.8 - 2.0318*(0.05+0.02) = 26.658 V  (transducer noise sigma 0.05)
    assert abs(read_value(tb1, "mt.bus.e.v") - 26.658) < 0.3
    assert abs(read_value(tb1, "mt.bat.1.i") - 2.032) < 0.15


def test_contactor_close_requires_confirm(tb1: Simulation) -> None:
    result = tb1.execute("eps.bat.1.contactor", "close", set())
    assert not result.ok
    assert "--confirm" in result.text


def test_precharge_interlock_refuses_with_tie_closed(tb1: Simulation) -> None:
    tb1.step(1)
    tb1.execute("eps.bus.a.tie", "close", {"confirm"})  # 0 V across it: closes clean
    result = tb1.execute("eps.bus.a.precharge", "start", set())
    assert not result.ok
    assert "interlock" in result.text
    assert "SOM 24-00-00" in result.text  # errors teach


def test_direct_tie_close_onto_dead_bus_trips_on_inrush(tb1: Simulation) -> None:
    tb1.step(1)
    tb1.execute("eps.bat.1.contactor", "close", {"confirm"})
    tb1.step(10)  # bus.e at ~26.8 V, bus.a at ~0 V
    result = tb1.execute("eps.bus.a.tie", "close", {"confirm"})
    assert result.ok  # the command executed; physics answered
    assert "TRIPPED" in result.text
    # Peak = 26.8/0.02 = 1340 A >> 150 A limit.
    assert raw_device(tb1, "tie.a").state == "tripped"
    tb1.step(5)
    assert raw_bus_voltage_v(tb1, "bus.a") < 1.0  # bus never energized
    events = [e for e in tb1.log if e.kind == "inrush-trip"]
    assert len(events) == 1 and events[0].source == "tie.a"


def test_precharge_sequence_energizes_bus_a(tb1: Simulation) -> None:
    tb1.step(1)
    tb1.execute("eps.bat.1.contactor", "close", {"confirm"})
    tb1.step(10)
    assert tb1.execute("eps.bus.a.precharge", "start", set()).ok
    # tau = 50.02 ohm * 12 mF = 0.6 s; |dV| < 1.5 V needs t = tau*ln(26.8/1.5) = 1.73 s.
    tb1.step_s(3.0)
    assert raw_device(tb1, "pcu.a").state == "complete"
    assert any(e.kind == "precharge-complete" for e in tb1.log)
    result = tb1.execute("eps.bus.a.tie", "close", {"confirm"})
    assert result.ok and "TRIPPED" not in result.text
    assert tb1.execute("eps.cb.a1", "close", set()).ok
    tb1.step(10)
    # Two-bus hand calc (test_two_bus_tie_hand_computed): V_bus.a = 26.21 V.
    assert abs(read_value(tb1, "mt.bus.a.v") - 26.21) < 0.3
    assert raw_device(tb1, "tie.a").state == "closed"


def test_undervolt_annunciator_arms_then_raises(tb1: Simulation) -> None:
    tb1.step(1)
    tb1.execute("eps.bat.1.contactor", "close", {"confirm"})
    tb1.execute("eps.cb.e1", "close", set())
    tb1.step(20)  # bus.e ~26.7 V > 25.0: annunciator arms
    caution_before = tb1.panel.master_caution
    assert not caution_before
    tb1.execute("eps.bat.1.contactor", "open", set())
    tb1.step_s(2.0)  # bus.e cap drains through avionics load, tau ~ 0.1 s
    caution_after = tb1.panel.master_caution
    assert caution_after
    assert "BUS E UNDERVOLT" in tb1.panel.active_messages()
    assert any(e.kind == "annunciator-raise" for e in tb1.log)


def test_read_and_summary_are_instrument_mediated(tb1: Simulation) -> None:
    tb1.step(2)
    result = tb1.execute("eps.bus.e", "read", set())
    assert result.ok
    assert "src: mt.bus.e.v" in result.text and "age" in result.text
    summary = tb1.summary()
    assert "MASTER CAUTION" in summary and "MET" in summary


def test_unknown_address_refused(tb1: Simulation) -> None:
    result = tb1.execute("eps.bus.zz", "read", set())
    assert not result.ok
