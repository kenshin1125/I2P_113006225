import pygame as pg
from src.utils import load_img, load_font, load_sound

class ResourceManager:
    """
    Make sure you are not loading the resource twice
    If the resource is already loaded, you can use the loaded image instead of loading it again.
    """
    def __init__(self) -> None:
        self._images: dict[str, pg.Surface] = {}
        self._sounds: dict[str, pg.mixer.Sound] = {}
        self._fonts: dict[tuple[str, int], pg.font.Font] = {}

    def get_image(self, path: str) -> pg.Surface:
        if path not in self._images:
            self._images[path] = load_img(path)
        return self._images[path]

    def get_sound(self, path: str) -> pg.mixer.Sound:
        if path not in self._sounds:
            self._sounds[path] = load_sound(path)
        return self._sounds[path]

    def get_font(self, path: str, size: int) -> pg.font.Font:
        key = (path, size)
        if key not in self._fonts:
            self._fonts[key] = load_font(path, size)
        return self._fonts[key]

    def clear(self) -> None:
        """Clear all cached assets (useful when switching levels)."""
        self._images.clear()
        self._sounds.clear()
        self._fonts.clear()
