from dataclasses import replace

import pytest

from mass_properties import Component, Store


@pytest.fixture
def store():
    s = Store(":memory:")
    yield s
    s.close()


def test_insert_and_read_back(store):
    c = Component("ac", "Aircraft", mass=0)
    store.upsert(c)
    assert store.get("ac") == c


def test_update_logs_each_changed_field(store):
    c = Component("eng", "Engine", mass=300, cg_x=2)
    store.upsert(c, source="initial")
    changes = store.upsert(replace(c, mass=320, cg_x=2.5), source="design update")
    assert changes == 2
    fields = [row["field"] for row in store.history("eng")]
    assert fields == ["created", "mass", "cg_x"]
    mass_row = store.history("eng")[1]
    assert (mass_row["old_value"], mass_row["new_value"]) == ("300.0", "320.0")
    assert mass_row["source"] == "design update"


def test_unchanged_upsert_logs_nothing(store):
    c = Component("a", "A", mass=1)
    store.upsert(c)
    assert store.upsert(c) == 0


def test_batch_inserts_parents_before_children(store):
    child = Component("wing", "Wing", parent_id="ac", mass=100)
    parent = Component("ac", "Aircraft")
    store.upsert_many([child, parent])
    assert {c.id for c in store.all()} == {"ac", "wing"}


def test_negative_mass_blocked_by_database(store):
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        store.upsert(Component("bad", "Bad", mass=-1))
