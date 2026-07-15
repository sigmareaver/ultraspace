"""DC electrical network: quasi-static nodal analysis with capacitive bus
dynamics, integrated by backward Euler (spec: docs/design/systems/ata-24-eps.md §3).

Solve cycle per tick (driven by one NETWORKS-phase task in the ship layer):

    network.begin()
    <devices stamp conductances/current sources, in blueprint order>
    network.solve()
    <devices read node voltages / branch currents, update their state>

Backward Euler makes bus capacitance a diagonal stamp ``c/dt`` plus a history
source ``(c/dt)·v_prev`` — unconditionally stable at the 100 ms tick, and it
gives precharge its honest RC curve.
"""

from __future__ import annotations

__all__ = ["GROUND", "ElectricalNetwork", "solve_linear"]

GROUND = "gnd"


def solve_linear(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting; deterministic tie-break (lowest row).

    Sizes here are small (n < 20 at M1); pure Python is well within budget.
    """
    n = len(rhs)
    a = [[*row, rhs[i]] for i, row in enumerate(matrix)]  # augmented copy

    for col in range(n):
        pivot_row = col
        pivot_mag = abs(a[col][col])
        for row in range(col + 1, n):  # strict > keeps ties on the lowest index
            if abs(a[row][col]) > pivot_mag:
                pivot_row, pivot_mag = row, abs(a[row][col])
        if pivot_mag == 0.0:
            raise ValueError(f"singular matrix at column {col} (isolated node without c_f?)")
        if pivot_row != col:
            a[col], a[pivot_row] = a[pivot_row], a[col]
        for row in range(col + 1, n):
            factor = a[row][col] / a[col][col]
            if factor != 0.0:
                for k in range(col, n + 1):
                    a[row][k] -= factor * a[col][k]

    x = [0.0] * n
    for row in range(n - 1, -1, -1):
        acc = a[row][n]
        for k in range(row + 1, n):
            acc -= a[row][k] * x[k]
        x[row] = acc / a[row][row]
    return x


class ElectricalNetwork:
    """One DC network instance: nodes with capacitance, ground as reference."""

    def __init__(self, nodes: list[tuple[str, float]], dt_s: float) -> None:
        """``nodes``: (node id, capacitance c_f), ground excluded; order is canonical."""
        self._ids = [node_id for node_id, _ in nodes]
        self._index = {node_id: i for i, (node_id, _) in enumerate(nodes)}
        self._c_f = [c_f for _, c_f in nodes]
        self._dt_s = dt_s
        self._v = [0.0] * len(nodes)
        self._v_prev = [0.0] * len(nodes)
        n = len(nodes)
        self._g = [[0.0] * n for _ in range(n)]
        self._i = [0.0] * n
        self._stamping = False

    # -- stamp phase -------------------------------------------------------

    def begin(self) -> None:
        n = len(self._ids)
        self._g = [[0.0] * n for _ in range(n)]
        self._i = [0.0] * n
        self._stamping = True

    def stamp_conductance(self, a: str, b: str, g_s: float) -> None:
        """Stamp conductance ``g_s`` (siemens) between nodes ``a`` and ``b``."""
        assert self._stamping, "stamp outside begin()/solve() window"
        if g_s < 0.0:
            raise ValueError(f"negative conductance {g_s}")
        ia = self._node(a)
        ib = self._node(b)
        if ia >= 0:
            self._g[ia][ia] += g_s
        if ib >= 0:
            self._g[ib][ib] += g_s
        if ia >= 0 and ib >= 0:
            self._g[ia][ib] -= g_s
            self._g[ib][ia] -= g_s

    def stamp_current_a(self, node: str, i_a: float) -> None:
        """Inject current ``i_a`` (amperes) into ``node`` (Norton source term)."""
        assert self._stamping, "stamp outside begin()/solve() window"
        idx = self._node(node)
        if idx >= 0:
            self._i[idx] += i_a

    # -- solve phase ---------------------------------------------------------

    def solve(self) -> None:
        """Add capacitor history stamps and solve for node voltages."""
        for idx, c_f in enumerate(self._c_f):
            g_hist = c_f / self._dt_s
            self._g[idx][idx] += g_hist
            self._i[idx] += g_hist * self._v[idx]
        self._v_prev = self._v
        self._v = solve_linear(self._g, self._i)
        self._stamping = False

    def capacitor_power_w(self) -> float:
        """Power absorbed by node capacitances this tick: Σ V·C(V-V_prev)/dt.

        Backward-Euler consistent; term in the conservation audit
        (source = dissipation + storage, testing.md invariant #3).
        """
        total_w = 0.0
        for idx, c_f in enumerate(self._c_f):
            i_cap_a = c_f * (self._v[idx] - self._v_prev[idx]) / self._dt_s
            total_w += self._v[idx] * i_cap_a
        return total_w

    # -- read phase ----------------------------------------------------------

    def voltage_v(self, node: str) -> float:
        idx = self._node(node)
        return 0.0 if idx < 0 else self._v[idx]

    def branch_current_a(self, a: str, b: str, g_s: float) -> float:
        """Current a→b through a stamped conductance (post-solve)."""
        return g_s * (self.voltage_v(a) - self.voltage_v(b))

    def residual(self) -> float:
        """Max |G·V - I| over nodes; solver-accuracy check used by invariants."""
        worst = 0.0
        for row in range(len(self._ids)):
            acc = -self._i[row]
            for col in range(len(self._ids)):
                acc += self._g[row][col] * self._v[col]
            worst = max(worst, abs(acc))
        return worst

    def _node(self, node: str) -> int:
        if node == GROUND:
            return -1
        return self._index[node]
