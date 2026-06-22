"""Tests for Grid, FlowField, DataManager, SaveManager, and Level."""

import json
import math
import os

import pygame

from world import DataManager, FlowField, Grid, Level, SaveManager
from settings import (
    ITEM_APPLE,
    ITEM_CANDLE,
    ITEM_COAL,
    ITEM_LEVER,
    ITEM_STONE,
    TILE_FLOOR,
    TILE_FURNACE,
    TILE_SPAWN,
    TILE_WALL,
    TILE_WALL_TOP,
    TILE_SIZE,
    COLD_MAX,
    HUNGER_MAX,
    STONE_THROW_RANGE,
)


# ─── Grid ────────────────────────────────────────────────────────────────────


class TestGridBasic:
    def test_create_from_data(self, small_grid):
        assert small_grid.rows == 5
        assert small_grid.cols == 5

    def test_find_spawn_tile_replaces(self, small_grid):
        tile = small_grid.find_spawn_tile()
        assert tile == (2, 2)
        assert small_grid.data[2][2] == TILE_FLOOR

    def test_find_spawn_tile_fallback(self):
        data = [[TILE_FLOOR, TILE_FLOOR], [TILE_FLOOR, TILE_FLOOR]]
        g = Grid(None, data=data)
        assert g.find_spawn_tile() == (1, 1)

    def test_map_size_px(self, small_grid):
        w, h = small_grid.map_size_px
        assert w == 5 * TILE_SIZE
        assert h == 5 * TILE_SIZE

    def test_collect_floor_tiles(self, small_grid):
        tiles = small_grid.collect_floor_tiles()
        assert len(tiles) == 8

    def test_collect_floor_tiles_excludes_walls(self, small_grid):
        tiles = small_grid.collect_floor_tiles()
        assert (0, 0) not in tiles
        assert (1, 1) in tiles

    def test_adjacent_tiles_center(self):
        tiles = Grid.adjacent_tiles((3, 4))
        assert (4, 4) in tiles
        assert (2, 4) in tiles
        assert (3, 5) in tiles
        assert (3, 3) in tiles
        assert len(tiles) == 4

    def test_tile_in_bounds_true(self, small_grid):
        assert small_grid.tile_in_bounds((0, 0))
        assert small_grid.tile_in_bounds((4, 4))

    def test_tile_in_bounds_false(self, small_grid):
        assert not small_grid.tile_in_bounds((-1, 0))
        assert not small_grid.tile_in_bounds((0, 5))
        assert not small_grid.tile_in_bounds((5, 0))

    def test_tile_is_placeable(self, small_grid):
        assert small_grid.tile_is_placeable((2, 1))
        assert not small_grid.tile_is_placeable((0, 0))
        assert not small_grid.tile_is_placeable((-1, 0))

    def test_tile_is_furnace(self):
        data = [[TILE_FLOOR, TILE_FURNACE], [TILE_WALL, TILE_FLOOR]]
        g = Grid(None, data=data)
        assert g.tile_is_furnace((0, 1)) is False
        assert g.tile_is_furnace((1, 0)) is True

    def test_tile_blocks_vision(self):
        data = [[TILE_FLOOR, TILE_WALL], [TILE_WALL_TOP, TILE_FURNACE]]
        g = Grid(None, data=data)
        assert not g.tile_blocks_vision((0, 0))
        assert g.tile_blocks_vision((1, 0))
        assert g.tile_blocks_vision((0, 1))
        assert g.tile_blocks_vision((1, 1))
        assert g.tile_blocks_vision((-1, 0))

    def test_tile_is_walkable(self):
        data = [[TILE_FLOOR, TILE_WALL], [TILE_WALL_TOP, TILE_FURNACE]]
        g = Grid(None, data=data)
        assert g.tile_is_walkable((0, 0))
        assert not g.tile_is_walkable((1, 0))
        assert not g.tile_is_walkable((0, 1))
        assert not g.tile_is_walkable((1, 1))
        assert not g.tile_is_walkable((-1, 0))

    def test_is_solid(self):
        assert not Grid.is_solid(TILE_FLOOR)
        assert Grid.is_solid(TILE_WALL)
        assert Grid.is_solid(TILE_WALL_TOP)
        assert Grid.is_solid(TILE_FURNACE)

    def test_tile_to_world_center(self):
        result = Grid.tile_to_world_center((2, 3))
        assert result == (2 * TILE_SIZE + TILE_SIZE / 2, 3 * TILE_SIZE + TILE_SIZE / 2)

    def test_direction_to_offset_zero(self):
        assert Grid.direction_to_offset(pygame.Vector2(0, 0)) == (0, 0)

    def test_direction_to_offset_right(self):
        assert Grid.direction_to_offset(pygame.Vector2(10, 3)) == (1, 0)

    def test_direction_to_offset_up(self):
        assert Grid.direction_to_offset(pygame.Vector2(-2, -10)) == (0, -1)

    def test_get_wall_tiles_near(self, small_grid):
        walls = small_grid.get_wall_tiles_near((2, 2), 2)
        assert (1, 0) in walls


