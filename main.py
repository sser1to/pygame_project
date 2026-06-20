import pygame

from assets import load_sound, load_svg_surface, tint_surface
from entities import Item, Monster, Player, build_item_outlines
from settings import (
    AMBIENT_VOLUME,
    CAMERA_ZOOM,
    CHASE_VOLUME,
    COLD_MAX,
    COLD_RATE,
    COLD_RECOVERY_RATE,
    CURRENT_LEVEL,
    DARK_OVERLAY_ALPHA,
    FOOTSTEP_FADE_MS,
    FOOTSTEP_VOLUME,
    FREEZE_ENABLED,
    HUNGER_ENABLED,
    HUNGER_MAX,
    HUNGER_RATE,
    HUNGER_RESTORE,
    ITEM_APPLE,
    ITEM_CANDLE,
    ITEM_COAL,
    ITEM_DRAW_SCALE,
    ITEM_LEVER,
    ITEM_OUTLINE_COLOR,
    ITEM_STONE,
    LEVELS_PATH,
    MAP_PATH,
    MONSTER_ARM_LOWER_SCALE_X,
    MONSTER_ARM_LOWER_SCALE_Y,
    MONSTER_ARM_UPPER_SCALE_X,
    MONSTER_ARM_UPPER_SCALE_Y,
    MONSTER_HEAD_SCALE,
    MONSTER_HEARING_RANGE_TILES,
    MONSTER_KILL_RADIUS,
    MONSTER_PATROL_COUNT,
    MONSTER_PATROL_SAMPLE_SIZE,
    MONSTER_SMELL_RANGE_TILES,
    MONSTER_SMELL_SPEED,
    MONSTER_PASSIVE_SPEED,
    MONSTER_SPAWN_MIN_DISTANCE,
    MONSTER_SPAWN_SAFE_RADIUS,
    MONSTER_STEP_SPEED,
    MONSTER_TINT,
    MUSIC_FADE_MS,
    SFX_VOLUME,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SOUNDS_DIR,
    TEXTURES_DIR,
    TILE_SIZE,
)
from ui import (
    draw_chase_pulse,
    draw_cold_bar,
    draw_dust,
    draw_film_grain,
    draw_frost_overlay,
    draw_hunger_bar,
    draw_objectives,
    draw_spotlight,
    draw_vignette,
    run_level_intro,
    run_message_screen,
    run_menu,
    toggle_fullscreen,
)
from world import (
    blit_zoomed_world,
    build_dark_tiles,
    build_patrol_points,
    compute_camera,
    draw_carried_item,
    draw_darkness,
    draw_furnace_outline,
    draw_item_outlines,
    draw_items,
    draw_map,
    draw_projectiles,
    emit_sound,
    find_spawn_tile,
    get_candle_centers,
    get_candle_light_tiles,
    get_candle_visibility_tiles,
    get_level_config,
    get_player_tile,
    handle_interaction,
    load_levels,
    load_map,
    pick_monster_spawns,
    spawn_items,
)


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
    walk_sound = load_sound(SOUNDS_DIR / "player_walk.mp3", FOOTSTEP_VOLUME, speed=2.0)
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
    chase_timer = 0.0
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
        monster_pos = (tile[0] * TILE_SIZE + TILE_SIZE / 2, tile[1] * TILE_SIZE + TILE_SIZE / 2)
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
            if event.type == pygame.KEYDOWN:
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
            chase_timer = chase_timer + dt if chase_active else 0.0
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

        levers_active = sum(1 for item in items if item.kind == ITEM_LEVER and item.active)
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
        draw_spotlight(world_surface, player, candle_centers, camera, dt)
        draw_darkness(world_surface, dark_tiles, dark_overlay, candle_centers, camera)
        for monster in monsters:
            monster.draw(world_surface, camera)
        draw_item_outlines(world_surface, items, item_assets, item_outlines, camera, player, dark_tiles, visibility_tiles)
        draw_furnace_outline(world_surface, grid, player, camera)
        draw_dust(world_surface, camera, dt)
        blit_zoomed_world(screen, world_surface, CAMERA_ZOOM)

        # Atmosphere effects
        draw_frost_overlay(screen, cold_value, freeze_enabled)
        draw_film_grain(screen, 0.12)
        vignette_intensity = 0.65 if not chase_active else 0.75
        draw_vignette(screen, vignette_intensity)
        draw_chase_pulse(screen, chase_timer, chase_active, dt)

        if freeze_enabled:
            draw_cold_bar(screen, cold_value)
        if hunger_enabled:
            draw_hunger_bar(screen, hunger_value)
        draw_objectives(screen, hud_font, coal_loaded, coal_required, levers_active, levers_required)
        pygame.display.flip()

        if dead:
            stop_level_audio()
            pygame.event.clear()
            snapshot = screen.copy()
            result = run_message_screen(screen, clock, "Вы умерли", snapshot)
            return "quit" if result == "quit" else "restart"
        if level_complete:
            stop_level_audio()
            pygame.event.clear()
            snapshot = screen.copy()
            result = run_message_screen(screen, clock, "Вы прошли уровень!", snapshot)
            return "quit" if result == "quit" else "menu"
    return "menu"


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)
    clock = pygame.time.Clock()
    pygame.mouse.set_visible(False)

    last_selected_level = CURRENT_LEVEL

    while True:
        selected_level = run_menu(screen, clock, last_selected_level)
        if selected_level is None:
            break
        last_selected_level = selected_level
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


if __name__ == "__main__":
    main()
