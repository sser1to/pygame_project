import math
import random

import pygame

from settings import (
    CANDLE_LIGHT_RADIUS,
    CANDLE_LIGHT_ALPHA,
    CANDLE_PULSE_SPEED,
    CANDLE_PULSE_AMOUNT,
    DUST_COUNT,
    DUST_SPEED,
    DUST_MAX_ALPHA,
    DUST_MIN_SIZE,
    DUST_MAX_SIZE,
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
    MENU_LOCKED,
    MENU_LOCKED_DIM,
    MENU_LOCKED_TEXT,
    MENU_TEXT,
    PLAYER_LIGHT_ALPHA,
    SPOTLIGHT_ALPHA,
    SPOTLIGHT_FEATHER,
    SPOTLIGHT_RADIUS,
    SPOTLIGHT_PULSE_SPEED,
    SPOTLIGHT_PULSE_AMOUNT,
    TILE_SIZE,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)


class ScreenUtils:
    @staticmethod
    def toggle_fullscreen():
        current = pygame.display.get_surface()
        if current is None:
            return pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        is_fullscreen = bool(current.get_flags() & pygame.FULLSCREEN)
        if is_fullscreen:
            return pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        return pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)


class Effects:
    def __init__(self):
        self.vignette_cache = {}
        self.vignette_overlay = None
        self.chase_pulse_alpha = 0.0
        self.chase_pulse_timer = 0.0
        self.chase_glow_cache = {}
        self.chase_glow_overlay = None
        self.frost_cache = {}
        self.dust_particles = None
        self.dust_overlay = None
        self.grain_cache = {}
        self.hunger_distortion_time = 0.0

    def draw_vignette(self, screen, intensity=1.0):
        if intensity <= 0.01:
            return
        vignette = self._get_vignette(*screen.get_size())
        if self.vignette_overlay is None or self.vignette_overlay.get_size() != screen.get_size():
            self.vignette_overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        self.vignette_overlay.fill((0, 0, 0))
        self.vignette_overlay.blit(vignette, (0, 0))
        self.vignette_overlay.set_alpha(min(255, int(130 * intensity)))
        screen.blit(self.vignette_overlay, (0, 0))

    def _get_vignette(self, width, height):
        key = (width, height)
        if key not in self.vignette_cache:
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
            self.vignette_cache[key] = surf
        return self.vignette_cache[key]

    def draw_chase_pulse(self, screen, chase_active, dt):
        target = 1.0 if chase_active else 0.0
        rate = 4.0 if chase_active else 1.2
        self.chase_pulse_alpha += (target - self.chase_pulse_alpha) * min(1.0, rate * dt)

        if self.chase_pulse_alpha < 0.001:
            self.chase_pulse_alpha = 0.0
            self.chase_pulse_timer = 0.0
            return

        self.chase_pulse_timer += dt

        glow = self._get_chase_glow(*screen.get_size())
        if self.chase_glow_overlay is None or self.chase_glow_overlay.get_size() != screen.get_size():
            self.chase_glow_overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        self.chase_glow_overlay.fill((0, 0, 0, 0))
        self.chase_glow_overlay.blit(glow, (0, 0))

        pulse = max(0.3, abs(math.sin(self.chase_pulse_timer * 3.0)))
        self.chase_glow_overlay.set_alpha(int(pulse * 80 * self.chase_pulse_alpha))
        screen.blit(self.chase_glow_overlay, (0, 0))

    def _get_chase_glow(self, width, height):
        key = (width, height)
        if key not in self.chase_glow_cache:
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
            self.chase_glow_cache[key] = surf
        return self.chase_glow_cache[key]

    def draw_frost_overlay(self, screen, cold_value, freeze_enabled):
        if not freeze_enabled or cold_value <= 20:
            return
        intensity = min(1.0, (cold_value - 20) / 60.0)
        surf = self._get_frost_surface(*screen.get_size())
        surf.set_alpha(int(120 * intensity))
        screen.blit(surf, (0, 0))

    def _get_frost_surface(self, width, height):
        key = (width, height)
        if key not in self.frost_cache:
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
            self.frost_cache[key] = surf
        return self.frost_cache[key]

    def draw_dust(self, screen, camera, dt):
        width, height = SCREEN_WIDTH, SCREEN_HEIGHT
        cam_x, cam_y = camera.x, camera.y

        if self.dust_particles is None or len(self.dust_particles) != DUST_COUNT:
            self.dust_particles = []
            for _ in range(DUST_COUNT):
                self.dust_particles.append([
                    random.uniform(cam_x, cam_x + width),
                    random.uniform(cam_y, cam_y + height),
                    random.uniform(-DUST_SPEED, DUST_SPEED),
                    random.uniform(-DUST_SPEED, DUST_SPEED),
                    random.randint(DUST_MIN_SIZE, DUST_MAX_SIZE),
                    random.randint(10, DUST_MAX_ALPHA),
                ])

        if self.dust_overlay is None or self.dust_overlay.get_size() != (width, height):
            self.dust_overlay = pygame.Surface((width, height), pygame.SRCALPHA)

        self.dust_overlay.fill((0, 0, 0, 0))

        margin = 200
        for p in self.dust_particles:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            if (p[0] < cam_x - margin or p[0] > cam_x + width + margin or
                p[1] < cam_y - margin or p[1] > cam_y + height + margin):
                p[0] = random.uniform(cam_x, cam_x + width)
                p[1] = random.uniform(cam_y, cam_y + height)
            pygame.draw.circle(
                self.dust_overlay, (255, 255, 255, p[5]),
                (int(p[0] - cam_x), int(p[1] - cam_y)), p[4]
            )

        screen.blit(self.dust_overlay, (0, 0))

    def draw_film_grain(self, screen, intensity=0.15):
        if intensity <= 0:
            return
        grain = self._get_grain(*screen.get_size())
        grain.set_alpha(int(intensity * 255))
        screen.blit(grain, (0, 0))

    def _get_grain(self, width, height):
        key = (width, height)
        if key not in self.grain_cache:
            surf = pygame.Surface((width, height), pygame.SRCALPHA)
            count = max(800, (width * height) // 250)
            for _ in range(count):
                x = random.randint(0, width - 1)
                y = random.randint(0, height - 1)
                a = random.randint(0, 25)
                surf.set_at((x, y), (255, 255, 255, a))
            self.grain_cache[key] = surf
        return self.grain_cache[key]

    def draw_hunger_distortion(self, screen, hunger_value, dt):
        if hunger_value <= 50.0:
            self.hunger_distortion_time = 0.0
            return

        self.hunger_distortion_time += dt
        intensity = (hunger_value - 50.0) / 50.0
        width, height = screen.get_size()
        snapshot = screen.copy()

        amplitude = 6.0 * intensity
        freq = 0.04
        speed = 2.5
        step = 3

        for y in range(0, height, step):
            offset = int(math.sin(y * freq + self.hunger_distortion_time * speed) * amplitude)
            if offset > 0:
                screen.blit(snapshot, (offset, y), (0, y, width - offset, step))
            elif offset < 0:
                screen.blit(snapshot, (0, y), (-offset, y, width + offset, step))


class HUD:
    @staticmethod
    def draw_cold_bar(screen, cold_value):
        bar_width = 220
        bar_height = 16
        x = 16
        y = 16
        pygame.draw.rect(screen, (30, 30, 30), (x, y, bar_width, bar_height))
        fill_width = int(bar_width * (cold_value / 100.0))
        pygame.draw.rect(screen, (80, 180, 255), (x, y, fill_width, bar_height))
        pygame.draw.rect(screen, (230, 230, 230), (x, y, bar_width, bar_height), 1)

    @staticmethod
    def draw_hunger_bar(screen, hunger_value):
        bar_width = 220
        bar_height = 16
        x = 16
        y = 38
        pygame.draw.rect(screen, (30, 30, 30), (x, y, bar_width, bar_height))
        fill_width = int(bar_width * (hunger_value / 100.0))
        pygame.draw.rect(screen, (255, 160, 80), (x, y, fill_width, bar_height))
        pygame.draw.rect(screen, (230, 230, 230), (x, y, bar_width, bar_height), 1)

    @staticmethod
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


class SplashScreen:
    @staticmethod
    def run(screen, clock):
        big_font = pygame.font.SysFont(None, 120)
        text_surface = big_font.render("Project Abyss", True, (255, 255, 255))
        text_rect = text_surface.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
        elapsed = 0.0
        duration = 5.0

        while elapsed < duration:
            dt = clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_F11:
                        screen = ScreenUtils.toggle_fullscreen()
                        continue
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE, pygame.K_SPACE):
                        return "ok"

            elapsed += dt
            alpha = 0
            if elapsed < 1.5:
                alpha = int((elapsed / 1.5) * 255)
            elif elapsed < 3.5:
                alpha = 255
            else:
                t = (elapsed - 3.5) / 1.5
                alpha = int(max(0, 255 * (1 - t)))

            screen.fill((0, 0, 0))
            text_surface.set_alpha(alpha)
            screen.blit(text_surface, text_rect)
            pygame.display.flip()
        return "ok"


