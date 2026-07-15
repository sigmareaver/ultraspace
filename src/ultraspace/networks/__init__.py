"""Physical network solvers (electrical at M1; thermal/fluid/data follow).

Layering: may import kernel and content only (architecture.md).
"""

from ultraspace.networks.electrical import GROUND, ElectricalNetwork, solve_linear

__all__ = ["GROUND", "ElectricalNetwork", "solve_linear"]
