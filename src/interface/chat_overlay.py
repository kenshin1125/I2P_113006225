import pygame as pg
import string
from src.utils import GameSettings


class ChatOverlay:
    """シンプルなチャットオーバーレイ（オンライン用）。"""

    def __init__(self):
        w = GameSettings.SCREEN_WIDTH
        h = 200
        self.panel_rect = pg.Rect(20, GameSettings.SCREEN_HEIGHT - h - 20, w // 2, h)
        self.font = pg.font.SysFont("Arial", 22)
        self.small_font = pg.font.SysFont("Arial", 18)
        self.messages: list[dict] = []
        self.input_text: str = ""
        self.is_open: bool = False

    def sync_messages(self, msgs: list[dict]) -> None:
        cleaned: list[dict] = []
        for m in msgs:
            cleaned.append({
                "id": m.get("id"),
                "text": self._clean_text(str(m.get("text", "")))
            })
        self.messages = cleaned[-8:]

    def toggle(self) -> None:
        self.is_open = not self.is_open
        if not self.is_open:
            self.input_text = ""

    def update(self, input_manager) -> str | None:
        """入力を処理し、送信する文字列があれば返す。"""
        if not self.is_open:
            return None
        # 文字入力
        for ch in input_manager.consume_text_input():
            if len(self.input_text) < 120:
                self.input_text += ch
        # バックスペース
        if input_manager.key_pressed(pg.K_BACKSPACE) and self.input_text:
            self.input_text = self.input_text[:-1]
        # Enterで送信
        if input_manager.key_pressed(pg.K_RETURN) and self.input_text.strip():
            text = self.input_text.strip()
            self.input_text = ""
            return text
        # Escで閉じる
        if input_manager.key_pressed(pg.K_ESCAPE):
            self.toggle()
        return None

    def _clean_text(self, text: str) -> str:
        # 制御文字・非ASCIIを落として末尾の空白も除去
        allowed = set(string.printable)
        filtered = "".join(ch for ch in text if ch in allowed and ch not in "\r\n\t")
        return filtered.strip()

    def draw(self, screen: pg.Surface, self_id: int = -1) -> None:
        # 背景
        panel = self.panel_rect
        surf = pg.Surface(panel.size, pg.SRCALPHA)
        surf.fill((20, 20, 20, 180))
        pg.draw.rect(surf, (200, 200, 200), surf.get_rect(), 2, border_radius=8)

        # メッセージ表示（上から古い順）
        y = 10
        for msg in self.messages[-6:]:
            sender = msg.get("id", "?")
            name = "me" if sender == self_id else "friend"
            text = f"{name}: {msg.get('text', '')}"
            color = (120, 200, 255) if name == "me" else (230, 230, 230)
            line = self.small_font.render(text, True, color)
            surf.blit(line, (10, y))
            y += line.get_height() + 4

        # 入力欄
        if self.is_open:
            input_rect = pg.Rect(10, panel.height - 40, panel.width - 20, 30)
            pg.draw.rect(surf, (40, 40, 40), input_rect, border_radius=6)
            pg.draw.rect(surf, (120, 120, 120), input_rect, 2, border_radius=6)
            txt = self.font.render(self.input_text or "Type message...", True, (255, 255, 255))
            surf.blit(txt, (input_rect.x + 8, input_rect.y + 5))

        screen.blit(surf, panel.topleft)
