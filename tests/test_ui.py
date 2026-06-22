"""Tests for Effects, ScreenUtils, HUD, and screen classes."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from ui import Effects, HUD, ScreenUtils, SplashScreen, IntroScreen, MessageScreen, NoteScreen, CreditsScreen, GuideScreen, MenuScreen
from settings import SCREEN_WIDTH, SCREEN_HEIGHT


# ─── Effects ─────────────────────────────────────────────────────────────────


class TestEffects:
    def test_draw_vignette_does_not_crash(self):
        fx = Effects()
        screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        fx.draw_vignette(screen, intensity=0.5)
        assert screen is not None

    def test_draw_vignette_zero_intensity_noop(self):
        fx = Effects()
        screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        before = screen.copy()
        fx.draw_vignette(screen, intensity=0.0)
        assert screen.get_at((0, 0)) == before.get_at((0, 0))

    def test_draw_film_grain_does_not_crash(self):
        fx = Effects()
        screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        fx.draw_film_grain(screen, intensity=0.1)
        assert screen is not None

    def test_draw_chase_pulse_does_not_crash(self):
        fx = Effects()
        screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        fx.draw_chase_pulse(screen, True, 0.016)
        fx.draw_chase_pulse(screen, False, 0.016)
        assert screen is not None

    def test_draw_frost_overlay_does_not_crash(self):
        fx = Effects()
        screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        fx.draw_frost_overlay(screen, 50.0, True)
        fx.draw_frost_overlay(screen, 50.0, False)
        assert screen is not None

    def test_draw_dust_does_not_crash(self):
        fx = Effects()
        screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        fx.draw_dust(screen, pygame.Vector2(0, 0), 0.016)
        assert screen is not None

    def test_draw_hunger_distortion_does_not_crash(self):
        fx = Effects()
        screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        fx.draw_hunger_distortion(screen, 50.0, 0.016)
        assert screen is not None

    def test_caches_vignette(self):
        fx = Effects()
        assert len(fx.vignette_cache) == 0
        fx.draw_vignette(pygame.Surface((100, 80)), 1.0)
        assert len(fx.vignette_cache) == 1

    def test_caches_grain(self):
        fx = Effects()
        assert len(fx.grain_cache) == 0
        fx.draw_film_grain(pygame.Surface((50, 50)), 0.1)
        assert len(fx.grain_cache) == 1


# ─── ScreenUtils ─────────────────────────────────────────────────────────────


class TestScreenUtils:
    def test_toggle_fullscreen_returns_surface(self):
        result = ScreenUtils.toggle_fullscreen()
        assert result is not None

    def test_toggle_fullscreen_toggle(self):
        ScreenUtils.toggle_fullscreen()
        result = ScreenUtils.toggle_fullscreen()
        assert result is not None


# ─── HUD ─────────────────────────────────────────────────────────────────────


class TestHUD:
    def test_draw_cold_bar_does_not_crash(self):
        screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        HUD.draw_cold_bar(screen, 50.0)

    def test_draw_hunger_bar_does_not_crash(self):
        screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        HUD.draw_hunger_bar(screen, 50.0)

    def test_draw_objectives_does_not_crash(self):
        screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        font = pygame.font.Font(None, 20)
        HUD.draw_objectives(screen, font, 1, 3, 0, 2)


# ─── Screen classes ──────────────────────────────────────────────────────────


class TestSplashScreen:
    def test_init(self):
        s = SplashScreen()
        assert s is not None


class TestIntroScreen:
    def test_init(self):
        s = IntroScreen({}, {}, 1)
        assert s is not None


class TestMessageScreen:
    def test_init(self):
        s = MessageScreen()
        assert s is not None


class TestNoteScreen:
    def test_init(self):
        s = NoteScreen()
        assert s is not None


class TestCreditsScreen:
    def test_init(self):
        s = CreditsScreen()
        assert s is not None


class TestGuideScreen:
    def test_init(self):
        s = GuideScreen()
        assert s is not None


class TestMenuScreen:
    def test_init(self):
        s = MenuScreen()
        assert s is not None
