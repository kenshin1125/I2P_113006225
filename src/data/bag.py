import pygame as pg
import json
from src.utils import GameSettings
from src.utils.definition import Monster, Item


class Bag:
    _monsters_data: list[Monster]
    _items_data: list[Item]
    _player_items: list[Item]

    def __init__(self, monsters_data: list[Monster] | None = None, items_data: list[Item] | None = None):
        self._monsters_data = monsters_data if monsters_data else []
        self._items_data = items_data if items_data else []
        self._player_items: list[Item] = []

    def update(self, dt: float):
        pass

    def draw(self, screen: pg.Surface):
        pass

    def to_dict(self) -> dict[str, object]:
        return {
            "monsters": list(self._monsters_data),
            "items": list(self._items_data),
            "player_items": list(self._player_items)
        }

    @property
    def monsters(self) -> list[Monster]:
        return self._monsters_data

    @property
    def items(self) -> list[Item]:
        return self._items_data

    @property
    def player_items(self) -> list[Item]:
        return self._player_items
    
    def add_monster(self, monster: Monster) -> None:
        self._monsters_data.append(monster)

    # Convenience helpers for shop interactions
    def add_item(self, name: str, count: int, sprite_path: str) -> None:
        """Add item count to bag; merges with existing entry if names match."""
        for item in self._items_data:
            if item["name"] == name:
                item["count"] += count
                return
        self._items_data.append({"name": name, "count": count, "sprite_path": sprite_path})

    def add_player_item(self, name: str, count: int, sprite_path: str) -> None:
        for item in self._player_items:
            if item["name"] == name:
                item["count"] += count
                return
        self._player_items.append({"name": name, "count": count, "sprite_path": sprite_path})

    def get_item_count(self, name: str) -> int:
        for item in self._items_data:
            if item["name"] == name:
                return item["count"]
        return 0

    def remove_item(self, name: str, count: int) -> bool:
        """Try to remove count of item; returns True if successful."""
        for item in list(self._items_data):
            if item["name"] == name:
                if item["count"] < count:
                    return False
                item["count"] -= count
                if item["count"] <= 0:
                    self._items_data.remove(item)
                return True
        return False

    def remove_player_item(self, name: str, count: int) -> bool:
        for item in list(self._player_items):
            if item["name"] == name:
                if item["count"] < count:
                    return False
                item["count"] -= count
                if item["count"] <= 0:
                    self._player_items.remove(item)
                return True
        return False

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "Bag":
        monsters = data.get("monsters") or []
        items = data.get("items") or []
        player_items = data.get("player_items") or []
        bag = cls(monsters, items)
        bag._player_items = player_items
        return bag
