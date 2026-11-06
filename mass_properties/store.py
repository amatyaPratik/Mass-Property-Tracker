"""SQLite persistence with a field-level change history."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import NUMERIC_FIELDS, Component

TRACKED_FIELDS = ("name", "parent_id", *NUMERIC_FIELDS)

SCHEMA = """
CREATE TABLE IF NOT EXISTS components (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    parent_id  TEXT REFERENCES components(id),
    mass       REAL NOT NULL CHECK (mass >= 0),
    cg_x REAL NOT NULL, cg_y REAL NOT NULL, cg_z REAL NOT NULL,
    ixx  REAL NOT NULL, iyy  REAL NOT NULL, izz  REAL NOT NULL,
    ixy  REAL NOT NULL, ixz  REAL NOT NULL, iyz  REAL NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS change_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id TEXT NOT NULL,
    field        TEXT NOT NULL,
    old_value    TEXT,
    new_value    TEXT,
    source       TEXT,
    changed_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_change_log_component ON change_log(component_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _str(value) -> Optional[str]:
    return None if value is None else str(value)


class Store:
    """Thin repository over a SQLite database file (or ``:memory:``)."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    # --- reads -----------------------------------------------------------
    def get(self, component_id: str) -> Optional[Component]:
        row = self.conn.execute("SELECT * FROM components WHERE id = ?", (component_id,)).fetchone()
        return self._row_to_component(row) if row else None

    def all(self) -> list[Component]:
        rows = self.conn.execute("SELECT * FROM components ORDER BY id").fetchall()
        return [self._row_to_component(r) for r in rows]

    def history(self, component_id: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT field, old_value, new_value, source, changed_at FROM change_log "
            "WHERE component_id = ? ORDER BY id",
            (component_id,),
        ).fetchall()

    # --- writes ----------------------------------------------------------
    def upsert(self, component: Component, source: str = "manual") -> int:
        """Insert or update one component. Returns the number of logged changes."""
        return self.upsert_many([component], source=source)

    def upsert_many(self, components: list[Component], source: str = "manual") -> int:
        """Insert or update components in one transaction, parents first."""
        changes = 0
        now = _now()
        with self.conn:
            for comp in _parents_first(components):
                old = self.get(comp.id)
                values = comp.to_dict()
                if old is None:
                    cols = ", ".join([*values.keys(), "updated_at"])
                    marks = ", ".join("?" for _ in range(len(values) + 1))
                    self.conn.execute(
                        f"INSERT INTO components ({cols}) VALUES ({marks})",
                        [*values.values(), now],
                    )
                    self._log(comp.id, "created", None, comp.name, source, now)
                    changes += 1
                    continue

                old_values = old.to_dict()
                diff = {f: values[f] for f in TRACKED_FIELDS if old_values[f] != values[f]}
                if not diff:
                    continue
                sets = ", ".join(f"{f} = ?" for f in diff)
                self.conn.execute(
                    f"UPDATE components SET {sets}, updated_at = ? WHERE id = ?",
                    [*diff.values(), now, comp.id],
                )
                for f, new in diff.items():
                    self._log(comp.id, f, old_values[f], new, source, now)
                    changes += 1
        return changes

    def _log(self, cid, field, old, new, source, when) -> None:
        self.conn.execute(
            "INSERT INTO change_log (component_id, field, old_value, new_value, source, changed_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (cid, field, _str(old), _str(new), source, when),
        )

    @staticmethod
    def _row_to_component(row: sqlite3.Row) -> Component:
        data = {k: row[k] for k in row.keys() if k != "updated_at"}
        return Component(**data)


def _parents_first(components: list[Component]) -> list[Component]:
    """Order components so that every parent in the batch precedes its children."""
    ids = {c.id for c in components}
    placed: set[str] = set()
    ordered: list[Component] = []
    pending = list(components)
    while pending:
        progressed = False
        rest = []
        for c in pending:
            if c.parent_id is None or c.parent_id not in ids or c.parent_id in placed:
                ordered.append(c)
                placed.add(c.id)
                progressed = True
            else:
                rest.append(c)
        if not progressed:
            raise ValueError("Cycle in parent references: " + ", ".join(c.id for c in rest))
        pending = rest
    return ordered
