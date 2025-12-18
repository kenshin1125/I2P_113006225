from __future__ import annotations
import pygame
from enum import Enum
from dataclasses import dataclass
from typing import override

from .entity import Entity
from src.sprites import Sprite, Animation
from src.core import GameManager
from src.utils import GameSettings, Direction, Position, PositionCamera


class EnemyTrainerClassification(Enum):
    STATIONARY = "stationary"

@dataclass
class IdleMovement:
    def update(self, enemy: "EnemyTrainer", dt: float) -> None:
        return

class EnemyTrainer(Entity):
    classification: EnemyTrainerClassification
    max_tiles: int | None
    _movement: IdleMovement
    warning_sign: Sprite
    detected: bool
    los_direction: Direction
    _assign_idx: int = 0  # 属性割り当て用カウンタ（トレーナーごとにバラけさせる）
    _sprite_idx: int = 0  # 見た目変更用カウンタ

    @override
    def __init__(
        self,
        x: float,
        y: float,
        game_manager: GameManager,
        classification: EnemyTrainerClassification = EnemyTrainerClassification.STATIONARY,
        max_tiles: int | None = 2,
        facing: Direction | None = None,
    ) -> None:
        super().__init__(x, y, game_manager)
        # 見た目を順番に切り替え（ow1〜ow10）
        sprite_num = (EnemyTrainer._sprite_idx % 10) + 1
        EnemyTrainer._sprite_idx += 1
        self.animation = Animation(
            f"character/ow{sprite_num}.png",
            ["down", "left", "right", "up"],
            4,
            (GameSettings.TILE_SIZE, GameSettings.TILE_SIZE)
        )
        self.animation.update_pos(self.position)
        self.classification = classification
        self.max_tiles = max_tiles
        if classification == EnemyTrainerClassification.STATIONARY:
            self._movement = IdleMovement()
            if facing is None:
                raise ValueError("Idle EnemyTrainer requires a 'facing' Direction at instantiation")
            self._set_direction(facing)
        else:
            raise ValueError("Invalid classification")
        self.warning_sign = Sprite("exclamation.png", (GameSettings.TILE_SIZE // 2, GameSettings.TILE_SIZE // 2))
        self.warning_sign.update_pos(Position(x + GameSettings.TILE_SIZE // 4, y - GameSettings.TILE_SIZE // 2))
        self.detected = False
        self.detection_distance = self.max_tiles if self.max_tiles is not None else 3

    @override
    def update(self, dt: float) -> None:
        self._movement.update(self, dt)
        self._has_los_to_player()
        self.warning_sign.update_pos(
            Position(
                self.position.x + GameSettings.TILE_SIZE // 4,
                self.position.y - GameSettings.TILE_SIZE // 2,
            )
        )
        self.animation.update_pos(self.position)

    @override
    def draw(self, screen: pygame.Surface, camera: PositionCamera) -> None:
        super().draw(screen, camera)
        if self.detected:
            self.warning_sign.draw(screen, camera)
        if GameSettings.DRAW_HITBOXES:
            tile = GameSettings.TILE_SIZE
            for tx, ty in self._front_tiles():
                rect = pygame.Rect(tx * tile, ty * tile, tile, tile)
                pygame.draw.rect(screen, (255, 255, 0), camera.transform_rect(rect), 1)

    def _set_direction(self, direction: Direction) -> None:
        self.direction = direction
        if direction == Direction.RIGHT:
            self.animation.switch("right")
        elif direction == Direction.LEFT:
            self.animation.switch("left")
        elif direction == Direction.DOWN:
            self.animation.switch("down")
        else:
            self.animation.switch("up")
        self.los_direction = self.direction

    def _front_tiles(self) -> list[tuple[int, int]]:
        tile = GameSettings.TILE_SIZE
        base_x = int(self.position.x // tile)
        base_y = int(self.position.y // tile)
        tiles: list[tuple[int, int]] = []
        dx, dy = 0, 0
        if self.los_direction == Direction.UP:
            dy = -1
        elif self.los_direction == Direction.DOWN:
            dy = 1
        elif self.los_direction == Direction.LEFT:
            dx = -1
        elif self.los_direction == Direction.RIGHT:
            dx = 1
        dist = self.detection_distance if self.detection_distance else 1
        for i in range(1, dist + 1):
            tiles.append((base_x + dx * i, base_y + dy * i))
        return tiles

    def _has_los_to_player(self) -> None:
        player = self.game_manager.player
        if player is None:
            self.detected = False
            return
        tile = GameSettings.TILE_SIZE
        player_rect = player.animation.rect
        player_tile = (
            int(player_rect.centerx // tile),
            int(player_rect.centery // tile)
        )
        self.detected = False
        for tx, ty in self._front_tiles():
            if player_tile == (tx, ty):
                self.detected = True
                break

    @classmethod
    @override
    def from_dict(cls, data: dict, game_manager: GameManager) -> "EnemyTrainer":
        classification = EnemyTrainerClassification(data.get("classification", "stationary"))
        max_tiles = data.get("max_tiles")
        facing_val = data.get("facing")
        facing: Direction | None = None
        if facing_val is not None:
            if isinstance(facing_val, str):
                facing = Direction[facing_val]
            elif isinstance(facing_val, Direction):
                facing = facing_val
        if facing is None and classification == EnemyTrainerClassification.STATIONARY:
            facing = Direction.DOWN
        trainer = cls(
            data["x"] * GameSettings.TILE_SIZE,
            data["y"] * GameSettings.TILE_SIZE,
            game_manager,
            classification,
            max_tiles,
            facing,
        )
        # モンスター属性が未指定ならトレーナーごとに割り当てる
        if not hasattr(trainer, "monster_data"):
            elements = ["Fire", "Water", "Grass", "Electric", "Normal"]
            idx = cls._assign_idx % len(elements)
            cls._assign_idx += 1
            element = elements[idx]
            trainer.monster_data = {
                "name": f"TrainerMon{idx+1}",
                "hp": 90 + idx * 10,
                "max_hp": 90 + idx * 10,
                "level": 10 + idx * 2,
                "attack": 20 + idx * 2,
                "defense": 10 + idx,
                "element": element,
                "sprite_path": f"menu_sprites/menusprite{idx+1}.png"
            }
        return trainer

    @override
    def to_dict(self) -> dict[str, object]:
        base: dict[str, object] = super().to_dict()
        base["classification"] = self.classification.value
        base["facing"] = self.direction.name
        base["max_tiles"] = self.max_tiles
        return base
