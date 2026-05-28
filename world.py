import heapq
import json
import math
import random

import pygame

from settings import (
    CANDLE_LIGHT_RADIUS,
    DARK_NOISE_OCTAVES,
    DARK_NOISE_PERSISTENCE,
    DARK_NOISE_SCALE,
    DARK_SAFE_RADIUS,
    DARK_SMOOTH_PASSES,
    DARK_TILE_FRACTION,
    DARK_OVERLAY_ALPHA,
    ITEM_APPLE,
    ITEM_CANDLE,
    ITEM_COAL,
    ITEM_LEVER,
    ITEM_MIN_DISTANCE_TILES,
    ITEM_SPAWN_ATTEMPTS,
    ITEM_SPAWN_SAMPLES,
    ITEM_STONE,
    MONSTER_PATROL_COUNT,
    MONSTER_PATROL_SAMPLE_SIZE,
    MONSTER_SPAWN_MIN_DISTANCE,
    MONSTER_SPAWN_SAFE_RADIUS,
    SHADOW_BLUR_PASSES,
    SHADOW_CORNER_RADIUS,
    SHADOW_PAD,
    TILE_FLOOR,
    TILE_FURNACE,
    TILE_SPAWN,
    TILE_SIZE,
    TILE_WALL,
    TILE_WALL_TOP,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SOLID_TILES,
)
from assets import soften_alpha_mask


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


def adjacent_tiles(tile):
    tx, ty = tile
    return [(tx + 1, ty), (tx - 1, ty), (tx, ty + 1), (tx, ty - 1)]


def tile_in_bounds(grid, tile):
    tx, ty = tile
    return 0 <= ty < len(grid) and 0 <= tx < len(grid[0])


def tile_is_placeable(grid, tile):
    if not tile_in_bounds(grid, tile):
        return False
    tx, ty = tile
    return grid[ty][tx] == TILE_FLOOR


def tile_is_furnace(grid, tile):
    if not tile_in_bounds(grid, tile):
        return False
    tx, ty = tile
    return grid[ty][tx] == TILE_FURNACE


def tile_blocks_vision(grid, tile):
    if not tile_in_bounds(grid, tile):
        return True
    return grid[tile[1]][tile[0]] in (TILE_WALL, TILE_WALL_TOP, TILE_FURNACE)


def tile_is_walkable(grid, tile):
    if not tile_in_bounds(grid, tile):
        return False
    return grid[tile[1]][tile[0]] not in SOLID_TILES


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


def tile_to_world_center(tile):
    return (
        tile[0] * TILE_SIZE + TILE_SIZE / 2,
        tile[1] * TILE_SIZE + TILE_SIZE / 2,
    )


def _wall_penalty(grid, tile):
    penalty = 0.0
    for neighbor in _neighbors8(tile):
        if not tile_is_walkable(grid, neighbor):
            penalty += 0.12
    return penalty


def build_flow_field(grid, goals):
    rows = len(grid)
    cols = len(grid[0])
    inf = float("inf")
    cost = [[inf for _ in range(cols)] for _ in range(rows)]
    heap = []

    for goal_tile, bias in goals:
        if not tile_is_walkable(grid, goal_tile):
            continue
        tx, ty = goal_tile
        if bias < cost[ty][tx]:
            cost[ty][tx] = bias
            heapq.heappush(heap, (bias, tx, ty))

    while heap:
        current_cost, tx, ty = heapq.heappop(heap)
        if current_cost != cost[ty][tx]:
            continue
        for nx, ny in adjacent_tiles((tx, ty)):
            if not tile_is_walkable(grid, (nx, ny)):
                continue
            step_cost = 1.0 + _wall_penalty(grid, (nx, ny))
            next_cost = current_cost + step_cost
            if next_cost < cost[ny][nx]:
                cost[ny][nx] = next_cost
                heapq.heappush(heap, (next_cost, nx, ny))

    return cost


