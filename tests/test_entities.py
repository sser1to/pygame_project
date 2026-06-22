"""Tests for Player, Monster, Item, StoneProjectile, and item helper functions."""

import math
import random

import pygame

from entities import (
    Item,
    Monster,
    Player,
    StoneProjectile,
    build_item_outlines,
    get_item_outline_key,
    get_item_sprite,
)
from settings import (
    ITEM_CANDLE,
    ITEM_COAL,
    ITEM_LEVER,
    ITEM_STONE,
    ITEM_OUTLINE_COLOR,
    PLAYER_SPEED,
    STONE_THROW_SPEED,
    TILE_SIZE,
)


class TestPlayer:
    def test_creation(self):
        p = Player((100, 200), 32, [pygame.Surface((32, 32))])
        assert p.pos == pygame.Vector2(100, 200)
        assert p.rect.size == (32, 32)
        assert p.carrying is None
        assert not p.moving

    def test_clamp_to_map(self):
        p = Player((200, 300), 32, [pygame.Surface((32, 32))])
        p.clamp_to_map((1280, 720))
        assert p.pos.x == 200 and p.pos.y == 300

    def test_clamp_to_map_negative(self):
        p = Player((-50, -30), 32, [pygame.Surface((32, 32))])
        p.clamp_to_map((1280, 720))
        assert p.pos.x >= 0 and p.pos.y >= 0

    def test_clamp_to_map_outside_right(self):
        p = Player((1500, 800), 32, [pygame.Surface((32, 32))])
        p.clamp_to_map((1280, 720))
        assert p.pos.x <= 1280 - 32
        assert p.pos.y <= 720 - 32

    def test_animation_cycles(self):
        images = [pygame.Surface((32, 32)) for _ in range(3)]
        p = Player((0, 0), 32, images)
        assert p.anim_index == 0
        p.moving = True
        p.update_animation(0.5)
        assert p.anim_index == 1
        p.update_animation(0.5)
        assert p.anim_index == 2
        p.update_animation(0.5)
        assert p.anim_index == 0

    def test_animation_resets_when_stopped(self, small_grid):
        images = [pygame.Surface((32, 32)) for _ in range(3)]
        p = Player((0, 0), 32, images)
        p.moving = True
        p.update_animation(0.5)
        assert p.anim_index == 1
        p.moving = False
        p.update_animation(0.5)
        assert p.anim_index == 0


class TestMonster:
    def test_creation(self):
        assets = {
            "head": pygame.Surface((20, 20)),
            "arm_upper": pygame.Surface((10, 10)),
            "arm_lower": pygame.Surface((10, 10)),
        }
        m = Monster((200, 300), assets, [(400, 300), (200, 100)])
        assert m.pos == pygame.Vector2(200, 300)
        assert len(m.patrol_points) == 2

    def test_next_patrol_target_cycles(self):
        assets = {
            "head": pygame.Surface((10, 10)),
            "arm_upper": pygame.Surface((5, 5)),
            "arm_lower": pygame.Surface((5, 5)),
        }
        m = Monster((0, 0), assets, [(100, 0), (200, 0)])
        m.patrol_index = 0
        assert m.next_patrol_target() == pygame.Vector2(100, 0)
        assert m.next_patrol_target() == pygame.Vector2(200, 0)
        assert m.next_patrol_target() == pygame.Vector2(100, 0)

    def test_next_patrol_target_none(self):
        assets = {
            "head": pygame.Surface((10, 10)),
            "arm_upper": pygame.Surface((5, 5)),
            "arm_lower": pygame.Surface((5, 5)),
        }
        m = Monster((0, 0), assets, [])
        assert m.next_patrol_target() is None

    def test_solve_arm_ik_returns_reasonable_angles(self):
        shoulder = pygame.Vector2(200, 200)
        target = pygame.Vector2(220, 180)
        upper, lower, elbow = Monster.solve_arm_ik(shoulder, target, 30, 25, 1.0)
        assert -180 < upper < 180
        assert -180 < lower < 180
        assert isinstance(elbow, pygame.Vector2)

    def test_solve_arm_ik_closest_point(self):
        shoulder = pygame.Vector2(0, 0)
        target = shoulder + pygame.Vector2(1, 1)
        upper, lower, elbow = Monster.solve_arm_ik(shoulder, target, 50, 50, 1.0)
        assert math.isfinite(upper)
        assert math.isfinite(lower)

    def test_solve_arm_ik_max_reach(self):
        shoulder = pygame.Vector2(0, 0)
        target = pygame.Vector2(500, 0)
        upper, lower, elbow = Monster.solve_arm_ik(shoulder, target, 50, 50, 1.0)
        assert math.isfinite(upper)
        assert math.isfinite(lower)

    def test_get_shoulders(self):
        assets = {
            "head": pygame.Surface((20, 20)),
            "arm_upper": pygame.Surface((10, 10)),
            "arm_lower": pygame.Surface((10, 10)),
        }
        m = Monster((100, 100), assets, [(200, 100)])
        left, right = m.get_shoulders()
        assert left.x < right.x

    def test_apply_grab_offset_not_moving_returns_target(self):
        assets = {
            "head": pygame.Surface((10, 10)),
            "arm_upper": pygame.Surface((5, 5)),
            "arm_lower": pygame.Surface((5, 5)),
        }
        m = Monster((0, 0), assets, [])
        result = m.apply_grab_offset(pygame.Vector2(0, 0), pygame.Vector2(50, 60), 0.0)
        assert result == pygame.Vector2(50, 60)

    def test_apply_grab_offset_none_target(self):
        assets = {
            "head": pygame.Surface((10, 10)),
            "arm_upper": pygame.Surface((5, 5)),
            "arm_lower": pygame.Surface((5, 5)),
        }
        m = Monster((100, 100), assets, [])
        result = m.apply_grab_offset(pygame.Vector2(100, 100), None, 0.0)
        assert result.y > 100


