'''
[TODO HACKATHON 5]
Try to mimic the menu_scene.py or game_scene.py to create this new scene
'''
import pygame as pg

from src.utils import GameSettings
from src.sprites import BackgroundSprite
from src.scenes.scene import Scene
from src.interface.components import Button
from src.core.services import scene_manager, input_manager, sound_manager
from typing import Callable, override

class Checkbox:
    def __init__(self, label: str, x: int, y: int, size: int, initial: bool,
                 on_change: Callable[[bool], None] | None = None) -> None:
        self.label = label
        self.rect = pg.Rect(x, y, size, size)
        self.is_checked = initial
        self.on_change = on_change
        self.font = pg.font.SysFont("Arial", 28)

    def update(self, dt: float) -> None:
        if self.rect.collidepoint(input_manager.mouse_pos):
            if input_manager.mouse_pressed(1):
                self.is_checked = not self.is_checked
                if self.on_change:
                    self.on_change(self.is_checked)

    def draw(self, screen: pg.Surface) -> None:
        pg.draw.rect(screen, (240, 240, 240), self.rect, border_radius=4)
        inner_rect = self.rect.inflate(-6, -6)
        color = (100, 100, 100) if not self.is_checked else (80, 180, 90)
        pg.draw.rect(screen, color, inner_rect, border_radius=4)
        if self.is_checked:
            pg.draw.line(screen, (255, 255, 255), inner_rect.topleft, inner_rect.bottomright, 4)
            pg.draw.line(screen, (255, 255, 255), inner_rect.topright, inner_rect.bottomleft, 4)
        text_surf = self.font.render(self.label, True, (255, 255, 255))
        screen.blit(text_surf, (self.rect.right + 16, self.rect.centery - text_surf.get_height() // 2))


class Slider:
    def __init__(self, label: str, x: int, y: int, width: int,
                 min_value: float, max_value: float, value: float,
                 on_change: Callable[[float], None] | None = None) -> None:
        self.label = label
        self.track_rect = pg.Rect(x, y, width, 12)
        self.min = min_value
        self.max = max_value
        self.value = value
        self.on_change = on_change
        self.dragging = False
        self.font = pg.font.SysFont("Arial", 28)

    def update(self, dt: float) -> None:
        mouse_pos = input_manager.mouse_pos
        if input_manager.mouse_pressed(1) and self.track_rect.inflate(0, 20).collidepoint(mouse_pos):
            self.dragging = True
            self._set_value_from_mouse(mouse_pos[0])
        elif input_manager.mouse_released(1):
            self.dragging = False

        if self.dragging and input_manager.mouse_down(1):
            self._set_value_from_mouse(mouse_pos[0])

    def _set_value_from_mouse(self, mouse_x: int) -> None:
        ratio = (mouse_x - self.track_rect.x) / self.track_rect.width
        ratio = max(0.0, min(1.0, ratio))
        self.value = self.min + ratio * (self.max - self.min)
        if self.on_change:
            self.on_change(self.value)

    def draw(self, screen: pg.Surface) -> None:
        label_surf = self.font.render(f"{self.label}: {self.value:.2f}", True, (255, 255, 255))
        screen.blit(label_surf, (self.track_rect.x, self.track_rect.y - label_surf.get_height() - 10))

        pg.draw.rect(screen, (70, 70, 70), self.track_rect, border_radius=6)
        filled_width = int(self.track_rect.width * (self.value - self.min) / (self.max - self.min))
        fill_rect = pg.Rect(self.track_rect.x, self.track_rect.y, filled_width, self.track_rect.height)
        pg.draw.rect(screen, (120, 200, 255), fill_rect, border_radius=6)

        thumb_x = self.track_rect.x + filled_width
        thumb_rect = pg.Rect(thumb_x - 8, self.track_rect.y - 6, 16, self.track_rect.height + 12)
        pg.draw.rect(screen, (240, 240, 240), thumb_rect, border_radius=6)

class SettingScene(Scene):
    # Background Image
    background: BackgroundSprite
    # Buttons
    back_button: Button

    def __init__(self):
        super().__init__()
        self.background = BackgroundSprite("backgrounds/background1.png")
        self.muted = GameSettings.AUDIO_MUTED

        # [HACKATHON 5] Create back button to return to menu
        px, py = GameSettings.SCREEN_WIDTH // 2, GameSettings.SCREEN_HEIGHT * 3 // 4
        self.back_button = Button(
            "UI/button_back.png", "UI/button_back_hover.png",
            px - 50, py, 100, 100,
            lambda: scene_manager.change_scene("menu")
        )

        check_x = GameSettings.SCREEN_WIDTH // 2 - 200
        check_y = GameSettings.SCREEN_HEIGHT // 3
        self.checkbox_hitbox = Checkbox(
            "Show Collision Hitboxes",
            check_x,
            check_y,
            40,
            GameSettings.DRAW_HITBOXES,
            self._toggle_hitboxes
        )
        self.checkbox_mute = Checkbox(
            "Mute Background Music",
            check_x,
            check_y + 80,
            40,
            self.muted,
            self._toggle_mute
        )

        slider_x = GameSettings.SCREEN_WIDTH // 2 - 250
        slider_y = check_y + 180
        self.volume_slider = Slider(
            "BGM Volume",
            slider_x,
            slider_y,
            500,
            0.0,
            1.0,
            GameSettings.AUDIO_VOLUME,
            self._set_volume
        )

    @override
    def enter(self) -> None:
        self.checkbox_hitbox.is_checked = GameSettings.DRAW_HITBOXES
        self.muted = GameSettings.AUDIO_MUTED
        self.checkbox_mute.is_checked = self.muted
        self.volume_slider.value = GameSettings.AUDIO_VOLUME

    @override
    def exit(self) -> None:
        pass

    @override
    def update(self, dt: float) -> None:
        if input_manager.key_pressed(pg.K_ESCAPE):
            scene_manager.change_scene("menu")
            return
        self.back_button.update(dt)
        self.checkbox_hitbox.update(dt)
        self.checkbox_mute.update(dt)
        self.volume_slider.update(dt)

    @override
    def draw(self, screen: pg.Surface) -> None:
        self.background.draw(screen)
        self.back_button.draw(screen)
        self.checkbox_hitbox.draw(screen)
        self.checkbox_mute.draw(screen)
        self.volume_slider.draw(screen)

    def _toggle_hitboxes(self, enabled: bool) -> None:
        GameSettings.DRAW_HITBOXES = enabled

    def _toggle_mute(self, enabled: bool) -> None:
        self.muted = enabled
        GameSettings.AUDIO_MUTED = enabled
        if enabled:
            sound_manager.pause_all()
        else:
            sound_manager.resume_all()

    def _set_volume(self, value: float) -> None:
        GameSettings.AUDIO_VOLUME = value
        if sound_manager.current_bgm:
            sound_manager.current_bgm.set_volume(value)