def pick_flow_step(flow_field, current_tile, rng):
    tx, ty = current_tile
    if ty < 0 or ty >= len(flow_field) or tx < 0 or tx >= len(flow_field[0]):
        return None
    current_cost = flow_field[ty][tx]
    if current_cost == float("inf"):
        return None
    candidates = []
    for nx, ny in adjacent_tiles(current_tile):
        if ny < 0 or ny >= len(flow_field) or nx < 0 or nx >= len(flow_field[0]):
            continue
        if flow_field[ny][nx] < current_cost:
            candidates.append((nx, ny))
    if not candidates:
        return None
    return rng.choice(candidates)


def _lerp(a, b, t):
    return a + (b - a) * t


def _smoothstep(t):
    return t * t * (3.0 - 2.0 * t)


def _value_noise_layer(cols, rows, scale, rng):
    grid_cols = max(2, cols // scale + 2)
    grid_rows = max(2, rows // scale + 2)
    values = [[rng.random() for _ in range(grid_cols)] for _ in range(grid_rows)]
    layer = [[0.0 for _ in range(cols)] for _ in range(rows)]
    for y in range(rows):
        gy = y / float(scale)
        y0 = int(gy)
        y1 = min(y0 + 1, grid_rows - 1)
        ty = _smoothstep(gy - y0)
        for x in range(cols):
            gx = x / float(scale)
            x0 = int(gx)
            x1 = min(x0 + 1, grid_cols - 1)
            tx = _smoothstep(gx - x0)
            v00 = values[y0][x0]
            v10 = values[y0][x1]
            v01 = values[y1][x0]
            v11 = values[y1][x1]
            v0 = _lerp(v00, v10, tx)
            v1 = _lerp(v01, v11, tx)
            layer[y][x] = _lerp(v0, v1, ty)
    return layer


def _fractal_noise(cols, rows, rng):
    noise = [[0.0 for _ in range(cols)] for _ in range(rows)]
    amplitude = 1.0
    total_amp = 0.0
    scale = max(1, DARK_NOISE_SCALE)
    for _ in range(max(1, DARK_NOISE_OCTAVES)):
        layer = _value_noise_layer(cols, rows, scale, rng)
        for y in range(rows):
            for x in range(cols):
                noise[y][x] += layer[y][x] * amplitude
        total_amp += amplitude
        amplitude *= DARK_NOISE_PERSISTENCE
        scale = max(1, int(scale * 0.5))
    if total_amp <= 0:
        return noise
    for y in range(rows):
        for x in range(cols):
            noise[y][x] /= total_amp
    return noise


def _neighbors8(tile):
    tx, ty = tile
    return [
        (tx - 1, ty - 1),
        (tx, ty - 1),
        (tx + 1, ty - 1),
        (tx - 1, ty),
        (tx + 1, ty),
        (tx - 1, ty + 1),
        (tx, ty + 1),
        (tx + 1, ty + 1),
    ]


def build_dark_tiles(grid, spawn_tile, darkness_amount):
    if darkness_amount <= 0:
        return set()
    floor_tiles = collect_floor_tiles(grid)
    if not floor_tiles:
        return set()

    rows = len(grid)
    cols = len(grid[0])
    rng = random.Random()
    noise = _fractal_noise(cols, rows, rng)

    safe_radius_sq = DARK_SAFE_RADIUS * DARK_SAFE_RADIUS
    scores = []
    for ty in range(rows):
        for tx in range(cols):
            if grid[ty][tx] != TILE_FLOOR:
                continue
            dx = tx - spawn_tile[0]
            dy = ty - spawn_tile[1]
            dist_sq = dx * dx + dy * dy
            if dist_sq <= safe_radius_sq:
                continue
            edge_bias = (abs(dx) + abs(dy)) * 0.015
            jitter = rng.uniform(-0.05, 0.05)
            score = noise[ty][tx] + edge_bias + jitter
            scores.append((score, (tx, ty)))

    if not scores:
        return set()

    fraction = DARK_TILE_FRACTION * max(0, darkness_amount)
    total = min(len(scores), max(0, int(len(scores) * fraction)))
    if total <= 0:
        return set()

    scores.sort(key=lambda item: item[0], reverse=True)
    dark_tiles = {tile for _, tile in scores[:total]}

    for _ in range(max(1, DARK_SMOOTH_PASSES)):
        next_dark = set()
        for _, tile in scores:
            dark_neighbors = 0
            for neighbor in _neighbors8(tile):
                if neighbor in dark_tiles:
                    dark_neighbors += 1
            if tile in dark_tiles:
                if dark_neighbors >= 3:
                    next_dark.add(tile)
            else:
                if dark_neighbors >= 5:
                    next_dark.add(tile)
        dark_tiles = next_dark

    return dark_tiles


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
            dist = min((cand[0] - p[0]) ** 2 + (cand[1] - p[1]) ** 2 for p in points)
            if dist > best_dist:
                best_dist = dist
                best_tile = cand
        points.append(best_tile)

    return [tile_to_world_center(tile) for tile in points]


def _tile_distance_sq(a, b):
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return dx * dx + dy * dy


def _best_candidate(available, existing, spawn_tile, min_dist_sq, rng):
    best = None
    best_score = -1.0
    if not available:
        return None
    samples = min(len(available), max(3, ITEM_SPAWN_SAMPLES))
    for _ in range(samples):
        cand = rng.choice(available)
        if _tile_distance_sq(cand, spawn_tile) < min_dist_sq:
            continue
        if existing:
            closest_same = min(_tile_distance_sq(cand, other) for other in existing)
            if closest_same < min_dist_sq:
                continue
        else:
            closest_same = min_dist_sq * 4
        score = min(closest_same, _tile_distance_sq(cand, spawn_tile))
        if score > best_score:
            best = cand
            best_score = score
    return best


def spawn_items(grid, spawn_tile, items_counts, objectives):
    from entities import Item

    floor_tiles = collect_floor_tiles(grid)
    available = [tile for tile in floor_tiles if tile != spawn_tile]
    rng = random.Random()
    min_dist_sq = ITEM_MIN_DISTANCE_TILES * ITEM_MIN_DISTANCE_TILES

    items = []
    placed_by_kind = {
        ITEM_COAL: [],
        ITEM_CANDLE: [],
        ITEM_APPLE: [],
        ITEM_LEVER: [],
        ITEM_STONE: [],
    }

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
        if count <= 0:
            continue
        for _ in range(count):
            candidate = None
            for _ in range(max(1, ITEM_SPAWN_ATTEMPTS)):
                candidate = _best_candidate(
                    available,
                    placed_by_kind[kind],
                    spawn_tile,
                    min_dist_sq,
                    rng,
                )
                if candidate is not None:
                    break
            if candidate is None:
                break
            items.append(Item(kind, candidate))
            placed_by_kind[kind].append(candidate)
            if candidate in available:
                available.remove(candidate)
    return items


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
        alternate = min((pos for pos in world_positions if pos != left), key=distance_sq, default=left)
        right = alternate

    return left, right


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


def get_furnace_rect(grid, tile):
    tx, ty = tile
    if not tile_in_bounds(grid, tile) or grid[ty][tx] != TILE_FURNACE:
        return None
    left_tx = tx
    if tile_in_bounds(grid, (tx - 1, ty)) and grid[ty][tx - 1] == TILE_FURNACE:
        left_tx = tx - 1
    width = TILE_SIZE * (
        2 if tile_in_bounds(grid, (left_tx + 1, ty)) and grid[ty][left_tx + 1] == TILE_FURNACE else 1
    )
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
    from entities import Item, StoneProjectile

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
                    screen.blit(assets["floor"], (world_x + TILE_SIZE - offset.x, world_y - offset.y))
                    screen.blit(assets["furnace"], (world_x - offset.x, world_y - offset.y))
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
    from entities import get_item_outline_key, get_item_sprite

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
    outline_rect = pygame.Rect(rect.x - offset.x, rect.y - offset.y, rect.width, rect.height)
    pygame.draw.rect(screen, (80, 140, 200), outline_rect, 2)


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
        screen_pos = (int(candle_center[0] - offset.x), int(candle_center[1] - offset.y))
        pygame.draw.circle(darkness, (0, 0, 0, 0), screen_pos, candle_radius)

    darkness = soften_alpha_mask(darkness, SHADOW_BLUR_PASSES)
    screen.blit(darkness, (0, 0))


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