class TestStoneProjectile:
    def test_creation(self):
        proj = StoneProjectile((0, 0), (100, 0), pygame.Surface((8, 8)), (3, 1))
        assert not proj.done
        assert proj.pos == pygame.Vector2(0, 0)
        assert proj.landing_tile == (3, 1)

    def test_update_moves_toward_end(self):
        proj = StoneProjectile((0, 0), (100, 0), pygame.Surface((8, 8)), (3, 1))
        proj.update(0.5)
        assert proj.pos.x > 0
        assert proj.pos.y == 0

    def test_update_completes(self):
        proj = StoneProjectile((0, 0), (50, 0), pygame.Surface((8, 8)), (3, 1))
        proj.update(10.0)
        assert proj.done
        assert proj.pos == proj.end

    def test_update_after_done_noop(self):
        proj = StoneProjectile((0, 0), (50, 0), pygame.Surface((8, 8)), (3, 1))
        proj.update(10.0)
        assert proj.done
        old_pos = proj.pos.copy()
        proj.update(1.0)
        assert proj.pos == old_pos

    def test_duration_based_on_distance(self):
        far = StoneProjectile((0, 0), (1000, 0), pygame.Surface((8, 8)), (10, 1))
        near = StoneProjectile((0, 0), (10, 0), pygame.Surface((8, 8)), (1, 1))
        assert far.duration > near.duration

    def test_minimum_duration(self):
        proj = StoneProjectile((0, 0), (0.1, 0), pygame.Surface((8, 8)), (1, 1))
        assert proj.duration >= 0.12


class TestItem:
    def test_creation(self):
        item = Item(ITEM_COAL, (5, 3))
        assert item.kind == ITEM_COAL
        assert item.tile == (5, 3)
        assert not item.active

    def test_lever_active(self):
        item = Item(ITEM_LEVER, (2, 2), active=True)
        assert item.active

    def test_default_active_false(self):
        item = Item(ITEM_CANDLE, (1, 1))
        assert not item.active


class TestItemFunctions:
    def test_get_item_sprite(self):
        assets = {ITEM_COAL: "coal_sprite", ITEM_LEVER: "noop"}
        assets["lever_off"] = "off_sprite"
        assets["lever_on"] = "on_sprite"
        item = Item(ITEM_COAL, (0, 0))
        assert get_item_sprite(item, assets) == "coal_sprite"

    def test_get_item_sprite_lever_off(self):
        assets = {"lever_off": "off", "lever_on": "on"}
        item = Item(ITEM_LEVER, (0, 0), active=False)
        assert get_item_sprite(item, assets) == "off"

    def test_get_item_sprite_lever_on(self):
        assets = {"lever_off": "off", "lever_on": "on"}
        item = Item(ITEM_LEVER, (0, 0), active=True)
        assert get_item_sprite(item, assets) == "on"

    def test_get_item_outline_key(self):
        assert get_item_outline_key(Item(ITEM_STONE, (0, 0))) == ITEM_STONE

    def test_get_item_outline_key_lever_off(self):
        assert get_item_outline_key(Item(ITEM_LEVER, (0, 0), active=False)) == "lever_off"

    def test_get_item_outline_key_lever_on(self):
        assert get_item_outline_key(Item(ITEM_LEVER, (0, 0), active=True)) == "lever_on"

    def test_build_item_outlines(self):
        assets = {
            "coal": pygame.Surface((16, 16), pygame.SRCALPHA),
            "candle": pygame.Surface((16, 16), pygame.SRCALPHA),
        }
        assets["coal"].fill((255, 255, 255))
        assets["candle"].fill((200, 200, 200))
        outlines = build_item_outlines(assets, (80, 140, 200))
        assert "coal" in outlines
        assert "candle" in outlines
