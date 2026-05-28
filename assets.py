import io
import importlib

import pygame

from settings import SCREEN_HEIGHT, SCREEN_WIDTH


def load_svg_surface(path, size):
    try:
        cairosvg = importlib.import_module("cairosvg")
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


def load_sound(path, volume=1.0, speed=1.0):
    sound = pygame.mixer.Sound(str(path))
    if speed == 1.0:
        sound.set_volume(volume)
        return sound
    try:
        import numpy as np

        arr = pygame.sndarray.array(sound)
        if arr is None or arr.size == 0:
            sound.set_volume(volume)
            return sound

        if speed <= 0:
            speed = 1.0

        if abs(speed - round(speed)) < 1e-9 and int(round(speed)) >= 1:
            stride = int(round(speed))
            new_arr = arr[::stride].copy()
        else:
            length = arr.shape[0]
            new_length = max(1, int(length / speed))
            indices = (np.arange(new_length) * speed).astype(np.int64)
            indices = np.clip(indices, 0, length - 1)
            new_arr = arr[indices]

        new_sound = pygame.sndarray.make_sound(new_arr)
        new_sound.set_volume(volume)
        return new_sound
    except Exception:
        sound.set_volume(volume)
        return sound


def tint_surface(surface, tint):
    tinted = surface.copy()
    tinted.fill(tint, special_flags=pygame.BLEND_RGB_MULT)
    return tinted


def soften_alpha_mask(surface, passes):
    for _ in range(passes):
        surface = pygame.transform.smoothscale(
            surface,
            (
                max(1, surface.get_width() // 2),
                max(1, surface.get_height() // 2),
            ),
        )
        surface = pygame.transform.smoothscale(surface, (SCREEN_WIDTH, SCREEN_HEIGHT))
    return surface
