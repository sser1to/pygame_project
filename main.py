import pygame

from assets import AssetManager
from entities import Monster, Player, build_item_outlines
from settings import (
    AMBIENT_VOLUME,
    CHASE_VOLUME,
    LEVEL_COUNT,
    HUNGER_RESTORE,
    DARK_OVERLAY_ALPHA,
    FOOTSTEP_FADE_MS,
    FOOTSTEP_VOLUME,
    INTRO_CHAR_RATE,
    ITEM_APPLE,
    ITEM_CANDLE,
    ITEM_COAL,
    ITEM_LEVER,
    ITEM_DRAW_SCALE,
    ITEM_OUTLINE_COLOR,
    ITEM_STONE,
    ITEM_NOTE,
    FILM_GRAIN_ALPHA,
    VIGNETTE_INTENSITY_NORMAL,
    VIGNETTE_INTENSITY_CHASE,
    PLAYER_SIZE_FACTOR,
    LEVELS_PATH,
    NOTES_PATH,
    MAP_PATH,
    MONSTER_ARM_LOWER_SCALE_X,
    MONSTER_ARM_LOWER_SCALE_Y,
    MONSTER_ARM_UPPER_SCALE_X,
    MONSTER_ARM_UPPER_SCALE_Y,
    MONSTER_HEAD_SCALE,
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
    Effects,
    HUD,
    SplashScreen,
    IntroScreen,
    MessageScreen,
    NoteScreen,
    CreditsScreen,
    MenuScreen,
    ScreenUtils,
)
from world import (
    Grid,
    DataManager,
    SaveManager,
    Level,
)


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Project Abyss")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)
        self.clock = pygame.time.Clock()
        pygame.mouse.set_visible(False)

        pygame.mixer.set_num_channels(12)
        self.effects = Effects()

        self._load_assets()
        self._setup_audio()

    def _load_assets(self):
        self.assets = {
            "floor": AssetManager.load_svg_surface(TEXTURES_DIR / "floor.svg", (TILE_SIZE, TILE_SIZE)),
            "wall": AssetManager.load_svg_surface(TEXTURES_DIR / "wall_side.svg", (TILE_SIZE, TILE_SIZE)),
            "wall_top": AssetManager.load_svg_surface(TEXTURES_DIR / "wall_top.svg", (TILE_SIZE, TILE_SIZE)),
            "furnace": AssetManager.load_svg_surface(TEXTURES_DIR / "furnace.svg", (TILE_SIZE * 2, TILE_SIZE)),
            "furnace_single": AssetManager.load_svg_surface(TEXTURES_DIR / "furnace.svg", (TILE_SIZE, TILE_SIZE)),
        }

        item_size = int(TILE_SIZE * ITEM_DRAW_SCALE)
        self.item_assets = {
            ITEM_COAL: AssetManager.load_svg_surface(TEXTURES_DIR / "coal.svg", (item_size, item_size)),
            ITEM_CANDLE: AssetManager.load_svg_surface(TEXTURES_DIR / "candle.svg", (item_size, item_size)),
            ITEM_APPLE: AssetManager.load_svg_surface(TEXTURES_DIR / "apple.svg", (item_size, item_size)),
            ITEM_STONE: AssetManager.load_svg_surface(TEXTURES_DIR / "stone.svg", (item_size, item_size)),
            ITEM_NOTE: AssetManager.load_svg_surface(TEXTURES_DIR / "note.svg", (item_size, item_size)),
            "lever_off": AssetManager.load_svg_surface(TEXTURES_DIR / "lever_off.svg", (item_size, item_size)),
            "lever_on": AssetManager.load_svg_surface(TEXTURES_DIR / "lever_on.svg", (item_size, item_size)),
        }
        self.item_outlines = build_item_outlines(self.item_assets, ITEM_OUTLINE_COLOR)

        player_size = int(TILE_SIZE * PLAYER_SIZE_FACTOR)
        self.player_images = [
            AssetManager.load_svg_surface(TEXTURES_DIR / "player_stand.svg", (player_size, player_size)),
            AssetManager.load_svg_surface(TEXTURES_DIR / "player_walk.svg", (player_size, player_size)),
            AssetManager.load_svg_surface(TEXTURES_DIR / "player_walk2.svg", (player_size, player_size)),
        ]
        self.player_size = player_size

        arm_lower = AssetManager.tint_surface(
            AssetManager.load_svg_surface(
                TEXTURES_DIR / "monster_arm_lower.svg",
                (
                    int(TILE_SIZE * MONSTER_ARM_LOWER_SCALE_X * 0.8),
                    int(TILE_SIZE * MONSTER_ARM_LOWER_SCALE_Y * 1.5),
                ),
            ),
            MONSTER_TINT,
        )
        arm_lower = pygame.transform.flip(arm_lower, True, False)
        self.monster_assets = {
            "head": AssetManager.tint_surface(
                AssetManager.load_svg_surface(
                    TEXTURES_DIR / "monster_head.svg",
                    (int(TILE_SIZE * MONSTER_HEAD_SCALE), int(TILE_SIZE * MONSTER_HEAD_SCALE)),
                ),
                MONSTER_TINT,
            ),
            "arm_upper": AssetManager.tint_surface(
                AssetManager.load_svg_surface(
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

    def _setup_audio(self):
        self.ambient_sound = AssetManager.load_sound(SOUNDS_DIR / "ambient.mp3", AMBIENT_VOLUME)
        self.chase_sound = AssetManager.load_sound(SOUNDS_DIR / "chase.mp3", CHASE_VOLUME)
        self.walk_sound = AssetManager.load_sound(SOUNDS_DIR / "player_walk.mp3", FOOTSTEP_VOLUME, speed=2.0)
        self.sfx = {
            "throw": AssetManager.load_sound(SOUNDS_DIR / "throw_stone.mp3", SFX_VOLUME),
            "furnace": AssetManager.load_sound(SOUNDS_DIR / "activate_furnace.mp3", SFX_VOLUME),
            "pickup": AssetManager.load_sound(SOUNDS_DIR / "pick_up.mp3", SFX_VOLUME),
            "lever": AssetManager.load_sound(SOUNDS_DIR / "activate_lever.mp3", SFX_VOLUME),
        }
        self.ambient_channel = pygame.mixer.Channel(0)
        self.chase_channel = pygame.mixer.Channel(1)
        self.footstep_channel = pygame.mixer.Channel(2)
        self.chase_active = False
        self.chase_timer = 0.0
        self.footstep_active = False

    def _stop_level_audio(self):
        self.ambient_channel.fadeout(MUSIC_FADE_MS)
        self.chase_channel.fadeout(MUSIC_FADE_MS)
        self.footstep_channel.fadeout(FOOTSTEP_FADE_MS)

    def _play_level_audio(self):
        self.ambient_channel.play(self.ambient_sound, loops=-1, fade_ms=MUSIC_FADE_MS)

    def _end_level(self, message, result_on_continue):
        self._stop_level_audio()
        pygame.event.clear()
        snapshot = self.screen.copy()
        result = MessageScreen.run(self.screen, self.clock, message, snapshot)
        return "quit" if result == "quit" else result_on_continue

    def run_level(self, level_number):
        grid = Grid(MAP_PATH)
        levels = DataManager.load_levels(LEVELS_PATH)
        notes = DataManager.load_notes(NOTES_PATH)
        level_config = DataManager.get_level_config(levels, level_number)
        abilities_config = level_config.get("monster_abilities", {})
        debuffs_config = level_config.get("debuffs", {})

        intro = IntroScreen(abilities_config, debuffs_config, level_number)
        intro_result = intro.run(self.screen, self.clock)
        if intro_result == "quit":
            return "quit"
        if intro_result == "menu":
            return "menu"

        level = Level(grid, level_number, levels)

        start_x = level.spawn_tile[0] * TILE_SIZE + (TILE_SIZE - self.player_size) / 2
        start_y = level.spawn_tile[1] * TILE_SIZE + (TILE_SIZE - self.player_size) / 2
        player = Player((start_x, start_y), self.player_size, self.player_images)

        patrol_points = level.build_patrol_points()
        monster_tiles = level.pick_monster_spawns()
        monsters = []
        for tile in monster_tiles:
            monster_pos = (tile[0] * TILE_SIZE + TILE_SIZE / 2, tile[1] * TILE_SIZE + TILE_SIZE / 2)
            monsters.append(Monster(monster_pos, self.monster_assets, patrol_points))

        items = level.spawn_items()
        level.setup_entities(player, items, monsters)

        dark_overlay = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        dark_overlay.fill((0, 0, 0, DARK_OVERLAY_ALPHA))

        stone_sprite = self.item_assets[ITEM_STONE]
        hud_font = pygame.font.SysFont(None, 26)
        self._play_level_audio()
        self.chase_active = False
        self.chase_timer = 0.0
        self.footstep_active = False
        sound_events = []

        running = True
        while running:
            dt = self.clock.tick(60) / 1000.0
            sound_events.clear()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._stop_level_audio()
                    return "quit"
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_F11:
                        self.screen = ScreenUtils.toggle_fullscreen()
                        continue
                    if event.key == pygame.K_ESCAPE:
                        self._stop_level_audio()
                        return "menu"
                    if event.key in (pygame.K_w, pygame.K_s, pygame.K_a, pygame.K_d):
                        move_map = {
                            pygame.K_w: pygame.Vector2(0, -1),
                            pygame.K_s: pygame.Vector2(0, 1),
                            pygame.K_a: pygame.Vector2(-1, 0),
                            pygame.K_d: pygame.Vector2(1, 0),
                        }
                        player.last_dir = move_map[event.key]
                    if event.key == pygame.K_RETURN and not level.dead:
                        ate_apple, loaded_coal, note_level = level.handle_interaction(
                            stone_sprite, self.sfx, sound_events,
                        )
                        if ate_apple and level.hunger_enabled:
                            level.hunger_value = max(0.0, level.hunger_value - HUNGER_RESTORE)
                        if loaded_coal and level.coal_loaded < level.coal_required:
                            level.coal_loaded += 1
                        if note_level is not None:
                            note_data = DataManager.get_note(notes, note_level)
                            if note_data is not None:
                                result = NoteScreen.run(
                                    self.screen, self.clock,
                                    note_data["title"], note_data["text"],
                                    background=self.screen.copy(),
                                )
                                if result == "quit":
                                    self._stop_level_audio()
                                    return "quit"

            level.update(dt, sound_events)

            any_chasing = any(monster.is_chasing for monster in monsters)
            if any_chasing and not self.chase_active:
                self.ambient_channel.fadeout(MUSIC_FADE_MS)
                self.chase_channel.play(self.chase_sound, loops=-1, fade_ms=MUSIC_FADE_MS)
                self.chase_active = True
            elif not any_chasing and self.chase_active:
                self.chase_channel.fadeout(MUSIC_FADE_MS)
                self.ambient_channel.play(self.ambient_sound, loops=-1, fade_ms=MUSIC_FADE_MS)
                self.chase_active = False
            self.chase_timer = self.chase_timer + dt if self.chase_active else 0.0

            if level.player.moving and not self.footstep_active:
                self.footstep_channel.play(self.walk_sound, loops=-1, fade_ms=FOOTSTEP_FADE_MS)
                self.footstep_active = True
            elif not level.player.moving and self.footstep_active:
                self.footstep_channel.fadeout(FOOTSTEP_FADE_MS)
                self.footstep_active = False

            camera = Level.compute_camera(level.player.rect, grid.map_size_px)
            candle_centers = level.get_candle_centers()

            self.screen = pygame.display.get_surface() or self.screen
            self.screen.fill((10, 10, 14))

            level.draw_world(self.screen, camera, self.assets, self.item_assets, self.item_outlines, dt)

            vignette_intensity = VIGNETTE_INTENSITY_NORMAL if not self.chase_active else VIGNETTE_INTENSITY_CHASE
            self.effects.draw_dust(self.screen, camera, dt)
            self.effects.draw_frost_overlay(self.screen, level.cold_value, level.freeze_enabled)
            self.effects.draw_film_grain(self.screen, FILM_GRAIN_ALPHA)
            self.effects.draw_vignette(self.screen, vignette_intensity)
            self.effects.draw_chase_pulse(self.screen, self.chase_active, dt)

            if level.freeze_enabled:
                HUD.draw_cold_bar(self.screen, level.cold_value)
            if level.hunger_enabled:
                HUD.draw_hunger_bar(self.screen, level.hunger_value)
            HUD.draw_objectives(
                self.screen, hud_font,
                level.coal_loaded, level.coal_required,
                sum(1 for item in items if item.kind == ITEM_LEVER and item.active),
                level.levers_required,
            )
            self.effects.draw_hunger_distortion(self.screen, level.hunger_value, dt)

            if level.exit_was_unlocked:
                NOTIF_TEXT = "Выход разблокирован"
                total_notif = len(NOTIF_TEXT)
                typing_time = total_notif / INTRO_CHAR_RATE
                hold_time = 1.5
                if level.exit_notification_timer < typing_time + hold_time:
                    level.exit_notification_timer += dt
                    visible = min(total_notif, int(level.exit_notification_timer * INTRO_CHAR_RATE))
                    notif_font = pygame.font.SysFont(None, 56)
                    notif_surf = notif_font.render(NOTIF_TEXT[:visible], True, (255, 255, 255))
                    notif_rect = notif_surf.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() // 4))
                    self.screen.blit(notif_surf, notif_rect)

            pygame.display.flip()

            if level.dead:
                return self._end_level("Вы умерли", "restart")
            if level.level_complete:
                return self._end_level("Вы прошли уровень!", "complete")

        return "menu"

    def run(self):
        if SplashScreen.run(self.screen, self.clock) == "quit":
            pygame.quit()
            return

        unlocked_level = SaveManager.load_progress()
        last_selected_level = unlocked_level

        while True:
            selected_level = MenuScreen.run(self.screen, self.clock, last_selected_level, unlocked_level)
            if selected_level is None:
                break
            last_selected_level = selected_level
            while True:
                result = self.run_level(selected_level)
                if result == "restart":
                    continue
                if result == "menu":
                    break
                if result == "complete":
                    if selected_level >= unlocked_level:
                        unlocked_level = min(selected_level + 1, LEVEL_COUNT)
                        SaveManager.save_progress(unlocked_level)
                        last_selected_level = unlocked_level
                    if selected_level < LEVEL_COUNT:
                        selected_level += 1
                        continue
                    else:
                        if CreditsScreen.run(self.screen, self.clock) == "quit":
                            pygame.quit()
                            return
                    break
                if result == "quit":
                    pygame.quit()
                    return
        pygame.quit()


def main():
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
