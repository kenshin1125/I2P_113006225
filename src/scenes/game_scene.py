import pygame as pg  # 画面描画・入力処理の中核ライブラリ
import threading  # オンライン同期などバックグラウンド処理に使うスレッド
import time  # 待機や経過時間計測に使用
import math  # トランジション描画で三角関数を利用
from collections import deque  # 経路探索(BFS)で使用

from src.scenes.scene import Scene  # シーン共通の基底クラス
from src.core import GameManager, OnlineManager  # ゲーム全体管理 / オンライン同期管理
from src.utils import Logger, PositionCamera, GameSettings, Position, Direction, Teleport  # ログ出力 / カメラ座標変換 / 設定値 / 座標型 / テレポート情報
from src.core.services import sound_manager, input_manager, scene_manager  # 音声制御 / 入力受付 / シーン遷移管理
from src.sprites import Sprite  # 画像スプライト描画
from src.interface.chat_overlay import ChatOverlay
from src.interface.components import Button  # UIボタンコンポーネント
from typing import Callable, override  # コールバック型ヒント / オーバーライド注釈
from src.scenes.battle_scene import BattleScene  # バトルシーンへの遷移先
from src.scenes.bush_scene import BushScene  # 草むらシーンへの遷移先
from src.entities.enemy_trainer import EnemyTrainer
from src.sprites import Animation
from src.entities.shop_npc import ShopNPC


# [Checkpoint2-02] 設定オーバーレイ用のシンプルな音量スライダー
class OverlaySlider:
    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        min_value: float,
        max_value: float,
        value: float,
        on_change: Callable[[float], None]
    ) -> None:
        self.track_rect = pg.Rect(x, y, width, 12)
        self.min = min_value
        self.max = max_value
        self.value = value
        self.on_change = on_change
        self.dragging = False
        self.font = pg.font.SysFont("Arial", 28)

    def update(self, dt: float) -> None: #値を計算　ボタンが押されてるか確認
        mouse_pos = input_manager.mouse_pos #input_manager.mouse_posでマウスの位置を確認
        if input_manager.mouse_pressed(1) and self.track_rect.inflate(0, 20).collidepoint(mouse_pos):
            self.dragging = True #左クリックした瞬間だけでtrue
            self._set_value_from_mouse(mouse_pos[0]) #クリックしたら少しボタンを大きくする
        elif input_manager.mouse_released(1):
            self.dragging = False

        if self.dragging and input_manager.mouse_down(1):
            self._set_value_from_mouse(mouse_pos[0])

    def _set_value_from_mouse(self, mouse_x: int) -> None: #音量の計算
        ratio = (mouse_x - self.track_rect.x) / self.track_rect.width
        ratio = max(0.0, min(1.0, ratio))
        self.value = self.min + ratio * (self.max - self.min)
        self.on_change(self.value) #音量が変わったらon.chageを呼ぶ

    def draw(self, screen: pg.Surface, label: str) -> None: #描画
        #つまみの上の音の大きさの記入
        label_surf = self.font.render(f"{label}: {self.value:.0f}", True, (255, 255, 255))
        screen.blit(label_surf, (self.track_rect.x, self.track_rect.y - label_surf.get_height() - 10))

        #棒
        pg.draw.rect(screen, (70, 70, 70), self.track_rect, border_radius=6)
        ratio = (self.value - self.min) / (self.max - self.min)
        filled_width = int(self.track_rect.width * ratio)
        fill_rect = pg.Rect(self.track_rect.x, self.track_rect.y, filled_width, self.track_rect.height)
        pg.draw.rect(screen, (120, 200, 255), fill_rect, border_radius=6)

        #つまみ
        thumb_x = self.track_rect.x + filled_width
        thumb_rect = pg.Rect(thumb_x - 8, self.track_rect.y - 6, 16, self.track_rect.height + 12)
        pg.draw.rect(screen, (240, 240, 240), thumb_rect, border_radius=6)

