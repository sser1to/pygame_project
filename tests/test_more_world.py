import math
import random

import world
from entities import Item
from settings import ITEM_CANDLE


def test_build_flow_field_multiple_goals(small_map):
    grid, _ = small_map
    goals = [((1, 1), 0.0), ((3, 1), 5.0)]
    field = world.build_flow_field(grid, goals)
    # both goals reachable and pref rule: lower-bias goal has <= cost
    assert math.isfinite(field[1][1])
    assert math.isfinite(field[1][3])
    assert field[1][1] <= field[1][3]


def test_pick_flow_step_decreases_cost():
    # build artificial field where cost decreases to the right
    field = [
        [3.0, 2.0, 1.0],
        [3.0, 2.0, 1.0],
        [3.0, 2.0, 1.0],
    ]
    start = (0, 1)
    step = world.pick_flow_step(field, start, random.Random(0))
    assert step is not None
    assert step[0] > start[0]


def test_spawn_items_relaxation_small_grid(small_map):
    grid, spawn = small_map
    items_counts = {'candles': 1, 'stones': 0, 'food': 1}
    objectives = {'coal': 1, 'levers': 2}
    items = world.spawn_items(grid, spawn, items_counts, objectives)
    # requested total = 1+0+1 +1 +2 = 5
    assert len(items) == 5
    kinds = [i.kind for i in items]
    assert world.ITEM_LEVER in kinds or any(k == world.ITEM_LEVER for k in kinds)


def test_get_candle_light_tiles_player_and_items():
    class DummyPlayer:
        def __init__(self):
            self.carrying = ITEM_CANDLE
            self.rect = type('R', (), {'centerx': 1 * world.TILE_SIZE + world.TILE_SIZE//2, 'centery': 1 * world.TILE_SIZE + world.TILE_SIZE//2})

    player = DummyPlayer()
    items = [Item(world.ITEM_CANDLE, (2, 1))]
    light = world.get_candle_light_tiles(items, player)
    # player tile should be lit and item tile lit
    player_tile = (player.rect.centerx // world.TILE_SIZE, player.rect.centery // world.TILE_SIZE)
    assert player_tile in light
    assert (2, 1) in light


def test_pick_monster_spawns_returns_count(small_map):
    grid, spawn = small_map
    spawns = world.pick_monster_spawns(grid, spawn, 2)
    assert len(spawns) == 2
