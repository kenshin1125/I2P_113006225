from __future__ import annotations
import pygame as pg
import pytmx

from src.utils import load_tmx, Position, GameSettings, PositionCamera, Teleport

class Map:
    # Map Properties
    path_name: str
    tmxdata: pytmx.TiledMap
    # Position Argument
    spawn: Position
    teleporters: list[Teleport]
    # Rendering Properties
    _surface: pg.Surface
    _collision_map: list[pg.Rect]
    _bush_tiles: set[tuple[int, int]]

    def __init__(self, path: str, tp: list[Teleport], spawn: Position):
        self.path_name = path
        self.tmxdata = load_tmx(path)
        self.spawn = spawn
        self.teleporters = tp

        pixel_w = self.tmxdata.width * GameSettings.TILE_SIZE
        pixel_h = self.tmxdata.height * GameSettings.TILE_SIZE
        self.pixel_width = pixel_w
        self.pixel_height = pixel_h

        # Prebake the map
        self._surface = pg.Surface((pixel_w, pixel_h), pg.SRCALPHA)
        self._render_all_layers(self._surface)
        # Prebake the collision map
        self._collision_map = self._create_collision_map()
        self._bush_tiles = self._create_bush_tiles()

    def update(self, dt: float):
        return

    def draw(self, screen: pg.Surface, camera: PositionCamera):
        screen.blit(self._surface, camera.transform_position(Position(0, 0)))
        
        # Draw the hitboxes collision map
        if GameSettings.DRAW_HITBOXES:
            for rect in self._collision_map:
                pg.draw.rect(screen, (255, 0, 0), camera.transform_rect(rect), 1)
        
    def check_collision(self, rect: pg.Rect) -> bool:
        '''
        [TODO HACKATHON 4]
        Return True if collide if rect param collide with self._collision_map
        Hint: use API colliderect and iterate each rectangle to check
        '''
        # [HACKATHON 4] Check collision with each rectangle in collision map
        for collision_rect in self._collision_map:
            if rect.colliderect(collision_rect):
                return True
        return False
        
    def check_teleport(self, rect: pg.Rect) -> Teleport | None:
        """
        プレイヤー矩形がテレポートタイル近傍に少しでも重なれば発火。
        少し上下左右にずれて止まっても拾えるように当たり範囲を拡げる。
        """
        tile_size = GameSettings.TILE_SIZE
        for tp in self.teleporters:
            tp_rect = pg.Rect(tp.pos.x, tp.pos.y, tile_size, tile_size)
            # ジムに関わる場合は判定を厳しく、その他は少し広げる
            if "gym" in self.path_name.lower() or "gym" in (tp.destination or "").lower():
                # さらに厳しく（元の半分程度に縮小）
                shrink = tile_size // 2
                tp_rect.inflate_ip(-shrink, -shrink)
            else:
                tp_rect.inflate_ip(tile_size // 4, tile_size // 4)
            if rect.colliderect(tp_rect):
                return tp
        return None
    
    def check_bush(self, pos: Position) -> bool:
        tile_x = int(pos.x / GameSettings.TILE_SIZE)
        tile_y = int(pos.y / GameSettings.TILE_SIZE)
        return (tile_x, tile_y) in self._bush_tiles

    def _render_all_layers(self, target: pg.Surface) -> None:
        for layer in self.tmxdata.visible_layers:
            if isinstance(layer, pytmx.TiledTileLayer):
                self._render_tile_layer(target, layer)
            # elif isinstance(layer, pytmx.TiledImageLayer) and layer.image:
            #     target.blit(layer.image, (layer.x or 0, layer.y or 0))
 
    def _render_tile_layer(self, target: pg.Surface, layer: pytmx.TiledTileLayer) -> None:
        for x, y, gid in layer:
            if gid == 0:
                continue
            image = self.tmxdata.get_tile_image_by_gid(gid)
            if image is None:
                continue

            image = pg.transform.scale(image, (GameSettings.TILE_SIZE, GameSettings.TILE_SIZE))
            target.blit(image, (x * GameSettings.TILE_SIZE, y * GameSettings.TILE_SIZE))
    
    def _create_collision_map(self) -> list[pg.Rect]:
        rects = []
        for layer in self.tmxdata.visible_layers:
            if isinstance(layer, pytmx.TiledTileLayer) and ("collision" in layer.name.lower() or "house" in layer.name.lower()):
                for x, y, gid in layer:
                    if gid != 0:
                        # Allow stepping on the front door tile so teleport sits right at the entrance
                        if "house" in layer.name.lower() and x == 16 and y == 27:
                            continue
                        '''
                        [TODO HACKATHON 4]
                        rects.append(pg.Rect(...))
                        Append the collision rectangle to the rects[] array
                        Remember scale the rectangle with the TILE_SIZE from settings
                        '''
                        # [HACKATHON 4] Create collision rectangle scaled by TILE_SIZE
                        rects.append(pg.Rect(x * GameSettings.TILE_SIZE, y * GameSettings.TILE_SIZE,
                                            GameSettings.TILE_SIZE, GameSettings.TILE_SIZE))
        return rects
    
    def _create_bush_tiles(self) -> set[tuple[int, int]]:
        tiles: set[tuple[int, int]] = set()
        for layer in self.tmxdata.visible_layers:
            if isinstance(layer, pytmx.TiledTileLayer) and "bush" in layer.name.lower():
                for x, y, gid in layer:
                    if gid != 0:
                        tiles.add((x, y))
        return tiles

    @classmethod
    def from_dict(cls, data: dict) -> "Map":
        tp = [Teleport.from_dict(t) for t in data["teleport"]]
        pos = Position(data["player"]["x"] * GameSettings.TILE_SIZE, data["player"]["y"] * GameSettings.TILE_SIZE)
        return cls(data["path"], tp, pos)

    def to_dict(self):
        return {
            "path": self.path_name,
            "teleport": [t.to_dict() for t in self.teleporters],
            "player": {
                "x": self.spawn.x // GameSettings.TILE_SIZE,
                "y": self.spawn.y // GameSettings.TILE_SIZE,
            }
        }
