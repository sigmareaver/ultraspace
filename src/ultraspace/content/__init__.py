"""Content pipeline: schemas, loading, validation (ADR-0003, data-model.md).

M1 carries the schema subset documented in docs/design/systems/ata-24-eps.md §9.
"""

from ultraspace.content.loader import ContentError, ContentTree, load_tree
from ultraspace.content.manuals import ManualPage, load_manual_pages
from ultraspace.content.schemas import (
    AnnunciatorSpec,
    DeviceSpec,
    NodeSpec,
    PartSpec,
    ProcedureSpec,
    ShipSpec,
    StepSpec,
)

__all__ = [
    "AnnunciatorSpec",
    "ContentError",
    "ContentTree",
    "DeviceSpec",
    "ManualPage",
    "NodeSpec",
    "PartSpec",
    "ProcedureSpec",
    "ShipSpec",
    "StepSpec",
    "load_manual_pages",
    "load_tree",
]
