from server.playerHandler import PlayerHandler

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
PORT = 8989

PLAYER_HANDLER = PlayerHandler()
CHAT_MESSAGES: list[dict] = []
CHAT_LIMIT = 50
PLAYER_HANDLER.start()
    
class Handler(BaseHTTPRequestHandler):
    # def log_message(self, fmt, *args):
    #     return

    def do_GET(self):
        if self.path == "/":
            self._json(200, {"status": "ok"})
            return
            
        if self.path == "/register":
            pid = PLAYER_HANDLER.register()
            self._json(200, {"message": "registration successful", "id": pid})
            return

        if self.path == "/players":
            self._json(200, {"players": PLAYER_HANDLER.list_players()})
            return
        
        if self.path == "/chat":
            self._json(200, {"messages": CHAT_MESSAGES[-CHAT_LIMIT:]})
            return
        if self.path == "/chat/clear":
            CHAT_MESSAGES.clear()
            self._json(200, {"success": True})
            return

        self._json(404, {"error": "not_found"})

    def do_POST(self):
        if self.path == "/chat":
            self._handle_chat_post()
            return
        if self.path == "/chat/clear":
            CHAT_MESSAGES.clear()
            self._json(200, {"success": True})
            return
        if self.path != "/players":
            self._json(404, {"error": "not_found"})
            return

        length = int(self.headers.get("Content-Length", "0"))
        try:
            body = self.rfile.read(length)
            data = json.loads(body.decode("utf-8"))
        except Exception:
            self._json(400, {"error": "invalid_json"})
            return

        missing = [k for k in ("id", "x", "y", "map") if k not in data]
        if missing:
            self._json(400, {"error": "bad_fields", "missing": missing})
            return

        try:
            pid = int(data["id"])
            x = float(data["x"])
            y = float(data["y"])
            map_name = str(data["map"])
            direction = data.get("dir")
            moving = data.get("moving")
        except (ValueError, TypeError):
            self._json(400, {"error": "bad_fields"})
            return

        ok = PLAYER_HANDLER.update(pid, x, y, map_name, direction, moving)
        if not ok:
            self._json(404, {"error": "player_not_found"})
            return

        self._json(200, {"success": True})

    # Utility for JSON responses
    def _json(self, code: int, obj: object) -> None:
        data = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle_chat_post(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        try:
            body = self.rfile.read(length)
            data = json.loads(body.decode("utf-8"))
        except Exception:
            self._json(400, {"error": "invalid_json"})
            return
        text = str(data.get("text", "")).strip()
        pid = data.get("id")
        if not text or pid is None:
            self._json(400, {"error": "bad_fields"})
            return
        CHAT_MESSAGES.append({"id": int(pid), "text": text[:120]})
        if len(CHAT_MESSAGES) > CHAT_LIMIT:
            del CHAT_MESSAGES[:-CHAT_LIMIT]
        self._json(200, {"success": True})

if __name__ == "__main__":
    print(f"[Server] Running on localhost with port {PORT}")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