class TestGridLineOfSight:
    def test_clear_sight(self):
        data = [[TILE_FLOOR] * 5 for _ in range(5)]
        for y in [0, 4]:
            for x in range(5):
                data[y][x] = TILE_WALL
        for x in [0, 4]:
            for y in range(5):
                data[y][x] = TILE_WALL
        g = Grid(None, data=data)
        start = (TILE_SIZE, TILE_SIZE)
        end = (3 * TILE_SIZE, 3 * TILE_SIZE)
        assert g.has_line_of_sight(start, end)

    def test_blocked_sight(self):
        data = [[TILE_FLOOR] * 5 for _ in range(5)]
        data[2][2] = TILE_WALL
        g = Grid(None, data=data)
        start = (TILE_SIZE, TILE_SIZE)
        end = (3 * TILE_SIZE, 3 * TILE_SIZE)
        assert not g.has_line_of_sight(start, end)

    def test_bresenham_iterates(self):
        result = list(Grid._bresenham_line((0, 0), (3, 2)))
        assert len(result) >= 3
        assert result[0] == (0, 0)
        assert result[-1] == (3, 2)


class TestGridIterSolidTiles:
    def test_iter_empty_room(self, small_grid):
        rect = pygame.Rect(1 * TILE_SIZE, 1 * TILE_SIZE, TILE_SIZE, TILE_SIZE)
        tiles = list(small_grid.iter_solid_tiles(rect))
        assert len(tiles) == 0

    def test_iter_wall(self, small_grid):
        rect = pygame.Rect(0, 0, TILE_SIZE, TILE_SIZE)
        tiles = list(small_grid.iter_solid_tiles(rect))
        assert len(tiles) == 1

    def test_skip_tiles(self):
        data = [[TILE_FURNACE, TILE_WALL]]
        g = Grid(None, data=data)
        rect = pygame.Rect(0, 0, TILE_SIZE * 2, TILE_SIZE)
        all_tiles = list(g.iter_solid_tiles(rect))
        assert len(all_tiles) == 2
        skip = list(g.iter_solid_tiles(rect, skip_tiles={TILE_FURNACE}))
        assert len(skip) == 1


class TestGridFurnace:
    def test_furnace_rect_single(self):
        data = [[TILE_FURNACE, TILE_FLOOR]]
        g = Grid(None, data=data)
        rect = g.get_furnace_rect((0, 0))
        assert rect is not None
        assert rect.width == TILE_SIZE

    def test_furnace_rect_double(self):
        data = [[TILE_FURNACE, TILE_FURNACE]]
        g = Grid(None, data=data)
        rect = g.get_furnace_rect((0, 0))
        assert rect is not None
        assert rect.width == TILE_SIZE * 2

    def test_furnace_rect_none(self):
        data = [[TILE_FLOOR]]
        g = Grid(None, data=data)
        assert g.get_furnace_rect((0, 0)) is None

    def test_get_all_furnace_rects(self):
        data = [
            [TILE_FURNACE, TILE_FURNACE, TILE_FLOOR],
            [TILE_FLOOR, TILE_FURNACE, TILE_FLOOR],
        ]
        g = Grid(None, data=data)
        rects = g.get_all_furnace_rects()
        assert len(rects) == 2

    def test_pick_arm_targets_empty(self):
        left, right = Grid.pick_arm_targets([], pygame.Vector2(100, 100))
        assert left is None
        assert right is None

    def test_pick_arm_targets_chooses(self):
        walls = [(2, 1), (4, 1)]
        pos = pygame.Vector2(300, 150)
        left, right = Grid.pick_arm_targets(walls, pos)
        assert left is not None
        assert right is not None


