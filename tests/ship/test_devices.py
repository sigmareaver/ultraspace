"""Device unit behaviors not reachable on the stock TB-1 configuration."""

from __future__ import annotations

from ultraspace.content.schemas import DeviceSpec, PartSpec
from ultraspace.kernel import EventLog
from ultraspace.networks import GROUND, ElectricalNetwork
from ultraspace.ship import Simulation
from ultraspace.ship.devices import Battery, Breaker
from ultraspace.testing import raw_device

BREAKER_PART = PartSpec.model_validate(
    {
        "schema": "part/1",
        "id": "cb-test",
        "part_number": "24-000-000",
        "name": "test breaker",
        "ata": 24,
        "tech_level": 0,
        "mass_kg": 0.1,
        "behavior": "breaker",
        "params": {"r_contact_ohm": 0.05, "rating_a": 5.0},
    }
)


def test_breaker_trips_on_sustained_overcurrent() -> None:
    spec = DeviceSpec(id="cb.t", part="core:cb-test", ports={"a": "n1", "b": "gnd"})
    breaker = Breaker(spec, BREAKER_PART)
    breaker.state = "closed"
    net = ElectricalNetwork([("n1", 0.001)], 0.1)
    log = EventLog()
    # EMF 10 V, r 0.5 ohm feeding n1; breaker (0.05 ohm) to gnd is the only load:
    # I = 10/(0.5+0.05) = 18.18 A > 5 A rating -> trip.
    for _ in range(3):
        net.begin()
        net.stamp_conductance("n1", GROUND, 1.0 / 0.5)
        net.stamp_current_a("n1", 10.0 / 0.5)
        breaker.stamp(net)
        net.solve()
        breaker.after_solve(net, log, 0)
    assert breaker.state == "tripped"
    assert any(e.kind == "overcurrent-trip" for e in log)
    # Tripped breakers refuse close until reset (panel discipline).
    assert not breaker.execute("close", set()).ok
    assert breaker.execute("reset", set()).ok
    assert breaker.state == "open"


def test_battery_soc_drains_under_load(tb1: Simulation) -> None:
    battery = raw_device(tb1, "bat1")
    assert isinstance(battery, Battery)
    soc_start = battery.soc
    tb1.execute("eps.bat.1.contactor", "close", {"confirm"})
    tb1.execute("eps.cb.e1", "close", set())
    tb1.step_s(10.0)
    # I ~ 2.03 A for 10 s = 20.3 C of 144000 C -> dSOC ~ 1.4e-4.
    assert 0 < soc_start - battery.soc < 5e-4


def test_tripped_contactor_requires_reset(tb1: Simulation) -> None:
    tb1.step(1)
    tb1.execute("eps.bat.1.contactor", "close", {"confirm"})
    tb1.step(10)
    tb1.execute("eps.bus.a.tie", "close", {"confirm"})  # inrush-trips
    assert raw_device(tb1, "tie.a").state == "tripped"
    assert not tb1.execute("eps.bus.a.tie", "close", {"confirm"}).ok
    assert tb1.execute("eps.bus.a.tie", "reset", set()).ok
    assert raw_device(tb1, "tie.a").state == "open"
