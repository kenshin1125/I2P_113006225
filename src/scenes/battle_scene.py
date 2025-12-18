import pygame as pg  # 画面描画・イベント用のPygame本体
from src.scenes.scene import Scene  # シーンの共通基底クラス
from src.core import GameManager  # ゲーム状態全体（マップ/敵/バッグなど）
from src.entities.enemy_trainer import EnemyTrainer  # トレーナー情報（座標・向き・モンスター）
from src.core.services import input_manager, scene_manager, sound_manager  # 入力管理 / シーン切替 / 音声制御
from src.utils import GameSettings, Logger  # 画面サイズ・音量設定等 / ログ出力
from src.sprites import Sprite  # 画像スプライト描画
from typing import override  # オーバーライド用アノテーション

class BattleScene(Scene):
    def __init__(self) -> None:#バトルのときに必要な箱を作る
        super().__init__()
        self.active_game_manager: GameManager | None = None
        self.enemy: EnemyTrainer | None = None
        self.enemy_map_key: str | None = None
        self.player_hp: int = 0
        self.enemy_hp: int = 0
        self.phase: str = "idle"
        self.message: str = "No battle"
        self.font = pg.font.SysFont("Arial", 28)
        self.title_font = pg.font.SysFont("Arial", 48)
        self.button_font = pg.font.SysFont("Arial", 32, bold=True)
        self.background = Sprite("backgrounds/background3.png", (GameSettings.SCREEN_WIDTH, GameSettings.SCREEN_HEIGHT))
        self.player_monster: dict[str, object] | None = None
        self.enemy_monster: dict[str, object] | None = None
        self.player_sprite: Sprite | None = None
        self.enemy_sprite: Sprite | None = None
        self.option_rects: dict[str, pg.Rect] = {}
        # バフ・アイテムメニュー状態
        self.player_atk_bonus: int = 0
        self.player_def_bonus: int = 0
        self.show_item_menu: bool = False
        self.item_rects: dict[str, pg.Rect] = {}
        self.evolution_message: str | None = None

    # [Checkpoint2-05] GameSceneから呼ばれ、敵データと自分の先頭モンスターをセット
    def start_battle(self, game_manager: GameManager, enemy: EnemyTrainer, map_key: str) -> None:
        #battlesceneに情報を渡す
        self.active_game_manager = game_manager
        self.enemy = enemy
        self.enemy_map_key = map_key
        #敵と自分のポケモンの決定
        self.player_monster = self._select_player_monster()
        self.enemy_monster = self._select_enemy_monster()
        # デフォルト値を補完（元素・攻撃・防御など）
        self._apply_monster_defaults(self.player_monster)
        self._apply_monster_defaults(self.enemy_monster)
        # バフ初期化
        self.player_atk_bonus = 0
        self.player_def_bonus = 0
        self.show_item_menu = False
        self.evolution_message = None
        #hpをバトル用の変数にコピー
        self.player_hp = int(self.player_monster["hp"])
        self.enemy_hp = int(self.enemy_monster["hp"])
        #ポケモンの大きさの設定
        sprite_size = (GameSettings.TILE_SIZE * 3, GameSettings.TILE_SIZE * 3)
        #ここでポケモンの絵の表示
        self.player_sprite = Sprite(self.player_monster["sprite_path"], sprite_size)
        self.enemy_sprite = Sprite(self.enemy_monster["sprite_path"], sprite_size)
        #敵出現の演出
        self.phase = "intro_enemy"
        #最初のメッセージ
        self.message = f"{self.enemy_monster['name']} appeared!"
        #それぞれの演出の時間の設定
        self.intro_timer = 0.0
        self.intro_enemy_duration = 1.2
        self.intro_player_duration = 1.2
        #選択肢ボタンの作成
        self._build_option_rects()
        #ログを残す
        Logger.info("Battle started")

    @override
    def enter(self) -> None: #シーン開始の関数
        sound_manager.play_bgm("RBY 107 Battle! (Trainer).ogg") #BGMを流す
        if GameSettings.AUDIO_MUTED:#muteなら流さない
            sound_manager.pause_all()

    @override
    #バトルが終わったらBGMを戻す
    def exit(self) -> None:
        sound_manager.play_bgm("RBY 103 Pallet Town.ogg")

    @override
    def update(self, dt: float) -> None: #毎フレーム呼ばれる関数
        #バトルが始まってない(return)
        if self.phase == "idle":
            return
        #敵登場演出
        if self.phase == "intro_enemy":
            self.intro_timer += dt #時間のカウント
            if self.intro_timer >= self.intro_enemy_duration or input_manager.key_pressed(pg.K_SPACE) or input_manager.key_pressed(pg.K_RETURN): #時間が経つorspace,enterを押すと次の画面へ
                self.phase = "intro_player"
                self.message = f"Go, {self.player_monster['name']}!" #messageを書く
                self.intro_timer = 0.0 #時間の初期化
            return
        if self.phase == "intro_player":
            self.intro_timer += dt
            if self.intro_timer >= self.intro_player_duration or input_manager.key_pressed(pg.K_SPACE) or input_manager.key_pressed(pg.K_RETURN): #時間が経つorspace,enterを押すと次の画面へ
                self.phase = "player_choice"
                self.message = f"What will {self.player_monster['name']} do?"#messageを書く
                self.intro_timer = 0.0 #時間の初期化
            return
        if self.phase == "evolution":
            # 簡易: 進化メッセージを表示したあとキー入力で終了
            if input_manager.key_pressed(pg.K_SPACE) or input_manager.key_pressed(pg.K_RETURN):
                self._close_battle()
            return
        #プレイヤーが行動を選ぶ
        if self.phase == "player_choice":
            #Aを押すと攻撃
            if input_manager.key_pressed(pg.K_a):
                self._player_attack()
            #Rを押すと逃げる
            elif input_manager.key_pressed(pg.K_r):
                self._player_run()
            #マウスでも可能
            elif input_manager.mouse_pressed(1):
                self._handle_option_click(input_manager.mouse_pos)
        elif self.phase == "item_menu":
            if input_manager.key_pressed(pg.K_ESCAPE):
                self.show_item_menu = False
                self.phase = "player_choice"
                self.message = "Item cancelled"
                return
            if input_manager.mouse_pressed(1):
                self._handle_item_click(input_manager.mouse_pos)
        #敵の番
        elif self.phase == "enemy_turn":
            self._enemy_attack()

    @override
    def draw(self, screen: pg.Surface) -> None:
        self.background.draw(screen) #バトルの背景画
        self._draw_monsters(screen) #ポケモンの絵
        self._draw_status_panels(screen) #ポケモンの近くに状態をかく
        self._draw_command_box(screen) #行動を選ぶ黒枠

    #攻撃処理
    def _player_attack(self) -> None:
        damage = self._calc_damage(self.player_monster, self.enemy_monster)
        self.enemy_hp = max(0, self.enemy_hp - damage)
        #メッセージ
        self.message = f"Player attacked! (-{damage})"
        if self.enemy_hp <= 0:
            self._finish_battle(True)
        else:
            self.phase = "enemy_turn"
            self.show_item_menu = False

    #逃げた際の処理
    def _player_run(self) -> None:
        self.message = "You ran away..."
        #hpを同期させる
        self._sync_player_monster_hp()
        #gamesceneに戻す
        self._close_battle()

    #敵の攻撃処理
    def _enemy_attack(self) -> None:
        #敵の攻撃中に自分が行動を選ばせないようにしてる
        self.phase = "busy"
        #ダメージ計算（属性・攻撃/防御を考慮）
        damage = self._calc_damage(self.enemy_monster, self.player_monster)
        self.player_hp = max(0, self.player_hp - damage)
        #hpをゲーム本体のhpと同期
        self._sync_player_monster_hp()
        #hpが０だと負け
        if self.player_hp <= 0:
            self.message = "You lost..."
            #gamesceneに戻す
            self._close_battle()
        else:
            self.message = f"Enemy attacked! (-{damage})"
            #自分のターンに移動
            self.phase = "player_choice"
            self.show_item_menu = False

    #バトル終了の処理
    def _finish_battle(self, player_won: bool) -> None:
        if player_won:
            self.message = "Enemy defeated!"
            if self.active_game_manager and self.enemy and self.enemy_map_key:
                #今いる敵の一覧mapの読み込み
                enemy_list = self.active_game_manager.enemy_trainers.get(self.enemy_map_key, [])
                #もし今いた相手を倒していたらその敵を消す
                if self.enemy in enemy_list:
                    enemy_list.remove(self.enemy)
            # 進化チェック
            self._try_evolution()
        #負けた場合
        else:
            self.message = "Defeated..."
        #hpを同期してシーンを戻す
        self._sync_player_monster_hp()
        # 進化メッセージがあれば表示フェーズへ
        if self.evolution_message:
            self.phase = "evolution"
        else:
            self._close_battle()

    #バトルを閉じる処理
    def _close_battle(self) -> None:
        #バトルを止める
        self.phase = "idle"
        #敵・マップキー・ゲーム状態をリセット
        self.enemy = None
        self.enemy_map_key = None
        self.active_game_manager = None
        #シーンを戻す
        scene_manager.change_scene("game")

    #プレイヤーのモンスターを呼ぶ(色々な情報を返す)
    def _select_player_monster(self) -> dict[str, object]:
        #ポケモンがいるかどうか確認
        if self.active_game_manager and self.active_game_manager.bag.monsters:
            #バックの先頭のポケモンを出す
            return self.active_game_manager.bag.monsters[0]
        #もしポケモンがいなかった場合使うポケモンの情報
        return {
            "name": "HeroMon",
            "hp": 100,
            "max_hp": 100,
            "level": 10,
            "attack": 20,
            "defense": 8,
            "element": "Normal",
            "sprite_path": "menu_sprites/menusprite1.png"
        }

    #敵ポケモンを選ぶ
    def _select_enemy_monster(self) -> dict[str, object]:
        #敵ポケモンがいて情報があるかどうか
        if self.enemy and hasattr(self.enemy, "monster_data"):
            #その情報を取り出す
            return getattr(self.enemy, "monster_data")
        #もしポケモンがいなかった場合使うポケモンの情報
        return {
            "name": "EnemyMon",
            "hp": 80,
            "max_hp": 80,
            "level": 8,
            "attack": 18,
            "defense": 6,
            "element": "Normal",
            "sprite_path": "menu_sprites/menusprite2.png"
        }

    # [Checkpoint2-05] トレーナーバトル用の配置（自ポケ右上寄り・敵左上寄り）
    #ポケモンを書いてる
    def _draw_monsters(self, screen: pg.Surface) -> None:
        #自分側のポケモン(trueなら)
        if self.player_sprite:
            rect = self.player_sprite.image.get_rect()#ポケモンサイズの箱を作る
            rect.center = (int(GameSettings.SCREEN_WIDTH * 0.4), int(GameSettings.SCREEN_HEIGHT * 0.58))#場所の指定
            screen.blit(self.player_sprite.image, rect)#画像を画面に貼り付け
        #敵側のポケモン
        if self.enemy_sprite:
            rect = self.enemy_sprite.image.get_rect()#ポケモンサイズの箱を作る
            rect.center = (int(GameSettings.SCREEN_WIDTH * 0.68), int(GameSettings.SCREEN_HEIGHT * 0.42))#場所の指定
            screen.blit(self.enemy_sprite.image, rect)#画像を画面に貼り付け

    # [Checkpoint2-05] LV/HP枠のレイアウト＋HP同期
    #ステータス画面の作成
    def _draw_status_panels(self, screen: pg.Surface) -> None:
        #もしポケモンがいないなら書かない
        if not self.player_monster or not self.enemy_monster:
            return
        #パネルの大きさの設定
        panel_width = 300
        panel_height = 115
        padding_bottom = 150
        #プレイヤーのパネルの設定
        player_panel = pg.Rect(30, GameSettings.SCREEN_HEIGHT - padding_bottom - panel_height - 10, panel_width, panel_height)
        #敵側のパネルの作成
        enemy_panel = pg.Rect(GameSettings.SCREEN_WIDTH - panel_width - 60, 70, panel_width, panel_height)
        #プレイヤー枠の中身をかく
        self._draw_panel(
            screen,
            player_panel,
            self.player_monster["name"],
            self.player_monster["level"],
            self.player_hp,
            self.player_monster["max_hp"],
            sprite_path=self.player_monster["sprite_path"],
            atk=self.player_monster.get("attack", 20),
            defense=self.player_monster.get("defense", 10),
            element=self.player_monster.get("element", "Normal"),
        )
        #敵枠の中身をかく
        self._draw_panel(
            screen,
            enemy_panel,
            self.enemy_monster["name"],
            self.enemy_monster["level"],
            self.enemy_hp,
            self.enemy_monster["max_hp"],
            sprite_path=self.enemy_monster["sprite_path"],
            align_right=True,
            atk=self.enemy_monster.get("attack", 18),
            defense=self.enemy_monster.get("defense", 8),
            element=self.enemy_monster.get("element", "Normal"),
        )
    #HP/名前/レベルのステータス枠を1個描く関数とバトル中のHPを本体データに同期する関数
    #ステータスパネル作成
    def _draw_panel(
        self,
        screen: pg.Surface,
        rect: pg.Rect,
        name: str,
        level: int,
        hp: int,
        max_hp: int,
        sprite_path: str | None = None,
        align_right: bool = False,
        atk: int | None = None,
        defense: int | None = None,
        element: str | None = None,
    ) -> None:
        #パネルの背景を３重でかく
        base_color = (250, 245, 216)
        outer_outline = (40, 26, 13)
        accent_outline = (227, 157, 64)
        #一番外側をかく
        pg.draw.rect(screen, outer_outline, rect, border_radius=12)
        #rectを小さくして金色の枠を作る
        accent_rect = rect.inflate(-4, -4)
        pg.draw.rect(screen, accent_outline, accent_rect, border_radius=10)
        #白の中身をかく
        inner = rect.inflate(-12, -12)
        inner_color = (255, 255, 255)
        pg.draw.rect(screen, inner_color, inner, border_radius=8)

        #左側のアイコンをかく
        icon_size = 48
        icon_rect = pg.Rect(inner.x + 12, inner.y + 18, icon_size, icon_size)
        #ポケモンの画像があるならかく
        if sprite_path:
            icon = Sprite(sprite_path, (icon_size, icon_size))
            screen.blit(icon.image, icon_rect)
        #なければ灰色の四角をおく
        else:
            pg.draw.rect(screen, (80, 80, 80), icon_rect, border_radius=8)

        #文字をかく座標を作る
        text_offset_x = icon_rect.right + 24
        #色とフォントの決定
        text_color = (40, 28, 20)
        name_font = pg.font.SysFont("Arial", 22, bold=True)
        info_font = pg.font.SysFont("Arial", 18)
        #名前のレベルの文字画像の作成
        name_text = name_font.render(name, True, text_color)
        lvl_text = info_font.render(f"Lv.{level}", True, text_color)
        #hpバーの計算
        hp_ratio = max(0.0, min(1.0, hp / max_hp if max_hp else 0))
        #HPバーの横幅を決める計算
        hp_bar_width = inner.width - (text_offset_x - inner.x) - 100
        #hpバーの位置
        hp_bar_y = inner.y + 44
        hp_bar_x = text_offset_x
        #hp数値の文字を作る
        hp_text = info_font.render(f"{hp}/{max_hp}", True, text_color)
        #文字の配置座標を決めて貼る
        name_y = inner.y + 6
        hp_y = hp_bar_y + 16
        lvl_x = hp_bar_x + hp_bar_width + 8
        lvl_y = hp_bar_y - lvl_text.get_height() // 2 + 7
        #いま計算した座標に文字を貼る
        screen.blit(name_text, (text_offset_x, name_y))
        screen.blit(lvl_text, (lvl_x, lvl_y))
        screen.blit(hp_text, (hp_bar_x, hp_y))
        # 属性・ATK/DEF表示（省略可）
        if element or atk is not None or defense is not None:
            attr_parts = []
            if element:
                attr_parts.append(f"{element}")
            if atk is not None:
                attr_parts.append(f"ATK {atk}")
            if defense is not None:
                attr_parts.append(f"DEF {defense}")
            attr_text = "  ".join(attr_parts)
            attr_surf = info_font.render(attr_text, True, text_color)
            screen.blit(attr_surf, (text_offset_x, hp_bar_y + 32))
        #HPバーを描く
        hp_bar_bg = pg.Rect(hp_bar_x, hp_bar_y, hp_bar_width, 12)#hpバーの背景の黒枠
        #背景と同じRectをコピーして幅だけ hp_ratio 分に縮める
        hp_bar = hp_bar_bg.copy()
        hp_bar.width = int(hp_bar.width * hp_ratio)
        #背景バー（灰色）→ その上に緑の残量バー
        pg.draw.rect(screen, (80, 80, 80), hp_bar_bg, border_radius=4)
        pg.draw.rect(screen, (120, 230, 120), hp_bar, border_radius=4)

    #モンスターがいなければ何もしない
    def _sync_player_monster_hp(self) -> None:
        if not self.active_game_manager or not self.player_monster:
            return
        #hpを０−１００にする
        current_hp = max(0, min(self.player_hp, self.player_monster["max_hp"]))
        #battlesceneのplayerのHPを更新
        self.player_monster["hp"] = current_hp
        #本体のhpも更新
        monsters = self.active_game_manager.bag.monsters
        if monsters:
            monsters[0]["hp"] = current_hp

    # --- 属性とステータスのデフォルト/ダメージ計算 ---
    def _apply_monster_defaults(self, mon: dict[str, object]) -> None:
        mon.setdefault("element", "Normal")
        mon.setdefault("attack", 20)
        mon.setdefault("defense", 10)
        # 進化関連のデフォルト（未使用でも保持しておく）
        mon.setdefault("evolve_level", mon.get("level", 1) + 5)
        mon.setdefault("evolve_sprite_path", mon.get("sprite_path", "menu_sprites/menusprite1.png"))
        mon.setdefault("evolved", False)

    def _calc_damage(self, attacker: dict[str, object], defender: dict[str, object]) -> int:
        atk = int(attacker.get("attack", 20))
        defense = int(defender.get("defense", 10))
        # 自分側のバフを考慮
        if attacker is self.player_monster:
            atk += self.player_atk_bonus
        if defender is self.player_monster:
            defense += self.player_def_bonus
        # 基本ダメージ
        base = max(5, atk - int(defense * 0.3))
        multiplier = self._element_multiplier(
            str(attacker.get("element", "Normal")),
            str(defender.get("element", "Normal"))
        )
        dmg = int(base * multiplier)
        return max(1, dmg)

    def _element_multiplier(self, atk_elem: str, def_elem: str) -> float:
        atk_elem = atk_elem.capitalize()
        def_elem = def_elem.capitalize()
        # 強み/弱み: Water>Fire, Fire>Grass, Grass>Water
        strong = {("Water", "Fire"), ("Fire", "Grass"), ("Grass", "Water")}
        if (atk_elem, def_elem) in strong:
            return 1.5
        if (def_elem, atk_elem) in strong:
            return 0.75
        return 1.0

    # --- Item handling ---
    def _handle_item_click(self, pos: tuple[int, int]) -> None:
        # 戻るボタン優先
        if hasattr(self, "item_back_rect") and self.item_back_rect.collidepoint(pos):
            self.show_item_menu = False
            self.phase = "player_choice"
            self.message = "What will you do?"
            return
        for name, rect in self.item_rects.items():
            if rect.collidepoint(pos):
                self._use_item(name)
                return

    def _use_item(self, name: str) -> None:
        if not self.active_game_manager:
            return
        bag = self.active_game_manager.bag
        if name == "Heal Potion":
            if bag.remove_item("Heal Potion", 1):
                heal = min(50, self.player_monster["max_hp"] - self.player_hp)
                self.player_hp = min(self.player_monster["max_hp"], self.player_hp + heal)
                self.message = f"Healed {heal} HP!"
                self.show_item_menu = False
                self.phase = "enemy_turn"
            else:
                self.message = "No Heal Potion!"
        elif name == "Strength Potion":
            if bag.remove_item("Strength Potion", 1):
                self.player_atk_bonus += 8
                self.message = "ATK rose!"
                self.show_item_menu = False
                self.phase = "enemy_turn"
            else:
                self.message = "No Strength Potion!"
        elif name == "Defense Potion":
            if bag.remove_item("Defense Potion", 1):
                self.player_def_bonus += 6
                self.message = "DEF rose!"
                self.show_item_menu = False
                self.phase = "enemy_turn"
            else:
                self.message = "No Defense Potion!"

    def _get_item_count(self, name: str) -> int:
        if not self.active_game_manager:
            return 0
        return self.active_game_manager.bag.get_item_count(name)

    # --- Evolution ---
    def _try_evolution(self) -> None:
        if not self.player_monster:
            return
        level = int(self.player_monster.get("level", 1))
        evolve_level = int(self.player_monster.get("evolve_level", level + 5))
        evolved = bool(self.player_monster.get("evolved", False))
        if evolved or level < evolve_level:
            return
        # 進化を適用
        self._apply_evolution(self.player_monster)
        self.evolution_message = f"{self.player_monster['name']} evolved!"
        # バトル中のスプライトも更新
        sprite_size = (GameSettings.TILE_SIZE * 3, GameSettings.TILE_SIZE * 3)
        self.player_sprite = Sprite(self.player_monster["sprite_path"], sprite_size)

    def _apply_evolution(self, mon: dict[str, object]) -> None:
        mon["evolved"] = True
        # ステータス上昇（増加分を現在HPに加算する）
        old_max = mon.get("max_hp", 100)
        new_max = int(old_max * 1.25)
        hp_gap = new_max - old_max
        mon["max_hp"] = new_max
        new_hp = min(new_max, mon.get("hp", old_max) + hp_gap)
        mon["hp"] = new_hp
        # バトル中表示用のHPも進化後値にそろえる
        if mon is self.player_monster:
            self.player_hp = new_hp
        mon["attack"] = int(mon.get("attack", 20) * 1.2) + 2
        mon["defense"] = int(mon.get("defense", 10) * 1.2) + 1
        # アセット切替
        mon["sprite_path"] = self._determine_evolve_sprite(mon)

    def _determine_evolve_sprite(self, mon: dict[str, object]) -> str:
        current = mon.get("sprite_path", "menu_sprites/menusprite1.png")
        mapping = {
            "menu_sprites/menusprite1.png": "menu_sprites/menusprite3.png",
            "menu_sprites/menusprite2.png": "menu_sprites/menusprite4.png",
            "menu_sprites/menusprite3.png": "menu_sprites/menusprite2.png",
            "menu_sprites/menusprite4.png": "menu_sprites/menusprite1.png",
        }
        return mapping.get(current, mon.get("evolve_sprite_path", current))

    # [Checkpoint2-05] 下部コマンドウィンドウ（EnemyMon appeared → Go → What will ...）
    #バトル画面のいちばん下にある「メッセージ＋コマンド（選択肢）欄」を描く関数
    def _draw_command_box(self, screen: pg.Surface) -> None:
        #黒枠を作る
        box_height = 150
        #画面下に黒枠を設置する
        box_rect = pg.Rect(0, GameSettings.SCREEN_HEIGHT - box_height, GameSettings.SCREEN_WIDTH, box_height)
        #箱を真っ黒にする
        pg.draw.rect(screen, (20, 20, 20), box_rect)
        #枠を灰色で覆う
        pg.draw.rect(screen, (80, 80, 80), box_rect, 2)
        #メッセージを表示
        msg_text = self.evolution_message if self.phase == "evolution" and self.evolution_message else self.message
        msg = self.font.render(msg_text, True, (255, 255, 255))
        #コマンド欄の左上あたりにメッセージを表示
        screen.blit(msg, (40, GameSettings.SCREEN_HEIGHT - box_height + 25))
        #プレイヤーのターンなら選択肢ボタンをかく
        if self.phase == "player_choice":
            #登録されてる全ボタンを順番に描くループ
            for label, rect in self.option_rects.items():
                #ボタンの中身の色と形の設定
                pg.draw.rect(screen, (240, 220, 180), rect, border_radius=6)
                #ボタンの枠組み
                pg.draw.rect(screen, (120, 100, 70), rect, 2, border_radius=6)
                #ボタンの中身の言葉
                text = self.button_font.render(label, True, (40, 30, 20))
                #ボタンのど真ん中に文字が来るように貼り付け
                screen.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))
        if self.show_item_menu and self.phase == "item_menu":
            self._draw_item_menu(screen, box_rect)

    # [Checkpoint2-05] 戦闘コマンドの配置（スペック準拠で4ボタン）
    #コマンドボタンのあたり判定の作成
    def _build_option_rects(self) -> None:
        #ボタンのサイズ
        button_width = 140
        button_height = 40
        #ボタンの隙間
        spacing = 20
        #ボタンに書く言葉
        labels = ["Fight (A)", "Item", "Switch", "Run (R)"]
        #ボタンを並べた時の横幅計算
        total_width = button_width * len(labels) + spacing * (len(labels) - 1)
        #一番左のボタンの横位置の決定
        start_x = (GameSettings.SCREEN_WIDTH - total_width) // 2
        #ボタンの縦位置の決定
        y = GameSettings.SCREEN_HEIGHT - 80
        #rectの空箱作成
        self.option_rects = {}
        #rectを順に作る
        for idx, label in enumerate(labels):
            rect = pg.Rect(start_x + idx * (button_width + spacing), y, button_width, button_height)
            #辞書に保存
            self.option_rects[label] = rect

    def _draw_item_menu(self, screen: pg.Surface, box_rect: pg.Rect) -> None:
        names = ["Heal Potion", "Strength Potion", "Defense Potion"]
        self.item_rects = {}
        # 横幅を半分にして余白を作る（高さは戻す）
        btn_h = 32
        spacing = 10
        start_x = box_rect.x + 24
        start_y = box_rect.y + 28
        btn_w = (box_rect.width - 48) // 2
        for idx, name in enumerate(names):
            rect = pg.Rect(start_x, start_y + idx * (btn_h + spacing), btn_w, btn_h)
            self.item_rects[name] = rect
            pg.draw.rect(screen, (60, 60, 60), rect, border_radius=6)
            pg.draw.rect(screen, (180, 180, 180), rect, 2, border_radius=6)
            count = self._get_item_count(name)
            label = f"{name} (x{count})"
            color = (240, 240, 240) if count > 0 else (160, 160, 160)
            text = self.button_font.render(label, True, color)
            screen.blit(text, (rect.x + 12, rect.centery - text.get_height() // 2))
        # 戻るボタン
        back_w, back_h = 100, 30
        back_x = box_rect.right - back_w - 20
        back_y = box_rect.bottom - back_h - 16
        self.item_back_rect = pg.Rect(back_x, back_y, back_w, back_h)
        pg.draw.rect(screen, (90, 90, 90), self.item_back_rect, border_radius=6)
        pg.draw.rect(screen, (190, 190, 190), self.item_back_rect, 2, border_radius=6)
        back_txt = self.button_font.render("Back", True, (240, 240, 240))
        screen.blit(back_txt, (self.item_back_rect.centerx - back_txt.get_width() // 2,
                               self.item_back_rect.centery - back_txt.get_height() // 2))

    def _handle_option_click(self, pos: tuple[int, int]) -> None:
        #fightのrectが存在かつクリック位置がそのRect内
        if self.option_rects.get("Fight (A)") and self.option_rects["Fight (A)"].collidepoint(pos):
            self._player_attack()
         #runのrectが存在かつクリック位置がそのRect内
        elif self.option_rects.get("Run (R)") and self.option_rects["Run (R)"].collidepoint(pos):
            self._player_run()
        elif self.option_rects.get("Item") and self.option_rects["Item"].collidepoint(pos):
            self.show_item_menu = True
            self.phase = "item_menu"
            # メッセージ欄は空にして項目だけ表示
            self.message = ""
        # SwitchやItemは今後の拡張用。Checkpoint2時点では未実装
# <<< Checkpoint2-05 END >>>
# ▲ Checkpoint2 追加コードここまで / Added code ends here
# ------------------------------------------------------------
