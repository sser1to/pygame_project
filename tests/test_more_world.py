import math
import random

from world import FlowField, Grid, Level
from entities import Item
from settings import ITEM_CANDLE, TILE_SIZE


def test_build_flow_field_multiple_goals(small_grid):
    grid = small_grid
    goals = [((1, 1), 0.0), ((3, 1), 5.0)]
    field = FlowField.build(grid, goals)
    assert math.isfinite(field[1][1])
    assert math.isfinite(field[1][3])
    assert field[1][1] <= field[1][3]


def test_pick_flow_step_decreases_cost():
    field = [
        [3.0, 2.0, 1.0],
        [3.0, 2.0, 1.0],
        [3.0, 2.0, 1.0],
    ]
    start = (0, 1)
    step = FlowField.pick_step(field, start, random.Random(0))
    assert step is not None
    assert step[0] > start[0]


def test_spawn_items_relaxation_small_grid():
    data = [[2]*5 for _ in range(5)]
    for y in range(1, 4):
        for x in range(1, 4):
            data[y][x] = 1
    grid = Grid(None, data=data)
    grid.data[2][2] = 6

    levels_data = [{
        "level": 1,
        "items": {"candles": 1, "stones": 0, "food": 1},
        "objectives": {"coal": 1, "levers": 2},
    }]
    level = Level(grid, 1, levels_data, [])
    items = level.spawn_items()
    assert len(items) == 6
    kinds = [i.kind for i in items]
    assert "lever" in kinds


def test_get_candle_light_tiles_player_and_items():
    data = [[1]*5 for _ in range(5)]
    grid = Grid(None, data=data)
    grid.data[2][2] = 6

    levels_data = [{
        "level": 1,
        "items": {"candles": 2},
        "objectives": {},
    }]
    level = Level(grid, 1, levels_data, [])

    class DummyPlayer:
        def __init__(self):
            self.carrying = ITEM_CANDLE
            self.rect = type('R', (), {'centerx': 1 * TILE_SIZE + TILE_SIZE//2, 'centery': 1 * TILE_SIZE + TILE_SIZE//2})()

    level.player = DummyPlayer()
    level.items = [Item(ITEM_CANDLE, (2, 1))]

    light = level.get_candle_light_tiles()
    player_tile = (level.player.rect.centerx // TILE_SIZE, level.player.rect.centery // TILE_SIZE)
    assert player_tile in light
    assert (2, 1) in light


def test_pick_monster_spawns_returns_count():
    data = [[2]*7 for _ in range(7)]
    for y in range(1, 6):
        for x in range(1, 6):
            data[y][x] = 1
    grid = Grid(None, data=data)
    grid.data[3][3] = 6

    levels_data = [{
        "level": 1,
        "items": {},
        "objectives": {},
        "monster_abilities": {"cloning": 1},
    }]
    level = Level(grid, 1, levels_data, [])
    spawns = level.pick_monster_spawns()
    assert len(spawns) == 2
