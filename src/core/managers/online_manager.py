import requests
import threading
import time
from src.utils import Logger, GameSettings

POLL_INTERVAL = 0.02

class OnlineManager:
    list_players: list[dict]
    player_id: int
    
    _stop_event: threading.Event
    _thread: threading.Thread | None
    _lock: threading.Lock
    
    def __init__(self):
        self.base: str = GameSettings.ONLINE_SERVER_URL
        self.player_id = -1
        self.list_players = []
        self._chat_messages: list[dict] = []
        self._ignore_first_chat_fetch = True

        self._thread = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        
        Logger.info("OnlineManager initialized")
        
    def enter(self):
        # 起動時にサーバー側履歴をクリアし、ローカルも空スタート
        self.clear_chat()
        self._ignore_first_chat_fetch = True
        self.register()
        self.start()
            
    def exit(self):
        self.stop()
        
    def get_list_players(self) -> list[dict]:
        with self._lock:
            return list(self.list_players)

    # ------------------------------------------------------------------
    # Threading and API Calling Below
    # ------------------------------------------------------------------
    def register(self):
        try:
            url = f"{self.base}/register"
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            if resp.status_code == 200:
                self.player_id = data["id"]
                Logger.info(f"OnlineManager registered with id={self.player_id}")
            else:
                Logger.error("Registration failed:", data)
        except Exception as e:
            Logger.warning(f"OnlineManager registration error: {e}")
        return

    def update(self, x: float, y: float, map_name: str, direction: str | None = None, moving: bool | None = None) -> bool:
        if self.player_id == -1:
            # Try to register again
            return False
        
        url = f"{self.base}/players"
        body = {"id": self.player_id, "x": x, "y": y, "map": map_name}
        if direction:
            body["dir"] = direction
        if moving is not None:
            body["moving"] = moving
        try:
            resp = requests.post(url, json=body, timeout=5)
            if resp.status_code == 200:
                return True
            Logger.warning(f"Update failed: {resp.status_code} {resp.text}")
        except Exception as e:
            if self._on_error:
                try:
                    self._on_error(e)
                except Exception:
                    pass
            Logger.warning(f"Online update error: {e}")
        return False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="OnlineManagerPoller",
            daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _loop(self) -> None:
        while not self._stop_event.wait(POLL_INTERVAL):
            self._fetch_players()
            
    def _fetch_players(self) -> None:
        try:
            url = f"{self.base}/players"
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            all_players = resp.json().get("players", [])

            pid = self.player_id
            filtered = []
            for key, p in all_players.items():
                if int(key) == pid:
                    continue
                # Ensure direction is always present for clients
                if "dir" not in p:
                    p["dir"] = "DOWN"
                if "moving" not in p:
                    p["moving"] = False
                filtered.append(p)
            with self._lock:
                self.list_players = filtered
            self._fetch_chat()
            
        except Exception as e:
            Logger.warning(f"OnlineManager fetch error: {e}")

    # ----------------------------- Chat ----------------------------- #
    def send_chat(self, text: str) -> bool:
        if not text.strip():
            return False
        url = f"{self.base}/chat"
        clean = text.strip()
        body = {"id": self.player_id, "text": clean[:120]}
        ok = False
        try:
            resp = requests.post(url, json=body, timeout=5)
            ok = resp.status_code == 200
        except Exception as e:
            Logger.warning(f"Online chat send error: {e}")
        # ローカルにも即時反映して、サーバー遅延や失敗でも表示を維持する
        with self._lock:
            if not hasattr(self, "_chat_messages"):
                self._chat_messages = []
            self._chat_messages.append({"id": self.player_id, "text": clean[:120]})
            self._chat_messages = self._chat_messages[-50:]
        return ok

    def get_chat_messages(self) -> list[dict]:
        with self._lock:
            return list(getattr(self, "_chat_messages", []))

    def _fetch_chat(self) -> None:
        try:
            url = f"{self.base}/chat"
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            msgs = resp.json().get("messages", [])
            # 初回フェッチでは履歴を採用せず空で開始
            if self._ignore_first_chat_fetch:
                with self._lock:
                    self._chat_messages = []
                self._ignore_first_chat_fetch = False
                return
            with self._lock:
                self._chat_messages = msgs[-50:]
        except Exception as e:
            Logger.warning(f"Online chat fetch error: {e}")

    def clear_chat(self) -> None:
        """互換用: サーバー側に履歴クリアを要求。失敗しても処理は続行。"""
        try:
            url = f"{self.base}/chat/clear"
            requests.post(url, timeout=5)
        except Exception as e:
            Logger.warning(f"Online chat clear error: {e}")
