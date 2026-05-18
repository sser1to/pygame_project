import io
import math
import random
from pathlib import Path

import pygame

TILE_SIZE = 48
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720

MAP_PATH = Path(__file__).with_name("map.txt")
TEXTURES_DIR = Path(__file__).with_name("textures")

TILE_FLOOR = 1
TILE_WALL = 2
TILE_WALL_TOP = 3
TILE_FURNACE = 4
TILE_SPAWN = 6

ITEM_COAL = "coal"
ITEM_CANDLE = "candle"
ITEM_APPLE = "apple"
ITEM_LEVER = "lever"
ITEM_TYPES = [ITEM_COAL, ITEM_CANDLE, ITEM_APPLE, ITEM_LEVER]

ITEM_DRAW_SCALE = 0.6
ITEM_OUTLINE_COLOR = (80, 140, 200)

DARK_TILE_FRACTION = 0.18
DARK_SAFE_RADIUS = 4
DARK_OVERLAY_ALPHA = 220
DARK_BLOB_COUNT = 2
DARK_BLOB_MIN_SIZE = 30
CANDLE_LIGHT_RADIUS = 1

SPOTLIGHT_RADIUS = 1
SPOTLIGHT_FEATHER = 40
SPOTLIGHT_ALPHA = 210
PLAYER_LIGHT_ALPHA = 40
CANDLE_LIGHT_ALPHA = 0

FREEZE_ENABLED = True
COLD_MAX = 100.0
COLD_RATE = 14.0
COLD_RECOVERY_RATE = COLD_RATE / 2

HUNGER_ENABLED = True
HUNGER_MAX = 100.0
HUNGER_RATE = 4.0
HUNGER_RESTORE = HUNGER_MAX / 3

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


def build_dark_tiles(grid, spawn_tile):
    floor_tiles = collect_floor_tiles(grid)
    safe_tiles = [
        tile
        for tile in floor_tiles
        if abs(tile[0] - spawn_tile[0]) + abs(tile[1] - spawn_tile[1]) > DARK_SAFE_RADIUS
    ]
    if not safe_tiles:
        return set()
    total = max(1, int(len(safe_tiles) * DARK_TILE_FRACTION))
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


def spawn_items(grid, spawn_tile):
    floor_tiles = collect_floor_tiles(grid)
    available = [tile for tile in floor_tiles if tile != spawn_tile]
    random.shuffle(available)
    items = []
    for kind in ITEM_TYPES:
        if not available:
            break
        items.append(Item(kind, available.pop()))
    return items


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


def get_item_at(items, tile):
    for item in items:
        if item.tile == tile:
            return item
    return None


def handle_interaction(player, items, grid):
    player_tile = get_player_tile(player)
    if player.carrying:
        offset = direction_to_offset(player.last_dir)
        if offset == (0, 0):
            return False
        target = (player_tile[0] + offset[0], player_tile[1] + offset[1])
        if tile_is_placeable(grid, target) and get_item_at(items, target) is None:
            items.append(Item(player.carrying, target))
            player.carrying = None
        return False

    candidate_tiles = [player_tile] + adjacent_tiles(player_tile)
    for tile in candidate_tiles:
        item = get_item_at(items, tile)
        if item is None:
            continue
        if item.kind == ITEM_LEVER:
            if item.active:
                continue
            item.active = True
        elif item.kind == ITEM_APPLE:
            items.remove(item)
            return True
        else:
            player.carrying = item.kind
            items.remove(item)
        return False
    return False


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


def draw_items(screen, items, assets, offset):
    for item in items:
        item.draw(screen, assets, offset)


def draw_item_outlines(screen, items, assets, outlines, offset, player):
    player_tile = get_player_tile(player)
    can_pick = player.carrying is None
    pickable_tiles = [player_tile] + adjacent_tiles(player_tile)
    candidate = None
    candidate_dist = None
    player_center = player.rect.center
    for item in items:
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


