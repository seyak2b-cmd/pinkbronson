"""
╔══════════════════════════════════════════════════════╗
║  EMERALD ROLEX  |  Twitch Chat → OBS Bridge         ║
║  v3.1  |  Background Service Edition                 ║
╚══════════════════════════════════════════════════════╝
"""
import threading, asyncio, websockets, json, os, socket, ssl, secrets
import requests, hashlib, time
from datetime import datetime
import win32console, win32gui

# コンソールを見えないようにする (Pink Bronsonからの起動時用)
hwnd = win32console.GetConsoleWindow()
if hwnd:
    win32gui.ShowWindow(hwnd, 0) # SW_HIDE

# ══════════════════════════════════════════════════════════╗
# 定数・パス                                                 ║
# ══════════════════════════════════════════════════════════╝
CONFIG_FILE = "config.json"
WS_HOST, WS_PORT = "localhost", 8765
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
VIEWS_DIR  = os.path.join(BASE_DIR, "views", "emerald_rolex")
CACHE_DIR  = os.path.join(VIEWS_DIR, "cache")
ARCHIVE_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", "data", "archive"))
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)

_stamp = datetime.now().strftime("%Y%m%d_%H%M")
CHAT_ARCHIVE = os.path.join(ARCHIVE_DIR, f"{_stamp}_chat.txt")
with open(CHAT_ARCHIVE, "a", encoding="utf-8") as _f:
    _f.write(f"# Emerald Rolex Chat Archive  [{datetime.now().strftime('%Y-%m-%d %H:%M')}]\n")

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

# ══════════════════════════════════════════════════════════╗
# Twitch Asset Cache                                        ║
# ══════════════════════════════════════════════════════════╝
class TwitchCache:
    STATIC_BADGES = {
        "broadcaster": "https://static-cdn.jtvnw.net/badges/v1/5527c58c-fb7d-422d-b71b-f309dcb85cc1/2",
        "moderator":   "https://static-cdn.jtvnw.net/badges/v1/3267646d-33f0-4b17-b3df-f923a41db1d6/2",
        "vip":         "https://static-cdn.jtvnw.net/badges/v1/b817aba4-fad8-49e2-b88a-7cc744dfa6ec/2",
        "subscriber":  "https://static-cdn.jtvnw.net/badges/v1/86828e5e-d523-4f80-8a42-c4f7c9171b58/2",
        "partner":     "https://static-cdn.jtvnw.net/badges/v1/d12a2e27-16f6-41d0-ab77-b780518f00a3/2",
        "premium":     "https://static-cdn.jtvnw.net/badges/v1/a1dd5073-19c3-4911-8cb4-c464a7bc1510/2",
    }

    def __init__(self, token: str, client_id: str, client_secret: str = ""):
        self.irc_token     = token.replace("oauth:", "").strip()
        self.client_id     = client_id
        self.client_secret = client_secret
        self._avatar_cache: dict = {}
        self._badge_cache:  dict = {}
        self.headers = {
            "Authorization": f"Bearer {self.irc_token}",
            "Client-Id": self.client_id,
        }
        if self.client_id and self.client_secret:
            self._get_app_token()

    def _get_app_token(self):
        try:
            r = requests.post("https://id.twitch.tv/oauth2/token", params={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
            }, timeout=10)
            if r.status_code == 200:
                app_token = r.json().get("access_token", "")
                if app_token:
                    self.headers = {"Authorization": f"Bearer {app_token}", "Client-Id": self.client_id}
                    print(f"[Auth] App Access Token 取得成功")
                    return
        except Exception as e:
            print(f"[Auth] App Token エラー: {e}")

    def _download(self, url: str, key: str) -> str | None:
        ext = url.split("?")[0].rsplit(".", 1)[-1][:5]
        if ext not in ("png", "jpg", "jpeg", "gif", "webp"): ext = "png"
        local_path = os.path.join(CACHE_DIR, f"{key}.{ext}")
        rel_path   = f"cache/{key}.{ext}"
        if os.path.exists(local_path): return rel_path
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                with open(local_path, "wb") as f:
                    f.write(r.content)
                return rel_path
        except Exception: pass
        return None

    def get_avatar(self, username: str) -> str:
        if username in self._avatar_cache: return self._avatar_cache[username] or ""
        if not self.client_id: return ""
        img_url = None
        try:
            r = requests.get("https://api.twitch.tv/helix/users", headers=self.headers, params={"login": username}, timeout=8)
            if r.status_code == 200:
                data = r.json().get("data", [])
                if data:
                    raw_url = data[0].get("profile_image_url", "")
                    img_url = raw_url.replace("{width}", "70").replace("{height}", "70")
                    key = "avatar_" + hashlib.md5(username.lower().encode()).hexdigest()[:12]
                    self._download(img_url, key)
        except Exception: pass
        self._avatar_cache[username] = img_url
        return img_url or ""

    def _load_global_badges(self):
        for badge_name, url in self.STATIC_BADGES.items():
            key = f"static_{badge_name}"
            if key not in self._badge_cache:
                path = self._download(url, f"badge_{badge_name}")
                if path: self._badge_cache[key] = path

        if self.client_id:
            try:
                r = requests.get("https://api.twitch.tv/helix/chat/badges/global", headers=self.headers, timeout=8)
                for badge_set in r.json().get("data", []):
                    set_id = badge_set["set_id"]
                    for v in badge_set["versions"]:
                        k = f"badge_{set_id}_{v['id']}"
                        if k not in self._badge_cache:
                            path = self._download(v.get("image_url_2x", v["image_url_1x"]), k)
                            if path: self._badge_cache[k] = path
            except Exception: pass

    def get_badge_path(self, set_id: str, version: str = "1") -> str:
        static_key = f"static_{set_id}"
        if static_key in self._badge_cache: return self._badge_cache[static_key]
        helix_key = f"badge_{set_id}_{version}"
        return self._badge_cache.get(helix_key, "")

    def preload(self):
        threading.Thread(target=self._load_global_badges, daemon=True).start()


