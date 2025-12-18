from __future__ import annotations
import pygame as pg

class Scene:
    def __init__(self) -> None:
        ...

    def enter(self) -> None:
        ...

    def exit(self) -> None:
        ...

    def update(self, dt: float) -> None:
        ...

    def draw(self, screen: pg.Surface) -> None:
        ...