def draw_carried_item(screen, player, assets, offset):
    if not player.carrying:
        return
    sprite = assets[player.carrying]
    world_x = player.rect.centerx - sprite.get_width() // 2
    world_y = player.rect.centery - sprite.get_height() // 2
    screen.blit(sprite, (world_x - offset.x, world_y - offset.y))


def draw_darkness(screen, dark_tiles, overlay, candle_centers, offset):
    darkness = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    for tx, ty in dark_tiles:
        world_x = tx * TILE_SIZE - offset.x
        world_y = ty * TILE_SIZE - offset.y
        darkness.blit(overlay, (world_x, world_y))

    candle_radius = int((CANDLE_LIGHT_RADIUS + 0.5) * TILE_SIZE)
    for candle_center in candle_centers:
        screen_pos = (
            int(candle_center[0] - offset.x),
            int(candle_center[1] - offset.y),
        )
        pygame.draw.circle(darkness, (0, 0, 0, 0), screen_pos, candle_radius)

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


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Abyss Walker - prototype")
    clock = pygame.time.Clock()

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

    spawn_tile = find_spawn_tile(grid)
    dark_tiles = build_dark_tiles(grid, spawn_tile)
    items = spawn_items(grid, spawn_tile)
    dark_overlay = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
    dark_overlay.fill((0, 0, 0, DARK_OVERLAY_ALPHA))
    cold_value = 0.0
    hunger_value = 0.0
    dead = False
    start_x = spawn_tile[0] * TILE_SIZE + (TILE_SIZE - player_size) / 2
    start_y = spawn_tile[1] * TILE_SIZE + (TILE_SIZE - player_size) / 2
    player = Player((start_x, start_y), player_size, player_images)

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_w:
                    player.last_dir = pygame.Vector2(0, -1)
                elif event.key == pygame.K_s:
                    player.last_dir = pygame.Vector2(0, 1)
                elif event.key == pygame.K_a:
                    player.last_dir = pygame.Vector2(-1, 0)
                elif event.key == pygame.K_d:
                    player.last_dir = pygame.Vector2(1, 0)
                elif event.key == pygame.K_RETURN and not dead:
                    ate_apple = handle_interaction(player, items, grid)
                    if ate_apple and HUNGER_ENABLED:
                        hunger_value = max(0.0, hunger_value - HUNGER_RESTORE)

        if not dead:
            player.update(dt, grid, map_size_px)
        camera = compute_camera(player.rect, map_size_px)

        player_tile = get_player_tile(player)
        light_tiles = get_candle_light_tiles(items, player)
        candle_centers = get_candle_centers(player, items)

        if FREEZE_ENABLED:
            in_dark = player_tile in dark_tiles and player_tile not in light_tiles
            if in_dark:
                cold_value = min(COLD_MAX, cold_value + COLD_RATE * dt)
            else:
                cold_value = max(0.0, cold_value - COLD_RECOVERY_RATE * dt)

        if HUNGER_ENABLED:
            hunger_value = min(HUNGER_MAX, hunger_value + HUNGER_RATE * dt)

        if FREEZE_ENABLED and cold_value >= COLD_MAX:
            dead = True
        if HUNGER_ENABLED and hunger_value >= HUNGER_MAX:
            dead = True

        screen.fill((10, 10, 14))
        draw_map(screen, grid, assets, camera)
        draw_items(screen, items, item_assets, camera)
        player.draw(screen, camera)
        draw_carried_item(screen, player, item_assets, camera)
        draw_spotlight(screen, player, candle_centers, camera)
        draw_darkness(screen, dark_tiles, dark_overlay, candle_centers, camera)
        draw_item_outlines(screen, items, item_assets, item_outlines, camera, player)
        if FREEZE_ENABLED:
            draw_cold_bar(screen, cold_value)
        if HUNGER_ENABLED:
            draw_hunger_bar(screen, hunger_value)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
