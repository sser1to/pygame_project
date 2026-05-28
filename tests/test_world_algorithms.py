import math
import random

import world


def test_build_flow_field_and_pick_step(small_map):
    grid, spawn = small_map
    # goal at (3,1) (a floor tile)
    goals = [((3, 1), 0.0)]
    field = world.build_flow_field(grid, goals)
    # goal tile cost should be finite and minimal
    gx, gy = 3, 1
    assert field[gy][gx] == 0.0

    # from tile (1,1) a step should move closer to goal
    start = (1, 1)
    rng = random.Random(0)
    step = world.pick_flow_step(field, start, rng)
    assert step is not None
    # distance to goal decreases
    def manhattan(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    assert manhattan(step, (gx, gy)) < manhattan(start, (gx, gy))


def test_pick_flow_step_none_when_isolated():
    # create field with inf everywhere
    field = [[float('inf') for _ in range(3)] for _ in range(3)]
    assert world.pick_flow_step(field, (1, 1), random.Random(0)) is None


def test_spawn_items_places_requested_counts(tmp_path):
    # create a simple open grid 5x5 with center spawn
    grid = [[2]*5 for _ in range(5)]
    for y in range(1, 4):
        for x in range(1, 4):
            grid[y][x] = 1
    spawn = (2, 2)
    items_counts = {'candles': 1, 'stones': 1, 'food': 1}
    objectives = {'coal': 1, 'levers': 2}
    items = world.spawn_items(grid, spawn, items_counts, objectives)
    # expected total = 1+1+1 + 1 + 2 = 6
    assert len(items) == 6
    # all items on floor and not on spawn
    floor = {(x, y) for y in range(5) for x in range(5) if grid[y][x] == 1}
    for item in items:
        assert item.tile in floor
        assert item.tile != spawn


def test_build_dark_tiles_returns_subset_of_floor(small_map):
    grid, spawn = small_map
    dark = world.build_dark_tiles(grid, spawn, darkness_amount=0.8)
    # dark tiles are subset of floor tiles and don't include spawn
    floor = set((x, y) for y, row in enumerate(grid) for x, t in enumerate(row) if t == 1)
    assert dark.issubset(floor)
    assert spawn not in dark
