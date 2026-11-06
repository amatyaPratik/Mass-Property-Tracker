"""Command-line interface: ``mpt <command> --db FILE``."""

from __future__ import annotations

import argparse
import sys

from .importer import read_csv
from .models import Component
from .rollup import rollup
from .store import Store

DEFAULT_DB = "mass_properties.db"


def _fmt(v: float) -> str:
    return f"{v:12.4f}"


def cmd_import(args) -> int:
    store = Store(args.db)
    known = [c.id for c in store.all()]
    result = read_csv(args.csv, known_ids=known)
    if not result.ok:
        print(f"Import rejected: {len(result.errors)} problem(s) found, nothing was written.")
        for err in result.errors:
            print(f"  - {err}")
        return 1
    changes = store.upsert_many(result.components, source=f"import:{args.csv}")
    print(f"Imported {len(result.components)} component(s), {changes} change(s) logged.")
    return 0


def cmd_rollup(args) -> int:
    store = Store(args.db)
    try:
        mp = rollup(store.all(), args.id)
    except KeyError as exc:
        print(exc.args[0])
        return 1
    root = store.get(args.id)
    print(f"{root.name} ({root.id}): {mp.component_count} component(s)")
    print(f"  Mass [kg]      {_fmt(mp.mass)}")
    print(f"  CG [m]       x {_fmt(mp.cg[0])}   y {_fmt(mp.cg[1])}   z {_fmt(mp.cg[2])}")
    print("  Inertia about CG [kg m^2]")
    for row in mp.inertia:
        print("    " + " ".join(_fmt(v) for v in row))
    return 0


def cmd_tree(args) -> int:
    store = Store(args.db)
    items = store.all()
    children: dict = {}
    for c in items:
        children.setdefault(c.parent_id, []).append(c)

    def walk(node: Component, depth: int) -> None:
        mp = rollup(items, node.id)
        print(f"{'  ' * depth}- {node.id}  {node.name}  ({mp.mass:.2f} kg)")
        for ch in sorted(children.get(node.id, []), key=lambda c: c.id):
            walk(ch, depth + 1)

    for top in sorted(children.get(None, []), key=lambda c: c.id):
        walk(top, 0)
    return 0


def cmd_history(args) -> int:
    store = Store(args.db)
    rows = store.history(args.id)
    if not rows:
        print(f"No history for {args.id}")
        return 1
    for r in rows:
        print(f"{r['changed_at']}  {r['field']:<10} {r['old_value']!s:>12} -> {r['new_value']!s:<12} ({r['source']})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mpt", description="Mass Properties Tracker")
    p.add_argument("--db", default=DEFAULT_DB, help=f"SQLite database file (default: {DEFAULT_DB})")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("import", help="validate and import a CSV file")
    s.add_argument("csv")
    s.set_defaults(func=cmd_import)

    s = sub.add_parser("rollup", help="mass, CG and inertia of a component and everything below it")
    s.add_argument("id")
    s.set_defaults(func=cmd_rollup)

    s = sub.add_parser("tree", help="show the component hierarchy with rolled-up masses")
    s.set_defaults(func=cmd_tree)

    s = sub.add_parser("history", help="show the change log of a component")
    s.add_argument("id")
    s.set_defaults(func=cmd_history)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
