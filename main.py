import io
import json
import math
import random
from pathlib import Path

import pygame

TILE_SIZE = 48
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720

MAP_PATH = Path(__file__).with_name("map.txt")
TEXTURES_DIR = Path(__file__).with_name("textures")
SOUNDS_DIR = Path(__file__).with_name("sounds")
LEVELS_PATH = Path(__file__).with_name("levels.json")
CURRENT_LEVEL = 1
LEVEL_COUNT = 7
TILE_FLOOR = 1
TILE_WALL = 2
TILE_WALL_TOP = 3
TILE_FURNACE = 4
TILE_SPAWN = 6

ITEM_COAL = "coal"
ITEM_CANDLE = "candle"
ITEM_APPLE = "apple"
ITEM_LEVER = "lever"
ITEM_STONE = "stone"

ITEM_DRAW_SCALE = 0.6
ITEM_OUTLINE_COLOR = (80, 140, 200)

MENU_BG = (12, 12, 16)
MENU_TEXT = (230, 230, 230)
MENU_ACCENT = (120, 180, 255)
MENU_DIM = (120, 120, 140)

INTRO_BG = (0, 0, 0)
INTRO_TEXT = (230, 230, 230)
INTRO_MONSTER = (200, 60, 60)
INTRO_CHAR_RATE = 42

HUD_TEXT = (230, 230, 230)
HUD_SHADOW = (20, 20, 20)

DARK_TILE_FRACTION = 0.18
DARK_SAFE_RADIUS = 4
DARK_OVERLAY_ALPHA = 220
DARK_BLOB_COUNT = 2
DARK_BLOB_MIN_SIZE = 30
CANDLE_LIGHT_RADIUS = 1
SHADOW_BLUR_PASSES = 3
SHADOW_CORNER_RADIUS = 14
SHADOW_PAD = 8

AMBIENT_VOLUME = 0.35
CHASE_VOLUME = 0.55
SFX_VOLUME = 0.7
FOOTSTEP_VOLUME = 0.45
MUSIC_FADE_MS = 800
FOOTSTEP_FADE_MS = 120

SPOTLIGHT_RADIUS = 40
SPOTLIGHT_FEATHER = 0
SPOTLIGHT_ALPHA = 190
PLAYER_LIGHT_ALPHA = 135
CANDLE_LIGHT_ALPHA = 115

MONSTER_SMELL_INTERVAL = 5.0
MONSTER_SMELL_RANGE_TILES = 10
MONSTER_SMELL_SPEED = 170
MONSTER_PASSIVE_SPEED = 90
MONSTER_HEARING_RANGE_TILES = 20
MONSTER_STOP_DISTANCE = 8
MONSTER_HEAD_SCALE = 1.4
MONSTER_ARM_UPPER_SCALE_X = 1.7
MONSTER_ARM_UPPER_SCALE_Y = 0.35
MONSTER_ARM_LOWER_SCALE_X = 1.8
MONSTER_ARM_LOWER_SCALE_Y = 0.5
MONSTER_SPAWN_SAFE_RADIUS = 20
MONSTER_SPAWN_MIN_DISTANCE = 10
MONSTER_PATROL_COUNT = 14
MONSTER_PATROL_SAMPLE_SIZE = 200
MONSTER_GRAB_RADIUS_TILES = 4
MONSTER_KILL_RADIUS = 36
MONSTER_STEP_SPEED = 1.6
MONSTER_GRAB_SWAY = 0.06
MONSTER_ANCHOR_LERP = 0.08
MONSTER_TINT = (70, 70, 70)
CAMERA_ZOOM = 1.1

STONE_THROW_SPEED = 520

FREEZE_ENABLED = True
COLD_MAX = 100.0
COLD_RATE = 14.0
COLD_RECOVERY_RATE = COLD_RATE / 2

HUNGER_ENABLED = True
HUNGER_MAX = 100.0
HUNGER_RATE = 1.5
HUNGER_RESTORE = HUNGER_MAX / 2

SOLID_TILES = {0, TILE_WALL, TILE_WALL_TOP, TILE_FURNACE}
PLAYER_SPEED = 220
PLAYER_ANIM_INTERVAL = 0.18


def load_map(path):
    rows = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = [int(value) for value in line.split()]
            rows.append(row)
    if not rows:
        raise ValueError("Map file is empty")
    width = max(len(row) for row in rows)
    for row in rows:
        if len(row) < width:
            row.extend([0] * (width - len(row)))
    return rows


def load_levels(path):
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def get_level_config(levels, level_number):
    for level in levels:
        if level.get("level") == level_number:
            return level
    return {}


def find_spawn_tile(grid):
    for ty, row in enumerate(grid):
        for tx, tile in enumerate(row):
            if tile == TILE_SPAWN:
                grid[ty][tx] = TILE_FLOOR
                return (tx, ty)
    return (1, 1)


def collect_floor_tiles(grid):
    tiles = []
    for ty, row in enumerate(grid):
        for tx, tile in enumerate(row):
            if tile == TILE_FLOOR:
                tiles.append((tx, ty))
    return tiles


def grow_dark_blob(seed, target_size, available):
    blob = {seed}
    frontier = [seed]
    available.remove(seed)
    while frontier and len(blob) < target_size:
        current = random.choice(frontier)
        neighbors = [tile for tile in adjacent_tiles(current) if tile in available]
        if not neighbors:
            frontier.remove(current)
            continue
        next_tile = random.choice(neighbors)
        blob.add(next_tile)
        available.remove(next_tile)
        frontier.append(next_tile)
    return blob