# ─── FlowField ───────────────────────────────────────────────────────────────


class TestFlowField:
    def test_build_basic(self, small_grid):
        goals = [((1, 1), 0.0)]
        cost = FlowField.build(small_grid, goals)
        assert cost[1][1] == 0.0
        assert cost[2][1] > 0.0

    def test_build_wall_blocks(self, small_grid):
        goals = [((1, 1), 0.0)]
        cost = FlowField.build(small_grid, goals)
        assert cost[0][0] == float("inf")

    def test_build_furnace_blocks(self):
        data = [[TILE_FLOOR, TILE_FURNACE], [TILE_FLOOR, TILE_FLOOR]]
        g = Grid(None, data=data)
        goals = [((0, 1), 0.0)]
        cost = FlowField.build(g, goals)
        assert cost[1][0] == 0.0
        assert cost[0][1] == float("inf")

    def test_wall_penalty(self, small_grid):
        penalty = FlowField._wall_penalty(small_grid, (2, 1))
        assert penalty > 0.0

    def test_wall_penalty_center(self, small_grid):
        penalty = FlowField._wall_penalty(small_grid, (2, 2))
        assert penalty == 0.0  # all immediate neighbours are walkable

    def test_neighbors8(self):
        tiles = FlowField._neighbors8((3, 3))
        assert len(tiles) == 8
        assert (4, 4) in tiles
        assert (2, 2) in tiles

    def test_pick_step_basic(self, small_grid):
        small_grid.find_spawn_tile()  # replace spawn tile with floor
        cost = FlowField.build(small_grid, [((3, 3), 0.0)])
        import random
        rng = random.Random(1)
        step = FlowField.pick_step(cost, (2, 2), rng)
        assert step is not None
        assert cost[step[1]][step[0]] < cost[2][2]

    def test_pick_step_returns_none_isolated(self, small_grid):
        cost = FlowField.build(small_grid, [((1, 1), 0.0)])
        import random
        rng = random.Random(0)
        step = FlowField.pick_step(cost, (0, 0), rng)
        assert step is None

    def test_pick_step_out_of_bounds(self):
        cost = [[float("inf")]]
        import random
        rng = random.Random(0)
        step = FlowField.pick_step(cost, (5, 5), rng)
        assert step is None

    def test_pick_step_inf_cost(self, small_grid):
        cost = FlowField.build(small_grid, [((3, 3), 0.0)])
        import random
        rng = random.Random(0)
        step = FlowField.pick_step(cost, (0, 0), rng)
        assert step is None


# ─── DataManager ─────────────────────────────────────────────────────────────


class TestDataManager:
    def test_load_levels_missing(self, tmp_path):
        missing = tmp_path / "nonexistent.json"
        assert DataManager.load_levels(missing) == []

    def test_load_levels_valid(self, tmp_path):
        path = tmp_path / "levels.json"
        path.write_text('[{"level": 1, "name": "test"}]')
        data = DataManager.load_levels(path)
        assert data == [{"level": 1, "name": "test"}]

    def test_get_level_config_found(self):
        levels = [{"level": 1, "a": 1}, {"level": 2, "b": 2}]
        assert DataManager.get_level_config(levels, 2) == {"level": 2, "b": 2}

    def test_get_level_config_not_found(self):
        assert DataManager.get_level_config([], 3) == {}

    def test_load_notes_missing(self, tmp_path):
        path = tmp_path / "notes.json"
        assert DataManager.load_notes(path) == []

    def test_load_notes_valid(self, tmp_path):
        path = tmp_path / "notes.json"
        path.write_text('[{"level": 1, "text": "hello"}]')
        assert DataManager.load_notes(path) == [{"level": 1, "text": "hello"}]

    def test_get_note_found(self):
        notes = [{"level": 1, "text": "a"}, {"level": 2, "text": "b"}]
        assert DataManager.get_note(notes, 2) == {"level": 2, "text": "b"}

    def test_get_note_not_found(self):
        assert DataManager.get_note([], 5) is None


