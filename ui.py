import math
import random

import pygame

from settings import (
    CANDLE_LIGHT_RADIUS,
    CANDLE_LIGHT_ALPHA,
    HUD_SHADOW,
    HUD_TEXT,
    INTRO_BG,
    INTRO_CHAR_RATE,
    INTRO_MONSTER,
    INTRO_TEXT,
    LEVEL_COUNT,
    MENU_ACCENT,
    MENU_BG,
    MENU_DIM,
    MENU_TEXT,
    PLAYER_LIGHT_ALPHA,
    SPOTLIGHT_ALPHA,
    SPOTLIGHT_FEATHER,
    SPOTLIGHT_RADIUS,
    TILE_SIZE,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)
from world import adjacent_tiles, get_player_tile, get_light_tiles, get_candle_centers, get_candle_light_tiles, get_candle_visibility_tiles


def toggle_fullscreen():
    current = pygame.display.get_surface()
    if current is None:
        return pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    is_fullscreen = bool(current.get_flags() & pygame.FULLSCREEN)
    if is_fullscreen:
        return pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    return pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)


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
        lines.append([("Монстр", INTRO_MONSTER), (f" умеет клонироваться (x{cloning_count})", INTRO_TEXT)])

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
    hold_duration = 3

    while True:
        dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                screen = toggle_fullscreen()
                continue
            if event.type == pygame.KEYDOWN and event.key in (
                pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_ESCAPE,
            ):
                if typing_done:
                    return "done"
                visible_chars = float(total_chars)
                typing_done = True
            if event.type == pygame.MOUSEBUTTONDOWN:
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


# ─── VIGNETTE ────────────────────────────────────────────────────────────────

_vignette_cache = {}
_vignette_overlay = None


def _get_vignette(width, height):
    key = (width, height)
    if key not in _vignette_cache:
        surf = pygame.Surface((width, height), pygame.SRCALPHA)
        try:
            import numpy as np

            arr = pygame.surfarray.pixels_alpha(surf)
            cx, cy = width // 2, height // 2
            max_dist = math.sqrt(cx**2 + cy**2)
            y_grid, x_grid = np.ogrid[:height, :width]
            dist = np.sqrt((x_grid - cx) ** 2 + (y_grid - cy) ** 2)
            arr[:] = np.clip(255 * (dist / max_dist) ** 1.8, 0, 255).astype(np.uint8).T
            del arr
        except Exception:
            surf.fill((0, 0, 0, 180))
        _vignette_cache[key] = surf
    return _vignette_cache[key]


def draw_vignette(screen, intensity=1.0):
    global _vignette_overlay
    if intensity <= 0.01:
        return
    vignette = _get_vignette(*screen.get_size())
    if _vignette_overlay is None or _vignette_overlay.get_size() != screen.get_size():
        _vignette_overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    _vignette_overlay.fill((0, 0, 0))
    _vignette_overlay.blit(vignette, (0, 0))
    _vignette_overlay.set_alpha(min(255, int(130 * intensity)))
    screen.blit(_vignette_overlay, (0, 0))


# ─── CHASE PULSE ─────────────────────────────────────────────────────────────

_chase_pulse_alpha = 0.0
_chase_pulse_timer = 0.0
_chase_glow_cache = {}
_chase_glow_overlay = None


def _get_chase_glow(width, height):
    key = (width, height)
    if key not in _chase_glow_cache:
        surf = pygame.Surface((width, height), pygame.SRCALPHA)
        surf.fill((160, 0, 0, 255))
        try:
            import numpy as np

            arr = pygame.surfarray.pixels_alpha(surf)
            cx, cy = width // 2, height // 2
            max_dist = math.sqrt(cx**2 + cy**2)
            y_grid, x_grid = np.ogrid[:height, :width]
            dist = np.sqrt((x_grid - cx) ** 2 + (y_grid - cy) ** 2)
            t = np.clip(dist / max_dist, 0, 1)
            arr[:] = np.clip(255 * t**3, 0, 255).astype(np.uint8).T
            del arr
        except Exception:
            pass
        _chase_glow_cache[key] = surf
    return _chase_glow_cache[key]


