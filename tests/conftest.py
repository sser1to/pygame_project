import os
import random
import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


@pytest.fixture(autouse=True)
def deterministic_random(monkeypatch):
    """Replace world.random with a deterministic substitute for tests."""
    import world as world_module

    def fixed_random(*args, **kwargs):
        return random.Random(0)

    monkeypatch.setattr(world_module, "random", type("R", (), {"Random": fixed_random}))
    yield


@pytest.fixture
def small_grid():
    from world import Grid

    data = [
        [2, 2, 2, 2, 2],
        [2, 1, 1, 1, 2],
        [2, 1, 3, 1, 2],
        [2, 1, 1, 1, 2],
        [2, 2, 2, 2, 2],
    ]
    return Grid(None, data=data)