# ─── SaveManager ─────────────────────────────────────────────────────────────


class TestSaveManager:
    def test_save_and_load(self, tmp_path):
        path = tmp_path / "save.json"
        SaveManager.SAVE_PATH = path
        SaveManager.save_progress(4)
        assert SaveManager.load_progress() == 4

    def test_load_default_when_missing(self, tmp_path):
        path = tmp_path / "save.json"
        SaveManager.SAVE_PATH = path
        assert SaveManager.load_progress() == 1

    def test_save_clamps(self, tmp_path):
        path = tmp_path / "save.json"
        SaveManager.SAVE_PATH = path
        SaveManager.save_progress(999)
        assert SaveManager.load_progress() <= 99

    def test_load_corrupt_returns_default(self, tmp_path):
        path = tmp_path / "save.json"
        path.write_text("not json", encoding="utf-8")
        SaveManager.SAVE_PATH = path
        assert SaveManager.load_progress() == 1


# ─── Level helpers ───────────────────────────────────────────────────────────


def make_player(tile=(1, 1)):
    import entities
    return entities.Player(
        (tile[0] * TILE_SIZE + TILE_SIZE // 2, tile[1] * TILE_SIZE + TILE_SIZE // 2),
        24,
        [pygame.Surface((24, 24))],
    )


class TestLevelBasic:
    def test_create(self, small_grid):
        level = Level(small_grid, 1, [])
        assert level.level_number == 1
        assert level.spawn_tile is not None
        assert not level.dead

    def test_cold_disabled(self, small_grid):
        level = Level(small_grid, 1, [])
        level.freeze_enabled = True
        level.dark_tiles = set()
        player = make_player((2, 2))
        level.setup_entities(player, [], [])
        level.update(1.0, [])
        assert level.cold_value == 0.0

    def test_cold_increases_in_dark(self, small_grid):
        level = Level(small_grid, 1, [])
        level.freeze_enabled = True
        level.dark_tiles = {(2, 2)}
        player = make_player((2, 2))
        level.setup_entities(player, [], [])
        level.update(1.0, [])
        assert level.cold_value > 0.0

    def test_cold_death(self, small_grid):
        level = Level(small_grid, 1, [])
        level.freeze_enabled = True
        level.dark_tiles = {(2, 2)}
        level.cold_value = COLD_MAX
        player = make_player((2, 2))
        level.setup_entities(player, [], [])
        level.update(0.01, [])
        assert level.dead

    def test_hunger_increases(self, small_grid):
        level = Level(small_grid, 1, [])
        level.hunger_enabled = True
        player = make_player()
        level.setup_entities(player, [], [])
        level.update(1.0, [])
        assert level.hunger_value > 0.0

    def test_hunger_death(self, small_grid):
        level = Level(small_grid, 1, [])
        level.hunger_enabled = True
        level.hunger_value = HUNGER_MAX
        player = make_player()
        level.setup_entities(player, [], [])
        level.update(0.01, [])
        assert level.dead

    def test_level_complete_no_requirements(self, small_grid):
        level = Level(small_grid, 1, [])
        level.coal_required = 0
        level.levers_required = 0
        player = make_player()
        level.setup_entities(player, [], [])
        level.update(0.01, [])
        assert level.level_complete


class TestLevelItems:
    def test_spawn_items_creates_apple(self, small_grid):
        level = Level(small_grid, 1, [])
        level.items_config = {"candles": 0, "stones": 0, "food": 1}
        level.objectives_config = {"coal": 0, "levers": 0}
        items = level.spawn_items()
        apples = [it for it in items if it.kind == ITEM_APPLE]
        assert len(apples) == 1

    def test_get_item_at_found(self, small_grid):
        from entities import Item
        item = Item(ITEM_COAL, (2, 1))
        result = Level.get_item_at([item], (2, 1))
        assert result is item

    def test_get_item_at_none(self, small_grid):
        result = Level.get_item_at([], (0, 0))
        assert result is None

    def test_item_is_visible_in_dark(self, small_grid):
        level = Level(small_grid, 1, [])
        level.dark_tiles = {(2, 2)}
        level.setup_entities(make_player((2, 2)), [], [])
        assert not level.item_is_visible((2, 2))

    def test_item_is_visible_normal(self, small_grid):
        level = Level(small_grid, 1, [])
        level.setup_entities(make_player((2, 2)), [], [])
        assert level.item_is_visible((1, 1))


class TestLevelLight:
    def test_get_light_tiles_zero_radius(self, small_grid):
        level = Level(small_grid, 1, [])
        assert level.get_light_tiles((2, 2), 0) == set()

    def test_get_light_tiles_radius_1(self, small_grid):
        level = Level(small_grid, 1, [])
        tiles = level.get_light_tiles((2, 2), 1)
        assert (2, 2) in tiles
        assert (1, 1) in tiles
        assert (3, 3) in tiles
        assert len(tiles) <= 9

    def test_get_candle_tiles_from_item(self, small_grid):
        from entities import Item
        level = Level(small_grid, 1, [])
        player = make_player()
        level.setup_entities(player, [Item(ITEM_CANDLE, (2, 1))], [])
        tiles = level._get_candle_tiles(2)
        assert (2, 1) in tiles

    def test_get_candle_centers_from_player(self, small_grid):
        level = Level(small_grid, 1, [])
        player = make_player((2, 2))
        player.carrying = ITEM_CANDLE
        level.setup_entities(player, [], [])
        centers = level.get_candle_centers()
        assert len(centers) == 1


class TestLevelCombat:
    def test_monster_kills_player(self, small_grid):
        from entities import Monster
        level = Level(small_grid, 1, [])
        monster_pos = 2 * TILE_SIZE + 12  # align with player rect center
        player = make_player((2, 2))
        head = pygame.Surface((20, 20))
        arms = pygame.Surface((10, 10))
        monster = Monster((monster_pos, monster_pos), {"head": head, "arm_upper": arms, "arm_lower": arms}, [])
        level.setup_entities(player, [], [monster])
        level.update(0.01, [])
        assert level.dead


class TestLevelProjectiles:
    def test_throw_stone_basic(self, small_grid):
        level = Level(small_grid, 1, [])
        tile = level.throw_stone((2, 2), (0, -1))
        assert tile == (2, 1)

    def test_throw_stone_blocked_by_wall(self, small_grid):
        level = Level(small_grid, 1, [])
        tile = level.throw_stone((1, 1), (-1, 0))
        assert tile == (1, 1)

    def test_throw_stone_blocked_by_item(self, small_grid):
        from entities import Item
        level = Level(small_grid, 1, [])
        level.items = [Item(ITEM_STONE, (2, 1))]
        tile = level.throw_stone((2, 2), (0, -1))
        assert tile == (2, 2)  # stone cannot leave start tile

    def test_throw_stone_out_of_bounds(self, small_grid):
        level = Level(small_grid, 1, [])
        tile = level.throw_stone((0, 1), (-1, 0))
        assert tile == (0, 1)


class TestLevelCamera:
    def test_compute_camera_center(self):
        player = pygame.Rect(400, 300, 24, 24)
        cam = Level.compute_camera(player, (800, 600))
        assert cam.x == 0
        assert cam.y == 0

    def test_compute_camera_clamps_x(self):
        player = pygame.Rect(500, 300, 24, 24)
        cam = Level.compute_camera(player, (600, 600))
        assert cam.x == 0

    def test_compute_camera_clamps_y(self):
        player = pygame.Rect(400, 500, 24, 24)
        cam = Level.compute_camera(player, (1600, 1200))
        assert cam.y == 152  # 500+12 - 720//2 = 512 - 360 = 152

    def test_compute_camera_negative_clamp(self):
        player = pygame.Rect(-50, -50, 24, 24)
        cam = Level.compute_camera(player, (800, 600))
        assert cam.x >= 0
        assert cam.y >= 0


class TestLevelInteraction:
    def test_interaction_eat_apple(self, small_grid):
        from entities import Item
        level = Level(small_grid, 1, [])
        player = make_player((2, 2))
        apple = Item(ITEM_APPLE, (2, 2))
        level.setup_entities(player, [apple], [])
        ate, loaded, note = level.handle_interaction(None, None, [])
        assert ate
        assert apple not in level.items

    def test_interaction_pickup_coal(self, small_grid):
        from entities import Item
        level = Level(small_grid, 1, [])
        player = make_player((2, 2))
        coal = Item(ITEM_COAL, (2, 2))
        level.setup_entities(player, [coal], [])
        ate, loaded, note = level.handle_interaction(None, None, [])
        assert player.carrying == ITEM_COAL

    def test_interaction_throw_stone(self, small_grid):
        level = Level(small_grid, 1, [])
        player = make_player((2, 2))
        player.carrying = ITEM_STONE
        level.setup_entities(player, [], [])
        stone_sprite = pygame.Surface((8, 8))
        level.handle_interaction(stone_sprite, None, [])

    def test_interaction_load_coal_to_furnace(self, small_grid):
        level = Level(small_grid, 1, [])
        player = make_player((1, 2))
        player.carrying = ITEM_COAL
        small_grid.data[1][1] = TILE_FURNACE  # tile above player
        level.setup_entities(player, [], [])
        ate, loaded, note = level.handle_interaction(None, None, [])
        assert loaded
        assert player.carrying is None

    def test_lever_activation(self, small_grid):
        from entities import Item
        level = Level(small_grid, 1, [])
        player = make_player((1, 1))
        lever = Item(ITEM_LEVER, (1, 1), active=False)
        level.setup_entities(player, [lever], [])
        ate, loaded, note = level.handle_interaction(None, None, [])
        assert lever.active

    def test_carrying_plus_no_direction_returns(self, small_grid):
        level = Level(small_grid, 1, [])
        player = make_player((2, 2))
        player.carrying = ITEM_STONE
        player.last_dir = pygame.Vector2(0, 0)
        level.setup_entities(player, [], [])
        ate, loaded, note = level.handle_interaction(None, None, [])
        assert not ate and not loaded


class TestLevelEdgeCases:
    def test_empty_level_no_crash(self):
        data = [[TILE_FLOOR for _ in range(3)] for _ in range(3)]
        data[1][1] = TILE_SPAWN
        g = Grid(None, data=data)
        level = Level(g, 1, [])
        player = make_player((1, 1))
        level.setup_entities(player, [], [])
        level.update(0.0, [])
        assert not level.dead

    def test_player_tile_computation(self):
        player = make_player((3, 4))
        tile = Level.get_player_tile(player)
        assert tile == (3, 4)

    def test_player_on_tile(self):
        player = make_player((2, 2))
        assert Level.player_on_tile(player, (2, 2))
        assert not Level.player_on_tile(player, (5, 5))

    def test_emit_sound(self):
        events = []
        Level._emit_sound(events, (3, 3))
        assert len(events) == 1

    def test_tile_distance_sq(self):
        d = Level._tile_distance_sq((0, 0), (3, 4))
        assert d == 25

    def test_lerp(self):
        assert Level._lerp(0, 10, 0.5) == 5.0

    def test_smoothstep(self):
        assert Level._smoothstep(0.0) == 0.0
        assert Level._smoothstep(1.0) == 1.0
        assert Level._smoothstep(0.5) == 0.5

    def test_neighbors8_delegates(self):
        tiles = Level._neighbors8((2, 2))
        assert len(tiles) == 8


class TestLevelSpawning:
    def test_pick_monster_spawns_default(self, small_grid):
        level = Level(small_grid, 1, [])
        spawns = level.pick_monster_spawns()
        assert isinstance(spawns, list)

    def test_build_patrol_points(self, small_grid):
        level = Level(small_grid, 1, [])
        points = level.build_patrol_points()
        assert isinstance(points, list)

    def test_filter_small_clusters_empty(self):
        assert Level._filter_small_clusters(set(), 2) == set()

    def test_filter_small_clusters_removes_small(self):
        tiles = {(1, 1), (1, 2), (5, 5)}
        result = Level._filter_small_clusters(tiles, 2)
        assert (1, 1) in result
        assert (5, 5) not in result
