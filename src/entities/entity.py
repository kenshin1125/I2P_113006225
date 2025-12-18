from __future__ import annotations
import pygame as pg
from typing import override
from src.sprites import Animation
from src.utils import Position, PositionCamera, Direction, GameSettings
from src.core import GameManager


class Entity:
    animation: Animation
    direction: Direction
    position: Position
    game_manager: GameManager
    
    def __init__(self, x: float, y: float, game_manager: GameManager) -> None:
        # Sprite is only for debug, need to change into animations
        self.animation = Animation(
            "character/ow1.png", ["down", "left", "right", "up"], 4,
            (GameSettings.TILE_SIZE, GameSettings.TILE_SIZE)
        )
        
        self.position = Position(x, y)
        self.direction = Direction.DOWN
        self.animation.update_pos(self.position)
        self.game_manager = game_manager

    def update(self, dt: float) -> None:
        self.animation.update_pos(self.position)
        self.animation.update(dt)
        
    def draw(self, screen: pg.Surface, camera: PositionCamera) -> None:
        self.animation.draw(screen, camera)
        if GameSettings.DRAW_HITBOXES:
            self.animation.draw_hitbox(screen, camera)
        
    @staticmethod
    def _snap_to_grid(value: float) -> int:
        return round(value / GameSettings.TILE_SIZE) * GameSettings.TILE_SIZE
    
    @property
    def camera(self) -> PositionCamera:
        '''
        [TODO HACKATHON 3]
        Implement the correct algorithm of player camera
        '''
        # Center the player and clamp camera to map bounds
        camera_x = int(self.position.x - GameSettings.SCREEN_WIDTH // 2)
        camera_y = int(self.position.y - GameSettings.SCREEN_HEIGHT // 2)
        current_map = self.game_manager.current_map
        max_x = max(0, current_map.pixel_width - GameSettings.SCREEN_WIDTH)
        max_y = max(0, current_map.pixel_height - GameSettings.SCREEN_HEIGHT)
        camera_x = max(0, min(camera_x, max_x))
        camera_y = max(0, min(camera_y, max_y))
        return PositionCamera(camera_x, camera_y)
        
    def to_dict(self) -> dict[str, object]:
        return {
            "x": self.position.x / GameSettings.TILE_SIZE,
            "y": self.position.y / GameSettings.TILE_SIZE,
        }
        
    @classmethod
    def from_dict(cls, data: dict[str, float | int], game_manager: GameManager) -> Entity:
        x = float(data["x"])
        y = float(data["y"])
        return cls(x * GameSettings.TILE_SIZE, y * GameSettings.TILE_SIZE, game_manager)
        
