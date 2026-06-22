import math
import random

from world import FlowField, Grid, Level
from settings import ITEM_COAL, ITEM_CANDLE, TILE_SIZE


def test_build_flow_field_and_pick_step(small_grid):
    grid = small_grid
    goals = [((3, 1), 0.0)]
    field = FlowField.build(grid, goals)
    gx, gy = 3, 1
    assert field[gy][gx] == 0.0

    start = (1, 1)
    rng = random.Random(0)
    step = FlowField.pick_step(field, start, rng)
    assert step is not None

    def manhattan(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    assert manhattan(step, (gx, gy)) < manhattan(start, (gx, gy))


def test_pick_flow_step_none_when_isolated():
    field = [[float('inf') for _ in range(3)] for _ in range(3)]
    assert FlowField.pick_step(field, (1, 1), random.Random(0)) is None


def test_spawn_items_places_requested_counts():
    data = [[2]*5 for _ in range(5)]
    for y in range(1, 4):
        for x in range(1, 4):
            data[y][x] = 1
    grid = Grid(None, data=data)
    grid.data[2][2] = 6  # spawn tile

    levels_data = [{
        "level": 1,
        "items": {"candles": 1, "stones": 1, "food": 1},
        "objectives": {"coal": 1, "levers": 2},
    }]
    level = Level(grid, 1, levels_data)
    items = level.spawn_items()
    assert len(items) == 7

    floor = {(x, y) for y in range(5) for x in range(5) if data[y][x] == 1}
    for item in items:
        assert item.tile in floor
        assert item.tile != level.spawn_tile


def test_build_dark_tiles_returns_subset_of_floor(small_grid):
    grid = small_grid

    levels_data = [{
        "level": 1,
        "items": {},
        "objectives": {},
        "debuffs": {"darkness_amount": 0.8},
    }]
    level = Level(grid, 1, levels_data)

    floor = set()
    for y, row in enumerate(grid.data):
        for x, t in enumerate(row):
            if t == 1:
                floor.add((x, y))
    assert level.dark_tiles.issubset(floor)
    assert level.spawn_tile not in level.dark_tiles
