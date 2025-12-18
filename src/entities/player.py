from __future__ import annotations
import pygame as pg
from .entity import Entity
from src.core.services import input_manager
from src.utils import Position, PositionCamera, GameSettings, Logger, Direction
from src.core import GameManager
import math
from typing import override

class Player(Entity):
    speed: float = 4.0 * GameSettings.TILE_SIZE
    game_manager: GameManager
    player_name: str = "Player"

    def __init__(self, x: float, y: float, game_manager: GameManager) -> None:
        super().__init__(x, y, game_manager)
        self.teleport_cooldown = 0.0
        self.is_moving = False
        self.speed_multiplier = 1.0
        self.speed_boost_timer = 0.0

    @override
    def update(self, dt: float) -> None:
        if self.teleport_cooldown > 0:
            self.teleport_cooldown = max(0.0, self.teleport_cooldown - dt)
        if self.speed_boost_timer > 0:
            self.speed_boost_timer = max(0.0, self.speed_boost_timer - dt)
            if self.speed_boost_timer == 0:
                self.speed_multiplier = 1.0
        dis = Position(0, 0)
        '''
        [TODO HACKATHON 2]
        Calculate the distance change, and then normalize the distance

        [TODO HACKATHON 4]
        Check if there is collision, if so try to make the movement smooth
        Hint #1 : use entity.py _snap_to_grid function or create a similar function
        Hint #2 : Beware of glitchy teleportation, you must do
                    1. Update X
                    2. If collide, snap to grid
                    3. Update Y
                    4. If collide, snap to grid
                  instead of update both x, y, then snap to grid

        if input_manager.key_down(pg.K_LEFT) or input_manager.key_down(pg.K_a):
            dis.x -= ...
        if input_manager.key_down(pg.K_RIGHT) or input_manager.key_down(pg.K_d):
            dis.x += ...
        if input_manager.key_down(pg.K_UP) or input_manager.key_down(pg.K_w):
            dis.y -= ...
        if input_manager.key_down(pg.K_DOWN) or input_manager.key_down(pg.K_s):
            dis.y += ...

        self.position = ...
        '''
        # [HACKATHON 2] Calculate movement direction
        if input_manager.key_down(pg.K_LEFT) or input_manager.key_down(pg.K_a):
            dis.x -= 1
        if input_manager.key_down(pg.K_RIGHT) or input_manager.key_down(pg.K_d):
            dis.x += 1
        if input_manager.key_down(pg.K_UP) or input_manager.key_down(pg.K_w):
            dis.y -= 1
        if input_manager.key_down(pg.K_DOWN) or input_manager.key_down(pg.K_s):
            dis.y += 1

        # [HACKATHON 2] Normalize the movement vector
        magnitude = math.sqrt(dis.x * dis.x + dis.y * dis.y)
        if magnitude > 0:
            self.is_moving = True
            dis.x /= magnitude
            dis.y /= magnitude
            # Update facing based on dominant movement axis
            if abs(dis.x) > abs(dis.y):
                self._set_direction(Direction.RIGHT if dis.x > 0 else Direction.LEFT)
            else:
                self._set_direction(Direction.DOWN if dis.y > 0 else Direction.UP)
        else:
            self.is_moving = False

        # [HACKATHON 4] Update position with collision detection
        effective_speed = self.speed * self.speed_multiplier
        # Update X axis first
        self.position.x += dis.x * effective_speed * dt
        self.animation.update_pos(self.position)
        # Check collision with map / enemies / NPCs
        if self.game_manager.check_collision(self.animation.rect):
            self.position.x = self._snap_to_grid(self.position.x)
            self.animation.update_pos(self.position)

        # Update Y axis
        self.position.y += dis.y * effective_speed * dt
        self.animation.update_pos(self.position)
        # Check collision with map / enemies / NPCs
        if self.game_manager.check_collision(self.animation.rect):
            self.position.y = self._snap_to_grid(self.position.y)
            self.animation.update_pos(self.position)

        # Check teleportation
        tp = self.game_manager.current_map.check_teleport(self.animation.rect)
        if tp and self.teleport_cooldown <= 0.0:
            dest = tp.destination
            self.game_manager.switch_map(dest)
            self.teleport_cooldown = 0.3

        super().update(dt)

    @override
    def draw(self, screen: pg.Surface, camera: PositionCamera) -> None:
        super().draw(screen, camera)
        
    @override
    def to_dict(self) -> dict[str, object]:
        return super().to_dict()

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


    #宣言(rate, time)(speed potion)
    def apply_speed_boost(self, factor: float, duration: float = 60.0) -> None:
        self.speed_multiplier = factor
        self.speed_boost_timer = duration
    
    @classmethod
    @override
    def from_dict(cls, data: dict[str, object], game_manager: GameManager) -> Player:
        return cls(data["x"] * GameSettings.TILE_SIZE, data["y"] * GameSettings.TILE_SIZE, game_manager)
