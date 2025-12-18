from __future__ import annotations
import pygame as pg
from typing import override

from .entity import Entity
from src.sprites import Animation
from src.utils import GameSettings
from src.core import GameManager


class ShopNPC(Entity):
    """Simple NPC that opens a shop overlay when interacted with."""

    def __init__(self, x: float, y: float, game_manager: GameManager, items: list[dict[str, object]]) -> None:
        super().__init__(x, y, game_manager)
        # 変化をつけるため専用スプライトに差し替え
        self.animation = Animation(
            "character/ow5.png", ["down", "left", "right", "up"], 4,
            (GameSettings.TILE_SIZE, GameSettings.TILE_SIZE)
        )
        self.animation.update_pos(self.position)
        self.animation.switch("down")
        self.items = items

    def interaction_rect(self) -> pg.Rect:
        """Slightly inflated rect to make interaction easier."""
        rect = self.animation.rect.copy()
        rect.inflate_ip(GameSettings.TILE_SIZE // 4, GameSettings.TILE_SIZE // 4)
        return rect

    @classmethod
    @override
    def from_dict(cls, data: dict[str, object], game_manager: GameManager) -> "ShopNPC":
        items = data.get("items", [])
        return cls(
            float(data["x"]) * GameSettings.TILE_SIZE,
            float(data["y"]) * GameSettings.TILE_SIZE,
            game_manager,
            items,
        )

    @override
    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base["items"] = list(self.items)
        base["type"] = "shop_npc"
        return base