def draw_chase_pulse(screen, chase_timer, chase_active, dt):
    global _chase_pulse_alpha, _chase_pulse_timer, _chase_glow_overlay

    target = 1.0 if chase_active else 0.0
    rate = 4.0 if chase_active else 1.2
    _chase_pulse_alpha += (target - _chase_pulse_alpha) * min(1.0, rate * dt)

    if _chase_pulse_alpha < 0.001:
        _chase_pulse_alpha = 0.0
        _chase_pulse_timer = 0.0
        return

    _chase_pulse_timer += dt

    glow = _get_chase_glow(*screen.get_size())
    if _chase_glow_overlay is None or _chase_glow_overlay.get_size() != screen.get_size():
        _chase_glow_overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    _chase_glow_overlay.fill((0, 0, 0, 0))
    _chase_glow_overlay.blit(glow, (0, 0))

    pulse = max(0.3, abs(math.sin(_chase_pulse_timer * 3.0)))
    _chase_glow_overlay.set_alpha(int(pulse * 80 * _chase_pulse_alpha))
    screen.blit(_chase_glow_overlay, (0, 0))


# ─── FROST ───────────────────────────────────────────────────────────────────

_frost_cache = {}


def _get_frost_surface(width, height):
    key = (width, height)
    if key not in _frost_cache:
        surf = pygame.Surface((width, height), pygame.SRCALPHA)
        surf.fill((160, 200, 255, 255))
        try:
            import numpy as np

            arr = pygame.surfarray.pixels_alpha(surf)
            cx, cy = width // 2, height // 2
            max_dist = math.sqrt(cx**2 + cy**2)
            y_grid, x_grid = np.ogrid[:height, :width]
            dist = np.sqrt((x_grid - cx) ** 2 + (y_grid - cy) ** 2)
            arr[:] = np.clip(255 * (dist / max_dist) ** 3, 0, 255).astype(np.uint8).T
            del arr
        except Exception:
            pass
        _frost_cache[key] = surf
    return _frost_cache[key]


def draw_frost_overlay(screen, cold_value, freeze_enabled):
    if not freeze_enabled or cold_value <= 20:
        return
    intensity = min(1.0, (cold_value - 20) / 60.0)
    surf = _get_frost_surface(*screen.get_size())
    surf.set_alpha(int(120 * intensity))
    screen.blit(surf, (0, 0))


# ─── FILM GRAIN ──────────────────────────────────────────────────────────────

_grain_cache = {}


def _get_grain(width, height):
    key = (width, height)
    if key not in _grain_cache:
        surf = pygame.Surface((width, height), pygame.SRCALPHA)
        count = max(800, (width * height) // 250)
        for _ in range(count):
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)
            a = random.randint(0, 25)
            surf.set_at((x, y), (255, 255, 255, a))
        _grain_cache[key] = surf
    return _grain_cache[key]


def draw_film_grain(screen, intensity=0.15):
    if intensity <= 0:
        return
    grain = _get_grain(*screen.get_size())
    grain.set_alpha(int(intensity * 255))
    screen.blit(grain, (0, 0))