def build_dark_tiles(grid, spawn_tile, darkness_amount):
    if darkness_amount <= 0:
        return set()
    floor_tiles = collect_floor_tiles(grid)
    safe_tiles = [
        tile
        for tile in floor_tiles
        if abs(tile[0] - spawn_tile[0]) + abs(tile[1] - spawn_tile[1]) > DARK_SAFE_RADIUS
    ]
    if not safe_tiles:
        return set()
    fraction = DARK_TILE_FRACTION * max(0, darkness_amount)
    total = int(len(safe_tiles) * fraction)
    if total <= 0:
        return set()
    total = min(total, len(safe_tiles))
    blob_count = min(DARK_BLOB_COUNT, max(1, total // DARK_BLOB_MIN_SIZE))
    remaining = total
    available = set(safe_tiles)
    dark_tiles = set()
    for index in range(blob_count):
        if not available:
            break
        blobs_left = blob_count - index
        target = max(DARK_BLOB_MIN_SIZE, remaining // blobs_left)
        target = min(target, len(available))
        seed = random.choice(tuple(available))
        blob = grow_dark_blob(seed, target, available)
        dark_tiles.update(blob)
        remaining -= len(blob)
    return dark_tiles


def load_svg_surface(path, size):
    try:
        import cairosvg

        png_bytes = cairosvg.svg2png(
            url=str(path),
            output_width=size[0],
            output_height=size[1],
        )
        return pygame.image.load(io.BytesIO(png_bytes)).convert_alpha()
    except Exception:
        try:
            image = pygame.image.load(str(path)).convert_alpha()
            return pygame.transform.smoothscale(image, size)
        except Exception:
            surface = pygame.Surface(size, pygame.SRCALPHA)
            surface.fill((200, 50, 200, 180))
            pygame.draw.rect(surface, (0, 0, 0), surface.get_rect(), 2)
            return surface


def load_sound(path, volume=1.0):
    sound = pygame.mixer.Sound(str(path))
    sound.set_volume(volume)
    return sound


def tint_surface(surface, tint):
    tinted = surface.copy()
    tinted.fill(tint, special_flags=pygame.BLEND_RGB_MULT)
    return tinted


def soften_alpha_mask(surface, passes):
    for _ in range(passes):
        surface = pygame.transform.smoothscale(
            surface,
            (
                max(1, surface.get_width() // 2),
                max(1, surface.get_height() // 2),
            ),
        )
        surface = pygame.transform.smoothscale(surface, (SCREEN_WIDTH, SCREEN_HEIGHT))
    return surface


def is_solid(tile):
    return tile in SOLID_TILES


def iter_solid_tiles(grid, rect):
    rows = len(grid)
    cols = len(grid[0])
    left = max(0, rect.left // TILE_SIZE)
    right = min(cols - 1, (rect.right - 1) // TILE_SIZE)
    top = max(0, rect.top // TILE_SIZE)
    bottom = min(rows - 1, (rect.bottom - 1) // TILE_SIZE)
    for ty in range(top, bottom + 1):
        for tx in range(left, right + 1):
            tile = grid[ty][tx]
            if is_solid(tile):
                yield pygame.Rect(tx * TILE_SIZE, ty * TILE_SIZE, TILE_SIZE, TILE_SIZE)


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

    def update(self, dt, grid, map_size_px):
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

        self.move_and_collide(move.x * PLAYER_SPEED * dt, move.y * PLAYER_SPEED * dt, grid)
        self.clamp_to_map(map_size_px)
        self.update_animation(dt)

    def move_and_collide(self, dx, dy, grid):
        if dx != 0:
            self.pos.x += dx
            self.rect.x = round(self.pos.x)
            self.resolve_collisions(grid, axis="x")
        if dy != 0:
            self.pos.y += dy
            self.rect.y = round(self.pos.y)
            self.resolve_collisions(grid, axis="y")

    def resolve_collisions(self, grid, axis):
        for tile_rect in iter_solid_tiles(grid, self.rect):
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
        self.chase_speed = MONSTER_SMELL_SPEED * self.rng.uniform(0.95, 1.05)
        self.passive_speed = MONSTER_PASSIVE_SPEED * self.rng.uniform(0.9, 1.1)
        self.step_speed = MONSTER_STEP_SPEED * self.rng.uniform(0.9, 1.1)
        self.grab_sway = MONSTER_GRAB_SWAY * self.rng.uniform(0.85, 1.15)
        self.smell_interval = MONSTER_SMELL_INTERVAL * self.rng.uniform(0.85, 1.15)
        self.vision_memory = 2.0 * self.rng.uniform(0.8, 1.2)
        self.target_offset = pygame.Vector2(
            self.rng.uniform(-12, 12),
            self.rng.uniform(-12, 12),
        )
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
        active_speed = None
        if self.last_seen is not None and self.vision_timer > 0.0:
            active_target = self.last_seen
            active_speed = self.chase_speed
        elif self.hearing_target is not None:
            active_target = self.hearing_target
            active_speed = self.chase_speed
        elif self.smell_target is not None:
            active_target = self.smell_target
            active_speed = self.chase_speed

        self.is_chasing = active_target is not None
        self.moving = False
        if active_target is not None:
            to_target = active_target - self.pos
            if to_target.length_squared() <= MONSTER_STOP_DISTANCE * MONSTER_STOP_DISTANCE:
                if active_target == self.hearing_target:
                    self.hearing_target = None
                if active_target == self.smell_target:
                    self.smell_target = None
            else:
                direction = to_target.normalize()
                self.pos += direction * active_speed * dt
                self.moving = True
        else:
            if self.passive_target is None:
                self.passive_target = self.next_patrol_target()
            if self.passive_target is not None:
                to_target = self.passive_target - self.pos
                if to_target.length_squared() <= MONSTER_STOP_DISTANCE * MONSTER_STOP_DISTANCE:
                    self.passive_target = None
                else:
                    direction = to_target.normalize()
                    self.pos += direction * self.passive_speed * dt
                    self.moving = True

        speed_factor = self.step_speed if self.moving else 1.0
        self.step_time += dt * speed_factor
        self.update_anchors(grid)

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
        wall_tiles = get_wall_tiles_near(grid, center_tile, MONSTER_GRAB_RADIUS_TILES)
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
        upper_angle, lower_angle, elbow = self.solve_arm_ik(
            shoulder, target, upper_len, lower_len, bend_sign
        )
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
        rect = rotated.get_rect(
            center=(pivot.x - rotated_offset.x, pivot.y - rotated_offset.y)
        )
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


def spawn_items(grid, spawn_tile, items_counts, objectives):
    floor_tiles = collect_floor_tiles(grid)
    available = [tile for tile in floor_tiles if tile != spawn_tile]
    random.shuffle(available)
    items = []

    candle_count = items_counts.get("candles", 1)
    stone_count = items_counts.get("stones", 0)
    food_count = items_counts.get("food", 0)
    coal_count = objectives.get("coal", 0)
    lever_count = objectives.get("levers", 0)
    spawn_plan = [
        (ITEM_COAL, coal_count),
        (ITEM_CANDLE, candle_count),
        (ITEM_APPLE, food_count),
        (ITEM_LEVER, lever_count),
        (ITEM_STONE, stone_count),
    ]

    for kind, count in spawn_plan:
        for _ in range(count):
            if not available:
                break
            items.append(Item(kind, available.pop()))
    return items


def tile_to_world_center(tile):
    return (
        tile[0] * TILE_SIZE + TILE_SIZE / 2,
        tile[1] * TILE_SIZE + TILE_SIZE / 2,
    )


def build_patrol_points(grid, count, sample_size):
    floor_tiles = collect_floor_tiles(grid)
    if not floor_tiles:
        return []

    rng = random.Random()
    points = [rng.choice(floor_tiles)]
    while len(points) < min(count, len(floor_tiles)):
        candidates = rng.sample(floor_tiles, min(sample_size, len(floor_tiles)))
        best_tile = None
        best_dist = -1
        for cand in candidates:
            dist = min(
                (cand[0] - p[0]) ** 2 + (cand[1] - p[1]) ** 2
                for p in points
            )
            if dist > best_dist:
                best_dist = dist
                best_tile = cand
        points.append(best_tile)

    return [tile_to_world_center(tile) for tile in points]


def pick_monster_spawn(grid, player_tile):
    floor_tiles = collect_floor_tiles(grid)
    far_tiles = [
        tile
        for tile in floor_tiles
        if abs(tile[0] - player_tile[0]) + abs(tile[1] - player_tile[1]) > MONSTER_SPAWN_SAFE_RADIUS
    ]
    if not far_tiles:
        far_tiles = floor_tiles
    return random.choice(far_tiles)


def pick_monster_spawns(grid, player_tile, count):
    if count <= 0:
        return []
    floor_tiles = collect_floor_tiles(grid)
    candidates = [
        tile
        for tile in floor_tiles
        if abs(tile[0] - player_tile[0]) + abs(tile[1] - player_tile[1]) > MONSTER_SPAWN_SAFE_RADIUS
    ]
    if not candidates:
        candidates = floor_tiles[:]

    rng = random.Random()
    rng.shuffle(candidates)
    spawns = []

    def far_enough(tile):
        return all(
            abs(tile[0] - other[0]) + abs(tile[1] - other[1]) >= MONSTER_SPAWN_MIN_DISTANCE
            for other in spawns
        )

    for tile in candidates:
        if len(spawns) >= count:
            break
        if far_enough(tile):
            spawns.append(tile)

    if len(spawns) < count:
        for tile in candidates:
            if len(spawns) >= count:
                break
            if tile not in spawns:
                spawns.append(tile)

    return spawns[:count]


def get_wall_tiles_near(grid, center_tile, radius):
    rows = len(grid)
    cols = len(grid[0])
    tiles = []
    for ty in range(max(0, center_tile[1] - radius), min(rows - 1, center_tile[1] + radius) + 1):
        for tx in range(max(0, center_tile[0] - radius), min(cols - 1, center_tile[0] + radius) + 1):
            if grid[ty][tx] in (TILE_WALL, TILE_WALL_TOP):
                tiles.append((tx, ty))
    return tiles


def tile_blocks_vision(grid, tile):
    if not tile_in_bounds(grid, tile):
        return True
    return grid[tile[1]][tile[0]] in (TILE_WALL, TILE_WALL_TOP, TILE_FURNACE)


def bresenham_line(start_tile, end_tile):
    x0, y0 = start_tile
    x1, y1 = end_tile
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        yield (x0, y0)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def has_line_of_sight(grid, start_pos, end_pos):
    start_tile = (int(start_pos[0] // TILE_SIZE), int(start_pos[1] // TILE_SIZE))
    end_tile = (int(end_pos[0] // TILE_SIZE), int(end_pos[1] // TILE_SIZE))
    for tile in bresenham_line(start_tile, end_tile):
        if tile == start_tile or tile == end_tile:
            continue
        if tile_blocks_vision(grid, tile):
            return False
    return True


def pick_arm_targets(wall_tiles, monster_pos):
    if not wall_tiles:
        return None, None

    world_positions = [tile_to_world_center(tile) for tile in wall_tiles]

    def distance_sq(pos):
        return (pos[0] - monster_pos.x) ** 2 + (pos[1] - monster_pos.y) ** 2

    left_candidates = [pos for pos in world_positions if pos[0] <= monster_pos.x]
    right_candidates = [pos for pos in world_positions if pos[0] >= monster_pos.x]

    left = min(left_candidates, key=distance_sq) if left_candidates else None
    right = min(right_candidates, key=distance_sq) if right_candidates else None

    if left is None:
        left = min(world_positions, key=distance_sq)
    if right is None:
        right = min((pos for pos in world_positions if pos != left), key=distance_sq, default=left)
    if left == right:
        alternate = min(
            (pos for pos in world_positions if pos != left),
            key=distance_sq,
            default=left,
        )
        right = alternate

    return left, right


def tile_in_bounds(grid, tile):
    tx, ty = tile
    return 0 <= ty < len(grid) and 0 <= tx < len(grid[0])


def tile_is_placeable(grid, tile):
    if not tile_in_bounds(grid, tile):
        return False
    tx, ty = tile
    return grid[ty][tx] == TILE_FLOOR


def get_player_tile(player):
    return (player.rect.centerx // TILE_SIZE, player.rect.centery // TILE_SIZE)


def player_on_tile(player, tile):
    tile_rect = pygame.Rect(tile[0] * TILE_SIZE, tile[1] * TILE_SIZE, TILE_SIZE, TILE_SIZE)
    return player.rect.colliderect(tile_rect)


def direction_to_offset(direction):
    if direction.length_squared() == 0:
        return (0, 0)
    if abs(direction.x) >= abs(direction.y):
        return (1 if direction.x > 0 else -1, 0)
    return (0, 1 if direction.y > 0 else -1)


def adjacent_tiles(tile):
    tx, ty = tile
    return [(tx + 1, ty), (tx - 1, ty), (tx, ty + 1), (tx, ty - 1)]


def get_light_tiles(center_tile, radius):
    if radius <= 0:
        return set()
    cx, cy = center_tile
    light_tiles = set()
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            if max(abs(dx), abs(dy)) > radius:
                continue
            tile = (cx + dx, cy + dy)
            light_tiles.add(tile)
    return light_tiles


def get_candle_light_tiles(items, player):
    light_tiles = set()
    if player.carrying == ITEM_CANDLE:
        light_tiles.update(get_light_tiles(get_player_tile(player), CANDLE_LIGHT_RADIUS))
    for item in items:
        if item.kind == ITEM_CANDLE:
            light_tiles.update(get_light_tiles(item.tile, CANDLE_LIGHT_RADIUS))
    return light_tiles


def get_candle_visibility_tiles(items, player):
    visibility_tiles = set()
    visibility_radius = CANDLE_LIGHT_RADIUS + 1
    if player.carrying == ITEM_CANDLE:
        visibility_tiles.update(get_light_tiles(get_player_tile(player), visibility_radius))
    for item in items:
        if item.kind == ITEM_CANDLE:
            visibility_tiles.update(get_light_tiles(item.tile, visibility_radius))
    return visibility_tiles


def get_candle_centers(player, items):
    centers = []
    if player.carrying == ITEM_CANDLE:
        centers.append((player.rect.centerx, player.rect.centery))
    for item in items:
        if item.kind != ITEM_CANDLE:
            continue
        centers.append(
            (
                item.tile[0] * TILE_SIZE + TILE_SIZE // 2,
                item.tile[1] * TILE_SIZE + TILE_SIZE // 2,
            )
        )
    return centers


def item_is_visible(item_tile, dark_tiles, visibility_tiles):
    return item_tile not in dark_tiles or item_tile in visibility_tiles


def get_item_at(items, tile):
    for item in items:
        if item.tile == tile:
            return item
    return None


def emit_sound(sound_events, tile):
    sound_events.append(pygame.Vector2(tile_to_world_center(tile)))


def tile_is_furnace(grid, tile):
    if not tile_in_bounds(grid, tile):
        return False
    tx, ty = tile
    return grid[ty][tx] == TILE_FURNACE


def get_furnace_rect(grid, tile):
    tx, ty = tile
    if not tile_in_bounds(grid, tile) or grid[ty][tx] != TILE_FURNACE:
        return None
    left_tx = tx
    if tile_in_bounds(grid, (tx - 1, ty)) and grid[ty][tx - 1] == TILE_FURNACE:
        left_tx = tx - 1
    width = TILE_SIZE * (2 if tile_in_bounds(grid, (left_tx + 1, ty)) and grid[ty][left_tx + 1] == TILE_FURNACE else 1)
    return pygame.Rect(left_tx * TILE_SIZE, ty * TILE_SIZE, width, TILE_SIZE)


def throw_stone(grid, items, start_tile, direction):
    last_valid = start_tile
    for step in range(1, 4):
        tile = (start_tile[0] + direction[0] * step, start_tile[1] + direction[1] * step)
        if not tile_in_bounds(grid, tile):
            break
        if grid[tile[1]][tile[0]] in (TILE_WALL, TILE_WALL_TOP, TILE_FURNACE):
            break
        if get_item_at(items, tile) is not None:
            break
        last_valid = tile

    if last_valid == start_tile and get_item_at(items, last_valid) is not None:
        return None
    return last_valid


def handle_interaction(
    player,
    items,
    grid,
    sound_events,
    stone_projectiles,
    stone_sprite,
    dark_tiles=None,
    sfx=None,
):
    player_tile = get_player_tile(player)
    offset = direction_to_offset(player.last_dir)
    target_tile = (player_tile[0] + offset[0], player_tile[1] + offset[1]) if offset != (0, 0) else None
    if player.carrying:
        if offset == (0, 0):
            return False, False
        if player.carrying == ITEM_COAL and target_tile and tile_is_furnace(grid, target_tile):
            player.carrying = None
            emit_sound(sound_events, target_tile)
            if sfx is not None:
                sfx["furnace"].play()
            return False, True
        if player.carrying == ITEM_STONE:
            landing_tile = throw_stone(grid, items, player_tile, offset)
            if landing_tile is not None:
                if landing_tile == player_tile:
                    items.append(Item(ITEM_STONE, landing_tile))
                    emit_sound(sound_events, landing_tile)
                else:
                    stone_projectiles.append(
                        StoneProjectile(
                            player.rect.center,
                            tile_to_world_center(landing_tile),
                            stone_sprite,
                            landing_tile,
                        )
                    )
            player.carrying = None
            return False, False
        if target_tile and tile_is_placeable(grid, target_tile) and get_item_at(items, target_tile) is None:
            items.append(Item(player.carrying, target_tile))
            player.carrying = None
        return False, False

    candidate_tiles = [player_tile] + adjacent_tiles(player_tile)
    for tile in candidate_tiles:
        item = get_item_at(items, tile)
        if item is None:
            continue
        if item.kind == ITEM_LEVER:
            if item.active:
                continue
            item.active = True
            emit_sound(sound_events, tile)
            if sfx is not None:
                sfx["lever"].play()
        elif item.kind == ITEM_APPLE:
            items.remove(item)
            if sfx is not None:
                sfx["pickup"].play()
            return True, False
        else:
            player.carrying = item.kind
            items.remove(item)
            if sfx is not None:
                sfx["pickup"].play()
        return False, False
    return False, False


def compute_camera(player_rect, map_size_px):
    map_w, map_h = map_size_px
    cam_x = player_rect.centerx - SCREEN_WIDTH // 2
    cam_y = player_rect.centery - SCREEN_HEIGHT // 2
    cam_x = max(0, min(cam_x, map_w - SCREEN_WIDTH))
    cam_y = max(0, min(cam_y, map_h - SCREEN_HEIGHT))
    return pygame.Vector2(cam_x, cam_y)


def draw_map(screen, grid, assets, offset):
    rows = len(grid)
    cols = len(grid[0])
    skipped_furnace = set()
    for ty in range(rows):
        for tx in range(cols):
            tile = grid[ty][tx]
            if tile == 0:
                continue
            world_x = tx * TILE_SIZE
            world_y = ty * TILE_SIZE
            if tile == TILE_FURNACE:
                if (tx, ty) in skipped_furnace:
                    continue
                if tx + 1 < cols and grid[ty][tx + 1] == TILE_FURNACE:
                    screen.blit(assets["floor"], (world_x - offset.x, world_y - offset.y))
                    screen.blit(
                        assets["floor"],
                        (world_x + TILE_SIZE - offset.x, world_y - offset.y),
                    )
                    screen.blit(
                        assets["furnace"],
                        (world_x - offset.x, world_y - offset.y),
                    )
                    skipped_furnace.add((tx + 1, ty))
                    continue

            screen.blit(assets["floor"], (world_x - offset.x, world_y - offset.y))

            if tile == TILE_WALL:
                screen.blit(assets["wall"], (world_x - offset.x, world_y - offset.y))
            elif tile == TILE_WALL_TOP:
                screen.blit(assets["wall_top"], (world_x - offset.x, world_y - offset.y))
            elif tile == TILE_FURNACE:
                screen.blit(assets["furnace_single"], (world_x - offset.x, world_y - offset.y))


def draw_items(screen, items, assets, offset, dark_tiles=None, visibility_tiles=None):
    for item in items:
        if dark_tiles is not None and visibility_tiles is not None and not item_is_visible(item.tile, dark_tiles, visibility_tiles):
            continue
        item.draw(screen, assets, offset)


def draw_item_outlines(screen, items, assets, outlines, offset, player, dark_tiles=None, visibility_tiles=None):
    player_tile = get_player_tile(player)
    can_pick = player.carrying is None
    pickable_tiles = [player_tile] + adjacent_tiles(player_tile)
    candidate = None
    candidate_dist = None
    player_center = player.rect.center
    for item in items:
        if dark_tiles is not None and visibility_tiles is not None and not item_is_visible(item.tile, dark_tiles, visibility_tiles):
            continue
        if item.tile not in pickable_tiles:
            continue
        if item.kind == ITEM_LEVER and item.active:
            continue
        if item.kind != ITEM_LEVER and not can_pick:
            continue
        tile_center = (
            item.tile[0] * TILE_SIZE + TILE_SIZE // 2,
            item.tile[1] * TILE_SIZE + TILE_SIZE // 2,
        )
        dist = (tile_center[0] - player_center[0]) ** 2 + (tile_center[1] - player_center[1]) ** 2
        if candidate is None or dist < candidate_dist:
            candidate = item
            candidate_dist = dist

    if candidate is None:
        return
    outline_key = get_item_outline_key(candidate)
    outline = outlines.get(outline_key)
    if outline is None:
        return
    sprite = get_item_sprite(candidate, assets)
    world_x = candidate.tile[0] * TILE_SIZE + (TILE_SIZE - sprite.get_width()) // 2
    world_y = candidate.tile[1] * TILE_SIZE + (TILE_SIZE - sprite.get_height()) // 2
    screen.blit(outline, (world_x - offset.x, world_y - offset.y))


def draw_furnace_outline(screen, grid, player, offset):
    if player.carrying != ITEM_COAL:
        return
    offset_dir = direction_to_offset(player.last_dir)
    if offset_dir == (0, 0):
        return
    player_tile = get_player_tile(player)
    target = (player_tile[0] + offset_dir[0], player_tile[1] + offset_dir[1])
    rect = get_furnace_rect(grid, target)
    if rect is None:
        return
    outline_rect = pygame.Rect(
        rect.x - offset.x,
        rect.y - offset.y,
        rect.width,
        rect.height,
    )
    pygame.draw.rect(screen, ITEM_OUTLINE_COLOR, outline_rect, 2)


def draw_carried_item(screen, player, assets, offset):
    if not player.carrying:
        return
    sprite = assets[player.carrying]
    world_x = player.rect.centerx - sprite.get_width() // 2
    world_y = player.rect.centery - sprite.get_height() // 2
    screen.blit(sprite, (world_x - offset.x, world_y - offset.y))


def draw_projectiles(screen, projectiles, offset):
    for projectile in projectiles:
        projectile.draw(screen, offset)


def draw_darkness(screen, dark_tiles, overlay, candle_centers, offset):
    darkness = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    for tx, ty in dark_tiles:
        world_x = tx * TILE_SIZE - offset.x
        world_y = ty * TILE_SIZE - offset.y
        rect = pygame.Rect(
            world_x - SHADOW_PAD,
            world_y - SHADOW_PAD,
            TILE_SIZE + SHADOW_PAD * 2,
            TILE_SIZE + SHADOW_PAD * 2,
        )
        pygame.draw.rect(
            darkness,
            (0, 0, 0, DARK_OVERLAY_ALPHA),
            rect,
            border_radius=SHADOW_CORNER_RADIUS + SHADOW_PAD,
        )

    candle_radius = int((CANDLE_LIGHT_RADIUS + 0.5) * TILE_SIZE)
    for candle_center in candle_centers:
        screen_pos = (
            int(candle_center[0] - offset.x),
            int(candle_center[1] - offset.y),
        )
        pygame.draw.circle(darkness, (0, 0, 0, 0), screen_pos, candle_radius)

    darkness = soften_alpha_mask(darkness, SHADOW_BLUR_PASSES)
    screen.blit(darkness, (0, 0))


def draw_cold_bar(screen, cold_value):
    bar_width = 220
    bar_height = 16
    x = 16
    y = 16
    pygame.draw.rect(screen, (30, 30, 30), (x, y, bar_width, bar_height))
    fill_width = int(bar_width * (cold_value / COLD_MAX))
    pygame.draw.rect(screen, (80, 180, 255), (x, y, fill_width, bar_height))
    pygame.draw.rect(screen, (230, 230, 230), (x, y, bar_width, bar_height), 1)


def draw_hunger_bar(screen, hunger_value):
    bar_width = 220
    bar_height = 16
    x = 16
    y = 38
    pygame.draw.rect(screen, (30, 30, 30), (x, y, bar_width, bar_height))
    fill_width = int(bar_width * (hunger_value / HUNGER_MAX))
    pygame.draw.rect(screen, (255, 160, 80), (x, y, fill_width, bar_height))
    pygame.draw.rect(screen, (230, 230, 230), (x, y, bar_width, bar_height), 1)


def draw_objectives(screen, font, coal_loaded, coal_required, levers_active, levers_required):
    lines = []
    if coal_required > 0:
        lines.append(f"Уголь: {coal_loaded}/{coal_required}")
    if levers_required > 0:
        lines.append(f"Рычаги: {levers_active}/{levers_required}")
    if not lines:
        return

    line_height = font.get_linesize() + 4
    width = screen.get_width()
    x_padding = 16
    y = 12
    for line in lines:
        text = font.render(line, True, HUD_TEXT)
        shadow = font.render(line, True, HUD_SHADOW)
        x = width - text.get_width() - x_padding
        screen.blit(shadow, (x + 2, y + 2))
        screen.blit(text, (x, y))
        y += line_height


def blit_zoomed_world(screen, world_surface, zoom):
    if zoom <= 1.0:
        screen.blit(world_surface, (0, 0))
        return
    width, height = world_surface.get_size()
    zoomed_size = (int(width * zoom), int(height * zoom))
    zoomed_surface = pygame.transform.smoothscale(world_surface, zoomed_size)
    offset_x = (width - zoomed_size[0]) // 2
    offset_y = (height - zoomed_size[1]) // 2
    screen.blit(zoomed_surface, (offset_x, offset_y))


def draw_spotlight(screen, player, candle_centers, camera):
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, SPOTLIGHT_ALPHA))

    center = (
        int(player.rect.centerx - camera.x),
        int(player.rect.centery - camera.y),
    )
    for step in range(4):
        radius = SPOTLIGHT_RADIUS + step * (SPOTLIGHT_FEATHER // 3)
        alpha = max(0, SPOTLIGHT_ALPHA - (step + 1) * (SPOTLIGHT_ALPHA // 5))
        pygame.draw.circle(overlay, (0, 0, 0, alpha), center, radius)
    pygame.draw.circle(overlay, (0, 0, 0, PLAYER_LIGHT_ALPHA), center, SPOTLIGHT_RADIUS)

    candle_radius = int((CANDLE_LIGHT_RADIUS + 0.5) * TILE_SIZE)
    for candle_center in candle_centers:
        screen_pos = (
            int(candle_center[0] - camera.x),
            int(candle_center[1] - camera.y),
        )
        pygame.draw.circle(overlay, (0, 0, 0, CANDLE_LIGHT_ALPHA), screen_pos, candle_radius)

    screen.blit(overlay, (0, 0))


def build_intro_lines(abilities_config, debuffs_config):
    lines = []

    if abilities_config.get("hearing", False):
        lines.append([("Монстр", INTRO_MONSTER), (" умеет слышать", INTRO_TEXT)])
    if abilities_config.get("vision", False):
        lines.append([("Монстр", INTRO_MONSTER), (" умеет видеть", INTRO_TEXT)])
    if abilities_config.get("smell", False):
        lines.append([("Монстр", INTRO_MONSTER), (" умеет нюхать", INTRO_TEXT)])

    cloning_count = max(0, int(abilities_config.get("cloning", 0)))
    if cloning_count > 0:
        lines.append(
            [
                ("Монстр", INTRO_MONSTER),
                (f" умеет клонироваться (x{cloning_count})", INTRO_TEXT),
            ]
        )

    debuff_lines = []
    if debuffs_config.get("freezing", False):
        debuff_lines.append([("В лаборатории становится холодно", INTRO_TEXT)])
    if debuffs_config.get("hunger", False):
        debuff_lines.append([("У вас урчит живот", INTRO_TEXT)])
    if debuffs_config.get("darkness_amount", 0) > 0:
        debuff_lines.append([("Темнота сгущается", INTRO_TEXT)])

    if lines and debuff_lines:
        lines.append([])
    lines.extend(debuff_lines)

    return lines


def draw_typed_line(screen, font, x, y, segments, max_chars):
    if max_chars <= 0:
        return
    remaining = max_chars
    cursor_x = x
    for text, color in segments:
        if remaining <= 0:
            break
        chunk = text[:remaining]
        if chunk:
            surface = font.render(chunk, True, color)
            screen.blit(surface, (cursor_x, y))
            cursor_x += surface.get_width()
        remaining -= len(text)


def toggle_fullscreen():
    current = pygame.display.get_surface()
    if current is None:
        return pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    is_fullscreen = bool(current.get_flags() & pygame.FULLSCREEN)
    if is_fullscreen:
        return pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    return pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)


def run_level_intro(screen, clock, abilities_config, debuffs_config, level_number):
    lines = build_intro_lines(abilities_config, debuffs_config)
    if not lines:
        return "ok"

    font = pygame.font.SysFont(None, 36)
    header_font = pygame.font.SysFont(None, 44)
    prompt_font = pygame.font.SysFont(None, 28)
    level_text = f"Уровень {level_number}"
    prompt_text = "Нажмите Enter, чтобы продолжить"
    line_height = font.get_linesize() + 6
    line_widths = []
    line_lengths = []
    total_chars = 0

    for segments in lines:
        if not segments:
            line_widths.append(0)
            line_lengths.append(0)
            continue
        width = sum(font.size(text)[0] for text, _ in segments)
        length = sum(len(text) for text, _ in segments)
        line_widths.append(width)
        line_lengths.append(length)
        total_chars += length

    if total_chars <= 0:
        return "ok"

    visible_chars = 0.0
    typing_done = False
    header_surface = header_font.render(level_text, True, INTRO_TEXT)
    prompt_surface = prompt_font.render(prompt_text, True, INTRO_TEXT)

    while True:
        dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    screen = toggle_fullscreen()
                    continue
                if event.key == pygame.K_ESCAPE:
                    return "menu"
                if typing_done:
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        return "ok"
                else:
                    visible_chars = float(total_chars)
                    typing_done = True
            if event.type == pygame.MOUSEBUTTONDOWN and not typing_done:
                visible_chars = float(total_chars)
                typing_done = True

        if not typing_done:
            visible_chars = min(float(total_chars), visible_chars + INTRO_CHAR_RATE * dt)
            if visible_chars >= total_chars:
                typing_done = True

        screen = pygame.display.get_surface() or screen
        screen.fill(INTRO_BG)
        width, height = screen.get_size()
        block_height = len(lines) * line_height
        header_rect = header_surface.get_rect(midtop=(width // 2, 24))
        prompt_rect = prompt_surface.get_rect(midbottom=(width // 2, height - 24))
        top_limit = header_rect.bottom + 20
        bottom_limit = prompt_rect.top - 20
        available_height = max(0, bottom_limit - top_limit)
        start_y = top_limit + max(0, (available_height - block_height) // 2)
        screen.blit(header_surface, header_rect)

        remaining = int(visible_chars)
        for index, segments in enumerate(lines):
            y = start_y + index * line_height
            if not segments:
                continue
            if remaining <= 0:
                break
            show_chars = min(line_lengths[index], remaining)
            x = (width - line_widths[index]) // 2
            draw_typed_line(screen, font, x, y, segments, show_chars)
            remaining -= line_lengths[index]

        if typing_done:
            screen.blit(prompt_surface, prompt_rect)

        pygame.display.flip()


def run_message_screen(screen, clock, message, background=None):
    font = pygame.font.SysFont(None, 48)
    total_chars = len(message)
    if total_chars <= 0:
        return "done"

    visible_chars = 0.0
    typing_done = False
    hold_timer = 0.0
    fade_alpha = 0.0
    fade_duration = 0.5
    hold_duration = 1.1

    while True:
        dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                    screen = toggle_fullscreen()
                    continue
                if typing_done:
                    return "done"
                visible_chars = float(total_chars)
                typing_done = True

        if not typing_done:
            visible_chars = min(float(total_chars), visible_chars + INTRO_CHAR_RATE * dt)
            if visible_chars >= total_chars:
                typing_done = True
        else:
            hold_timer += dt
            if hold_timer >= hold_duration:
                return "done"

        fade_alpha = min(255.0, fade_alpha + 255.0 * dt / max(0.001, fade_duration))

        screen = pygame.display.get_surface() or screen
        if background is not None:
            screen.blit(background, (0, 0))
            overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, int(fade_alpha)))
            screen.blit(overlay, (0, 0))
        else:
            screen.fill((0, 0, 0))

        width, height = screen.get_size()
        text = message[:int(visible_chars)]
        surface = font.render(text, True, INTRO_TEXT)
        rect = surface.get_rect(center=(width // 2, height // 2))
        screen.blit(surface, rect)

        pygame.display.flip()


def run_menu(screen, clock, initial_level):
    title_font = pygame.font.SysFont(None, 72)
    label_font = pygame.font.SysFont(None, 36)
    button_font = pygame.font.SysFont(None, 32)

    selected_level = initial_level
    selected_button = 0

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    screen = toggle_fullscreen()
                    continue
                if event.key == pygame.K_ESCAPE:
                    return None
                if event.key == pygame.K_LEFT or event.key == pygame.K_a:
                    selected_level -= 1
                    if selected_level < 1:
                        selected_level = LEVEL_COUNT
                if event.key == pygame.K_RIGHT or event.key == pygame.K_d:
                    selected_level += 1
                    if selected_level > LEVEL_COUNT:
                        selected_level = 1
                if (
                    event.key == pygame.K_UP
                    or event.key == pygame.K_DOWN
                    or event.key == pygame.K_w
                    or event.key == pygame.K_s
                ):
                    selected_button = 1 - selected_button
                if event.key == pygame.K_RETURN:
                    return selected_level if selected_button == 0 else None

        screen = pygame.display.get_surface() or screen
        screen.fill(MENU_BG)
        width, height = screen.get_size()

        title = title_font.render("Abyss Walker", True, MENU_TEXT)
        title_rect = title.get_rect(center=(width // 2, height // 4))
        screen.blit(title, title_rect)

        level_label = label_font.render("Level", True, MENU_DIM)
        level_label_rect = level_label.get_rect(center=(width // 2, height // 2 - 80))
        screen.blit(level_label, level_label_rect)

        level_text = title_font.render(str(selected_level), True, MENU_TEXT)
        level_rect = level_text.get_rect(center=(width // 2, height // 2 - 10))
        screen.blit(level_text, level_rect)

        left_arrow = label_font.render("<", True, MENU_ACCENT)
        right_arrow = label_font.render(">", True, MENU_ACCENT)
        screen.blit(left_arrow, left_arrow.get_rect(center=(width // 2 - 90, height // 2 - 10)))
        screen.blit(right_arrow, right_arrow.get_rect(center=(width // 2 + 90, height // 2 - 10)))

        buttons = [("Начать", 0), ("Выход", 1)]
        for label, index in buttons:
            text_color = MENU_TEXT if selected_button == index else MENU_DIM
            rect_color = MENU_ACCENT if selected_button == index else MENU_DIM
            text_surface = button_font.render(label, True, text_color)
            button_rect = pygame.Rect(0, 0, 200, 46)
            button_rect.center = (width // 2, height // 2 + 90 + index * 64)
            pygame.draw.rect(screen, rect_color, button_rect, 2)
            text_rect = text_surface.get_rect(center=button_rect.center)
            screen.blit(text_surface, text_rect)

        pygame.display.flip()
        clock.tick(60)


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)
    clock = pygame.time.Clock()
    pygame.mouse.set_visible(False)

    while True:
        selected_level = run_menu(screen, clock, CURRENT_LEVEL)
        if selected_level is None:
            break
        while True:
            result = run_game(screen, clock, selected_level)
            if result == "restart":
                continue
            if result == "menu":
                break
            if result == "quit":
                pygame.quit()
                return
    pygame.quit()


def run_game(screen, clock, level_number):
    pygame.display.set_caption("Abyss Walker - prototype")
    grid = load_map(MAP_PATH)
    rows = len(grid)
    cols = len(grid[0])
    map_size_px = (cols * TILE_SIZE, rows * TILE_SIZE)

    assets = {
        "floor": load_svg_surface(TEXTURES_DIR / "floor.svg", (TILE_SIZE, TILE_SIZE)),
        "wall": load_svg_surface(TEXTURES_DIR / "wall_side.svg", (TILE_SIZE, TILE_SIZE)),
        "wall_top": load_svg_surface(TEXTURES_DIR / "wall_top.svg", (TILE_SIZE, TILE_SIZE)),
        "furnace": load_svg_surface(TEXTURES_DIR / "furnace.svg", (TILE_SIZE * 2, TILE_SIZE)),
        "furnace_single": load_svg_surface(TEXTURES_DIR / "furnace.svg", (TILE_SIZE, TILE_SIZE)),
    }

    item_size = int(TILE_SIZE * ITEM_DRAW_SCALE)
    item_assets = {
        ITEM_COAL: load_svg_surface(TEXTURES_DIR / "coal.svg", (item_size, item_size)),
        ITEM_CANDLE: load_svg_surface(TEXTURES_DIR / "candle.svg", (item_size, item_size)),
        ITEM_APPLE: load_svg_surface(TEXTURES_DIR / "apple.svg", (item_size, item_size)),
        ITEM_STONE: load_svg_surface(TEXTURES_DIR / "stone.svg", (item_size, item_size)),
        "lever_off": load_svg_surface(TEXTURES_DIR / "lever_off.svg", (item_size, item_size)),
        "lever_on": load_svg_surface(TEXTURES_DIR / "lever_on.svg", (item_size, item_size)),
    }
    item_outlines = build_item_outlines(item_assets, ITEM_OUTLINE_COLOR)

    player_size = int(TILE_SIZE * 0.75)
    player_images = [
        load_svg_surface(TEXTURES_DIR / "player_stand.svg", (player_size, player_size)),
        load_svg_surface(TEXTURES_DIR / "player_walk.svg", (player_size, player_size)),
        load_svg_surface(TEXTURES_DIR / "player_walk2.svg", (player_size, player_size)),
    ]

    arm_lower = tint_surface(
        load_svg_surface(
            TEXTURES_DIR / "monster_arm_lower.svg",
            (
                int(TILE_SIZE * MONSTER_ARM_LOWER_SCALE_X * 0.8),
                int(TILE_SIZE * MONSTER_ARM_LOWER_SCALE_Y * 1.5),
            ),
        ),
        MONSTER_TINT,
    )
    arm_lower = pygame.transform.flip(arm_lower, True, False)
    monster_assets = {
        "head": tint_surface(
            load_svg_surface(
                TEXTURES_DIR / "monster_head.svg",
                (int(TILE_SIZE * MONSTER_HEAD_SCALE), int(TILE_SIZE * MONSTER_HEAD_SCALE)),
            ),
            MONSTER_TINT,
        ),
        "arm_upper": tint_surface(
            load_svg_surface(
                TEXTURES_DIR / "monster_arm_upper.svg",
                (
                    int(TILE_SIZE * MONSTER_ARM_UPPER_SCALE_X),
                    int(TILE_SIZE * MONSTER_ARM_UPPER_SCALE_Y),
                ),
            ),
            MONSTER_TINT,
        ),
        "arm_lower": arm_lower,
    }

    pygame.mixer.set_num_channels(12)
    ambient_sound = load_sound(SOUNDS_DIR / "ambient.mp3", AMBIENT_VOLUME)
    chase_sound = load_sound(SOUNDS_DIR / "chase.mp3", CHASE_VOLUME)
    walk_sound = load_sound(SOUNDS_DIR / "player_walk.mp3", FOOTSTEP_VOLUME)
    sfx = {
        "throw": load_sound(SOUNDS_DIR / "throw_stone.mp3", SFX_VOLUME),
        "furnace": load_sound(SOUNDS_DIR / "activate_furnace.mp3", SFX_VOLUME),
        "pickup": load_sound(SOUNDS_DIR / "pick_up.mp3", SFX_VOLUME),
        "lever": load_sound(SOUNDS_DIR / "activate_lever.mp3", SFX_VOLUME),
    }
    ambient_channel = pygame.mixer.Channel(0)
    chase_channel = pygame.mixer.Channel(1)
    footstep_channel = pygame.mixer.Channel(2)
    ambient_channel.play(ambient_sound, loops=-1, fade_ms=MUSIC_FADE_MS)
    chase_active = False
    footstep_active = False

    def stop_level_audio():
        ambient_channel.fadeout(MUSIC_FADE_MS)
        chase_channel.fadeout(MUSIC_FADE_MS)
        footstep_channel.fadeout(FOOTSTEP_FADE_MS)

    levels = load_levels(LEVELS_PATH)
    level_config = get_level_config(levels, level_number)
    items_config = level_config.get("items", {})
    objectives_config = level_config.get("objectives", {})
    debuffs_config = level_config.get("debuffs", {})
    abilities_config = level_config.get("monster_abilities", {})
    hud_font = pygame.font.SysFont(None, 26)
    monster_hearing = abilities_config.get("hearing", False)
    monster_smell = abilities_config.get("smell", False)
    monster_vision = abilities_config.get("vision", False)
    monster_cloning = max(0, int(abilities_config.get("cloning", 0)))
    freeze_enabled = debuffs_config.get("freezing", False)
    hunger_enabled = debuffs_config.get("hunger", False)
    darkness_amount = debuffs_config.get("darkness_amount", 0)

    coal_required = max(0, int(objectives_config.get("coal", 0)))
    levers_required = max(0, int(objectives_config.get("levers", 0)))
    coal_loaded = 0

    intro_status = run_level_intro(screen, clock, abilities_config, debuffs_config, level_number)
    if intro_status == "quit":
        stop_level_audio()
        return "quit"
    if intro_status == "menu":
        stop_level_audio()
        return "menu"

    spawn_tile = find_spawn_tile(grid)
    dark_tiles = build_dark_tiles(grid, spawn_tile, darkness_amount)
    items = spawn_items(grid, spawn_tile, items_config, objectives_config)
    dark_overlay = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
    dark_overlay.fill((0, 0, 0, DARK_OVERLAY_ALPHA))
    cold_value = 0.0
    hunger_value = 0.0
    dead = False
    monster_kill_radius_sq = MONSTER_KILL_RADIUS * MONSTER_KILL_RADIUS
    start_x = spawn_tile[0] * TILE_SIZE + (TILE_SIZE - player_size) / 2
    start_y = spawn_tile[1] * TILE_SIZE + (TILE_SIZE - player_size) / 2
    player = Player((start_x, start_y), player_size, player_images)
    patrol_points = build_patrol_points(grid, MONSTER_PATROL_COUNT, MONSTER_PATROL_SAMPLE_SIZE)
    monster_count = 1 + monster_cloning
    monster_tiles = pick_monster_spawns(grid, spawn_tile, monster_count)
    monsters = []
    for tile in monster_tiles:
        monster_pos = (
            tile[0] * TILE_SIZE + TILE_SIZE / 2,
            tile[1] * TILE_SIZE + TILE_SIZE / 2,
        )
        monsters.append(Monster(monster_pos, monster_assets, patrol_points))
    stone_projectiles = []

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        sound_events = []
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                stop_level_audio()
                return "quit"
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    screen = toggle_fullscreen()
                    continue
                if event.key == pygame.K_ESCAPE:
                    stop_level_audio()
                    return "menu"
                if event.key == pygame.K_w:
                    player.last_dir = pygame.Vector2(0, -1)
                elif event.key == pygame.K_s:
                    player.last_dir = pygame.Vector2(0, 1)
                elif event.key == pygame.K_a:
                    player.last_dir = pygame.Vector2(-1, 0)
                elif event.key == pygame.K_d:
                    player.last_dir = pygame.Vector2(1, 0)
                elif event.key == pygame.K_RETURN and not dead:
                    ate_apple, loaded_coal = handle_interaction(
                        player,
                        items,
                        grid,
                        sound_events,
                        stone_projectiles,
                        item_assets[ITEM_STONE],
                        dark_tiles,
                        sfx,
                    )
                    if ate_apple and HUNGER_ENABLED:
                        hunger_value = max(0.0, hunger_value - HUNGER_RESTORE)
                    if loaded_coal and coal_loaded < coal_required:
                        coal_loaded += 1

        if not dead:
            player.update(dt, grid, map_size_px)
            if player.moving and not footstep_active:
                footstep_channel.play(walk_sound, loops=-1, fade_ms=FOOTSTEP_FADE_MS)
                footstep_active = True
            elif not player.moving and footstep_active:
                footstep_channel.fadeout(FOOTSTEP_FADE_MS)
                footstep_active = False
            for projectile in stone_projectiles[:]:
                projectile.update(dt)
                if projectile.done:
                    items.append(Item(ITEM_STONE, projectile.landing_tile))
                    emit_sound(sound_events, projectile.landing_tile)
                    sfx["throw"].play()
                    stone_projectiles.remove(projectile)
            for monster in monsters:
                monster.update(
                    dt,
                    player.rect.center,
                    grid,
                    sound_events,
                    monster_hearing,
                    monster_smell,
                    monster_vision,
                )
            any_chasing = any(monster.is_chasing for monster in monsters)
            if any_chasing and not chase_active:
                ambient_channel.fadeout(MUSIC_FADE_MS)
                chase_channel.play(chase_sound, loops=-1, fade_ms=MUSIC_FADE_MS)
                chase_active = True
            elif not any_chasing and chase_active:
                chase_channel.fadeout(MUSIC_FADE_MS)
                ambient_channel.play(ambient_sound, loops=-1, fade_ms=MUSIC_FADE_MS)
                chase_active = False
            player_center = pygame.Vector2(player.rect.center)
            for monster in monsters:
                if (monster.pos - player_center).length_squared() <= monster_kill_radius_sq:
                    dead = True
                    break
        camera = compute_camera(player.rect, map_size_px)

        player_tile = get_player_tile(player)
        light_tiles = get_candle_light_tiles(items, player)
        visibility_tiles = get_candle_visibility_tiles(items, player)
        candle_centers = get_candle_centers(player, items)

        if freeze_enabled:
            in_dark = player_tile in dark_tiles and player_tile not in light_tiles
            if in_dark:
                cold_value = min(COLD_MAX, cold_value + COLD_RATE * dt)
            else:
                cold_value = max(0.0, cold_value - COLD_RECOVERY_RATE * dt)

        if hunger_enabled:
            hunger_value = min(HUNGER_MAX, hunger_value + HUNGER_RATE * dt)

        if freeze_enabled and cold_value >= COLD_MAX:
            dead = True
        if hunger_enabled and hunger_value >= HUNGER_MAX:
            dead = True

        levers_active = sum(
            1 for item in items if item.kind == ITEM_LEVER and item.active
        )
        level_complete = False
        if not dead:
            coal_done = coal_required <= 0 or coal_loaded >= coal_required
            levers_done = levers_required <= 0 or levers_active >= levers_required
            level_complete = coal_done and levers_done

        screen = pygame.display.get_surface() or screen
        screen.fill((10, 10, 14))
        world_surface = pygame.Surface(screen.get_size())
        world_surface.fill((10, 10, 14))
        draw_map(world_surface, grid, assets, camera)
        draw_items(world_surface, items, item_assets, camera, dark_tiles, visibility_tiles)
        draw_projectiles(world_surface, stone_projectiles, camera)
        player.draw(world_surface, camera)
        draw_carried_item(world_surface, player, item_assets, camera)
        draw_spotlight(world_surface, player, candle_centers, camera)
        draw_darkness(world_surface, dark_tiles, dark_overlay, candle_centers, camera)
        for monster in monsters:
            monster.draw(world_surface, camera)
        draw_item_outlines(world_surface, items, item_assets, item_outlines, camera, player, dark_tiles, visibility_tiles)
        draw_furnace_outline(world_surface, grid, player, camera)
        blit_zoomed_world(screen, world_surface, CAMERA_ZOOM)
        if freeze_enabled:
            draw_cold_bar(screen, cold_value)
        if hunger_enabled:
            draw_hunger_bar(screen, hunger_value)
        draw_objectives(
            screen,
            hud_font,
            coal_loaded,
            coal_required,
            levers_active,
            levers_required,
        )
        pygame.display.flip()

        if dead:
            stop_level_audio()
            snapshot = screen.copy()
            result = run_message_screen(screen, clock, "Вы умерли", snapshot)
            return "quit" if result == "quit" else "restart"
        if level_complete:
            stop_level_audio()
            snapshot = screen.copy()
            result = run_message_screen(screen, clock, "Вы прошли уровень!", snapshot)
            return "quit" if result == "quit" else "menu"
    return "menu"


if __name__ == "__main__":
    main()
