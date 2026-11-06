"""CSV import with row-level validation.

Expected columns (header row required):

    id, name, parent_id, mass, cg_x, cg_y, cg_z, ixx, iyy, izz, ixy, ixz, iyz

``parent_id`` may be empty for top-level items. Inertia columns may be empty,
in which case the component is treated as a point mass (all zeros).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from .models import Component

REQUIRED_COLUMNS = ("id", "name", "mass", "cg_x", "cg_y", "cg_z")
INERTIA_COLUMNS = ("ixx", "iyy", "izz", "ixy", "ixz", "iyz")
TOLERANCE = 1e-9


@dataclass
class ValidationError:
    row: int  # 1-based data row (header excluded); 0 = file-level
    component_id: Optional[str]
    message: str

    def __str__(self) -> str:
        where = f"row {self.row}" if self.row else "file"
        cid = f" [{self.component_id}]" if self.component_id else ""
        return f"{where}{cid}: {self.message}"


@dataclass
class ImportResult:
    components: list[Component] = field(default_factory=list)
    errors: list[ValidationError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _parse_float(raw: Optional[str], name: str, errors: list[str], required: bool) -> float:
    text = (raw or "").strip()
    if not text:
        if required:
            errors.append(f"missing value for '{name}'")
        return 0.0
    try:
        return float(text)
    except ValueError:
        errors.append(f"'{name}' is not a number: {text!r}")
        return 0.0


def validate_row(values: dict[str, Optional[str]]) -> tuple[Optional[Component], list[str]]:
    """Parse one CSV row into a Component, returning any problems found."""
    problems: list[str] = []
    cid = (values.get("id") or "").strip()
    name = (values.get("name") or "").strip()
    if not cid:
        problems.append("missing value for 'id'")
    if not name:
        problems.append("missing value for 'name'")

    nums = {col: _parse_float(values.get(col), col, problems, required=True) for col in REQUIRED_COLUMNS[2:]}
    nums.update({col: _parse_float(values.get(col), col, problems, required=False) for col in INERTIA_COLUMNS})

    if nums["mass"] < 0:
        problems.append(f"mass must not be negative (got {nums['mass']})")

    ixx, iyy, izz = nums["ixx"], nums["iyy"], nums["izz"]
    if min(ixx, iyy, izz) < 0:
        problems.append("moments of inertia (ixx, iyy, izz) must not be negative")
    elif ixx + iyy + izz > 0:
        # Physically valid inertia tensors satisfy the triangle inequality.
        for a, b, c, label in ((ixx, iyy, izz, "izz"), (iyy, izz, ixx, "ixx"), (izz, ixx, iyy, "iyy")):
            if c > a + b + TOLERANCE:
                problems.append(f"{label} exceeds the sum of the other two moments (not physically possible)")

    if problems:
        return None, problems

    parent = (values.get("parent_id") or "").strip() or None
    return Component(id=cid, name=name, parent_id=parent, **nums), []


def validate_batch(
    components: Iterable[Component],
    known_ids: Iterable[str] = (),
    row_numbers: Optional[dict[str, int]] = None,
) -> list[ValidationError]:
    """Cross-row checks: unknown parents and cycles.

    ``row_numbers`` maps component ids to their CSV row so errors point at the
    right line; without it, rows are numbered by position in ``components``.
    """
    items = list(components)
    known = set(known_ids) | {c.id for c in items}
    errors: list[ValidationError] = []

    parent_of = {c.id: c.parent_id for c in items}
    for pos, c in enumerate(items, start=1):
        row = (row_numbers or {}).get(c.id, pos)
        if c.parent_id and c.parent_id not in known:
            errors.append(ValidationError(row, c.id, f"unknown parent_id '{c.parent_id}'"))
        if c.parent_id == c.id:
            errors.append(ValidationError(row, c.id, "component cannot be its own parent"))
            continue
        seen = {c.id}
        cur = c.parent_id
        while cur in parent_of:
            if cur in seen:
                errors.append(ValidationError(row, c.id, "cycle in parent hierarchy"))
                break
            seen.add(cur)
            cur = parent_of[cur]
    return errors


def read_csv(path: str | Path, known_ids: Iterable[str] = ()) -> ImportResult:
    """Read and validate a CSV file. Nothing is written to the database here."""
    result = ImportResult()
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        header = [h.strip() for h in (reader.fieldnames or [])]
        missing = [c for c in REQUIRED_COLUMNS if c not in header]
        if missing:
            result.errors.append(ValidationError(0, None, f"missing columns: {', '.join(missing)}"))
            return result
        reader.fieldnames = header

        seen_ids: dict[str, int] = {}
        for row_no, raw in enumerate(reader, start=1):
            comp, problems = validate_row(raw)
            cid = (raw.get("id") or "").strip() or None
            for p in problems:
                result.errors.append(ValidationError(row_no, cid, p))
            if comp is None:
                continue
            if comp.id in seen_ids:
                result.errors.append(
                    ValidationError(row_no, comp.id, f"duplicate id (first seen in row {seen_ids[comp.id]})")
                )
                continue
            seen_ids[comp.id] = row_no
            result.components.append(comp)

    result.errors.extend(validate_batch(result.components, known_ids, row_numbers=seen_ids))
    result.errors.sort(key=lambda e: e.row)
    return result
