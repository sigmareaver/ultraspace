"""Electrical solver: hand-computed cases, RC dynamics, solver residual."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ultraspace.networks import GROUND, ElectricalNetwork, solve_linear

DT_S = 0.1  # base tick


def step(
    net: ElectricalNetwork,
    stamps: list[tuple[str, str, float]],
    emf: tuple[str, float, float] | None = None,
) -> None:
    """One tick: Thevenin source (node, emf_v, r_ohm) + resistive stamps."""
    net.begin()
    if emf is not None:
        node, emf_v, r_ohm = emf
        net.stamp_conductance(node, GROUND, 1.0 / r_ohm)
        net.stamp_current(node, emf_v / r_ohm)
    for a, b, r_ohm in stamps:
        net.stamp_conductance(a, b, 1.0 / r_ohm)
    net.solve()


def test_solve_linear_hand_case() -> None:
    # 2x2: [[2, -1], [-1, 2]] x = [1, 4]  ->  x = [2, 3]
    # (check: 2*2 - 3 = 1; -2 + 2*3 = 4)
    assert solve_linear([[2.0, -1.0], [-1.0, 2.0]], [1.0, 4.0]) == pytest.approx([2.0, 3.0])


def test_singular_matrix_raises() -> None:
    with pytest.raises(ValueError, match="singular"):
        solve_linear([[1.0, 1.0], [1.0, 1.0]], [1.0, 2.0])


def test_resistive_divider_converges_to_analytic() -> None:
    """EMF 10 V, r_int 1 Ω, load 4 Ω: V = 10*4/5 = 8.0 V; I = 2.0 A.

    Node cap 0.01 F gives tau = R_parallel*C = 0.8*0.01 = 8 ms << 100 ms tick,
    so convergence is nearly immediate.
    """
    net = ElectricalNetwork([("n1", 0.01)], DT_S)
    for _ in range(10):
        step(net, [("n1", GROUND, 4.0)], emf=("n1", 10.0, 1.0))
    assert net.voltage_v("n1") == pytest.approx(8.0, abs=1e-6)
    assert net.branch_current_a("n1", GROUND, 1.0 / 4.0) == pytest.approx(2.0, abs=1e-6)


def test_rc_charge_backward_euler_hand_computed() -> None:
    """10 V through 50 Ω into 0.01 F: RC = 0.5 s, dt/RC = 0.2.

    Backward Euler recurrence: v' = (v + (dt/RC)*V_src) / (1 + dt/RC)
      tick 1: (0     + 2.0) / 1.2 = 1.666667
      tick 2: (1.666667 + 2.0) / 1.2 = 3.055556
    """
    net = ElectricalNetwork([("bus", 0.01)], DT_S)
    step(net, [], emf=("bus", 10.0, 50.0))
    assert net.voltage_v("bus") == pytest.approx(1.666667, abs=1e-5)
    step(net, [], emf=("bus", 10.0, 50.0))
    assert net.voltage_v("bus") == pytest.approx(3.055556, abs=1e-5)


def test_isolated_node_decays_through_load() -> None:
    net = ElectricalNetwork([("bus", 0.01)], DT_S)
    for _ in range(50):
        step(net, [], emf=("bus", 10.0, 1.0))
    assert net.voltage_v("bus") == pytest.approx(10.0, abs=1e-3)
    # Source removed; 5 Ω load drains the cap monotonically toward 0.
    previous = net.voltage_v("bus")
    for _ in range(20):
        step(net, [("bus", GROUND, 5.0)])
        now = net.voltage_v("bus")
        assert 0.0 <= now < previous
        previous = now


def test_two_bus_tie_hand_computed() -> None:
    """Steady state, tie closed: EMF 26.8 V, r 0.07 Ω to bus.e; tie 0.02 Ω to
    bus.a; loads 13.12 Ω (bus.e) and 5.28 Ω (bus.a).

    R_a_branch = 0.02 + 5.28 = 5.30; parallel(13.12, 5.30) = 3.7752
    I_bat = 26.8 / (0.07 + 3.7752) = 6.9697 A
    V_bus.e = 26.8 - 6.9697*0.07 = 26.3121 V
    V_bus.a = V_bus.e * 5.28/5.30 = 26.2128 V
    """
    net = ElectricalNetwork([("bus.e", 0.008), ("bus.a", 0.012)], DT_S)
    for _ in range(30):
        step(
            net,
            [("bus.e", GROUND, 13.12), ("bus.e", "bus.a", 0.02), ("bus.a", GROUND, 5.28)],
            emf=("bus.e", 26.8, 0.07),
        )
    assert net.voltage_v("bus.e") == pytest.approx(26.3121, abs=1e-3)
    assert net.voltage_v("bus.a") == pytest.approx(26.2128, abs=1e-3)


@given(
    conductances=st.lists(
        st.tuples(st.integers(0, 3), st.integers(0, 3), st.floats(0.01, 100.0)),
        min_size=1,
        max_size=10,
    ),
    injections=st.lists(st.floats(-50.0, 50.0), min_size=4, max_size=4),
)
def test_solver_residual_property(
    conductances: list[tuple[int, int, float]], injections: list[float]
) -> None:
    """For arbitrary valid stamp sets, the solution satisfies G·V = I tightly."""
    names = ["n0", "n1", "n2", "n3"]
    net = ElectricalNetwork([(n, 0.001) for n in names], DT_S)
    net.begin()
    for a, b, g_s in conductances:
        net.stamp_conductance(names[a], GROUND if a == b else names[b], g_s)
    for name, i_a in zip(names, injections, strict=True):
        net.stamp_current(name, i_a)
    net.solve()
    assert net.residual() < 1e-9
