import pytest

from mass_properties import Component, combine, rollup
from mass_properties.rollup import parallel_axis_shift, subtree


def approx_matrix(actual, expected, tol=1e-9):
    for row_a, row_e in zip(actual, expected):
        assert row_a == pytest.approx(row_e, abs=tol)


def test_two_equal_point_masses_cg_is_midpoint():
    a = Component("a", "A", mass=10, cg_x=0)
    b = Component("b", "B", mass=10, cg_x=2)
    mp = combine([a, b])
    assert mp.mass == 20
    assert mp.cg == pytest.approx((1.0, 0.0, 0.0))


def test_two_point_masses_inertia_from_parallel_axis():
    # Two 10 kg point masses 1 m either side of the CG on the x-axis:
    # Iyy = Izz = 2 * 10 * 1^2 = 20, Ixx = 0
    a = Component("a", "A", mass=10, cg_x=-1)
    b = Component("b", "B", mass=10, cg_x=1)
    mp = combine([a, b])
    approx_matrix(mp.inertia, ((0, 0, 0), (0, 20, 0), (0, 0, 20)))


def test_own_inertia_is_added_to_shift():
    a = Component("a", "A", mass=2, cg_y=3, ixx=1, iyy=1, izz=1)
    mp = combine([a])
    # Single component: CG is its own CG, so total inertia = own inertia.
    approx_matrix(mp.inertia, ((1, 0, 0), (0, 1, 0), (0, 0, 1)))


def test_parallel_axis_products_of_inertia():
    shift = parallel_axis_shift(4.0, (1.0, 2.0, 0.0))
    # Ixx = m(dy^2+dz^2) = 16, Iyy = m(dx^2+dz^2) = 4, Izz = m(dx^2+dy^2) = 20, Ixy = -m dx dy = -8
    approx_matrix(shift, ((16, -8, 0), (-8, 4, 0), (0, 0, 20)))


def test_rollup_includes_descendants_only():
    items = [
        Component("ac", "Aircraft"),
        Component("wing", "Wing", parent_id="ac"),
        Component("wl", "Left wing", parent_id="wing", mass=100, cg_y=-5),
        Component("wr", "Right wing", parent_id="wing", mass=100, cg_y=5),
        Component("eng", "Engine", parent_id="ac", mass=300, cg_x=2),
    ]
    wing = rollup(items, "wing")
    assert wing.mass == 200
    assert wing.cg == pytest.approx((0, 0, 0))
    total = rollup(items, "ac")
    assert total.mass == 500
    assert total.cg[0] == pytest.approx(300 * 2 / 500)


def test_zero_mass_rollup_is_safe():
    mp = combine([Component("empty", "Empty assembly")])
    assert mp.mass == 0
    assert mp.cg == (0.0, 0.0, 0.0)


def test_unknown_root_raises():
    with pytest.raises(KeyError):
        subtree([Component("a", "A")], "missing")
