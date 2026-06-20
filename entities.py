import math
import random

import pygame

from settings import (
    MONSTER_ANCHOR_LERP,
    MONSTER_ARM_LOWER_SCALE_X,
    MONSTER_ARM_LOWER_SCALE_Y,
    MONSTER_ARM_UPPER_SCALE_X,
    MONSTER_ARM_UPPER_SCALE_Y,
    MONSTER_GRAB_SWAY,
    MONSTER_HEARING_RANGE_TILES,
    MONSTER_HEAD_SCALE,
    MONSTER_PASSIVE_SPEED,
    MONSTER_SMELL_INTERVAL,
    MONSTER_SMELL_RANGE_TILES,
    MONSTER_SMELL_SPEED,
    MONSTER_STOP_DISTANCE,
    MONSTER_STEP_SPEED,
    MONSTER_TINT,
    PLAYER_ANIM_INTERVAL,
    PLAYER_SPEED,
    STONE_THROW_SPEED,
    TILE_SIZE,
    ITEM_LEVER,
)
from world import (
    build_flow_field,
    get_wall_tiles_near,
    has_line_of_sight,
    pick_arm_targets,
    pick_flow_step,
    tile_to_world_center,
)


class Player:
    def __init__(self, start_px, size_px, images):
        self.pos = pygame.Vector2(start_px)
        self.rect = pygame.Rect(self.pos.x, self.pos.y, size_px, size_px)
        self.images = images
        self.anim_timer = 0.0
        self.anim_index = 0
        self.moving = False
        self.last_dir = pygame.Vector2(0, -1)
        self.carrying = None

    def update(self, dt, grid, map_size_px, skip_solid_tiles=None):
        keys = pygame.key.get_pressed()
        move = pygame.Vector2(0, 0)
        if keys[pygame.K_w]:
            move.y -= 1
        if keys[pygame.K_s]:
            move.y += 1
        if keys[pygame.K_a]:
            move.x -= 1
        if keys[pygame.K_d]:
            move.x += 1

        if move.length_squared() > 0:
            self.last_dir = move
            move = move.normalize()
            self.moving = True
        else:
            self.moving = False

        self.move_and_collide(move.x * PLAYER_SPEED * dt, move.y * PLAYER_SPEED * dt, grid, skip_solid_tiles)
        self.clamp_to_map(map_size_px)
        self.update_animation(dt)

    def move_and_collide(self, dx, dy, grid, skip_solid_tiles=None):
        if dx != 0:
            self.pos.x += dx
            self.rect.x = round(self.pos.x)
            self.resolve_collisions(grid, axis="x", skip_solid_tiles=skip_solid_tiles)
        if dy != 0:
            self.pos.y += dy
            self.rect.y = round(self.pos.y)
            self.resolve_collisions(grid, axis="y", skip_solid_tiles=skip_solid_tiles)

    def resolve_collisions(self, grid, axis, skip_solid_tiles=None):
        from world import iter_solid_tiles

        for tile_rect in iter_solid_tiles(grid, self.rect, skip_solid_tiles):
            if not self.rect.colliderect(tile_rect):
                continue
            if axis == "x":
                if self.rect.centerx > tile_rect.centerx:
                    self.rect.left = tile_rect.right
                else:
                    self.rect.right = tile_rect.left
                self.pos.x = self.rect.x
            else:
                if self.rect.centery > tile_rect.centery:
                    self.rect.top = tile_rect.bottom
                else:
                    self.rect.bottom = tile_rect.top
                self.pos.y = self.rect.y

    def clamp_to_map(self, map_size_px):
        map_w, map_h = map_size_px
        self.pos.x = max(0, min(self.pos.x, map_w - self.rect.width))
        self.pos.y = max(0, min(self.pos.y, map_h - self.rect.height))
        self.rect.x = round(self.pos.x)
        self.rect.y = round(self.pos.y)

    def update_animation(self, dt):
        if not self.moving:
            self.anim_index = 0
            self.anim_timer = 0.0
            return
        self.anim_timer += dt
        if self.anim_timer >= PLAYER_ANIM_INTERVAL:
            self.anim_timer = 0.0
            self.anim_index = (self.anim_index + 1) % len(self.images)

    def draw(self, screen, offset):
        screen.blit(self.images[self.anim_index], (self.rect.x - offset.x, self.rect.y - offset.y))


