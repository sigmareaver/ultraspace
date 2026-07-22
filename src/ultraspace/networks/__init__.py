"""Physical network solvers (electrical M1; data M2; thermal/fluid follow).

Layering: may import kernel and content only (architecture.md).
"""

from ultraspace.networks.data import DataBus
from ultraspace.networks.electrical import GROUND, ElectricalNetwork, solve_linear

__all__ = ["GROUND", "DataBus", "ElectricalNetwork", "solve_linear"]
