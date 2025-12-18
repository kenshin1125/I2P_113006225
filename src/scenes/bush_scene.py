import random  # 草むらポケモンをランダム抽選
import pygame as pg  # 描画・入力イベント

from src.scenes.scene import Scene  # ベースシーンクラス
from src.core import GameManager  # ゲーム全体の状態管理
from src.core.services import input_manager, scene_manager, sound_manager  # 入力/シーン切替/音声
from src.utils import GameSettings  # 画面サイズなど共通設定
from src.utils.definition import Monster  # モンスター型定義（dictみたいな構造）
from typing import override  # オーバーライド明示
from src.sprites import Sprite  # スプライト描画


# 草むらで出てくる野生モンスターの候補リスト
WILD_MONSTERS: list[Monster] = [
    {"name": "Caterpie", "hp": 30, "max_hp": 30, "level": 4, "attack": 14, "defense": 6, "element": "Grass", "sprite_path": "menu_sprites/menusprite1.png"},
    {"name": "Weedle", "hp": 28, "max_hp": 28, "level": 4, "attack": 15, "defense": 6, "element": "Grass", "sprite_path": "menu_sprites/menusprite2.png"},
    {"name": "Oddish", "hp": 35, "max_hp": 35, "level": 6, "attack": 16, "defense": 7, "element": "Grass", "sprite_path": "menu_sprites/menusprite3.png"},
    {"name": "Pidgey", "hp": 32, "max_hp": 32, "level": 5, "attack": 17, "defense": 8, "element": "Fire", "sprite_path": "menu_sprites/menusprite4.png"},
]
# 野生ポケモン用の属性プール（ランダム付与）
WILD_ELEMENTS: list[str] = ["Fire", "Water", "Grass", "Electric", "Normal", "Ice", "Rock"]


