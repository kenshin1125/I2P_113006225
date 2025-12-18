from __future__ import annotations
from src.utils import Logger, GameSettings, Position, Teleport
import json, os
import pygame as pg
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.maps.map import Map
    from src.entities.player import Player
    from src.entities.enemy_trainer import EnemyTrainer
    from src.entities.shop_npc import ShopNPC
    from src.data.bag import Bag

class GameManager:
    # Entities
    player: Player | None
    enemy_trainers: dict[str, list[EnemyTrainer]]
    shop_npcs: dict[str, list["ShopNPC"]]
    bag: "Bag"
    bumped_enemy: "EnemyTrainer | None"
    bumped_shop_npc: "ShopNPC | None"

    # Map properties
    current_map_key: str
    maps: dict[str, Map]
    player_spawns: dict[str, Position]
    last_positions: dict[str, Position]  # Track last position on each map

    # Changing Scene properties
    should_change_scene: bool
    next_map: str

    def __init__(self, maps: dict[str, Map], start_map: str,
                 player: Player | None,
                 enemy_trainers: dict[str, list[EnemyTrainer]],
                 bag: Bag | None = None,
                 player_spawns: dict[str, Position] | None = None):

        from src.data.bag import Bag
        # Game Properties
        self.maps = maps
        self.current_map_key = start_map
        self.player = player
        self.enemy_trainers = enemy_trainers
        self.shop_npcs = {k: [] for k in maps.keys()}
        self.bag = bag if bag is not None else Bag([], [])
        self.player_spawns = player_spawns if player_spawns is not None else {}
        self.last_positions = {}  # Initialize empty - will be populated as player moves
        self.bumped_enemy = None
        self.bumped_shop_npc = None

        # Check If you should change scene
        self.should_change_scene = False
        self.next_map = ""
        
    @property
    def current_map(self) -> Map:
        return self.maps[self.current_map_key]
        
    @property
    def current_enemy_trainers(self) -> list[EnemyTrainer]:
        return self.enemy_trainers[self.current_map_key]

    @property
    def current_shop_npcs(self) -> list["ShopNPC"]:
        return self.shop_npcs.get(self.current_map_key, [])
        
    @property
    def current_teleporter(self) -> list[Teleport]:
        return self.maps[self.current_map_key].teleporters
    
    def switch_map(self, target: str) -> None:
        if target not in self.maps:
            Logger.warning(f"Map '{target}' not loaded; cannot switch.")
            return

        # Save current position before switching
        if self.player:
            self.last_positions[self.current_map_key] = self.player.position.copy()

        self.next_map = target
        self.should_change_scene = True
            
    def try_switch_map(self) -> None:
        if self.should_change_scene:
            self.current_map_key = self.next_map
            self.next_map = ""
            self.should_change_scene = False
            if self.player:
                # Use last position if available, otherwise use spawn position
                if self.current_map_key in self.last_positions:
                    target_pos = self.last_positions[self.current_map_key]
                else:
                    target_pos = self.maps[self.current_map_key].spawn

                self.player.position.x = target_pos.x
                self.player.position.y = target_pos.y
                self.player.animation.update_pos(self.player.position)
                # マップ切替直後に再度テレポートを踏まないようクールダウンを付与
                if hasattr(self.player, "teleport_cooldown"):
                    self.player.teleport_cooldown = 0.5
            
    def check_collision(self, rect: pg.Rect) -> bool:
        if self.maps[self.current_map_key].check_collision(rect):
            return True
        for entity in self.enemy_trainers[self.current_map_key]:
            if rect.colliderect(entity.animation.rect):
                self.bumped_enemy = entity
                entity.detected = True  # reuse existing indicator
                return True
        for npc in self.current_shop_npcs:
            if rect.colliderect(npc.animation.rect):
                self.bumped_shop_npc = npc
                return True
        
        return False

    def clear_bumps(self) -> None:
        """Reset bump tracking (call once per frame before movement)."""
        self.bumped_enemy = None
        self.bumped_shop_npc = None
        
    def save(self, path: str) -> None:
        try:
            with open(path, "w") as f:
                json.dump(self.to_dict(), f, indent=2)
            Logger.info(f"Game saved to {path}")
        except Exception as e:
            Logger.warning(f"Failed to save game: {e}")
             
    @classmethod
    def load(cls, path: str) -> "GameManager | None":
        if not os.path.exists(path):
            Logger.error(f"No file found: {path}, ignoring load function")
            return None

        with open(path, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                Logger.error(f"Failed to parse save file '{path}': {e}")
                return None
        return cls.from_dict(data)

    def to_dict(self) -> dict[str, object]:
        map_blocks: list[dict[str, object]] = []
        for key, m in self.maps.items():
            block = m.to_dict()
            block["enemy_trainers"] = [t.to_dict() for t in self.enemy_trainers.get(key, [])]
            block["shop_npcs"] = [n.to_dict() for n in self.shop_npcs.get(key, [])]
            spawn = self.player_spawns.get(key)
            if spawn is None:
                spawn = m.spawn
            block["player"] = {
                "x": spawn.x / GameSettings.TILE_SIZE,
                "y": spawn.y / GameSettings.TILE_SIZE
            }
            map_blocks.append(block)
        return {
            "map": map_blocks,
            "current_map": self.current_map_key,
            "player": self.player.to_dict() if self.player is not None else None,
            "bag": self.bag.to_dict(),
            # NOTE: ここは Checkpoint2 ボーナスで追加した保存項目
            # EN: Added in Checkpoint2 bonus (save audio/hitbox settings)
            # ------------------------------------------------------------
            "settings": {
                "audio_volume": GameSettings.AUDIO_VOLUME,#overlay のスライダーで変えた値がここに入る
                "draw_hitboxes": GameSettings.DRAW_HITBOXES,#当たり判定（ヒットボックス）表示をON/OFFした状態を保存
                "audio_muted": GameSettings.AUDIO_MUTED,#ミュート状態かどうかを保存
                "show_chat": GameSettings.SHOW_CHAT
            }
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "GameManager":
        from src.maps.map import Map
        from src.entities.player import Player
        from src.entities.enemy_trainer import EnemyTrainer
        from src.entities.shop_npc import ShopNPC
        from src.data.bag import Bag
        
        Logger.info("Loading maps")
        maps_data = data["map"]
        maps: dict[str, Map] = {}
        player_spawns: dict[str, Position] = {}
        trainers: dict[str, list[EnemyTrainer]] = {}
        shop_npcs: dict[str, list[ShopNPC]] = {}

        raw_shop_npcs: dict[str, list[dict[str, object]]] = {}
        for entry in maps_data:
            path = entry["path"]
            maps[path] = Map.from_dict(entry)
            sp = entry.get("player")
            if sp:
                player_spawns[path] = Position(
                    sp["x"] * GameSettings.TILE_SIZE,
                    sp["y"] * GameSettings.TILE_SIZE
                )
            raw_shop_npcs[path] = entry.get("shop_npcs", []) or []
        current_map = data["current_map"]
        gm = cls(
            maps, current_map,
            None, # Player
            trainers,
            bag=None,
            player_spawns=player_spawns
        )
        for map_key, raw in raw_shop_npcs.items():
            gm.shop_npcs[map_key] = [ShopNPC.from_dict(n, gm) for n in raw]
        gm.current_map_key = current_map
        
        Logger.info("Loading enemy trainers")
        for m in data["map"]:
            raw_data = m["enemy_trainers"]
            gm.enemy_trainers[m["path"]] = [EnemyTrainer.from_dict(t, gm) for t in raw_data]
            if m.get("shop_npcs"):
                gm.shop_npcs[m["path"]] = [ShopNPC.from_dict(n, gm) for n in m["shop_npcs"]]
        
        Logger.info("Loading Player")
        if data.get("player"):
            gm.player = Player.from_dict(data["player"], gm)
        
        Logger.info("Loading bag")
        from src.data.bag import Bag as _Bag
        gm.bag = Bag.from_dict(data.get("bag", {})) if data.get("bag") else _Bag([], [])
        settings_data = data.get("settings")
        #settingがある時
        if settings_data:
            # NOTE: ここは Checkpoint2 ボーナスで追加したロード項目
            # EN: Added in Checkpoint2 bonus (restore audio/hitbox settings)
            # ------------------------------------------------------------
            #"audio_volume" が settings にあればそれを使う
            GameSettings.AUDIO_VOLUME = float(settings_data.get("audio_volume", GameSettings.AUDIO_VOLUME))
            #"draw_hitboxes" のON/OFFを復元
            GameSettings.DRAW_HITBOXES = bool(settings_data.get("draw_hitboxes", GameSettings.DRAW_HITBOXES))
            #"audio_muted"（ミュートON/OFF）を復元
            GameSettings.AUDIO_MUTED = bool(settings_data.get("audio_muted", GameSettings.AUDIO_MUTED))
            GameSettings.SHOW_CHAT = bool(settings_data.get("show_chat", GameSettings.SHOW_CHAT))

        return gm
