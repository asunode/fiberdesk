import pytest

from fiberdesk.core.colorcode import (CABLE_SIZES, TIA598_COLORS, cable_grid,
                                      color_for_position, locate_fiber)

ORDER = ["Blue", "Orange", "Green", "Brown", "Slate", "White",
         "Red", "Black", "Yellow", "Violet", "Rose", "Aqua"]


def test_sequence_matches_tia598():
    assert [name for name, _ in TIA598_COLORS] == ORDER


@pytest.mark.parametrize("fiber, tube, color", [
    (1, "Blue", "Blue"),
    (12, "Blue", "Aqua"),
    (13, "Orange", "Blue"),
    (37, "Brown", "Blue"),
    (48, "Brown", "Aqua"),
    (96, "Black", "Aqua"),
    (144, "Aqua", "Aqua"),
])
def test_locate_fiber(fiber, tube, color):
    addr = locate_fiber(fiber, 144)
    assert addr.tube.name == tube
    assert addr.color.name == color
    assert addr.tube.tracer is None and addr.color.tracer is None


def test_tube_numbers():
    addr = locate_fiber(37, 48)
    assert addr.tube.position == 4
    assert addr.color.position == 1


def test_positions_above_twelve_get_tracer():
    assert color_for_position(13).label == "Blue / Black tracer"
    assert color_for_position(20).label == "Black / Yellow tracer"
    assert color_for_position(24).name == "Aqua"
    assert color_for_position(25).tracer is None  # cycle restarts


def test_cable_larger_than_144_uses_tracer_tubes():
    addr = locate_fiber(145, 288)
    assert addr.tube.position == 13
    assert addr.tube.tracer == "Black"


@pytest.mark.parametrize("size", CABLE_SIZES)
def test_grid_shape(size):
    grid = cable_grid(size)
    assert len(grid) == size // 12
    assert all(len(row) == 12 for row in grid)
    assert [a.fiber for row in grid for a in row] == list(range(1, size + 1))


def test_grid_with_six_fibers_per_tube():
    grid = cable_grid(24, fibers_per_tube=6)
    assert len(grid) == 4
    assert grid[1][0].tube.name == "Orange"


@pytest.mark.parametrize("fiber, size", [(0, 12), (13, 12), (49, 48)])
def test_out_of_range(fiber, size):
    with pytest.raises(ValueError):
        locate_fiber(fiber, size)
