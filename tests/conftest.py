"""Pytest fixtures and test helpers."""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from settings import SCREEN_HEIGHT, SCREEN_WIDTH, TILE_FLOOR, TILE_SPAWN, TILE_WALL


@pytest.fixture(scope="session", autouse=True)
def pygame_init():
    """Initialise pygame display and font module once for the whole test session."""
    pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.font.init()
    yield


@pytest.fixture
def small_grid():
    """5x5 grid with a 3x3 walkable room surrounded by walls and a spawn at (2,2)."""
    from world import Grid

    data = [
        [TILE_WALL, TILE_WALL, TILE_WALL, TILE_WALL, TILE_WALL],
        [TILE_WALL, TILE_FLOOR, TILE_FLOOR, TILE_FLOOR, TILE_WALL],
        [TILE_WALL, TILE_FLOOR, TILE_SPAWN, TILE_FLOOR, TILE_WALL],
        [TILE_WALL, TILE_FLOOR, TILE_FLOOR, TILE_FLOOR, TILE_WALL],
        [TILE_WALL, TILE_WALL, TILE_WALL, TILE_WALL, TILE_WALL],
    ]
    return Grid(None, data=data)


@pytest.fixture
def empty_15_grid():
    """15x15 grid with a 13x13 floor area and a spawn tile at (7, 7)."""
    from world import Grid

    data = [[TILE_WALL] * 15 for _ in range(15)]
    for y in range(1, 14):
        for x in range(1, 14):
            data[y][x] = TILE_FLOOR
    data[7][7] = TILE_SPAWN
    return Grid(None, data=data)