# ══════════════════════════════════════════════════════════╗
# Emerald Rolex Background Service                          ║
# ══════════════════════════════════════════════════════════╝
class EmeraldRolexService:
    def __init__(self):
        self.cfg = load_config()
        keys = self.cfg.get("api_keys", {})

        raw_token = keys.get("twitch_token", "").strip()
        self.twitch_token = raw_token if raw_token.startswith("oauth:") else (f"oauth:{raw_token}" if raw_token else "")
        self.channel = keys.get("twitch_channel", "").strip().lower()
        self.client_id     = keys.get("twitch_client_id", "").strip()
        self.client_secret = keys.get("twitch_client_secret", "").strip()

        # WS config
        self.connected_clients: set = set()
        self.ws_running = False
        self.irc_running = False
        self.ws_loop = None
        self.ws_token = secrets.token_hex(32)
        self._write_ws_token()

        self.cache = TwitchCache(self.twitch_token, self.client_id, self.client_secret)
        self.cache.preload()

    def _write_ws_token(self):
        token_path = os.path.join(VIEWS_DIR, "ws_token.json")
        with open(token_path, "w", encoding="utf-8") as f:
            json.dump({"token": self.ws_token}, f)

    def start(self):
        print(f"[EmeraldRolex] Starting Service for channel: {self.channel}")
        
        # Start WS Server
        threading.Thread(target=self._run_ws, daemon=True).start()

        # Start IRC Client
        if self.twitch_token and self.channel:
            self._run_irc() # Main thread blocks here
        else:
            print("[EmeraldRolex] ⚠️ Twitchトークンまたはチャンネル名が未設定です。")
            while True:  # Block if IRC didn't start, keep WS alive
                time.sleep(1)

    # ── WebSocket Server ──────────────────────────────────
    def _run_ws(self):
        async def _serve():
            try:
                async with websockets.serve(self._ws_handler, WS_HOST, WS_PORT):
                    self.ws_running = True
                    print(f"[EmeraldRolex] ✅ OBS Bridge started ws://{WS_HOST}:{WS_PORT}")
                    await asyncio.Future()
            except Exception as e:
                print(f"[EmeraldRolex] ❌ WS Error: {e}")

        self.ws_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.ws_loop)
        self.ws_loop.run_until_complete(_serve())

    async def _ws_handler(self, websocket):
        # トークン認証: 最初のメッセージで {"auth": "<token>"} を期待する
        try:
            raw = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            data = json.loads(raw)
            if data.get("auth") != self.ws_token:
                await websocket.close(1008, "Unauthorized")
                print("[EmeraldRolex] ⛔ 不正な接続を拒否しました")
                return
        except Exception:
            await websocket.close(1008, "Unauthorized")
            return

        self.connected_clients.add(websocket)
        print("[EmeraldRolex] 👀 OBS Browser connected!")
        try:
            async for _ in websocket:
                pass
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.connected_clients.discard(websocket)
            print("[EmeraldRolex] 💨 OBS Browser disconnected.")

    async def _broadcast(self, data: dict):
        if not self.connected_clients:
            return
        msg = json.dumps(data, ensure_ascii=False)
        await asyncio.gather(*[c.send(msg) for c in list(self.connected_clients)], return_exceptions=True)

    # ── 通知音 ────────────────────────────────────────────
    def _play_notification(self):
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_OK)
        except:
            pass

    # ── Twitch IRC ────────────────────────────────────────
    def _run_irc(self):
        self.irc_running = True
        print("[EmeraldRolex] 🟡 Twitch: Connecting… (TLS)")
        raw_sock = socket.socket()
        raw_sock.settimeout(30)
        ssl_ctx = ssl.create_default_context()
        sock = ssl_ctx.wrap_socket(raw_sock, server_hostname="irc.chat.twitch.tv")
        try:
            sock.connect(("irc.chat.twitch.tv", 6697))
            sock.send(f"PASS {self.twitch_token}\n".encode("utf-8"))
            sock.send(b"NICK justinfan12345\n")
            sock.send(b"CAP REQ :twitch.tv/tags\n")
            sock.send(f"JOIN #{self.channel}\n".encode("utf-8"))
            print(f"[EmeraldRolex] ✅ Twitch IRC joined: #{self.channel}")
            sock.settimeout(None)
            buf = ""
            while self.irc_running:
                try:
                    chunk = sock.recv(4096).decode("utf-8", errors="replace")
                    if not chunk: break
                    buf += chunk
                    while "\r\n" in buf:
                        line, buf = buf.split("\r\n", 1)
                        self._process_line(line, sock)
                except Exception as e:
                    print(f"Loop error: {e}")
                    time.sleep(1)
        except Exception as e:
            print(f"[EmeraldRolex] ❌ IRC Error: {e}")
        finally:
            sock.close()
            self.irc_running = False

    def _process_line(self, line: str, sock: socket.socket):
        if line.startswith("PING"):
            sock.send(b"PONG :tmi.twitch.tv\n")
        elif "PRIVMSG" in line:
            self._handle_privmsg(line)

    def _handle_privmsg(self, line: str):
        tags_str = ""
        if line.startswith("@"):
            space = line.find(" :")
            if space != -1:
                tags_str = line[1:space]
                line = line[space + 1:]

        try:
            _, rest = line.split(f" PRIVMSG #{self.channel} :", 1)
            msg_content = rest.strip()
        except ValueError:
            return
        if not msg_content:
            return

        name       = "Anonymous"
        login_name = ""
        color      = "#AAFF00"
        badge_type = "none"
        badge_ver  = "1"

        nick_part = line.lstrip(":")
        if "!" in nick_part:
            login_name = nick_part.split("!")[0].strip().lower()

        for tag in tags_str.split(";"):
            if "=" not in tag: continue
            k, v = tag.split("=", 1)
            if k == "display-name" and v: name = v
            elif k == "color" and v.startswith("#"): color = v
            elif k == "badges" and v:
                if "broadcaster" in v:   badge_type, badge_ver = "broadcaster", "1"
                elif "moderator" in v:   badge_type, badge_ver = "moderator", "1"
                elif "vip" in v:         badge_type, badge_ver = "vip", "1"
                elif "subscriber" in v:
                    badge_type = "subscriber"
                    for b in v.split(","):
                        if "subscriber" in b:
                            badge_ver = b.split("/")[-1] if "/" in b else "1"

        fetch_name = login_name if login_name else name

        def _fetch_and_broadcast():
            avatar_path = self.cache.get_avatar(fetch_name) if self.client_id else ""
            badge_path  = self.cache.get_badge_path(badge_type, badge_ver) if badge_type != "none" else ""
            data = {
                "name": name,
                "message": msg_content,
                "badge": badge_type,
                "badge_img": badge_path,
                "avatar": avatar_path,
                "color": color
            }
            if self.ws_loop and self.ws_running:
                asyncio.run_coroutine_threadsafe(self._broadcast(data), self.ws_loop)
                self._play_notification()
            print(f"💬 [{badge_type}] {name}: {msg_content}")

            # ── Blue_Rayban Rolex Bridge へ転送 ──────────────
            # cross_tool.rolex_bridge_enabled が true の場合に
            # Blue_Rayban の HTTP Bridge (localhost:8767) へ POST する。
            cfg = self.cfg
            ct  = cfg.get("cross_tool", {})
            if ct.get("rolex_bridge_enabled", True):
                port = int(ct.get("rolex_bridge_port", 8767))
                try:
                    requests.post(
                        f"http://localhost:{port}/chat",
                        json=data,
                        timeout=1
                    )
                except Exception:
                    pass  # Blue_Rayban 未起動時はサイレントに無視

        threading.Thread(target=_fetch_and_broadcast, daemon=True).start()

        # チャットアーカイブに追記
        try:
            ts = datetime.now().strftime("%H:%M:%S")
            with open(CHAT_ARCHIVE, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] <{name}> {msg_content}\n")
        except Exception:
            pass

if __name__ == "__main__":
    service = EmeraldRolexService()
    try:
        service.start()
    except KeyboardInterrupt:
        print("[EmeraldRolex] Shutdown.")