class Monster:
    def __init__(self, start_pos, assets, patrol_points):
        self.pos = pygame.Vector2(start_pos)
        self.velocity = pygame.Vector2(0, 0)
        self.head = assets["head"]
        self.arm_upper = assets["arm_upper"]
        self.arm_lower = assets["arm_lower"]
        self.rng = random.Random(random.random())
        self.smell_timer = 0.0
        self.target = None
        self.vision_timer = 0.0
        self.last_seen = None
        self.hearing_target = None
        self.smell_target = None
        self.patrol_points = [pygame.Vector2(p) for p in patrol_points]
        self.patrol_index = 0
        self.passive_target = None
        self.moving = False
        self.step_time = 0.0
        self.left_anchor = None
        self.right_anchor = None
        self.is_chasing = False
        self.nav_timer = 0.0
        self.nav_interval = 0.35 * self.rng.uniform(0.8, 1.2)
        self.nav_field = None
        self.nav_goals = None
        self.stall_timer = 0.0
        self.chase_speed = MONSTER_SMELL_SPEED * self.rng.uniform(0.95, 1.05)
        self.passive_speed = MONSTER_PASSIVE_SPEED * self.rng.uniform(0.9, 1.1)
        self.step_speed = MONSTER_STEP_SPEED * self.rng.uniform(0.9, 1.1)
        self.grab_sway = MONSTER_GRAB_SWAY * self.rng.uniform(0.85, 1.15)
        self.smell_interval = MONSTER_SMELL_INTERVAL * self.rng.uniform(0.85, 1.15)
        self.vision_memory = 2.0 * self.rng.uniform(0.8, 1.2)
        self.target_offset = pygame.Vector2(self.rng.uniform(-12, 12), self.rng.uniform(-12, 12))
        if self.patrol_points:
            self.patrol_index = self.rng.randrange(len(self.patrol_points))

    def update(self, dt, player_pos, grid, sound_events, hearing_enabled, smell_enabled, vision_enabled):
        player_vec = pygame.Vector2(player_pos)

        if not hearing_enabled:
            self.hearing_target = None
        if not smell_enabled:
            self.smell_target = None
        if not vision_enabled:
            self.vision_timer = 0.0
            self.last_seen = None

        if vision_enabled and has_line_of_sight(grid, self.pos, player_vec):
            self.last_seen = player_vec + self.target_offset
            self.vision_timer = self.vision_memory
        elif self.vision_timer > 0.0:
            self.vision_timer = max(0.0, self.vision_timer - dt)
            if self.vision_timer == 0.0:
                self.last_seen = None

        if hearing_enabled and sound_events:
            closest_event = None
            closest_dist = None
            for event_pos in sound_events:
                dist = (event_pos - self.pos).length()
                if dist <= MONSTER_HEARING_RANGE_TILES * TILE_SIZE:
                    if closest_event is None or dist < closest_dist:
                        closest_event = event_pos
                        closest_dist = dist
            if closest_event is not None:
                self.hearing_target = pygame.Vector2(closest_event) + self.target_offset

        if smell_enabled:
            self.smell_timer += dt
            if self.smell_timer >= self.smell_interval:
                self.smell_timer = 0.0
                distance = (player_vec - self.pos).length()
                if distance <= MONSTER_SMELL_RANGE_TILES * TILE_SIZE:
                    self.smell_target = player_vec + self.target_offset

        active_target = None
        if self.last_seen is not None and self.vision_timer > 0.0:
            active_target = self.last_seen
        elif self.hearing_target is not None:
            active_target = self.hearing_target
        elif self.smell_target is not None:
            active_target = self.smell_target

        if active_target is not None:
            to_target = active_target - self.pos
            if to_target.length_squared() <= MONSTER_STOP_DISTANCE * MONSTER_STOP_DISTANCE:
                if active_target == self.hearing_target:
                    self.hearing_target = None
                if active_target == self.smell_target:
                    self.smell_target = None
        if self.passive_target is not None:
            to_passive = self.passive_target - self.pos
            if to_passive.length_squared() <= MONSTER_STOP_DISTANCE * MONSTER_STOP_DISTANCE:
                self.passive_target = None
                self.nav_goals = None
                self.nav_field = None

        if active_target is None and self.passive_target is None:
            self.passive_target = self.next_patrol_target()
        elif active_target is not None:
            self.passive_target = None

        goals = []
        if self.last_seen is not None and self.vision_timer > 0.0:
            goals.append((self._pos_to_tile(self.last_seen), 0.0))
        if self.hearing_target is not None:
            goals.append((self._pos_to_tile(self.hearing_target), 6.0))
        if self.smell_target is not None:
            goals.append((self._pos_to_tile(self.smell_target), 8.0))
        if not goals and self.passive_target is not None:
            goals.append((self._pos_to_tile(self.passive_target), 10.0))

        self.is_chasing = bool(self.last_seen or self.hearing_target or self.smell_target)
        self.moving = False

        if goals:
            if self.nav_timer <= 0.0 or goals != self.nav_goals:
                self.nav_field = build_flow_field(grid, goals)
                self.nav_timer = self.nav_interval
                self.nav_goals = list(goals)
            else:
                self.nav_timer = max(0.0, self.nav_timer - dt)

            current_tile = self._pos_to_tile(self.pos)
            step_tile = pick_flow_step(self.nav_field, current_tile, self.rng)
            if step_tile is not None:
                desired_pos = pygame.Vector2(tile_to_world_center(step_tile))
                desired_vec = desired_pos - self.pos
                if desired_vec.length_squared() > 0:
                    desired_dir = desired_vec.normalize()
                else:
                    desired_dir = pygame.Vector2(0, 0)
                speed = self.chase_speed if self.is_chasing else self.passive_speed
                steering = desired_dir * speed
                self.velocity = self.velocity.lerp(steering, 0.18)
                self.pos += self.velocity * dt
                self.moving = self.velocity.length_squared() > 1e-4
            else:
                self.velocity *= 0.85
                if not self.is_chasing:
                    self.passive_target = None
                    self.nav_goals = None
                    self.nav_field = None
        else:
            self.velocity *= 0.85

        if self.is_chasing and not self.moving:
            self.stall_timer += dt
            if self.stall_timer >= 1.25:
                if self.hearing_target is not None:
                    self.hearing_target = None
                if self.smell_target is not None:
                    self.smell_target = None
                if self.last_seen is not None and self.vision_timer <= 0.1:
                    self.last_seen = None
                self.stall_timer = 0.0
        else:
            self.stall_timer = 0.0

        speed_factor = self.step_speed if self.moving else 1.0
        self.step_time += dt * speed_factor
        self.update_anchors(grid)

    @staticmethod
    def _pos_to_tile(pos):
        return (int(pos[0] // TILE_SIZE), int(pos[1] // TILE_SIZE))

    def next_patrol_target(self):
        if not self.patrol_points:
            return None
        if self.patrol_index >= len(self.patrol_points):
            self.patrol_index = 0
        target = self.patrol_points[self.patrol_index]
        self.patrol_index += 1
        return target

    def draw(self, screen, offset):
        head_center = pygame.Vector2(self.pos.x - offset.x, self.pos.y - offset.y)
        head_rect = self.head.get_rect(center=(head_center.x, head_center.y))

        left_shoulder, right_shoulder = self.get_shoulders()
        left_anchor = self.apply_grab_offset(left_shoulder, self.left_anchor, 0.0)
        right_anchor = self.apply_grab_offset(right_shoulder, self.right_anchor, math.pi)

        self.draw_arm(screen, offset, left_shoulder, left_anchor, 1.0, flip_lower=True)
        self.draw_arm(screen, offset, right_shoulder, right_anchor, -1.0)
        screen.blit(self.head, head_rect.topleft)

    def get_shoulders(self):
        shoulder_dx = self.head.get_width() * 0.35
        shoulder_dy = self.head.get_height() * 0.1
        left_shoulder = pygame.Vector2(self.pos.x - shoulder_dx, self.pos.y + shoulder_dy)
        right_shoulder = pygame.Vector2(self.pos.x + shoulder_dx, self.pos.y + shoulder_dy)
        return left_shoulder, right_shoulder

    def update_anchors(self, grid):
        if grid is None:
            return
        center_tile = (int(self.pos.x // TILE_SIZE), int(self.pos.y // TILE_SIZE))
        wall_tiles = get_wall_tiles_near(grid, center_tile, 4)
        left_shoulder, right_shoulder = self.get_shoulders()
        floor_offset = TILE_SIZE * 0.9

        if not wall_tiles:
            desired_left = pygame.Vector2(left_shoulder.x, left_shoulder.y + floor_offset)
            desired_right = pygame.Vector2(right_shoulder.x, right_shoulder.y + floor_offset)
        else:
            left_target, right_target = pick_arm_targets(wall_tiles, self.pos)
            if left_target is None:
                left_target = (left_shoulder.x, left_shoulder.y + floor_offset)
            if right_target is None:
                right_target = (right_shoulder.x, right_shoulder.y + floor_offset)
            desired_left = pygame.Vector2(left_target)
            desired_right = pygame.Vector2(right_target)

        if self.left_anchor is None:
            self.left_anchor = desired_left
        else:
            self.left_anchor = self.left_anchor.lerp(desired_left, MONSTER_ANCHOR_LERP)
        if self.right_anchor is None:
            self.right_anchor = desired_right
        else:
            self.right_anchor = self.right_anchor.lerp(desired_right, MONSTER_ANCHOR_LERP)

    def apply_grab_offset(self, shoulder, target, phase):
        if target is None:
            return shoulder + pygame.Vector2(0, TILE_SIZE * 0.9)
        target_vec = pygame.Vector2(target)
        if not self.moving:
            return target_vec
        direction = target_vec - shoulder
        if direction.length_squared() == 0:
            return target_vec
        direction = direction.normalize()
        offset = math.sin(self.step_time + phase) * (TILE_SIZE * self.grab_sway)
        return target_vec + direction * offset

    def draw_arm(self, screen, offset, shoulder, target, bend_sign, flip_lower=False):
        upper_len = self.arm_upper.get_width() * 0.9
        lower_len = self.arm_lower.get_width() * 0.9
        upper_angle, lower_angle, elbow = self.solve_arm_ik(shoulder, target, upper_len, lower_len, bend_sign)
        shoulder_screen = pygame.Vector2(shoulder.x - offset.x, shoulder.y - offset.y)
        self.blit_segment(screen, self.arm_upper, shoulder_screen, upper_angle)

        elbow_screen = pygame.Vector2(elbow.x - offset.x, elbow.y - offset.y)
        if flip_lower:
            lower_angle += 180
        self.blit_segment(screen, self.arm_lower, elbow_screen, lower_angle)

    @staticmethod
    def solve_arm_ik(shoulder, target, upper_len, lower_len, bend_sign):
        dx = target.x - shoulder.x
        dy = target.y - shoulder.y
        dist = math.hypot(dx, dy)
        if dist < 1e-3:
            dist = 1e-3
        max_reach = upper_len + lower_len - 1
        min_reach = abs(upper_len - lower_len) + 1
        dist = max(min_reach, min(dist, max_reach))

        base_angle = math.atan2(dy, dx)
        cos_angle = (upper_len * upper_len + dist * dist - lower_len * lower_len) / (2 * upper_len * dist)
        cos_angle = max(-1.0, min(1.0, cos_angle))
        offset_angle = math.acos(cos_angle)
        upper_angle = base_angle + bend_sign * offset_angle

        elbow = pygame.Vector2(
            shoulder.x + math.cos(upper_angle) * upper_len,
            shoulder.y + math.sin(upper_angle) * upper_len,
        )
        lower_angle = math.atan2(target.y - elbow.y, target.x - elbow.x)

        return math.degrees(upper_angle), math.degrees(lower_angle), elbow

    @staticmethod
    def blit_segment(screen, image, pivot, angle_deg):
        rotated = pygame.transform.rotate(image, -angle_deg)
        pivot_offset = pygame.Vector2(0, image.get_height() / 2)
        image_center = pygame.Vector2(image.get_width() / 2, image.get_height() / 2)
        offset = pivot_offset - image_center
        rotated_offset = offset.rotate(angle_deg)
        rect = rotated.get_rect(center=(pivot.x - rotated_offset.x, pivot.y - rotated_offset.y))
        screen.blit(rotated, rect.topleft)


class Item:
    def __init__(self, kind, tile, active=False):
        self.kind = kind
        self.tile = tile
        self.active = active

    def draw(self, screen, assets, offset, outline=None):
        sprite = get_item_sprite(self, assets)
        world_x = self.tile[0] * TILE_SIZE + (TILE_SIZE - sprite.get_width()) // 2
        world_y = self.tile[1] * TILE_SIZE + (TILE_SIZE - sprite.get_height()) // 2
        if outline is not None:
            screen.blit(outline, (world_x - offset.x, world_y - offset.y))
        screen.blit(sprite, (world_x - offset.x, world_y - offset.y))


class StoneProjectile:
    def __init__(self, start_pos, end_pos, sprite, landing_tile):
        self.start = pygame.Vector2(start_pos)
        self.end = pygame.Vector2(end_pos)
        self.sprite = sprite
        self.landing_tile = landing_tile
        self.elapsed = 0.0
        distance = (self.end - self.start).length()
        self.duration = max(0.12, distance / STONE_THROW_SPEED)
        self.pos = pygame.Vector2(self.start)
        self.done = False

    def update(self, dt):
        if self.done:
            return
        self.elapsed += dt
        t = min(1.0, self.elapsed / self.duration)
        self.pos = self.start.lerp(self.end, t)
        if t >= 1.0:
            self.done = True

    def draw(self, screen, offset):
        if self.pos is None:
            return
        world_x = self.pos.x - self.sprite.get_width() / 2
        world_y = self.pos.y - self.sprite.get_height() / 2
        screen.blit(self.sprite, (world_x - offset.x, world_y - offset.y))


def get_item_sprite(item, assets):
    if item.kind == ITEM_LEVER:
        return assets["lever_on"] if item.active else assets["lever_off"]
    return assets[item.kind]


def get_item_outline_key(item):
    if item.kind == ITEM_LEVER:
        return "lever_on" if item.active else "lever_off"
    return item.kind


def build_item_outlines(item_assets, color):
    outlines = {}
    for key, sprite in item_assets.items():
        mask = pygame.mask.from_surface(sprite)
        outline = mask.outline()
        if outline:
            outline_surface = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
            pygame.draw.polygon(outline_surface, color, outline, 2)
            outlines[key] = outline_surface
        else:
            outlines[key] = None
    return outlines
