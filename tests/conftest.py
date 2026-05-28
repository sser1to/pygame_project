import os
import random
import pytest

# ensure headless SDL for pygame if any tests import it
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


@pytest.fixture(autouse=True)
def deterministic_random(monkeypatch):
    """Replace world.random.Random with a deterministic constructor for tests."""
    import world

    def fixed_random(*args, **kwargs):
        return random.Random(0)

    monkeypatch.setattr(world, "random", type("R", (), {"Random": fixed_random}))
    yield


@pytest.fixture
def small_map():
    # 5x5 map: 0=empty/unused, 1=floor, 2=wall, 3=spawn
    grid = [
        [2, 2, 2, 2, 2],
        [2, 1, 1, 1, 2],
        [2, 1, 3, 1, 2],
        [2, 1, 1, 1, 2],
        [2, 2, 2, 2, 2],
    ]
    spawn = (2, 2)
    return grid, spawn