def run_guide_screen(screen, clock):
    font = pygame.font.SysFont(None, 30)
    header_font = pygame.font.SysFont(None, 44)
    title_font = pygame.font.SysFont(None, 34)
    prompt_font = pygame.font.SysFont(None, 28)

    sections = [
        (
            "Управление",
            [
                "Передвижение - WASD",
                "Взаимодействие - ENTER",
                "Выход - ESC",
            ],
        ),
        (
            "Способности монстра",
            [
                "- Обоняние - периодически чувствует запах игрока вблизи",
                "- Слух - слышит переключение рычага, закидывание угля в печь, бросок камня",
                "- Зрение - видит игрока, если между ним и монстром нет стены",
                "- Клонирование - добавляются новые монстры",
            ],
        ),
        (
            "Предметы",
            [
                "- Уголь - используется для печи, один из ключевых предметов, можно перетаскивать",
                "- Рычаг - один из ключевых предметов, при активации издает звук",
                "- Свеча - помогает видеть в темных участках карты, можно перетаскивать",
                "- Камень - помогает отвлекать монстров звуком броска, можно перетаскивать",
                "- Яблоко - восстанавливает половину голода",
            ],
        ),
        (
            "Прочее",
            [
                "- Темнота - появляется случайным образом на карте и ограничивает видимость",
                "- Замерзание - на некоторых уровнях игрок в темноте начинает замерзать, если не выйти из темноты или не воспользоваться свечой, то игрок умрет",
                "- Голод - на некоторых уровнях игрок испытывает голод, если вовремя не съесть яблоко, то игрок умрет",
            ],
        ),
    ]

    prompt_surface = prompt_font.render("Нажмите ESC или Enter, чтобы вернуться", True, INTRO_TEXT)

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    screen = toggle_fullscreen()
                    continue
                if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER):
                    return "menu"

        screen = pygame.display.get_surface() or screen
        screen.fill((0, 0, 0))
        width, height = screen.get_size()

        header_surface = header_font.render("Гайд", True, INTRO_TEXT)
        header_rect = header_surface.get_rect(midtop=(width // 2, 24))
        screen.blit(header_surface, header_rect)

        top = header_rect.bottom + 18
        bottom = height - prompt_surface.get_height() - 28
        available_height = max(0, bottom - top)
        section_gap = 12
        header_gap = 10
        body_line_height = font.get_linesize() + 4
        title_line_height = title_font.get_linesize() + 4

        content_height = 0
        for section_title, body_lines in sections:
            content_height += title_line_height + header_gap
            content_height += len(body_lines) * body_line_height
            content_height += section_gap
        content_height = max(0, content_height - section_gap)

        y = top + max(0, (available_height - content_height) // 2)
        for section_title, body_lines in sections:
            title_surface = title_font.render(section_title, True, MENU_ACCENT)
            screen.blit(title_surface, (64, y))
            y += title_line_height
            y += header_gap
            for line in body_lines:
                text_surface = font.render(line, True, INTRO_TEXT)
                screen.blit(text_surface, (84, y))
                y += body_line_height
            y += section_gap

        screen.blit(prompt_surface, prompt_surface.get_rect(midbottom=(width // 2, height - 20)))
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
                if event.key == pygame.K_UP or event.key == pygame.K_w:
                    selected_button = (selected_button - 1) % 3
                if event.key == pygame.K_DOWN or event.key == pygame.K_s:
                    selected_button = (selected_button + 1) % 3
                if event.key == pygame.K_RETURN:
                    if selected_button == 0:
                        return selected_level
                    if selected_button == 1:
                        guide_result = run_guide_screen(screen, clock)
                        if guide_result == "quit":
                            return None
                    else:
                        return None

        screen = pygame.display.get_surface() or screen
        screen.fill(MENU_BG)
        width, height = screen.get_size()

        title = title_font.render("Abyss Walker", True, MENU_TEXT)
        title_rect = title.get_rect(center=(width // 2, height // 4))
        screen.blit(title, title_rect)

        level_label = label_font.render("Уровень", True, MENU_DIM)
        level_label_rect = level_label.get_rect(center=(width // 2, height // 2 - 80))
        screen.blit(level_label, level_label_rect)

        level_text = title_font.render(str(selected_level), True, MENU_TEXT)
        level_rect = level_text.get_rect(center=(width // 2, height // 2 - 10))
        screen.blit(level_text, level_rect)

        left_arrow = label_font.render("<", True, MENU_ACCENT)
        right_arrow = label_font.render(">", True, MENU_ACCENT)
        screen.blit(left_arrow, left_arrow.get_rect(center=(width // 2 - 90, height // 2 - 10)))
        screen.blit(right_arrow, right_arrow.get_rect(center=(width // 2 + 90, height // 2 - 10)))

        buttons = [("Начать", 0), ("Гайд", 1), ("Выход", 2)]
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


def draw_cold_bar(screen, cold_value):
    bar_width = 220
    bar_height = 16
    x = 16
    y = 16
    pygame.draw.rect(screen, (30, 30, 30), (x, y, bar_width, bar_height))
    fill_width = int(bar_width * (cold_value / 100.0))
    pygame.draw.rect(screen, (80, 180, 255), (x, y, fill_width, bar_height))
    pygame.draw.rect(screen, (230, 230, 230), (x, y, bar_width, bar_height), 1)


def draw_hunger_bar(screen, hunger_value):
    bar_width = 220
    bar_height = 16
    x = 16
    y = 38
    pygame.draw.rect(screen, (30, 30, 30), (x, y, bar_width, bar_height))
    fill_width = int(bar_width * (hunger_value / 100.0))
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
        screen_pos = (int(candle_center[0] - camera.x), int(candle_center[1] - camera.y))
        pygame.draw.circle(overlay, (0, 0, 0, CANDLE_LIGHT_ALPHA), screen_pos, candle_radius)

    screen.blit(overlay, (0, 0))