class IntroScreen:
    def __init__(self, abilities_config, debuffs_config, level_number):
        self.lines = self._build_lines(abilities_config, debuffs_config)
        self.level_number = level_number
        self.font = pygame.font.SysFont(None, 36)
        self.header_font = pygame.font.SysFont(None, 44)
        self.prompt_font = pygame.font.SysFont(None, 28)
        self.header_surface = self.header_font.render(f"Уровень {level_number}", True, INTRO_TEXT)
        self.prompt_surface = self.prompt_font.render("Нажмите Enter, чтобы продолжить", True, INTRO_TEXT)
        self.line_height = self.font.get_linesize() + 6
        self.line_widths = []
        self.line_lengths = []
        self.total_chars = 0
        self._measure_lines()

    @staticmethod
    def _build_lines(abilities_config, debuffs_config):
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

    def _measure_lines(self):
        for segments in self.lines:
            if not segments:
                self.line_widths.append(0)
                self.line_lengths.append(0)
                continue
            width = sum(self.font.size(text)[0] for text, _ in segments)
            length = sum(len(text) for text, _ in segments)
            self.line_widths.append(width)
            self.line_lengths.append(length)
            self.total_chars += length

    @staticmethod
    def _draw_typed_line(screen, font, x, y, segments, max_chars):
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

    def run(self, screen, clock):
        if not self.lines or self.total_chars <= 0:
            return "ok"

        visible_chars = 0.0
        typing_done = False

        while True:
            dt = clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_F11:
                        screen = ScreenUtils.toggle_fullscreen()
                        continue
                    if event.key == pygame.K_ESCAPE:
                        return "menu"
                    if typing_done:
                        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                            return "ok"
                    else:
                        visible_chars = float(self.total_chars)
                        typing_done = True
                if event.type == pygame.MOUSEBUTTONDOWN and not typing_done:
                    visible_chars = float(self.total_chars)
                    typing_done = True

            if not typing_done:
                visible_chars = min(float(self.total_chars), visible_chars + INTRO_CHAR_RATE * dt)
                if visible_chars >= self.total_chars:
                    typing_done = True

            screen = pygame.display.get_surface() or screen
            screen.fill(INTRO_BG)
            width, height = screen.get_size()
            block_height = len(self.lines) * self.line_height
            header_rect = self.header_surface.get_rect(midtop=(width // 2, 24))
            prompt_rect = self.prompt_surface.get_rect(midbottom=(width // 2, height - 24))
            top_limit = header_rect.bottom + 20
            bottom_limit = prompt_rect.top - 20
            available_height = max(0, bottom_limit - top_limit)
            start_y = top_limit + max(0, (available_height - block_height) // 2)
            screen.blit(self.header_surface, header_rect)

            remaining = int(visible_chars)
            for index, segments in enumerate(self.lines):
                y = start_y + index * self.line_height
                if not segments:
                    continue
                if remaining <= 0:
                    break
                show_chars = min(self.line_lengths[index], remaining)
                x = (width - self.line_widths[index]) // 2
                self._draw_typed_line(screen, self.font, x, y, segments, show_chars)
                remaining -= self.line_lengths[index]

            if typing_done:
                screen.blit(self.prompt_surface, prompt_rect)

            pygame.display.flip()


class MessageScreen:
    @staticmethod
    def run(screen, clock, message, background=None):
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
                    screen = ScreenUtils.toggle_fullscreen()
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


class NoteScreen:
    @staticmethod
    def run(screen, clock, title, text, background=None):
        title_font = pygame.font.SysFont(None, 38)
        text_font = pygame.font.SysFont(None, 26)
        prompt_font = pygame.font.SysFont(None, 24)

        paper_color = (215, 210, 205)
        paper_border = (150, 145, 140)
        title_color = (40, 40, 40)
        text_color = (55, 55, 55)
        prompt_color = (130, 125, 120)

        while True:
            dt = clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_F11:
                        screen = ScreenUtils.toggle_fullscreen()
                        continue
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE, pygame.K_SPACE):
                        return "done"

            screen = pygame.display.get_surface() or screen
            width, height = screen.get_size()

            if background is not None:
                screen.blit(background, (0, 0))
                overlay = pygame.Surface((width, height), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 130))
                screen.blit(overlay, (0, 0))
            else:
                screen.fill((12, 12, 16))

            paper_w = min(640, width - 80)
            paper_h = min(500, height - 80)
            paper_x = (width - paper_w) // 2
            paper_y = (height - paper_h) // 2

            pygame.draw.rect(screen, paper_color, (paper_x, paper_y, paper_w, paper_h), border_radius=6)
            pygame.draw.rect(screen, paper_border, (paper_x, paper_y, paper_w, paper_h), 2, border_radius=6)

            inner_x = paper_x + 30
            inner_w = paper_w - 60

            title_surf = title_font.render(title, True, title_color)
            title_rect = title_surf.get_rect(midtop=(paper_x + paper_w // 2, paper_y + 24))
            screen.blit(title_surf, title_rect)

            line_y = title_rect.bottom + 18
            line_rect = pygame.Rect(inner_x, line_y, inner_w, 1)
            pygame.draw.rect(screen, paper_border, line_rect)

            text_y = line_y + 14
            max_text_height = paper_y + paper_h - 60 - text_y
            available_width = inner_w

            paragraphs = text.split("\n")
            lines = []
            for para in paragraphs:
                if not para.strip():
                    lines.append("")
                    continue
                words = para.split()
                current_line = ""
                for word in words:
                    test_line = (current_line + " " + word).strip()
                    if text_font.size(test_line)[0] <= available_width:
                        current_line = test_line
                    else:
                        if current_line:
                            lines.append(current_line)
                        current_line = word
                if current_line:
                    lines.append(current_line)

            for line in lines:
                if text_y + text_font.get_linesize() > paper_y + paper_h - 30:
                    break
                line_surf = text_font.render(line, True, text_color)
                screen.blit(line_surf, (inner_x, text_y))
                text_y += text_font.get_linesize() + 4

            prompt_surf = prompt_font.render("Нажмите Enter, чтобы закрыть", True, prompt_color)
            prompt_rect = prompt_surf.get_rect(midbottom=(paper_x + paper_w // 2, paper_y + paper_h - 16))
            screen.blit(prompt_surf, prompt_rect)

            pygame.display.flip()


class CreditsScreen:
    @staticmethod
    def run(screen, clock):
        font = pygame.font.SysFont(None, 36)
        lines = [
            "Вы смогли выбраться из злополучного цикла.",
            "",
            "Спасибо за прохождение игры!",
        ]
        full_text = "\n".join(lines)
        total_chars = len(full_text)
        if total_chars <= 0:
            return "done"

        visible_chars = 0.0
        typing_done = False
        hold_timer = 0.0
        hold_duration = 5

        while True:
            dt = clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                    screen = ScreenUtils.toggle_fullscreen()
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

            screen = pygame.display.get_surface() or screen
            screen.fill((0, 0, 0))

            width, height = screen.get_size()
            shown = full_text[:int(visible_chars)]
            rendered_lines = shown.split("\n")

            line_height = font.get_linesize() + 8
            total_text_height = len(lines) * line_height
            start_y = (height - total_text_height) // 2

            for i, line in enumerate(rendered_lines):
                if not line:
                    continue
                surface = font.render(line, True, INTRO_TEXT)
                rect = surface.get_rect(center=(width // 2, start_y + i * line_height))
                screen.blit(surface, rect)

            pygame.display.flip()


class GuideScreen:
    @staticmethod
    def run(screen, clock):
        font = pygame.font.SysFont(None, 24)
        header_font = pygame.font.SysFont(None, 36)
        title_font = pygame.font.SysFont(None, 28)
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
                    "- Записка - раскрывает историю",
                ],
            ),
            (
                "Прочее",
                [
                    "- Темнота - появляется случайным образом на карте и ограничивает видимость",
                    "- Замерзание - на некоторых уровнях игрок в темноте начинает замерзать, если не выйти из темноты или",
                    "не воспользоваться свечой, то игрок умрет",
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
                        screen = ScreenUtils.toggle_fullscreen()
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


class MenuScreen:
    @staticmethod
    def run(screen, clock, initial_level, unlocked_level):
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
                        screen = ScreenUtils.toggle_fullscreen()
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
                            if selected_level <= unlocked_level:
                                return selected_level
                        elif selected_button == 1:
                            guide_result = GuideScreen.run(screen, clock)
                            if guide_result == "quit":
                                return None
                        else:
                            return None

            screen = pygame.display.get_surface() or screen
            screen.fill(MENU_BG)
            width, height = screen.get_size()

            title = title_font.render("Project Abyss", True, MENU_TEXT)
            title_rect = title.get_rect(center=(width // 2, height // 4))
            screen.blit(title, title_rect)

            level_label = label_font.render("Уровень", True, MENU_DIM)
            level_label_rect = level_label.get_rect(center=(width // 2, height // 2 - 80))
            screen.blit(level_label, level_label_rect)

            is_locked = selected_level > unlocked_level
            level_color = MENU_DIM if is_locked else MENU_TEXT
            level_text = title_font.render(str(selected_level), True, level_color)
            level_rect = level_text.get_rect(center=(width // 2, height // 2 - 10))
            screen.blit(level_text, level_rect)

            left_arrow = label_font.render("<", True, MENU_ACCENT)
            right_arrow = label_font.render(">", True, MENU_ACCENT)
            screen.blit(left_arrow, left_arrow.get_rect(center=(width // 2 - 90, height // 2 - 10)))
            screen.blit(right_arrow, right_arrow.get_rect(center=(width // 2 + 90, height // 2 - 10)))

            if is_locked:
                lock_label = pygame.font.SysFont(None, 22).render("Пройдите предыдущий уровень", True, MENU_LOCKED_TEXT)
                lock_rect = lock_label.get_rect(center=(width // 2, height // 2 + 40))
                screen.blit(lock_label, lock_rect)

            buttons = [("Начать", 0), ("Гайд", 1), ("Выход", 2)]
            for label, index in buttons:
                disabled = index == 0 and is_locked
                if is_locked and index == 0:
                    if selected_button == index:
                        text_color = (90, 90, 110)
                        rect_color = MENU_LOCKED
                    else:
                        text_color = MENU_DIM
                        rect_color = MENU_DIM
                else:
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
