import pygame as pg
from typing import Protocol

class UIComponent(Protocol):
    def update(self, dt: float) -> None: ...
    def draw(self, screen: pg.Surface) -> None: ...

MonsterInfoType = UIComponent
ItemInfoType = UIComponent