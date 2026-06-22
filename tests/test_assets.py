"""Tests for AssetManager — loading, tinting, and alpha mask softening."""

import pygame

from assets import AssetManager
from settings import SCREEN_HEIGHT, SCREEN_WIDTH


class TestTintSurface:
    def test_tint_preserves_alpha(self):
        surf = pygame.Surface((8, 8), pygame.SRCALPHA)
        surf.fill((100, 150, 200, 128))
        tinted = AssetManager.tint_surface(surf, (200, 100, 50))
        assert tinted.get_at((0, 0)).a == 128

    def test_tint_multiplies_rgb(self):
        surf = pygame.Surface((4, 4), pygame.SRCALPHA)
        surf.fill((128, 128, 128, 255))
        tinted = AssetManager.tint_surface(surf, (200, 100, 50))
        r, g, b, _ = tinted.get_at((0, 0))
        assert r < 200
        assert g < 100

    def test_tint_returns_new_surface(self):
        surf = pygame.Surface((4, 4))
        tinted = AssetManager.tint_surface(surf, (255, 0, 0))
        assert tinted is not surf


class TestSoftenAlphaMask:
    def test_returns_screen_size(self):
        surf = pygame.Surface((200, 150), pygame.SRCALPHA)
        result = AssetManager.soften_alpha_mask(surf, passes=1)
        assert result.get_size() == (SCREEN_WIDTH, SCREEN_HEIGHT)

    def test_zero_passes_still_scales(self):
        surf = pygame.Surface((200, 150), pygame.SRCALPHA)
        result = AssetManager.soften_alpha_mask(surf, passes=0)
        assert result.get_width() == SCREEN_WIDTH

    def test_preserves_alpha_channel(self):
        surf = pygame.Surface((100, 80), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 200))
        result = AssetManager.soften_alpha_mask(surf, passes=2)
        assert result.get_flags() & pygame.SRCALPHA


class TestLoadSvgSurface:
    def test_fallback_placeholder(self, tmp_path):
        missing = tmp_path / "nonexistent.svg"
        surf = AssetManager.load_svg_surface(missing, (32, 32))
        assert surf.get_size() == (32, 32)
        assert surf.get_flags() & pygame.SRCALPHA

    def test_fallback_fills_color(self, tmp_path):
        missing = tmp_path / "missing.svg"
        surf = AssetManager.load_svg_surface(missing, (16, 16))
        color = surf.get_at((2, 2))
        assert color.r == 200 and color.g == 50 and color.b == 200