class BushScene(Scene):
    def __init__(self) -> None:
        super().__init__()
        # GameSceneから渡されたGameManager（草むら中だけ保持）
        #ゲームの情報をgamesceneから渡される
        self.game_manager: GameManager | None = None
        
        # 草むらで遭遇した野生モンスターを入れる箱
        self.monster: Monster | None = None
        
        # 草むらシーンの状態（intro/choice/caught/finishedなど）最初はidle
        self.state: str = "idle"
        
        # 文字表示用フォント
        self.font = pg.font.SysFont("Arial", 32)
        self.title_font = pg.font.SysFont("Arial", 48)
        
        # 画面下に出るメッセージ
        self.message = ""
        
        # コマンドボタン文字用フォント
        self.option_font = pg.font.SysFont("Arial", 28, bold=True)
        
        # ボタンのRectの辞書（Fight/Item/Catch/Run）
        self.option_rects: dict[str, pg.Rect] = {}
        
        # 背景（battle_sceneと同じ画像を流用）
        self.background = Sprite(
            "backgrounds/background3.png",
            (GameSettings.SCREEN_WIDTH, GameSettings.SCREEN_HEIGHT)
        )
        
        # プレイヤー側の先頭モンスター（バッグの1匹目）
        self.player_monster: Monster | None = None
        
        # プレイヤー側の表示用スプライト
        self.player_sprite: Sprite | None = None
        
        # 敵（野生モンスター）の表示用スプライト
        self.enemy_sprite: Sprite | None = None

    # [Checkpoint2-06] 草むら遭遇の初期化（ランダム敵＆自分の先頭モンスターをセット）
    #ここで情報を入れる
    def start_encounter(self, game_manager: GameManager) -> None:
        # GameSceneから渡されたmanagerを保持
        self.game_manager = game_manager
        
        # 野生モンスターを候補からランダム選択し、copyして保持
        self.monster = random.choice(WILD_MONSTERS).copy()
        # 出現時に属性をランダムで付与（ベース属性を上書き）
        self.monster["element"] = random.choice(WILD_ELEMENTS)
        
        # 自分の先頭モンスターを取得
        self.player_monster = self._select_player_monster()
        
        # スプライトサイズ(ポケモンのサイズ)はタイル3枚分（battleと同じ）
        sprite_size = (GameSettings.TILE_SIZE * 3, GameSettings.TILE_SIZE * 3)
        
        # 自分側と敵側のスプライトを準備
        self.player_sprite = Sprite(self.player_monster["sprite_path"], sprite_size)
        self.enemy_sprite = Sprite(self.monster["sprite_path"], sprite_size)
        
        # まず敵登場フェーズから開始
        self.state = "intro_enemy"
        
        # 初期メッセージ
        self.message = f"Wild {self.monster['name']} appeared!"
        
        # フェーズ用タイマー初期化
        self.intro_timer = 0.0
        
        # 敵登場、自分登場の演出時間
        self.intro_enemy_duration = 1.0
        self.intro_player_duration = 1.0
        
        # コマンドボタン配置を準備
        self._build_option_rects()

    @override
    def enter(self) -> None:
        # 草むら専用の野生バトルBGM再生
        sound_manager.play_bgm("RBY 110 Battle! (Wild Pokemon).ogg")
        # ミュートなら停止
        if GameSettings.AUDIO_MUTED:
            sound_manager.pause_all()

    @override
    def exit(self) -> None:
        # 草むら終了時は通常フィールドBGMへ戻す
        sound_manager.play_bgm("RBY 103 Pallet Town.ogg")
        # ミュートなら停止
        if GameSettings.AUDIO_MUTED:
            sound_manager.pause_all()

    @override
    def update(self, dt: float) -> None: #毎フレーム呼ぶ関数
        # --- 敵登場フェーズ ---
        if self.state == "intro_enemy":#敵演出中
            self.intro_timer += dt  # 経過時間を進める
            # 一定時間経つ or spaceで次へ
            if self.intro_timer >= self.intro_enemy_duration or input_manager.key_pressed(pg.K_SPACE):#時間が経つorspace,enterを押すと次の画面へ
                self.phase = "intro_player" 
                self.state = "intro_player"  # 自分登場フェーズへ
                # プレイヤー名があれば表示、なければ"Trainer"
                self.message = f"Go, {self.game_manager.player.player_name if self.game_manager and self.game_manager.player else 'Trainer'}!"
                self.intro_timer = 0.0  # タイマーリセット
            return

        # --- 自分登場フェーズ ---
        if self.state == "intro_player":
            self.intro_timer += dt
            # 時間経過 or spaceで行動選択へ
            if self.intro_timer >= self.intro_player_duration or input_manager.key_pressed(pg.K_SPACE):#時間が経つorspace,enterを押すと次の画面へ
                self.phase = "intro_player"
                self.state = "choice"
                self.message = f"What will you do?"
            return

        # --- 行動選択フェーズ ---
        if self.state == "choice":
            # マウスでボタン選択
            if input_manager.mouse_pressed(1):
                self._handle_option_click(input_manager.mouse_pos) #どのボタンを押したのか判定

            # Aキーで攻撃
            if input_manager.key_pressed(pg.K_a):
                self._attempt_attack()

            # Rキーで逃走（finishedへ）
            elif input_manager.key_pressed(pg.K_r):
                self.message = "Got away safely. Press Enter."
                self.state = "finished"

            # Cキーで捕獲
            elif input_manager.key_pressed(pg.K_c):
                self._catch_monster()

        # --- 捕獲後フェーズ ---
        elif self.state == "caught":
            # EnterでGameSceneへ戻る
            if input_manager.key_pressed(pg.K_RETURN):
                self._close_scene()

        # --- 終了（逃げた/倒したなど）フェーズ ---
        elif self.state == "finished":
            # EnterでGameSceneへ戻る
            if input_manager.key_pressed(pg.K_RETURN):
                self._close_scene()

    @override
    def draw(self, screen: pg.Surface) -> None:
        # 背景 → モンスター → ステータス → 下部コマンド の順に描く
        self.background.draw(screen)
        self._draw_monsters(screen)
        self._draw_status_panels(screen)
        self._draw_command_box(screen)

    # [Checkpoint2-06] 捕獲→Bagへ即時追加→オーバーレイで確認できる
    #捕獲処理
    def _catch_monster(self) -> None:
        # 捕獲可能な状態（managerとmonsterがある）なら(バックの容量がへいきand野生モンスターがいる)
        if self.game_manager and self.monster:
            # Bagにそのまま追加（copyして安全に）
            self.game_manager.bag.add_monster(self.monster.copy())
            # 捕獲メッセージ
            self.message = f"Caught {self.monster['name']}! Press Enter."
            # caughtフェーズへ
            self.state = "caught"
        else:
            # 何も起きない保険(捕獲できない条件)
            self.message = "Nothing happened."
            self.state = "finished"

    # 草むらシーンを閉じてGameSceneに戻る
    def _close_scene(self) -> None:
        #何もしてない状態に戻す
        self.state = "idle"
        #野生モンスターの情報を消す
        self.monster = None
        #gamesceneからもらった情報を消す
        self.game_manager = None
        #gamesceneに戻す
        scene_manager.change_scene("game")

    # 自分の先頭モンスターを選ぶ（バッグ0番）
    def _select_player_monster(self) -> Monster:
        #gamesceneから情報を受け取ってポケモンが1匹以上いる
        if self.game_manager and self.game_manager.bag.monsters:
            return self.game_manager.bag.monsters[0]
        # いなければダミー
        return {"name": "HeroMon", "hp": 100, "max_hp": 100, "level": 10, "sprite_path": "menu_sprites/menusprite1.png"}

    # [Checkpoint2-06] "Fight/Item/Catch/Run" ボタン配置の位置と大きさと当たり判定
    def _build_option_rects(self) -> None:
        #ボタンの基本設定
        button_width = 140
        button_height = 40
        spacing = 20
        labels = ["Fight (A)", "Item", "Catch", "Run (R)"]

        # 4ボタンの横幅合計を計算して中央揃え
        total_width = button_width * len(labels) + spacing * (len(labels) - 1)
        #x座標を決める
        start_x = (GameSettings.SCREEN_WIDTH - total_width) // 2

        # 画面下から80px上に配置
        y = GameSettings.SCREEN_HEIGHT - 80

        # Rect辞書を作成(空)
        self.option_rects = {}
        #ボタンを1つずつ作る
        for i, label in enumerate(labels):
            rect = pg.Rect(start_x + i * (button_width + spacing), y, button_width, button_height)
            self.option_rects[label] = rect

    # ボタンクリック時の判定 collidepoint(pos)でクリックの位置が適切か判定
    def _handle_option_click(self, pos: tuple[int, int]) -> None:
        # Fightクリック → 攻撃
        if self.option_rects.get("Fight (A)") and self.option_rects["Fight (A)"].collidepoint(pos):
            self._attempt_attack()
        # Catchクリック → 捕獲
        elif self.option_rects.get("Catch") and self.option_rects["Catch"].collidepoint(pos):
            self._catch_monster()
        # Runクリック → 逃走
        elif self.option_rects.get("Run (R)") and self.option_rects["Run (R)"].collidepoint(pos):
            self.message = "Got away safely. Press Enter."
            self.state = "finished"

    # [Checkpoint2-06] 草むらでも攻撃→HP減少→敵も反撃
    def _attempt_attack(self) -> None:
        # どちらかのデータが無ければ処理しない
        #自分と相手のポケモンがいるかどうか
        if not self.monster or not self.player_monster:
            return

        damage = 15  # プレイヤー攻撃ダメージ固定
        # 野生モンスターのHPを減らす
        self.monster["hp"] = max(0, self.monster["hp"] - damage)

        # HPが0なら弱って捕獲チャンス
        if self.monster["hp"] <= 0:
            self.message = f"The wild {self.monster['name']} is weakened! Try catching it."
        else:
            # まだ生きてるなら攻撃メッセージ＋反撃
            self.message = f"You attack! {self.monster['name']} HP {self.monster['hp']}/{self.monster['max_hp']}."
            self._wild_counter_attack()

    # 野生側の反撃処理
    def _wild_counter_attack(self) -> None:
        #自分のポケモンがいるかどうか
        if not self.player_monster:
            return

        damage = 10  # 反撃ダメージ固定
        # プレイヤー側HPを減らす
        self.player_monster["hp"] = max(0, self.player_monster["hp"] - damage)

        # HP0なら戦闘終了
        if self.player_monster["hp"] <= 0:
            self.message += f" The wild {self.monster['name']} fought back! Your partner fainted..."
            self.state = "finished"
        else:
            # 生きていれば反撃メッセージ
            self.message += f" The wild {self.monster['name']} struck back! HP {self.player_monster['hp']}/{self.player_monster['max_hp']}."

    # モンスター画像の配置（battle_sceneと同じ位置）
    def _draw_monsters(self, screen: pg.Surface) -> None:
        #自分のポケモン
        if self.player_sprite:
            #rectを作る
            rect = self.player_sprite.image.get_rect()
            #画像の中心をどこに置くか決める
            rect.center = (int(GameSettings.SCREEN_WIDTH * 0.4), int(GameSettings.SCREEN_HEIGHT * 0.58))
            #画像を貼り付け
            screen.blit(self.player_sprite.image, rect)
        #敵側
        if self.enemy_sprite:
            #rectを作る
            rect = self.enemy_sprite.image.get_rect()
            #画像の中心をどこに置くか決める
            rect.center = (int(GameSettings.SCREEN_WIDTH * 0.68), int(GameSettings.SCREEN_HEIGHT * 0.42))
             #画像を貼り付け
            screen.blit(self.enemy_sprite.image, rect)

    # [Checkpoint2-06] 草むら用ステータス枠（battle_sceneと同じUI） HP/名前/レベルが出るステータス枠を2つ描く処理
    def _draw_status_panels(self, screen: pg.Surface) -> None:
        #自分と敵のポケモンがいるかどうか
        if not self.player_monster or not self.monster:
            return
        #枠のサイズ決め
        panel_width = 300
        panel_height = 115

        # プレイヤー枠（左下寄り）
        player_panel = pg.Rect(30, GameSettings.SCREEN_HEIGHT - 150 - panel_height - 10, panel_width, panel_height)
        # 敵枠（右上寄り）
        enemy_panel = pg.Rect(GameSettings.SCREEN_WIDTH - panel_width - 60, 70, panel_width, panel_height)

        # パネル描画（battleと同じデザイン）枠のデザイン描画 + 名前/レベル/HPバー/アイコン描画をかく
        self._draw_panel(
            screen,
            player_panel,
            self.player_monster["name"],
            self.player_monster["level"],
            self.player_monster["hp"],
            self.player_monster["max_hp"],
            self.player_monster["sprite_path"],
            element=self.player_monster.get("element", "Normal"),
            atk=self.player_monster.get("attack"),
            defense=self.player_monster.get("defense"),
        )
        self._draw_panel(
            screen,
            enemy_panel,
            self.monster["name"],
            self.monster["level"],
            self.monster["hp"],
            self.monster["max_hp"],
            self.monster["sprite_path"],
            element=self.monster.get("element", "Normal"),
            atk=self.monster.get("attack"),
            defense=self.monster.get("defense"),
        )

    # パネル1個分の描画（battle_sceneのデザイン流用版）
    #黒枠ないのステータスの記入
    def _draw_panel(
        self,
        screen: pg.Surface,
        rect: pg.Rect,
        name: str,
        level: int,
        hp: int,
        max_hp: int,
        sprite_path: str,
        element: str | None = None,
        atk: int | None = None,
        defense: int | None = None,
    ) -> None:
        base_color = (250, 245, 216)
        outer_outline = (40, 26, 13)#外側の色　黒茶色
        accent_outline = (227, 157, 64)#内側の色　金色

        # 3重枠のパネル背景
        pg.draw.rect(screen, outer_outline, rect, border_radius=12) #一番外側
        accent_rect = rect.inflate(-4, -4)#黒枠の内側　ここではサイズ変更
        pg.draw.rect(screen, accent_outline, accent_rect, border_radius=10)
        inner = rect.inflate(-12, -12)#中身の白いろ　ここではサイズ変更
        pg.draw.rect(screen, (255, 255, 255), inner, border_radius=8)

        # 左側アイコン(黒枠内のポケモン)
        icon_size = 48 #サイズ
        icon_rect = pg.Rect(inner.x + 12, inner.y + 18, icon_size, icon_size) #位置
        icon = Sprite(sprite_path, (icon_size, icon_size)) #画像をサイズに合わせる
        screen.blit(icon.image, icon_rect) #これを画面に貼る

        # 名前/Lv/HPバー
        #文字の色とフォントを決定
        text_color = (40, 28, 20)
        name_font = pg.font.SysFont("Arial", 22, bold=True)
        info_font = pg.font.SysFont("Arial", 18)

        #文字の開始位置
        text_offset_x = icon_rect.right + 24
        #名前とLVの文字の作成
        name_text = name_font.render(name, True, text_color)
        lvl_text = info_font.render(f"Lv.{level}", True, text_color)

        #hpバーの計算
        hp_ratio = max(0.0, min(1.0, hp / max_hp if max_hp else 0))
        hp_bar_width = inner.width - (text_offset_x - inner.x) - 100
        hp_bar_y = inner.y + 44
        hp_bar_x = text_offset_x

        #hpを文字画像にする
        hp_text = info_font.render(f"{hp}/{max_hp}", True, text_color)
        #レベル表示の位置計算
        lvl_x = hp_bar_x + hp_bar_width + 8
        lvl_y = hp_bar_y - lvl_text.get_height() // 2 + 7

        #名前、lv、hpをはる
        screen.blit(name_text, (text_offset_x, inner.y + 6))
        screen.blit(lvl_text, (lvl_x, lvl_y))
        screen.blit(hp_text, (hp_bar_x, hp_bar_y + 16))

        # 属性・ATK/DEFの簡易表示
        if element or atk is not None or defense is not None:
            attr_parts: list[str] = []
            if element:
                attr_parts.append(str(element))
            if atk is not None:
                attr_parts.append(f"ATK {atk}")
            if defense is not None:
                attr_parts.append(f"DEF {defense}")
            attr_text = "  ".join(attr_parts)
            attr_surf = info_font.render(attr_text, True, text_color)
            screen.blit(attr_surf, (text_offset_x, hp_bar_y + 32))

        # HPバー描画
        hp_bar_bg = pg.Rect(hp_bar_x, hp_bar_y, hp_bar_width, 12) #hpバーを作る
        hp_bar = hp_bar_bg.copy()#コピーして残りHPようにする
        hp_bar.width = int(hp_bar.width * hp_ratio)#hpバーを小さくする
        pg.draw.rect(screen, (80, 80, 80), hp_bar_bg, border_radius=4)#背景バーをかく
        pg.draw.rect(screen, (120, 230, 120), hp_bar, border_radius=4)#その上に残量バーをかく

    # [Checkpoint2-06] 画面下のメッセージ＋コマンド表示（battleと同等UI）
    #画面の一番下にある黒いメッセージ枠（コマンド枠）を描く部分
    def _draw_command_box(self, screen: pg.Surface) -> None:
        box_height = 150
        #位置とサイズを作る
        box_rect = pg.Rect(0, GameSettings.SCREEN_HEIGHT - box_height, GameSettings.SCREEN_WIDTH, box_height)

        # 背景の黒枠
        pg.draw.rect(screen, (20, 20, 20), box_rect)
        #枠線をかく
        pg.draw.rect(screen, (80, 80, 80), box_rect, 2)

        # メッセージを表示
        msg = self.font.render(self.message, True, (255, 255, 255))#messageを作る
        screen.blit(msg, (40, GameSettings.SCREEN_HEIGHT - box_height + 25))#messageをはる

        # choice中だけコマンドボタン表示
        if self.state == "choice":
            #辞書に入ってるボタンを1個ずつ取り出して順番に描く
            for label, rect in self.option_rects.items():
                pg.draw.rect(screen, (240, 220, 180), rect, border_radius=6) #ボタンの本体
                pg.draw.rect(screen, (120, 100, 70), rect, 2, border_radius=6)#ボタンの周り
                text = self.option_font.render(label, True, (40, 30, 20))#ボタンに表示する文字
                screen.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))#これらを全部はる

        # === Checkpoint2 Section (06): Bush Interaction END ===
