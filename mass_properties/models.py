"""Data model for a single component's mass properties.

Units are SI throughout: kg, m, kg*m^2.

Inertia is stored as the inertia *tensor* about the component's own centre of
gravity, expressed in the global aircraft axes. Off-diagonal entries follow
the tensor convention, i.e. ``ixy = -integral(x*y dm)``. If your source data
uses positive "products of inertia" (Pxy = +integral(x*y dm)), negate them on
import.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

Vector = tuple[float, float, float]
Matrix = tuple[Vector, Vector, Vector]

NUMERIC_FIELDS = ("mass", "cg_x", "cg_y", "cg_z", "ixx", "iyy", "izz", "ixy", "ixz", "iyz")


@dataclass(frozen=True)
class Component:
    id: str
    name: str
    parent_id: Optional[str] = None
    mass: float = 0.0
    cg_x: float = 0.0
    cg_y: float = 0.0
    cg_z: float = 0.0
    ixx: float = 0.0
    iyy: float = 0.0
    izz: float = 0.0
    ixy: float = 0.0
    ixz: float = 0.0
    iyz: float = 0.0

    def __post_init__(self) -> None:
        # Normalise numbers so that 300 and 300.0 compare and log identically.
        for name in NUMERIC_FIELDS:
            object.__setattr__(self, name, float(getattr(self, name)))

    @property
    def cg(self) -> Vector:
        return (self.cg_x, self.cg_y, self.cg_z)

    @property
    def inertia(self) -> Matrix:
        return (
            (self.ixx, self.ixy, self.ixz),
            (self.ixy, self.iyy, self.iyz),
            (self.ixz, self.iyz, self.izz),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class MassProperties:
    """Result of a rollup: totals about the combined centre of gravity."""

    mass: float
    cg: Vector
    inertia: Matrix
    component_count: int = field(default=0)
