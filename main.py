import io
import math
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

SOLID_TILES = {0, TILE_WALL, TILE_WALL_TOP, TILE_FURNACE}
PLAYER_START_TILE = (16, 4)
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
            screen.blit(assets["floor"], (world_x - offset.x, world_y - offset.y))

            if tile == TILE_WALL:
                screen.blit(assets["wall"], (world_x - offset.x, world_y - offset.y))
            elif tile == TILE_WALL_TOP:
                screen.blit(assets["wall_top"], (world_x - offset.x, world_y - offset.y))
            elif tile == TILE_FURNACE:
                if (tx, ty) in skipped_furnace:
                    continue
                if tx + 1 < cols and grid[ty][tx + 1] == TILE_FURNACE:
                    screen.blit(
                        assets["furnace"],
                        (world_x - offset.x, world_y - offset.y),
                    )
                    skipped_furnace.add((tx + 1, ty))
                else:
                    screen.blit(assets["furnace_single"], (world_x - offset.x, world_y - offset.y))


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

    player_size = int(TILE_SIZE * 0.9)
    player_images = [
        load_svg_surface(TEXTURES_DIR / "player_stand.svg", (player_size, player_size)),
        load_svg_surface(TEXTURES_DIR / "player_walk.svg", (player_size, player_size)),
    ]

    start_x = PLAYER_START_TILE[0] * TILE_SIZE + (TILE_SIZE - player_size) / 2
    start_y = PLAYER_START_TILE[1] * TILE_SIZE + (TILE_SIZE - player_size) / 2
    player = Player((start_x, start_y), player_size, player_images)

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        player.update(dt, grid, map_size_px)
        camera = compute_camera(player.rect, map_size_px)

        screen.fill((10, 10, 14))
        draw_map(screen, grid, assets, camera)
        player.draw(screen, camera)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