#もとのコード
class GameScene(Scene):
    game_manager: GameManager
    online_manager: OnlineManager | None
    sprite_online: Sprite
    
    def __init__(self):
        super().__init__()
        # Game Manager
        manager = GameManager.load("saves/game0.json")
        if manager is None:
            Logger.error("Failed to load game manager")
            exit(1)
        self.game_manager = manager
        
        # Online Manager
        if GameSettings.IS_ONLINE:
            self.online_manager = OnlineManager()
        else:
            self.online_manager = None
        self.sprite_online = Sprite("ingame_ui/options1.png", (GameSettings.TILE_SIZE, GameSettings.TILE_SIZE))
        self.online_player_sprites: dict[int, Animation] = {}
        # ショップ衝突用アイコン（コイン）
        self.shop_bump_icon = Sprite("ingame_ui/coin.png", (GameSettings.TILE_SIZE // 2, GameSettings.TILE_SIZE // 2))
        # チャットオーバーレイ
        self.chat_overlay = ChatOverlay()
        self.chat_open = False
        self.last_dt = 0.0
        self._last_chat_messages: list[dict] = []
        # 吹き出し管理（オンラインチャット短時間表示）
        self.chat_bubbles: dict[int, dict[str, float]] = {}  # pid -> {"text": str, "timer": float}
        self.chat_seen: set[tuple[int, str]] = set()
        # 再起動時は履歴を空にする
        self.chat_overlay.sync_messages([])
        # ミニマップ
        self.minimap_surface: pg.Surface | None = None
        self.minimap_scale: float = 1.0
        self.minimap_map_key: str = ""
        self.bush_cooldown = 0.0
        self.transition_active = False
        self.transition_progress = 0.0
        self.transition_angle = 0.0
        self.transition_enemy = None
        self.transition_hold_time = 0.0
        self.transition_hold_duration = 0.35
        self.transition_center = (GameSettings.SCREEN_WIDTH // 2, GameSettings.SCREEN_HEIGHT // 2)

#END

        # <<< Checkpoint2-01~04 START : Overlayボタン＆パネル初期化 >>>
        # [Checkpoint2 Overlay] ゲーム中に開けるオーバーレイ（バックパック & 設定）の初期化
        button_size = 80
        margin = 20
        btn_y = margin
        #ボタンの位置計算 x座標(横)
        backpack_x = GameSettings.SCREEN_WIDTH - button_size - margin
        settings_x = backpack_x - button_size - 10
        nav_x = settings_x - button_size - 10
        #backpackボタンの作成
        self.backpack_button = Button(
            "UI/button_backpack.png",
            "UI/button_backpack_hover.png",
            backpack_x,
            btn_y,
            button_size,
            button_size,
            lambda: self._open_overlay("backpack") #ボタンを押したらoverlay_modeをbackpackにする
        )
        #settingのボタンの作成
        self.settings_button = Button(
            "UI/button_setting.png",
            "UI/button_setting_hover.png",
            settings_x,
            btn_y,
            button_size,
            button_size,
            lambda: self._open_overlay("settings")#ボタンを押したらoverlay_modeをsettingにする
        )
        # ナビゲーションボタン（テキスト描画で代用）
        self.nav_button_rect = pg.Rect(nav_x, btn_y, button_size, button_size)
        self.nav_hover = False
        #オーバーレイのサイズ計算
        panel_width = GameSettings.SCREEN_WIDTH // 2
        panel_height = int(GameSettings.SCREEN_HEIGHT * 0.7)
        #オーバーレイの位置計算
        panel_x = (GameSettings.SCREEN_WIDTH - panel_width) // 2
        panel_y = (GameSettings.SCREEN_HEIGHT - panel_height) // 2
        self.overlay_panel_rect = pg.Rect(panel_x, panel_y, panel_width, panel_height) #位置と大きさを保存
        self.overlay_mode: str | None = None #今開いてるかどうか
        #画面を暗くする（上から画面をはる）
        self.overlay_dim_surface = pg.Surface(
            (GameSettings.SCREEN_WIDTH, GameSettings.SCREEN_HEIGHT), pg.SRCALPHA
        )
        self.overlay_dim_surface.fill((0, 0, 0, 180))
        #バックパックやsetting中の背景
        self.overlay_panel_surface = pg.Surface((panel_width, panel_height), pg.SRCALPHA) #パネル同じ大きさの背景
        self.overlay_panel_surface.fill((30, 30, 30, 230))
        #settingやbackpackを押した時に出るフォントを用意
        self.overlay_title_font = pg.font.SysFont("Arial", 40) #大きい文字用
        self.overlay_text_font = pg.font.SysFont("Arial", 26) #普通文字用
        # ショップ用小さめフォント
        self.overlay_small_font = pg.font.SysFont("Arial", 22)
        # チェックボックスとボタンなどのUIパーツ配置
        #チェックボックスボタン
        spacing_x = 60
        top_y = panel_y + 160
        self.overlay_checkbox_mute = pg.Rect(panel_x + spacing_x, top_y, 32, 32)
        self.overlay_checkbox_hitbox = pg.Rect(panel_x + spacing_x, top_y + 60, 32, 32)
        self.overlay_checkbox_chat = pg.Rect(panel_x + spacing_x, top_y + 120, 32, 32)
        #closeボタン
        close_btn_size = 80
        close_x = self.overlay_panel_rect.centerx - close_btn_size // 2
        close_y = self.overlay_panel_rect.bottom - close_btn_size - 50
        self.overlay_close_button = Button(
            "UI/button_back.png",
            "UI/button_back_hover.png",
            close_x,
            close_y,
            close_btn_size,
            close_btn_size,
            self._close_overlay
        )
        #音源スライダー
        slider_width = panel_width - 160
        slider_x = panel_x + 80
        slider_y = panel_y + 120
        self.setting_slider = OverlaySlider(
            slider_x,
            slider_y,
            slider_width,
            0,
            100,
            GameSettings.AUDIO_VOLUME * 100,
            self._set_audio_volume
        )
        #saveボタン
        save_btn_x = panel_x + 40
        save_btn_y = close_y
        self.setting_save_button = Button(
            "UI/button_save.png",
            "UI/button_save_hover.png",
            save_btn_x,
            save_btn_y,
            100,
            100,
            self._save_game
        )
        #loadボタン
        load_btn_x = panel_x + panel_width - 140
        load_btn_y = close_y
        self.setting_load_button = Button(
            "UI/button_load.png",
            "UI/button_load_hover.png",
            load_btn_x,
            load_btn_y,
            100,
            100,
            self._load_game
        )
        # ショップオーバーレイの状態管理
        self.current_shop_npc: ShopNPC | None = None
        self.shop_tab: str = "buy"
        self.shop_message: str = ""
        self.shop_item_rects: list[tuple[pg.Rect, dict[str, object]]] = []
        self.shop_buy_tab_rect = pg.Rect(panel_x + 30, panel_y + 60, 120, 40)
        self.shop_sell_tab_rect = pg.Rect(panel_x + 170, panel_y + 60, 120, 40)
        # <<< Checkpoint2-01~04 END >>> ここまででオーバーレイの配置を完了
        # ナビゲーション関連
        self.navigation_targets: list[tuple[str, Position]] = []
        self.navigation_rects: list[tuple[pg.Rect, Position]] = []
        self.navigation_path: list[Position] = []
        self.navigation_message: str = ""
        self.navigation_active: bool = False
        self.navigation_idx: int = 0
        self.navigation_goal_map: str | None = None
        self.navigation_goal_point: Position | None = None
        # ナビ用矢印サーフェス（赤い三角）
        self.nav_arrow_surface = self._create_nav_arrow_surface()
        # バックパック（プレイヤー用アイテム）のクリック領域
        self.player_item_rects: list[tuple[pg.Rect, dict[str, object]]] = []
        # ベースマップ（スポーン地）を決めておく
        if "map.tmx" in self.game_manager.maps:
            self.base_map_key = "map.tmx"
        else:
            # 最初のマップをベース扱い
            self.base_map_key = list(self.game_manager.maps.keys())[0]
        # ジムマップキー
        self.gym_map_key = next((k for k in self.game_manager.maps.keys() if "gym" in k.lower()), None)
        
    @override
    def enter(self) -> None:
        sound_manager.play_bgm("RBY 103 Pallet Town.ogg")
        if GameSettings.AUDIO_MUTED:
            sound_manager.pause_all()
        # オンライン開始は一度だけ。バトル遷移で戻った際に履歴を消さない。
        if self.online_manager and not getattr(self, "_online_started", False):
            self.online_manager.enter()
            self._online_started = True
            self.chat_overlay.sync_messages([])
            self.chat_seen.clear()
            self.chat_bubbles.clear()
        
    @override
    def exit(self) -> None:
        if self.online_manager:
            self.online_manager.exit()
        self.transition_active = False
        self.transition_enemy = None
        self.transition_progress = 0.0
        self.transition_hold_time = 0.0
        
    @override
    def update(self, dt: float):
        # Check if there is assigned next scene
        self.game_manager.try_switch_map()
        self.game_manager.clear_bumps()
        if self.bush_cooldown > 0:
            self.bush_cooldown = max(0.0, self.bush_cooldown - dt)
        self.last_dt = dt
        # ミニマップ再生成（マップが切り替わった場合）
        if self.minimap_map_key != self.game_manager.current_map_key:
            self._rebuild_minimap()
            self.navigation_path = []
            self.navigation_targets = []
            self.navigation_idx = 0
            # 目的地マップに到達したらナビを終了し、その場に留まる
            if self.navigation_active and self.navigation_goal_map == self.game_manager.current_map_key:
                self.navigation_active = False
                self.navigation_goal_map = None
                self.navigation_goal_point = None
                self.navigation_message = "到着しました"
            # チャット吹き出しの寿命を減算
        expired = []
        for pid, data in self.chat_bubbles.items():
            data["timer"] -= dt
            if data["timer"] <= 0:
                expired.append(pid)
        for pid in expired:
            self.chat_bubbles.pop(pid, None)
        # もしナビが継続中で、現在マップが目的地マップかつ経路が空なら再計算する
        if (
            self.navigation_active
            and self.navigation_goal_map == self.game_manager.current_map_key
            and not self.navigation_path
            and self.navigation_goal_point is not None
            and self.game_manager.player is not None
        ):
            new_path = self._find_path(self.game_manager.player.position, self.navigation_goal_point)
            if new_path:
                self.navigation_path = new_path
                self.navigation_idx = 1
            else:
                # テレポート直後などでパスが見つからない場合は停止
                self.navigation_active = False
                self.navigation_goal_map = None
                self.navigation_goal_point = None
                self.navigation_message = "経路が見つかりません"

        # ショップを開いている間はプレイヤー移動を止め、ショップUIのみ更新
        if self.overlay_mode == "shop":
            self._update_shop_overlay(dt)
            return
        if self.overlay_mode == "backpack":
            # 閉じるボタンとプレイヤーアイテムのクリックのみ処理し、それ以外の更新は行わない
            self.overlay_close_button.update(dt)
            self._handle_backpack_input()
            return
        
        # Update player and other data
        if self.game_manager.player:
            if self.navigation_active:
                self._auto_move_navigation(dt)
            else:
                self.game_manager.player.update(dt)
        for npc in self.game_manager.current_shop_npcs:
            npc.update(dt)
        # <<< Checkpoint2-05 START : Trainer Detection & Battle Trigger >>>
        for enemy in self.game_manager.current_enemy_trainers:#マップにいる敵のリスト
            enemy.update(dt)
            if enemy.detected and input_manager.key_pressed(pg.K_SPACE):
                # [Checkpoint2-05] トレーナーに見つかったらスペースでバトル遷移
                self._begin_battle_transition(enemy)#黒の線の演出
                return
        # <<< Checkpoint2-05 END >>>
            
        # Update others
        self.game_manager.bag.update(dt)
        
        if self.game_manager.player is not None and self.online_manager is not None:
            _ = self.online_manager.update(
                self.game_manager.player.position.x, 
                self.game_manager.player.position.y,
                self.game_manager.current_map.path_name,
                direction=self.game_manager.player.direction.name,
                moving=self.game_manager.player.is_moving
            )
        if self.transition_active:
            if self.transition_progress < 1.0:
                self.transition_progress += dt * 1.2
                self.transition_angle += dt * 5
                if self.transition_progress >= 1.0:
                    self.transition_progress = 1.0
                    self.transition_hold_time = 0.0
            else:
                self.transition_hold_time += dt
                if self.transition_hold_time >= self.transition_hold_duration and self.transition_enemy is not None:
                    if self.transition_enemy == "bush":
                        self._enter_bush_scene()
                    else:
                        enemy = self.transition_enemy
                        self._start_battle(enemy)
                    self.transition_enemy = None
                    self.transition_hold_time = 0.0
            return
        if self.overlay_mode is not None:
            self.overlay_close_button.update(dt)
            if self.overlay_mode == "settings":
                self.setting_slider.update(dt)
                self.setting_save_button.update(dt)
                self.setting_load_button.update(dt)
                self._handle_overlay_settings_input()
            elif self.overlay_mode == "navigation":
                self._update_navigation_overlay()
            # backpack など他のオーバーレイでは特別な更新なし
        else:
            self.backpack_button.update(dt)
            self.settings_button.update(dt)
            self._update_navigation_button()
            self._check_shop_interaction()
            self._check_online_battle()
            # ナビゲーション中なら手動入力を受け付けない
            if self.navigation_active:
                input_manager.reset()
        self._update_chat(dt)
        self._check_bush_interaction()
        
    @override
    def draw(self, screen: pg.Surface):
        if self.game_manager.player:
            '''
            [TODO HACKATHON 3]
            Implement the camera algorithm logic here
            Right now it's hard coded, you need to follow the player's positions
            you may use the below example, but the function still incorrect, you may trace the entity.py

            camera = self.game_manager.player.camera
            '''
            # [HACKATHON 3] Use player's camera to center player on screen
            camera = self.game_manager.player.camera
            self.game_manager.current_map.draw(screen, camera)
            self.game_manager.player.draw(screen, camera)
        else:
            camera = PositionCamera(0, 0)
            self.game_manager.current_map.draw(screen, camera)
        for enemy in self.game_manager.current_enemy_trainers:
            enemy.draw(screen, camera)
        for npc in self.game_manager.current_shop_npcs:
            npc.draw(screen, camera)
            # 取引可能距離にプレイヤーがいるか、衝突中なら印を表示
            player_rect = self.game_manager.player.animation.rect if self.game_manager.player else None
            can_trade = False
            if player_rect:
                can_trade = npc.interaction_rect().colliderect(player_rect)
            if can_trade or self.game_manager.bumped_shop_npc is npc:
                icon_pos = Position(npc.position.x + GameSettings.TILE_SIZE // 4,
                                    npc.position.y - GameSettings.TILE_SIZE // 2)
                self.shop_bump_icon.update_pos(icon_pos)
                self.shop_bump_icon.draw(screen, camera)

        # <<< Checkpoint2-01~06 START : Overlay描画＆遭遇演出 >>>
        #バックのUIを画面に描画
        self.game_manager.bag.draw(screen)
        
        #
        if self.online_manager and self.game_manager.player: #オンライン専用処理
            list_online = self.online_manager.get_list_players() #他のプレイヤーの情報リストを取得
            #オンラインで同じマップにいる他プレイヤーを画面上に表示
            for player in list_online:
                if player["map"] == self.game_manager.current_map.path_name:
                    pid = player.get("id", -1)
                    anim = self._get_online_animation(pid)
                    if anim is None:
                        continue
                    pos_world = Position(player.get("x", 0), player.get("y", 0))
                    anim.update_pos(pos_world)
                    dir_name = str(player.get("dir", "DOWN"))
                    anim.switch(dir_name.lower())
                    if player.get("moving"):
                        anim.update(self.last_dt)
                    else:
                        anim.accumulator = 0
                    anim.draw(screen, self.game_manager.player.camera)
            # チャット吹き出し表示（自分＋他プレイヤー）
            bubble_positions: dict[int, Position] = {}
            if self.game_manager.player:
                bubble_positions[self.online_manager.player_id] = self.game_manager.player.position.copy()
            for p in list_online:
                if p.get("map") == self.game_manager.current_map.path_name:
                    bubble_positions[p.get("id", -1)] = Position(p.get("x", 0), p.get("y", 0))
            self._draw_chat_bubbles(screen, bubble_positions, camera=self.game_manager.player.camera if self.game_manager.player else PositionCamera(0, 0))
        if self.overlay_mode is not None: #オーバーレイを開いてるか確認
            screen.blit(self.overlay_dim_surface, (0, 0)) #背景を暗く
            screen.blit(self.overlay_panel_surface, self.overlay_panel_rect.topleft) #中央にグレーの箱を作成
            pg.draw.rect(screen, (200, 200, 200), self.overlay_panel_rect, 4, border_radius=16) #箱の枠組み
            #backpackかsettingによって表示するものを変える
            if self.overlay_mode == "backpack":
                self._draw_backpack_contents(screen)
            elif self.overlay_mode == "settings":
                self._draw_setting_contents(screen)
            elif self.overlay_mode == "shop":
                self._draw_shop_overlay(screen)
            elif self.overlay_mode == "navigation":
                self._draw_navigation_overlay(screen)
            #閉じるボタン
            self.overlay_close_button.draw(screen)
        else:
            #オーバーレイが閉じてる時(右上のボタンの記入)
            self.backpack_button.draw(screen)
            self.settings_button.draw(screen)
            self._draw_navigation_button(screen)
        #敵と遭遇した時の黒の線の演出　(上からはる)
        if self.transition_active:
            self._draw_battle_transition(screen)
        # <<< Checkpoint2-01~06 END >>>（オーバーレイ描画と遭遇アニメ）
        # ナビゲーション経路を描画
        self._draw_navigation_path(screen, camera)
        # チャット表示
        if GameSettings.SHOW_CHAT:
            self.chat_overlay.draw(screen, self_id=self.online_manager.player_id if self.online_manager else -1)
        # ミニマップ表示（左上）
        self._draw_minimap(screen, camera)
        # ナビ経路を途中でキャンセルした場合も描画を消す
        if not self.navigation_active and not self.navigation_path and self.navigation_message == "arrived":
            self.navigation_message = ""

    def _open_overlay(self, mode: str) -> None:
        self.overlay_mode = mode
        if mode == "navigation":
            self._refresh_navigation_targets()
            self.navigation_message = ""

    def _close_overlay(self) -> None:
        self.overlay_mode = None
        self.current_shop_npc = None
        self.shop_message = ""

    # <<< Checkpoint2-03 START : Backpack Overlay >>> 
    # [Checkpoint2-03] バックパックオーバーレイのメイン描画
    #パネルのもとを作成
    def _draw_backpack_contents(self, screen: pg.Surface) -> None:
        panel = self.overlay_panel_rect
        #backpackの文字を作成
        title = self.overlay_title_font.render("Backpack", True, (255, 255, 255))
        screen.blit(title, (panel.centerx - title.get_width() // 2, panel.y + 20))

        #小さい文字でmonsterやitemを記入
        header_font = self.overlay_text_font
        monsters_title = header_font.render("Monsters", True, (255, 255, 0))
        items_title = header_font.render("Items", True, (0, 220, 255))
        player_items_title = header_font.render("Player Items", True, (0, 255, 150))

        #モンスターとアイテムの位置
        monsters_start_x = panel.x + 30
        column_gap = 50
        items_start_x = panel.x + panel.width // 2 + column_gap
        base_y = panel.y + 80
        #ここで見出しを置いてる
        screen.blit(monsters_title, (monsters_start_x, base_y))
        screen.blit(items_title, (items_start_x, base_y))

        #リストとcloseボタンが被らないようにしてる
        content_bottom = self.overlay_close_button.hitbox.top - 20
        
        # 左: モンスター → プレイヤーアイテム
        monsters_end_y = self._draw_monster_list(screen, monsters_start_x, base_y + 40, content_bottom)
        player_items_header_y = monsters_end_y + 10
        screen.blit(player_items_title, (monsters_start_x, player_items_header_y))
        self._draw_player_item_list(screen, monsters_start_x, player_items_header_y + 30, content_bottom)

        # 右: アイテム（1カラムのみ）
        self._draw_item_list(screen, items_start_x, base_y + 40, content_bottom)

    # [Checkpoint2-03] 所持モンスターを2カラムで表示（視認性のため4体まで）
    #モンスター一覧の記入
    def _draw_monster_list(self, screen: pg.Surface, x: int, start_y: int, max_y: int) -> int:
        font = self.overlay_text_font
        line_height = 26
        column_width = 260
        monsters = self.game_manager.bag.monsters[:4]
        #モンスターがいない場合の処理
        if not monsters:
            no_data = font.render("No monsters owned.", True, (220, 220, 220))
            screen.blit(no_data, (x, start_y))
            return start_y + line_height

        #初期化
        col_x = x
        col_index = 0
        max_draw_y = start_y
        #1匹ずつかいてる
        for monster in monsters:
            line_y = start_y + col_index * line_height
            #下に行きすぎたら右へ移動
            if line_y + line_height > max_y:
                col_x += column_width
                col_index = 0
                line_y = start_y
            #文章作成
            text = f"{monster['name']}  Lv.{monster['level']}  HP {monster['hp']}/{monster['max_hp']}"
            surf = font.render(text, True, (230, 230, 230))
            #貼り付け
            screen.blit(surf, (col_x, line_y))
            max_draw_y = max(max_draw_y, line_y + line_height)
            #次のポケモン
            col_index += 1
        return max_draw_y

    # [Checkpoint2-03] 所持アイテム欄

    #アイテム一覧の記入
    def _draw_item_list(self, screen: pg.Surface, x: int, start_y: int, max_y: int) -> None:
        font = self.overlay_text_font
        line_height = 26
        items = self.game_manager.bag.items
        #アイテムがない場合
        if not items:
            no_data = font.render("No items owned.", True, (220, 220, 220))
            screen.blit(no_data, (x, start_y))
            return

        col_index = 0
        #１個ずつ（折り返さず1カラム）
        for item in items:
            line_y = start_y + col_index * line_height
            if line_y + line_height > max_y:
                break
            #文章作成
            text = f"{item['name']}  x{item['count']}"
            surf = font.render(text, True, (230, 230, 230))
            #貼り付け
            screen.blit(surf, (x, line_y))
            #次のアイテムへ
            col_index += 1



    def _handle_backpack_input(self) -> None:
        """バックパック画面でのクリック処理（プレイヤー用アイテム使用）"""
        if input_manager.mouse_pressed(1):
            mouse = input_manager.mouse_pos
            for rect, item in self.player_item_rects:
                if rect.collidepoint(mouse):
                    name = item.get("name", "")
                    #アイテム数減らす, 倍率をここで決める(倍率) (speed potion)
                    if name.lower() in ["speed potion", "speed boost", "speed up"]:
                        if self.game_manager.bag.remove_player_item(name, 1):
                            if self.game_manager.player:
                            
                                self.game_manager.player.apply_speed_boost(1.5)
                            # 使用後もバックパック表示は維持
                    break

    def _draw_player_item_list(self, screen: pg.Surface, x: int, start_y: int, max_y: int) -> None:
        font = self.overlay_text_font
        line_height = 26
        items = self.game_manager.bag.player_items
        self.player_item_rects = []
        if not items:
            no_data = font.render("No player items.", True, (220, 220, 220))
            screen.blit(no_data, (x, start_y))
            return
        col_index = 0
        for item in items:
            line_y = start_y + col_index * line_height
            if line_y + line_height > max_y:
                break
            text = f"{item['name']}  x{item['count']}"
            surf = font.render(text, True, (200, 255, 200))
            rect = pg.Rect(x, line_y, surf.get_width(), line_height)
            screen.blit(surf, rect.topleft)
            self.player_item_rects.append((rect, item))
            col_index += 1
    # <<< Checkpoint2-03 END >>>

    def _start_battle(self, enemy) -> None:
        battle_scene = scene_manager.get_scene("battle")
        if isinstance(battle_scene, BattleScene):
            battle_scene.start_battle(self.game_manager, enemy, self.game_manager.current_map_key)
            scene_manager.change_scene("battle")

    def _start_online_battle(self, op: dict) -> None:
        """オンライン相手用の簡易バトル開始。相手の向きに応じてトレーナーを生成。"""
        facing_name = str(op.get("dir", "DOWN"))
        try:
            facing = Direction[facing_name]
        except Exception:
            facing = Direction.DOWN
        enemy = EnemyTrainer(
            float(op.get("x", 0)),
            float(op.get("y", 0)),
            self.game_manager,
            facing=facing
        )
        enemy.monster_data = {
            "name": "OnlineRival",
            "hp": 90,
            "max_hp": 90,
            "level": 9,
            "attack": 22,
            "defense": 9,
            "element": "Electric",
            "sprite_path": "menu_sprites/menusprite2.png"
        }
        self._begin_battle_transition(enemy)
    
    # <<< Checkpoint2-05/06 START : 侵入演出アニメ >>> 

    # [Checkpoint2-05] バトル突入時の黒い線アニメーション
    #二重演出を避ける
    def _begin_battle_transition(self, enemy) -> None:
        if self.transition_active:
            return
        #演出状態を開始用にリセット
        self.transition_active = True
        self.transition_progress = 0.0
        self.transition_angle = 0.0
        self.transition_enemy = enemy
        self.transition_hold_time = 0.0
        #演出の中心を真ん中に設定
        center_x = GameSettings.SCREEN_WIDTH // 2
        center_y = GameSettings.SCREEN_HEIGHT // 2
        #黒の線の演出をプレイヤーから出るように設定
        player = self.game_manager.player
        if player:
            cam = player.camera
            screen_pos = cam.transform_position(player.position)
            center_x = int(screen_pos[0] + GameSettings.TILE_SIZE // 2)
            center_y = int(screen_pos[1] + GameSettings.TILE_SIZE // 2)
        #中心座標を保存
        self.transition_center = (center_x, center_y)

    # [Checkpoint2-06] 草むら専用のトランジション（同じアニメーションを流用）
    #二重演出を避ける
    def _begin_bush_transition(self) -> None:
        if self.transition_active:
            return
        #演出状態を開始用にリセット
        self.transition_active = True
        self.transition_progress = 0.0
        self.transition_angle = 0.0
        self.transition_hold_time = 0.0
        self.transition_enemy = "bush"
        #黒の線の演出をプレイヤーから出るように設定
        player = self.game_manager.player
        if player:
            cam = player.camera
            screen_pos = cam.transform_position(player.position)
            cx = int(screen_pos[0] + GameSettings.TILE_SIZE // 2)
            cy = int(screen_pos[1] + GameSettings.TILE_SIZE // 2)
            #中心座標を保存
            self.transition_center = (cx, cy)
        #プレイヤーが存在しないときは演出の中心を画面の真ん中にする
        else:
            self.transition_center = (GameSettings.SCREEN_WIDTH // 2, GameSettings.SCREEN_HEIGHT // 2)
    
    #黒い線の演出
    def _draw_battle_transition(self, screen: pg.Surface) -> None:
        #中心点
        cx, cy = self.transition_center
        #演出の半径を計算
        max_radius = math.hypot(GameSettings.SCREEN_WIDTH, GameSettings.SCREEN_HEIGHT)
        radius = max(30.0, max_radius * min(1.6, self.transition_progress * 1.4))
        #黒いせんの本数の設定
        base_angle = self.transition_angle
        wedge_count = 5
        base_width = math.pi / 10#最初の大きさ
        half_width = base_width * min(1.3, self.transition_progress * 1.6)#線を大きくしてる
        #黒線を５本かくループ
        for i in range(wedge_count):
            angle = base_angle + i * (2 * math.pi / wedge_count)#角度の設定（base_angleが毎フレーム増えてクルクルする）
            a1 = angle - half_width
            a2 = angle + half_width
            p1 = (cx + radius * math.cos(a1), cy + radius * math.sin(a1))
            p2 = (cx + radius * math.cos(a2), cy + radius * math.sin(a2))
            pg.draw.polygon(screen, (0, 0, 0), [(cx, cy), p1, p2]) #中心とp1, p2を結んで黒に塗る（三角形）
        #最後の画面が真っ黒になるシーン
        overlay = pg.Surface((GameSettings.SCREEN_WIDTH, GameSettings.SCREEN_HEIGHT)) #画面ぴったりの黒の画面
        level = min(1.0, max(0.0, (self.transition_progress - 0.5) / 0.5)) #-1-1の間で画面を徐々に暗くしてる
        overlay.set_alpha(int(level * 255))
        overlay.fill((0, 0, 0))
        screen.blit(overlay, (0, 0)) #これを画面の上に貼りつけ
    # <<< Checkpoint2-05/06 END >>>
    
    def _check_bush_interaction(self) -> None:

        # <<< Checkpoint2-06 START : 草むらエンカウント入口 >>>
        # [Checkpoint2-06] 草むらエンカウント判定
        
        #プレイヤーがいないならNone
        if self.game_manager.player is None:
            return
        #1度入ったらすぐ入れないようにする
        if self.bush_cooldown > 0:
            return
        player_rect = self.game_manager.player.animation.rect
        center_pos = Position(player_rect.centerx, player_rect.centery) #体の中心
        foot_pos = Position(player_rect.centerx, player_rect.bottom - 5) #足元
        if (self.game_manager.current_map.check_bush(center_pos) or
                self.game_manager.current_map.check_bush(foot_pos)): #体の中心か足元が芝生にあるかどうか
            if input_manager.key_pressed(pg.K_b):
                self._begin_bush_transition() #Bボタンを押した瞬間だけTRUE
        # <<< Checkpoint2-06 END >>>　

    # <<< Checkpoint2-02/04 START : Setting Overlay >>> 
    # [Checkpoint2-02/04] 設定オーバーレイのUI配置（スライダー＋チェック＋セーブ/ロード）
    #setting画面の中身をかく
    def _draw_setting_contents(self, screen: pg.Surface) -> None:
        #箱の位置とサイズこれを基準にする
        panel = self.overlay_panel_rect
        #タイトルをはる
        title = self.overlay_title_font.render("Settings", True, (255, 255, 255))
        screen.blit(title, (panel.centerx - title.get_width() // 2, panel.y + 20)) 

        self._draw_overlay_checkbox(screen, self.overlay_checkbox_hitbox, "Show Collision Hitboxes", GameSettings.DRAW_HITBOXES)  #DRAW_HITBOXESがtrueならon
        self._draw_overlay_checkbox(screen, self.overlay_checkbox_mute, "Mute BGM", GameSettings.AUDIO_MUTED) #AUDIO_MUTEDがtrueならon
        self._draw_overlay_checkbox(screen, self.overlay_checkbox_chat, "Show Chat Box", GameSettings.SHOW_CHAT)

        # スライダー・ボタンを描画（ここはCheckpoint2 Setting Overlayの要件）
        self.setting_slider.draw(screen, "Audio Volume") #音量ゲージ
        self.setting_save_button.draw(screen) #saveボタン
        self.setting_load_button.draw(screen) #loadボタンを書く

    # [Checkpoint2-02] ミュート＆ヒットボックス用チェックボックス
    def _draw_overlay_checkbox(self, screen: pg.Surface, rect: pg.Rect, label: str, checked: bool) -> None:
        color = (80, 180, 90) if checked else (100, 100, 100) #onなら緑offなら灰色
        pg.draw.rect(screen, (240, 240, 240), rect) #白枠の作成
        #枠の上からon/offボタンの貼り付け
        inner = rect.inflate(-6, -6)
        pg.draw.rect(screen, color, inner)
        #onならばつをかく(trueの場合)
        if checked:
            pg.draw.line(screen, (255, 255, 255), inner.topleft, inner.bottomright, 3)
            pg.draw.line(screen, (255, 255, 255), inner.topright, inner.bottomleft, 3)
        #説明文を作り貼り付け
        text = self.overlay_text_font.render(label, True, (255, 255, 255))
        screen.blit(text, (rect.right + 12, rect.centery - text.get_height() // 2))

    # [Checkpoint2-02] クリックで設定を反映し、音声も同期
    #onoffの切り替え
    def _handle_overlay_settings_input(self) -> None:
        if input_manager.mouse_pressed(1):#押した瞬間だけtrue
            if self.overlay_checkbox_hitbox.collidepoint(input_manager.mouse_pos):#マウスがヒットボックスボックスないかどうか
                GameSettings.DRAW_HITBOXES = not GameSettings.DRAW_HITBOXES #trueからfalseの切り替え
            elif self.overlay_checkbox_mute.collidepoint(input_manager.mouse_pos):#マウスがmuteボタンないか
                GameSettings.AUDIO_MUTED = not GameSettings.AUDIO_MUTED #trueからfalseの切り替え
                if GameSettings.AUDIO_MUTED:
                    sound_manager.pause_all() #mute onなら音を止める
                else:
                    sound_manager.resume_all() #mute offなら音を再開
            elif self.overlay_checkbox_chat.collidepoint(input_manager.mouse_pos):
                GameSettings.SHOW_CHAT = not GameSettings.SHOW_CHAT
    # --- Shop helpers ---
    def _check_shop_interaction(self) -> None:
        """Press E near a shop NPC to open shop overlay."""
        if self.overlay_mode is not None:
            return
        player = self.game_manager.player
        if player is None:
            return
        interact_rect = player.animation.rect.inflate(GameSettings.TILE_SIZE // 2, GameSettings.TILE_SIZE // 2)
        for npc in self.game_manager.current_shop_npcs:
            if interact_rect.colliderect(npc.interaction_rect()) and input_manager.key_pressed(pg.K_e):
                self._open_shop(npc)
                return

    def _check_online_battle(self) -> None:
        """オンラインの他プレイヤーと近づいてOキーでバトル開始。"""
        if self.overlay_mode is not None or self.transition_active:
            return
        if self.game_manager.player is None or self.online_manager is None:
            return
        my_rect = self.game_manager.player.animation.rect
        list_online = self.online_manager.get_list_players()
        for op in list_online:
            if op.get("map") != self.game_manager.current_map.path_name:
                continue
            opp_rect = pg.Rect(op.get("x", 0), op.get("y", 0), GameSettings.TILE_SIZE, GameSettings.TILE_SIZE)
            if my_rect.colliderect(opp_rect.inflate(GameSettings.TILE_SIZE // 2, GameSettings.TILE_SIZE // 2)):
                if input_manager.key_pressed(pg.K_o):
                    self._start_online_battle(op)
                break

    def _open_shop(self, npc: ShopNPC) -> None:
        self.current_shop_npc = npc
        self.shop_tab = "buy"
        self.shop_message = ""
        self.overlay_mode = "shop"

    def _update_shop_overlay(self, dt: float) -> None:
        # close button
        self.overlay_close_button.update(dt)
        if input_manager.key_pressed(pg.K_ESCAPE):
            self._close_overlay()
            return
        mouse_pos = input_manager.mouse_pos
        if input_manager.mouse_pressed(1):
            if self.shop_buy_tab_rect.collidepoint(mouse_pos):
                self.shop_tab = "buy"
            elif self.shop_sell_tab_rect.collidepoint(mouse_pos):
                self.shop_tab = "sell"
        entries = self._build_shop_entries()
        if input_manager.mouse_pressed(1):
            for rect, item in entries:
                if rect.collidepoint(mouse_pos):
                    if self.shop_tab == "buy":
                        self._handle_buy(item)
                    else:
                        self._handle_sell(item)
                    break

    def _build_shop_entries(self) -> list[tuple[pg.Rect, dict[str, object]]]:
        panel = self.overlay_panel_rect
        start_x = panel.x + 30
        start_y = panel.y + 150
        line_h = 44
        width = panel.width - 60
        entries: list[tuple[pg.Rect, dict[str, object]]] = []
        if self.shop_tab == "buy":
            items = self.current_shop_npc.items if self.current_shop_npc else []
        else:
            # Sell everything except coins
            items = [
                {"name": i["name"], "count": i["count"], "price": i.get("price", 0), "sprite_path": i.get("sprite_path", "")}
                for i in self.game_manager.bag.items
                if i["name"] != "Coins"
            ]
        for idx, item in enumerate(items):
            rect = pg.Rect(start_x, start_y + idx * line_h, width, line_h - 4)
            entries.append((rect, item))
        self.shop_item_rects = entries
        return entries

    def _handle_buy(self, item: dict[str, object]) -> None:
        price = int(item.get("price", 0))
        name = str(item.get("name", "Item"))
        sprite_path = str(item.get("sprite_path", "ingame_ui/potion.png"))
        if self._get_currency() < price:
            self.shop_message = "Not enough coins"
            return
        if not self.game_manager.bag.remove_item("Coins", price):
            self.shop_message = "No coins"
            return
        self.game_manager.bag.add_item(name, 1, sprite_path)
        self.shop_message = f"Bought {name}"

    def _handle_sell(self, item: dict[str, object]) -> None:
        name = str(item.get("name", "Item"))
        count = int(item.get("count", 0))
        sprite_path = str(item.get("sprite_path", ""))
        # use listed price if exists, otherwise flat 5
        price_full = int(item.get("price", 5))
        price = max(1, price_full // 2)
        if count <= 0:
            self.shop_message = "Out of stock"
            return
        if not self.game_manager.bag.remove_item(name, 1):
            self.shop_message = "Out of stock"
            return
        self.game_manager.bag.add_item("Coins", price, "ingame_ui/coin.png")
        self.shop_message = f"Sold {name} for {price}"
        # Keep sprite path if item removed then re-bought later
        if sprite_path:
            for item_entry in self.current_shop_npc.items if self.current_shop_npc else []:
                if item_entry.get("name") == name:
                    item_entry.setdefault("sprite_path", sprite_path)

    def _get_currency(self) -> int:
        return self.game_manager.bag.get_item_count("Coins")

    def _draw_shop_overlay(self, screen: pg.Surface) -> None:
        panel = self.overlay_panel_rect
        title = self.overlay_title_font.render("Shop", True, (255, 255, 255))
        screen.blit(title, (panel.centerx - title.get_width() // 2, panel.y + 15))
        # Tabs
        def draw_tab(rect: pg.Rect, text: str, active: bool):
            color = (120, 200, 255) if active else (70, 70, 70)
            pg.draw.rect(screen, color, rect, border_radius=8)
            label = self.overlay_text_font.render(text, True, (0, 0, 0))
            screen.blit(label, (rect.centerx - label.get_width() // 2, rect.centery - label.get_height() // 2))
        draw_tab(self.shop_buy_tab_rect, "Buy", self.shop_tab == "buy")
        draw_tab(self.shop_sell_tab_rect, "Sell", self.shop_tab == "sell")
        # Currency display
        coins_text = self.overlay_text_font.render(f"Coins: {self._get_currency()}", True, (255, 255, 0))
        screen.blit(coins_text, (panel.right - coins_text.get_width() - 30, panel.y + 70))
        # Items
        for rect, item in self.shop_item_rects:
            pg.draw.rect(screen, (50, 50, 50), rect, border_radius=6)
            pg.draw.rect(screen, (90, 90, 90), rect, 2, border_radius=6)
            name = str(item.get("name", "Item"))
            price = int(item.get("price", 0))
            if self.shop_tab == "sell":
                price = max(1, price // 2)
            count = self.game_manager.bag.get_item_count(name) if self.shop_tab == "buy" else int(item.get("count", 0))
            text = f"{name}  x{count}  Price: {price}"
            label = self.overlay_small_font.render(text, True, (230, 230, 230))
            screen.blit(label, (rect.x + 10, rect.centery - label.get_height() // 2))
        # Status message
        if self.shop_message:
            msg = self.overlay_small_font.render(self.shop_message, True, (255, 200, 120))
            screen.blit(msg, (panel.centerx - msg.get_width() // 2, panel.bottom - 180))

    # --- Online helpers ---
    def _get_online_animation(self, pid: int) -> Animation | None:
        if pid == -1:
            return None
        anim = self.online_player_sprites.get(pid)
        if anim is None:
            anim = Animation("character/ow2.png", ["down", "left", "right", "up"], 4,
                             (GameSettings.TILE_SIZE, GameSettings.TILE_SIZE))
            self.online_player_sprites[pid] = anim
        return anim

    def _update_chat(self, dt: float) -> None:
        # 開くトグル（Enter）
        if not self.chat_overlay.is_open and input_manager.key_pressed(pg.K_RETURN):
            self.chat_overlay.toggle()
            return
        if self.chat_overlay.is_open:
            send_text = self.chat_overlay.update(input_manager)
            if send_text:
                # ローカルに即時反映（オンライン状態に依らず）
                sender_id = self.online_manager.player_id if self.online_manager else 0
                cleaned = self.chat_overlay._clean_text(send_text)
                self.chat_overlay.messages.append({"id": sender_id, "text": cleaned})
                self.chat_overlay.messages = self.chat_overlay.messages[-8:]
                self._last_chat_messages = list(self.chat_overlay.messages)
                self._show_chat_bubble(sender_id, cleaned)
                # オンラインに送信（失敗してもローカル表示は維持）
                if self.online_manager:
                    self.online_manager.send_chat(send_text)
        if self.online_manager:
            latest_msgs = self.online_manager.get_chat_messages()
            if latest_msgs:
                # サーバー履歴を反映（重複はスキップしない、タイムライン順でそのまま採用）
                cleaned_msgs = [
                    {"id": int(m.get("id", -1)), "text": self.chat_overlay._clean_text(str(m.get("text", "")))}
                    for m in latest_msgs
                ]
                self._last_chat_messages = cleaned_msgs[-8:]
                self.chat_overlay.sync_messages(self._last_chat_messages)
                for idx, msg in enumerate(cleaned_msgs):
                    pid = int(msg.get("id", -1))
                    text = msg.get("text", "")
                    key = (idx, pid, text)
                    if key not in self.chat_seen:
                        self.chat_seen.add(key)
                        self._show_chat_bubble(pid, text)
                if len(self.chat_seen) > 300:
                    # 古いキーを間引き
                    self.chat_seen = set(list(self.chat_seen)[-150:])
            else:
                # サーバー応答が空・失敗時は直前の履歴を維持して消失を防ぐ
                if self._last_chat_messages:
                    self.chat_overlay.messages = list(self._last_chat_messages[-8:])

    def _show_chat_bubble(self, pid: int, text: str) -> None:
        cleaned = self.chat_overlay._clean_text(text)
        if not cleaned:
            return
        self.chat_bubbles[pid] = {"text": cleaned[:40], "timer": 1.5}

    def _draw_chat_bubbles(self, screen: pg.Surface, positions: dict[int, Position], camera: PositionCamera) -> None:
        if not self.chat_bubbles:
            return
        font = self.overlay_small_font
        for pid, data in list(self.chat_bubbles.items()):
            pos = positions.get(pid)
            if pos is None:
                continue
            text = data["text"]
            is_self = self.online_manager and pid == self.online_manager.player_id
            color = (30, 30, 30) if is_self else (0, 0, 0)
            bg_color = (220, 255, 220, 255) if is_self else (255, 255, 255, 255)
            surf = font.render(text, True, color)
            padding = 6
            box = pg.Surface((surf.get_width() + padding * 2, surf.get_height() + padding * 2), pg.SRCALPHA)
            box.fill(bg_color)
            outline = (40, 120, 60) if is_self else (0, 0, 0)
            pg.draw.rect(box, outline, box.get_rect(), 2, border_radius=4)
            box.blit(surf, (padding, padding))
            # ポインタ
            pointer = pg.Surface((10, 8), pg.SRCALPHA)
            pg.draw.polygon(pointer, bg_color, [(0, 0), (10, 0), (5, 8)])
            pg.draw.polygon(pointer, outline, [(0, 0), (10, 0), (5, 8)], 1)
            world_x = pos.x + GameSettings.TILE_SIZE // 2 - box.get_width() // 2
            world_y = pos.y - box.get_height() - 10
            screen.blit(box, camera.transform_position(Position(world_x, world_y)))
            screen.blit(pointer, camera.transform_position(Position(world_x + box.get_width() // 2 - 5, world_y + box.get_height())))

    # --- Navigation (Checkpoint3-06) ---
    def _update_navigation_button(self) -> None:
        self.nav_hover = self.nav_button_rect.collidepoint(input_manager.mouse_pos)
        if self.nav_hover and input_manager.mouse_pressed(1):
            self._open_overlay("navigation")

    def _draw_navigation_button(self, screen: pg.Surface) -> None:
        color = (110, 110, 110) if self.nav_hover else (80, 80, 80)
        pg.draw.rect(screen, color, self.nav_button_rect, border_radius=8)
        pg.draw.rect(screen, (220, 220, 220), self.nav_button_rect, 2, border_radius=8)
        label = self.overlay_text_font.render("Nav", True, (255, 255, 255))
        screen.blit(
            label,
            (self.nav_button_rect.centerx - label.get_width() // 2,
             self.nav_button_rect.centery - label.get_height() // 2),
        )

    def _refresh_navigation_targets(self) -> None:
        """現在マップ内で移動先候補を生成"""
        self.navigation_targets = []
        current_map = self.game_manager.current_map
        tile = GameSettings.TILE_SIZE
        # スポーン地点：ベースマップを目的地とし、今いるマップに応じて狙う座標を変える
        base_spawn = Position(self.game_manager.maps[self.base_map_key].spawn.x + tile // 2,
                              self.game_manager.maps[self.base_map_key].spawn.y + tile // 2)
        if current_map.path_name != self.base_map_key:
            # ベースマップへつながるテレポーターを目標にする
            base_tp = None
            for tp in current_map.teleporters:
                if tp.destination == self.base_map_key:
                    base_tp = tp
                    break
            if base_tp:
                spawn_target = Position(base_tp.pos.x + tile // 2, base_tp.pos.y + tile // 2)
                self.navigation_targets.append(("Spawn", spawn_target))
                # 目的マップと最終座標を保存できるように一緒に返す
                self.navigation_rects = []  # 後段で再計算
        else:
            self.navigation_targets.append(("Spawn", base_spawn))
        # ジムへのナビ（別マップのジム入口に行きたいケース用）
        if self.gym_map_key:
            gym_spawn = self._gym_target_point()
            if current_map.path_name != self.gym_map_key:
                for tp in current_map.teleporters:
                    dest = tp.destination.lower() if tp.destination else ""
                    # destination はファイル名の可能性が高いので、部分一致で判定
                    if self.gym_map_key.lower() in dest:
                        # ジムに入らないギリギリの手前で止める
                        pos = self._safe_point_before_teleport(tp)
                        self.navigation_targets.append(("Gym", pos))
                        break
            else:
                # ジム内なら内部目標を直接候補にする
                self.navigation_targets.append(("Gym", gym_spawn))
        # UIクリック領域の再生成は update で行う
        self.navigation_rects = []

    def _update_navigation_overlay(self) -> None:
        """ナビゲーションリストのクリック判定"""
        panel = self.overlay_panel_rect
        start_y = panel.y + 90
        item_height = 40
        self.navigation_rects = []
        for i, (_, pos) in enumerate(self.navigation_targets):
            rect = pg.Rect(panel.x + 40, start_y + i * (item_height + 10), panel.width - 80, item_height)
            self.navigation_rects.append((rect, pos))
            if rect.collidepoint(input_manager.mouse_pos) and input_manager.mouse_pressed(1):
                name = self.navigation_targets[i][0]
                # Spawn or Gymは多段移動に対応
                if name == "Spawn":
                    if self.game_manager.current_map.path_name != self.base_map_key:
                        final_pt = Position(self.game_manager.maps[self.base_map_key].spawn.x + GameSettings.TILE_SIZE // 2,
                                            self.game_manager.maps[self.base_map_key].spawn.y + GameSettings.TILE_SIZE // 2)
                        self._set_navigation_path(pos, name, target_map_key=self.base_map_key, final_point=final_pt)
                    else:
                        self._set_navigation_path(pos, name, target_map_key=self.base_map_key, final_point=pos)
                elif name == "Gym" and self.gym_map_key:
                    final_pt = self._gym_target_point()
                    target_map = self.gym_map_key
                    self._set_navigation_path(pos, name, target_map_key=target_map, final_point=final_pt)
                else:
                    self._set_navigation_path(pos, name)

    def _set_navigation_path(self, target_pos: Position, name: str, target_map_key: str | None = None, final_point: Position | None = None) -> None:
        if not self.game_manager.player:
            self.navigation_message = "プレイヤーがいません"
            return
        path = self._find_path(self.game_manager.player.position, target_pos)
        if path:
            self.navigation_path = path
            self.navigation_message = f"{name} までの経路を表示"
            self.navigation_active = True
            self.navigation_idx = 1  # 現在位置の次のノードからスタート
            self.navigation_goal_map = target_map_key or self.game_manager.current_map_key
            self.navigation_goal_point = final_point if final_point is not None else target_pos
            self._close_overlay()
        else:
            self.navigation_message = "経路が見つかりません"

    def _draw_navigation_overlay(self, screen: pg.Surface) -> None:
        panel = self.overlay_panel_rect
        title = self.overlay_title_font.render("Navigation", True, (255, 255, 255))
        screen.blit(title, (panel.centerx - title.get_width() // 2, panel.y + 20))
        info = self.overlay_small_font.render("行き先をクリックしてください", True, (220, 220, 220))
        screen.blit(info, (panel.x + 30, panel.y + 60))
        # リスト描画
        item_height = 40
        for i, (name, _) in enumerate(self.navigation_targets):
            rect = pg.Rect(panel.x + 40, panel.y + 90 + i * (item_height + 10), panel.width - 80, item_height)
            hovered = rect.collidepoint(input_manager.mouse_pos)
            color = (80, 80, 80, 220) if hovered else (60, 60, 60, 200)
            cell = pg.Surface(rect.size, pg.SRCALPHA)
            cell.fill(color)
            pg.draw.rect(cell, (200, 200, 200), cell.get_rect(), 2, border_radius=6)
            text = self.overlay_text_font.render(name, True, (255, 255, 255))
            cell.blit(text, (12, rect.height // 2 - text.get_height() // 2))
            screen.blit(cell, rect.topleft)
        # メッセージ
        if self.navigation_message:
            msg = self.overlay_small_font.render(self.navigation_message, True, (255, 255, 255))
            screen.blit(msg, (panel.x + 30, panel.bottom - 50))

    def _auto_move_navigation(self, dt: float) -> None:
        """BFSで求めた経路に沿って自動で移動する"""
        player = self.game_manager.player
        if not player or not self.navigation_path or self.navigation_idx >= len(self.navigation_path):
            self.navigation_active = False
            player.is_moving = False if player else False
            return
        # 現在位置（プレイヤー中心）と目標（矢印中心）を合わせる
        tile = GameSettings.TILE_SIZE
        cur = Position(player.position.x + tile / 2, player.position.y + tile / 2)
        tgt = self.navigation_path[self.navigation_idx]
        dx = tgt.x - cur.x
        dy = tgt.y - cur.y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < 2:
            # 次のノードへ
            self.navigation_idx += 1
            if self.navigation_idx >= len(self.navigation_path):
                self.navigation_active = False
                player.is_moving = False
                self.navigation_message = "到着しました"
                # 到着したら表示を消す
                self.navigation_path = []
                self.navigation_goal_map = None
                self.navigation_goal_point = None
            return
        # 移動量（プレイヤー中心を動かし、最後に左上へ戻す）
        step = player.speed * dt
        if step >= dist:
            cur.x = tgt.x
            cur.y = tgt.y
        else:
            cur.x += dx / dist * step
            cur.y += dy / dist * step
        # 中心座標から左上座標へ戻す
        player.position.x = cur.x - tile / 2
        player.position.y = cur.y - tile / 2
        # 向きとアニメーション
        if abs(dx) > abs(dy):
            player._set_direction(Direction.RIGHT if dx > 0 else Direction.LEFT)
        else:
            player._set_direction(Direction.DOWN if dy > 0 else Direction.UP)
        player.is_moving = True
        player.animation.update_pos(player.position)
        player.animation.update(dt)  # ナビ中も歩行アニメを進める
        # ナビ中はテレポートしない

    def _create_nav_arrow_surface(self) -> pg.Surface:
        """赤い三角矢印のサーフェスを生成"""
        surf = pg.Surface((28, 20), pg.SRCALPHA)
        pg.draw.polygon(surf, (220, 50, 50), [(0, 20), (28, 10), (0, 0)])
        return surf

    def _find_walkable_near(self, map_obj, center: Position) -> Position:
        """指定座標近傍で歩ける場所を返す（簡易探索）"""
        tile = GameSettings.TILE_SIZE
        offsets = [
            (0, 0),
            (0, tile),
            (0, -tile),
            (tile, 0),
            (-tile, 0),
            (tile, tile),
            (-tile, tile),
            (tile, -tile),
            (-tile, -tile),
        ]
        for dx, dy in offsets:
            pos = Position(center.x + dx, center.y + dy)
            rect = pg.Rect(pos.x - tile // 2, pos.y - tile // 2, tile, tile)
            if not map_obj.check_collision(rect):
                return pos
        return center

    def _safe_point_before_teleport(self, tp: Teleport) -> Position:
        """テレポートを踏まないギリギリ手前の位置（外から上方向に進入する前提）"""
        tile = GameSettings.TILE_SIZE
        return Position(tp.pos.x + tile // 2, tp.pos.y + tile + tile * 0.2)

    def _gym_target_point(self) -> Position:
        """ジム内での目標座標（少し奥の位置）"""
        if self.gym_map_key and self.gym_map_key in self.game_manager.maps:
            gmap = self.game_manager.maps[self.gym_map_key]
            # スポーン中央から少し奥へ（半タイル）進んだ位置を基点に、歩ける場所を探す
            base = Position(
                gmap.spawn.x + GameSettings.TILE_SIZE // 2,
                gmap.spawn.y + GameSettings.TILE_SIZE // 2 + GameSettings.TILE_SIZE * 0.5,
            )
            return self._find_walkable_near(gmap, base)
        # フォールバックは現在位置
        return self.game_manager.player.position if self.game_manager.player else Position(0, 0)

    def _find_path(self, start_pos: Position, goal_pos: Position) -> list[Position]:
        """現在マップ上でBFSを使って経路を探索（ブロック: collision_map）"""
        current_map = self.game_manager.current_map
        tile = GameSettings.TILE_SIZE
        width, height = current_map.tmxdata.width, current_map.tmxdata.height
        start = (int(start_pos.x // tile), int(start_pos.y // tile))
        goal = (int(goal_pos.x // tile), int(goal_pos.y // tile))
        def in_bounds(t: tuple[int, int]) -> bool:
            return 0 <= t[0] < width and 0 <= t[1] < height
        # ブロックセルを生成
        blocked: set[tuple[int, int]] = set()
        for rect in current_map._collision_map:
            sx = rect.x // tile
            sy = rect.y // tile
            w = max(1, rect.width // tile)
            h = max(1, rect.height // tile)
            for dx in range(w):
                for dy in range(h):
                    blocked.add((sx + dx, sy + dy))
        # 人物（敵トレーナー、ショップNPC）も障害物として扱う
        def add_entity_block(rect: pg.Rect) -> None:
            sx = rect.x // tile
            sy = rect.y // tile
            w = max(1, rect.width // tile)
            h = max(1, rect.height // tile)
            for dx in range(w):
                for dy in range(h):
                    blocked.add((sx + dx, sy + dy))
        for ent in self.game_manager.current_enemy_trainers:
            add_entity_block(ent.animation.rect)
        for npc in self.game_manager.current_shop_npcs:
            add_entity_block(npc.animation.rect)
        if not in_bounds(start) or not in_bounds(goal):
            return []
        if start in blocked or goal in blocked:
            return []
        # BFS
        q: deque[tuple[int, int]] = deque([start])
        came: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        while q:
            cur = q.popleft()
            if cur == goal:
                break
            for dx, dy in dirs:
                nxt = (cur[0] + dx, cur[1] + dy)
                if not in_bounds(nxt) or nxt in blocked or nxt in came:
                    continue
                came[nxt] = cur
                q.append(nxt)
        if goal not in came:
            return []
        # パス復元
        path_tiles: list[tuple[int, int]] = []
        node: tuple[int, int] | None = goal
        while node is not None:
            path_tiles.append(node)
            node = came[node]
        path_tiles.reverse()
        # タイル中央を経路点として返す
        return [Position(x * tile + tile // 2, y * tile + tile // 2) for x, y in path_tiles]

    def _draw_navigation_path(self, screen: pg.Surface, camera: PositionCamera) -> None:
        if not self.navigation_path:
            return
        # セグメントごとに赤い矢印を並べる
        arrow_base = self.nav_arrow_surface
        arrow_large = pg.transform.scale(arrow_base, (arrow_base.get_width() * 2, arrow_base.get_height() * 2))
        start_i = max(0, self.navigation_idx - 1)
        for i in range(start_i, len(self.navigation_path) - 1):
            a = self.navigation_path[i]
            b = self.navigation_path[i + 1]
            ax, ay = camera.transform_position(a)
            bx, by = camera.transform_position(b)
            dx = bx - ax
            dy = by - ay
            seg_len = math.hypot(dx, dy)
            if seg_len < 1:
                continue
            angle = math.degrees(math.atan2(-dy, dx))  # pygameはy軸下向きなので反転
            # タイル中央をたどるように短めのピッチで配置
            step = max(28, int(arrow_large.get_width() * 1.3))
            count = max(1, int(seg_len // step))
            arrow = pg.transform.rotate(arrow_large, angle)
            for j in range(count):
                # 矢印の中心を進行方向線上に均等配置
                t = (j + 0.5) / count
                px = ax + dx * t
                py = ay + dy * t
                rect = arrow.get_rect(center=(px, py))
                screen.blit(arrow, rect.topleft)
        # ゴール位置を強調
        goal = camera.transform_position(self.navigation_path[-1])
        pg.draw.circle(screen, (255, 70, 70), goal, 10, 2)
        if self.navigation_message:
            msg = self.overlay_small_font.render(self.navigation_message, True, (255, 255, 255))
            screen.blit(msg, (20, GameSettings.SCREEN_HEIGHT - msg.get_height() - 20))

    # --- Minimap ---
    def _rebuild_minimap(self) -> None:
        """現在のマップからミニマップ用の縮小サーフェスを作成"""
        current_map = self.game_manager.current_map
        max_w, max_h = 220, 140
        map_w, map_h = current_map.pixel_width, current_map.pixel_height
        scale = min(max_w / map_w, max_h / map_h)
        target_size = (max(1, int(map_w * scale)), max(1, int(map_h * scale)))
        surf = pg.transform.smoothscale(current_map._surface, target_size)
        self.minimap_surface = surf
        self.minimap_scale = scale
        self.minimap_map_key = self.game_manager.current_map_key

    def _draw_minimap(self, screen: pg.Surface, camera: PositionCamera) -> None:
        if self.minimap_surface is None:
            self._rebuild_minimap()
        if self.minimap_surface is None:
            return
        # パネル背景
        pad = 8
        bg_rect = pg.Rect(10, 10, self.minimap_surface.get_width() + pad * 2, self.minimap_surface.get_height() + pad * 2)
        bg = pg.Surface(bg_rect.size, pg.SRCALPHA)
        bg.fill((0, 0, 0, 160))
        pg.draw.rect(bg, (200, 200, 200), bg.get_rect(), 2, border_radius=6)
        screen.blit(bg, bg_rect.topleft)
        # マップを貼る
        screen.blit(self.minimap_surface, (bg_rect.x + pad, bg_rect.y + pad))
        # プレイヤー位置を描く
        if self.game_manager.player:
            px = int(self.game_manager.player.position.x * self.minimap_scale) + pad + bg_rect.x
            py = int(self.game_manager.player.position.y * self.minimap_scale) + pad + bg_rect.y
            pg.draw.circle(screen, (220, 40, 40), (px, py), 4)
        # 画面の表示範囲を枠で描く
        view_w = int(GameSettings.SCREEN_WIDTH * self.minimap_scale)
        view_h = int(GameSettings.SCREEN_HEIGHT * self.minimap_scale)
        view_x = int(camera.x * self.minimap_scale) + pad + bg_rect.x
        view_y = int(camera.y * self.minimap_scale) + pad + bg_rect.y
        pg.draw.rect(screen, (255, 215, 0), pg.Rect(view_x, view_y, view_w, view_h), 2)
        # テレポーターの位置を描く
        for tp in self.game_manager.current_map.teleporters:
            tx = int(tp.pos.x * self.minimap_scale) + pad + bg_rect.x
            ty = int(tp.pos.y * self.minimap_scale) + pad + bg_rect.y
            pg.draw.circle(screen, (255, 215, 0), (tx, ty), 3)

        # スピードブースト残り時間（ミニマップ下に表示）(speed potion ミニマップの表示)
        if self.game_manager.player and self.game_manager.player.speed_boost_timer > 0:
            remaining = math.ceil(self.game_manager.player.speed_boost_timer)
            label = self.overlay_small_font.render("Speed Boost", True, (255, 255, 255))
            timer = self.overlay_small_font.render(f"{remaining:02d}s", True, (255, 215, 120))
            text_x = bg_rect.x
            text_y = bg_rect.bottom + 6
            screen.blit(label, (text_x, text_y))
            screen.blit(timer, (text_x, text_y + label.get_height() + 2))

    #スライダーで音量変更
    def _set_audio_volume(self, value: float) -> None:
        vol = max(0.0, min(100.0, value))
        GameSettings.AUDIO_VOLUME = vol / 100.0 #音が0-100なのを0.01-1.0に変更
        #音が流れてるなら音量を変更
        if sound_manager.current_bgm:
            sound_manager.current_bgm.set_volume(GameSettings.AUDIO_VOLUME)

    # 設定オーバーレイのセーブボタン（Checkpoint2要件）
    #ゲームデータの保存(aves/game0.jsonに保存)
    def _save_game(self) -> None:
        self.game_manager.save("saves/game0.json")

    # 設定オーバーレイのロードボタン（Checkpoint2要件）
    def _load_game(self) -> None:
        manager = GameManager.load("saves/game0.json") #aves/game0.jsonの読み込みmanagerに入れる
        if manager:
            self.game_manager = manager #trueならロードしたのに入れる
            self.setting_slider.value = GameSettings.AUDIO_VOLUME * 100 #音量も合わせる
    # <<< Checkpoint2-02/04 END >>>
    # [Checkpoint2-06] BushSceneへ遷移し、草むら戦闘（捕獲）を開始
    def _enter_bush_scene(self) -> None:
        #bushsceneの呼び出し
        bush_scene = scene_manager.get_scene("bush")
        #bushsceneか確認
        if isinstance(bush_scene, BushScene):
            #bushsceneに情報を渡す
            bush_scene.start_encounter(self.game_manager)
            #草むらから出てまたすぐバトルになるのを防ぐ
            self.bush_cooldown = 0.5
            #bushsceneへの移動
            scene_manager.change_scene("bush")
