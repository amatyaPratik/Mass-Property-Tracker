"""Combine component mass properties into system or aircraft totals.

For a set of components with mass m_i, centre of gravity r_i and inertia
tensor I_i (about their own CG), the combined properties are:

    M      = sum(m_i)
    r_cg   = sum(m_i * r_i) / M
    I_tot  = sum( I_i + m_i * (|d_i|^2 * E - d_i d_i^T) ),   d_i = r_i - r_cg

The second term is the parallel axis (Steiner) theorem in tensor form.
"""

from __future__ import annotations

from collections.abc import Iterable

from .models import Component, MassProperties, Matrix, Vector


def _zero3() -> list[list[float]]:
    return [[0.0, 0.0, 0.0] for _ in range(3)]


def parallel_axis_shift(mass: float, d: Vector) -> Matrix:
    """Inertia added by moving a point mass ``mass`` to offset ``d``."""
    dx, dy, dz = d
    d2 = dx * dx + dy * dy + dz * dz
    return (
        (mass * (d2 - dx * dx), -mass * dx * dy, -mass * dx * dz),
        (-mass * dy * dx, mass * (d2 - dy * dy), -mass * dy * dz),
        (-mass * dz * dx, -mass * dz * dy, mass * (d2 - dz * dz)),
    )


def combine(components: Iterable[Component]) -> MassProperties:
    """Roll up any collection of components into one set of mass properties."""
    items = list(components)
    total_mass = sum(c.mass for c in items)

    if total_mass == 0:
        zero: Matrix = ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
        return MassProperties(mass=0.0, cg=(0.0, 0.0, 0.0), inertia=zero, component_count=len(items))

    cg = tuple(sum(c.mass * c.cg[k] for c in items) / total_mass for k in range(3))

    total = _zero3()
    for c in items:
        d = (c.cg[0] - cg[0], c.cg[1] - cg[1], c.cg[2] - cg[2])
        shift = parallel_axis_shift(c.mass, d)
        own = c.inertia
        for i in range(3):
            for j in range(3):
                total[i][j] += own[i][j] + shift[i][j]

    inertia: Matrix = tuple(tuple(row) for row in total)  # type: ignore[assignment]
    return MassProperties(mass=total_mass, cg=cg, inertia=inertia, component_count=len(items))  # type: ignore[arg-type]


def subtree(components: Iterable[Component], root_id: str) -> list[Component]:
    """Return ``root_id`` and all of its descendants."""
    items = list(components)
    by_parent: dict[str | None, list[Component]] = {}
    by_id = {c.id: c for c in items}
    for c in items:
        by_parent.setdefault(c.parent_id, []).append(c)

    if root_id not in by_id:
        raise KeyError(f"Unknown component: {root_id}")

    result: list[Component] = []
    stack = [by_id[root_id]]
    seen: set[str] = set()
    while stack:
        node = stack.pop()
        if node.id in seen:
            raise ValueError(f"Cycle detected at component {node.id}")
        seen.add(node.id)
        result.append(node)
        stack.extend(by_parent.get(node.id, []))
    return result


def rollup(components: Iterable[Component], root_id: str) -> MassProperties:
    """Mass properties of ``root_id`` including everything below it."""
    return combine(subtree(components, root_id))
