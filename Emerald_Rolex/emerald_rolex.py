# -*- coding: utf-8 -*-
import sys
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try: sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
"""
╔══════════════════════════════════════════════════════╗
║  EMERALD ROLEX  |  Twitch Chat → Multi-Output Bridge ║
║  v4.0  |  Translation + VOICEVOX + Firebase + OBS    ║
╚══════════════════════════════════════════════════════╝
"""
import threading, asyncio, websockets, json, os, socket, ssl, secrets
import requests, time, queue as _queue, urllib.parse, tempfile
from datetime import datetime
import win32console, win32gui

try:
    import winsound as _winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

try:
    from langdetect import detect as _ld, LangDetectException, DetectorFactory as _LDFactory
    _LDFactory.seed = 0  # 言語検知の結果を確定的にする
    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False

# system_logger
try:
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path: sys.path.insert(0, _root)
    from system_logger import send_system_log as _send_log
except Exception:
    def _send_log(m, msg): pass

try:
    from firebase_auth import FirebaseAuth as _FirebaseAuth
except Exception:
    _FirebaseAuth = None

# コンソールを非表示 (Pink Bronsonからの起動時)
hwnd = win32console.GetConsoleWindow()
if hwnd:
    win32gui.ShowWindow(hwnd, 0)

# ══════════════════════════════════════════════════════════
# 定数・パス
# ══════════════════════════════════════════════════════════
CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
WS_HOST, WS_PORT = "localhost", 8765
BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
VIEWS_DIR        = os.path.join(BASE_DIR, "views", "emerald_rolex")
CACHE_DIR        = os.path.join(VIEWS_DIR, "cache")
ARCHIVE_DIR      = os.path.normpath(os.path.join(BASE_DIR, "..", "data", "archive"))
AVATAR_CACHE_FILE = os.path.join(VIEWS_DIR, "cache", "avatar_urls.json")
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)

_stamp = datetime.now().strftime("%Y%m%d_%H%M")
CHAT_JSONL = os.path.join(ARCHIVE_DIR, f"{_stamp}_chat.jsonl")
with open(CHAT_JSONL, "a", encoding="utf-8") as _f:
    _f.write(json.dumps({"_session": datetime.now().isoformat()}) + "\n")

BADGE_CDN = {
    "broadcaster": "https://static-cdn.jtvnw.net/badges/v1/5527c58c-fb7d-422d-b71b-f309dcb85cc1/2",
    "moderator":   "https://static-cdn.jtvnw.net/badges/v1/3267646d-33f0-4b17-b3df-f923a41db1d6/2",
    "vip":         "https://static-cdn.jtvnw.net/badges/v1/b817aba4-fad8-49e2-b88a-7cc744dfa6ec/2",
    "subscriber":  "https://static-cdn.jtvnw.net/badges/v1/86828e5e-d523-4f80-8a42-c4f7c9171b58/2",
    "partner":     "https://static-cdn.jtvnw.net/badges/v1/d12a2e27-16f6-41d0-ab77-b780518f00a3/2",
    "premium":     "https://static-cdn.jtvnw.net/badges/v1/a1dd5073-19c3-4911-8cb4-c464a7bc1510/2",
    "turbo":       "https://static-cdn.jtvnw.net/badges/v1/bd444ec6-8f34-4bf9-91f4-af1e3428d80f/2",
}

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(cfg: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# ══════════════════════════════════════════════════════════
# Gemini 翻訳
# ══════════════════════════════════════════════════════════
_gemini_model = None
_gemini_lock  = threading.Lock()

def _get_gemini():
    global _gemini_model
    if _gemini_model:
        return _gemini_model
    if not HAS_GENAI:
        return None
    key = load_config().get("api_keys", {}).get("gemini_key", "")
    if not key:
        return None
    with _gemini_lock:
        if not _gemini_model:
            genai.configure(api_key=key)
            _gemini_model = genai.GenerativeModel("gemini-2.5-flash")
    return _gemini_model

def detect_lang(text: str) -> str:
    if not HAS_LANGDETECT or not text.strip():
        return "und"
    try:
        return _ld(text)
    except Exception:
        return "und"

def translate_text(text: str, target: str) -> str:
    model = _get_gemini()
    if not model or not text.strip():
        return ""
    names = {"ja": "Japanese", "en": "English", "ko": "Korean",
             "zh": "Chinese", "es": "Spanish", "fr": "French"}
    tname = names.get(target, target)
    prompt = (
        f"Translate the following Twitch chat message to {tname}. "
        f"Output ONLY the translation, no explanation.\n<msg>{text}</msg>"
    )
    try:
        return model.generate_content(prompt).text.strip()
    except Exception as e:
        print(f"[Trans] {e}")
        return ""

# ══════════════════════════════════════════════════════════
# Firebase
# ══════════════════════════════════════════════════════════
_firebase_url  = ""
_fb_auth_rolex = None  # FirebaseAuth インスタンス (起動時に初期化)

def _fb_url() -> str:
    global _firebase_url
    if not _firebase_url:
        _firebase_url = load_config().get("api_keys", {}).get("firebase_url", "")
    return _firebase_url

def _init_fb_auth():
    """起動時に一度だけ FirebaseAuth を初期化する。"""
    global _fb_auth_rolex
    if _FirebaseAuth is None:
        return
    cfg = load_config()
    _fb_auth_rolex = _FirebaseAuth.from_config(cfg)

def _fb_params() -> dict:
    return _fb_auth_rolex.params() if _fb_auth_rolex else {}

def push_chat_to_firebase(data: dict):
    url = _fb_url()
    if not url:
        return
    try:
        requests.post(f"{url.rstrip('/')}/chats.json", json=data,
                      params=_fb_params(), timeout=5)
    except Exception as e:
        print(f"[Firebase] {e}")

# ══════════════════════════════════════════════════════════
# VOICEVOX TTS
# ══════════════════════════════════════════════════════════
class VoicevoxTTS:
    def __init__(self):
        self._q = _queue.Queue(maxsize=3)
        threading.Thread(target=self._worker, daemon=True).start()

    def _er_cfg(self):
        return load_config().get("emerald_rolex", {})

    def enqueue(self, text: str):
        if not self._er_cfg().get("voicevox_enabled", False):
            return
        try:
            self._q.put_nowait(text)
        except _queue.Full:
            pass  # 話中はドロップ

    def _worker(self):
        while True:
            text = self._q.get()
            try:
                c = self._er_cfg()
                if not c.get("voicevox_enabled", False):
                    continue
                vurl    = c.get("voicevox_url", "http://localhost:50021").rstrip("/")
                speaker = int(c.get("voicevox_speaker", 1))
                volume  = float(c.get("voicevox_volume", 1.0))
                self._speak(text, vurl, speaker, volume)
            except Exception as e:
                print(f"[VVOX] {e}")

    def _speak(self, text: str, vurl: str, speaker: int, volume: float):
        if not HAS_WINSOUND:
            return
        try:
            enc = urllib.parse.quote(text, safe="")
            r1  = requests.post(f"{vurl}/audio_query?text={enc}&speaker={speaker}", timeout=10)
            r1.raise_for_status()
            aq = r1.json()
            aq["volumeScale"] = max(0.0, min(2.0, volume))
            r2  = requests.post(f"{vurl}/synthesis?speaker={speaker}", json=aq,
                                headers={"Content-Type": "application/json", "Accept": "audio/wav"},
                                timeout=20)
            r2.raise_for_status()
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.write(r2.content)
            tmp.close()
            try:
                _winsound.PlaySound(tmp.name, _winsound.SND_FILENAME)
            finally:
                try: os.unlink(tmp.name)
                except: pass
        except Exception as e:
            print(f"[VVOX] speak: {e}")

_vvox = VoicevoxTTS()

# ══════════════════════════════════════════════════════════
# Twitch Asset Cache
# ══════════════════════════════════════════════════════════
class TwitchCache:
    def __init__(self, token: str, client_id: str, client_secret: str = ""):
        self.irc_token     = token.replace("oauth:", "").strip()
        self.client_id     = client_id
        self.client_secret = client_secret
        self._avatar_cache: dict = self._load_disk_cache()
        self._cache_lock   = threading.Lock()
        self.headers = {
            "Authorization": f"Bearer {self.irc_token}",
            "Client-Id": self.client_id,
        }
        if self.client_id and self.client_secret:
            self._get_app_token()

    def _load_disk_cache(self) -> dict:
        try:
            if os.path.exists(AVATAR_CACHE_FILE):
                with open(AVATAR_CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                print(f"[Avatar] URLキャッシュ読込: {len(data)} 件 ({AVATAR_CACHE_FILE})")
                return data
        except Exception as e:
            print(f"[Avatar] URLキャッシュ読込失敗: {e}")
        return {}

    def _save_disk_cache(self):
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(AVATAR_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._avatar_cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Avatar] URLキャッシュ保存失敗: {e}")

    def _get_app_token(self):
        try:
            r = requests.post("https://id.twitch.tv/oauth2/token", params={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
            }, timeout=10)
            if r.status_code == 200:
                tok = r.json().get("access_token", "")
                if tok:
                    self.headers = {"Authorization": f"Bearer {tok}", "Client-Id": self.client_id}
                    print("[Auth] App Access Token OK")
        except Exception as e:
            print(f"[Auth] {e}")

    def get_avatar(self, username: str, user_id: str = "") -> str:
        """CDN URL をキャッシュして返す（ローカルへの画像保存は行わない）。"""
        cache_key = user_id or username
        with self._cache_lock:
            cached = self._avatar_cache.get(cache_key)
        if cached:
            return cached
        if not self.client_id:
            print(f"[Avatar] client_id 未設定のためスキップ: {username}")
            return ""
        img_url = ""
        try:
            params = {"id": user_id} if user_id else {"login": username}
            r = requests.get("https://api.twitch.tv/helix/users",
                             headers=self.headers, params=params, timeout=8)
            if r.status_code == 200:
                data = r.json().get("data", [])
                if data:
                    img_url = data[0].get("profile_image_url", "")
                    if img_url:
                        print(f"[Avatar] ✓ {username} → {img_url[:60]}")
                    else:
                        print(f"[Avatar] ✗ {username}: profile_image_url 空")
                else:
                    # user_id で見つからなければ login で再試行
                    if user_id and username:
                        r2 = requests.get("https://api.twitch.tv/helix/users",
                                          headers=self.headers,
                                          params={"login": username}, timeout=8)
                        if r2.status_code == 200:
                            d2 = r2.json().get("data", [])
                            if d2:
                                img_url = d2[0].get("profile_image_url", "")
                                if img_url:
                                    print(f"[Avatar] ✓(login) {username} → {img_url[:60]}")
                    if not img_url:
                        print(f"[Avatar] ✗ {username} (uid={user_id}): データなし")
            elif r.status_code == 401:
                print(f"[Avatar] 401 token期限切れ → 再取得: {username}")
                self._get_app_token()
            else:
                print(f"[Avatar] ✗ HTTP {r.status_code}: {username} — {r.text[:120]}")
        except Exception as e:
            print(f"[Avatar] exception {username}: {e}")

        if img_url:
            with self._cache_lock:
                self._avatar_cache[cache_key] = img_url
            threading.Thread(target=self._save_disk_cache, daemon=True).start()
        return img_url

    def get_badge_url(self, set_id: str) -> str:
        """Returns CDN URL for Firebase / web."""
        return BADGE_CDN.get(set_id, "")

    def clear_failed_avatars(self):
        """空文字列でキャッシュされた失敗エントリを削除してリトライ可能にする。"""
        before = len(self._avatar_cache)
        self._avatar_cache = {k: v for k, v in self._avatar_cache.items() if v}
        removed = before - len(self._avatar_cache)
        if removed:
            print(f"[Avatar] キャッシュクリア: {removed} 件の失敗エントリを削除")

    def preload(self):
        # バッジのローカルキャッシュは廃止。App Tokenのみ起動時に取得。
        if self.client_id and self.client_secret:
            threading.Thread(target=self._get_app_token, daemon=True).start()


# ══════════════════════════════════════════════════════════
# Emerald Rolex Service
# ══════════════════════════════════════════════════════════
class EmeraldRolexService:
    def __init__(self):
        self.cfg = load_config()
        keys = self.cfg.get("api_keys", {})

        raw_token = keys.get("twitch_token", "").strip()
        self.twitch_token  = raw_token if raw_token.startswith("oauth:") else (f"oauth:{raw_token}" if raw_token else "")
        self.channel       = keys.get("twitch_channel", "").strip().lower()
        self.client_id     = keys.get("twitch_client_id", "").strip()
        self.client_secret = keys.get("twitch_client_secret", "").strip()

        self.connected_clients: set = set()
        self.ws_running = False
        self.irc_running = False
        self.ws_loop = None
        self.ws_token = secrets.token_hex(32)
        self._write_ws_token()

        self.cache = TwitchCache(self.twitch_token, self.client_id, self.client_secret)
        self.cache.preload()
        # 5分ごとに失敗キャッシュをクリアしてリトライできるようにする
        def _periodic_cache_clear():
            while True:
                time.sleep(300)
                self.cache.clear_failed_avatars()
        threading.Thread(target=_periodic_cache_clear, daemon=True).start()

        _get_gemini()   # 起動時に初期化を試みる
        _init_fb_auth() # Firebase Auth 初期化

    def _write_ws_token(self):
        with open(os.path.join(VIEWS_DIR, "ws_token.json"), "w", encoding="utf-8") as f:
            json.dump({"token": self.ws_token}, f)

    def start(self):
        print(f"[EmeraldRolex] Starting for channel: #{self.channel}")
        _send_log("Emerald_Rolex", f"🟢 起動: #{self.channel}")
        if self.cfg.get('cross_tool', {}).get('obs_ws_enabled', True):
            threading.Thread(target=self._run_ws, daemon=True).start()
        else:
            print("[EmeraldRolex] OBS WebSocket 無効 (cross_tool.obs_ws_enabled=false)")
        if self.twitch_token and self.channel:
            self._run_irc()
        else:
            print("[EmeraldRolex] ⚠️ Token or channel not set.")
            while True: time.sleep(1)

    # ── WebSocket ──────────────────────────────────────────
    def _run_ws(self):
        async def _serve():
            try:
                async with websockets.serve(self._ws_handler, WS_HOST, WS_PORT):
                    self.ws_running = True
                    print(f"[EmeraldRolex] ✅ OBS Bridge ws://{WS_HOST}:{WS_PORT}")
                    _send_log("Emerald_Rolex", f"✅ OBS Bridge ws://localhost:{WS_PORT}")
                    await asyncio.Future()
            except Exception as e:
                print(f"[EmeraldRolex] ❌ WS Error: {e}")

        self.ws_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.ws_loop)
        self.ws_loop.run_until_complete(_serve())

    async def _ws_handler(self, websocket):
        try:
            raw  = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            data = json.loads(raw)
            if data.get("auth") != self.ws_token:
                await websocket.close(1008, "Unauthorized")
                return
        except Exception:
            await websocket.close(1008, "Unauthorized")
            return
        self.connected_clients.add(websocket)
        print("[EmeraldRolex] 👀 OBS connected")
        try:
            async for _ in websocket: pass
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.connected_clients.discard(websocket)
            print("[EmeraldRolex] 💨 OBS disconnected")

    async def _broadcast(self, data: dict):
        if not self.connected_clients: return
        msg = json.dumps(data, ensure_ascii=False)
        await asyncio.gather(*[c.send(msg) for c in list(self.connected_clients)],
                             return_exceptions=True)

    # ── Twitch IRC ─────────────────────────────────────────
    def _run_irc(self):
        self.irc_running = True
        print("[EmeraldRolex] 🟡 IRC: Connecting…")
        raw_sock = socket.socket()
        raw_sock.settimeout(30)
        ssl_ctx = ssl.create_default_context()
        sock = ssl_ctx.wrap_socket(raw_sock, server_hostname="irc.chat.twitch.tv")
        try:
            sock.connect(("irc.chat.twitch.tv", 6697))
            sock.send(b"PASS schmoopiie\n")  # justinfan匿名接続はダミーPASSを使用
            sock.send(b"NICK justinfan12345\n")
            # Request all tag capabilities
            sock.send(b"CAP REQ :twitch.tv/tags twitch.tv/commands twitch.tv/membership\n")
            sock.send(f"JOIN #{self.channel}\n".encode("utf-8"))
            print(f"[EmeraldRolex] ✅ IRC joined: #{self.channel}")
            _send_log("Emerald_Rolex", f"✅ IRC: #{self.channel}")
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
                    print(f"[IRC] loop error: {e}")
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
        # ── タグ全取得 ──────────────────────────────────────
        tags: dict = {}
        if line.startswith("@"):
            sp = line.find(" :")
            if sp != -1:
                for tag in line[1:sp].split(";"):
                    if "=" in tag:
                        k, v = tag.split("=", 1)
                        tags[k] = v
                line = line[sp + 1:]

        try:
            _, rest = line.split(f" PRIVMSG #{self.channel} :", 1)
            msg_content = rest.strip()
        except ValueError:
            return
        if not msg_content:
            return

        # ── ユーザー情報 ────────────────────────────────────
        display_name = tags.get("display-name") or "Anonymous"
        login_name   = ""
        nick = line.lstrip(":")
        if "!" in nick:
            login_name = nick.split("!")[0].strip().lower()
        login_name = login_name or display_name.lower()

        color          = tags.get("color") or "#AAFF00"
        user_id        = tags.get("user-id", "")
        msg_id         = tags.get("id", "")
        is_mod         = tags.get("mod", "0") == "1"
        is_sub         = tags.get("subscriber", "0") == "1"
        is_turbo       = tags.get("turbo", "0") == "1"
        is_first       = tags.get("first-msg", "0") == "1"
        bits           = tags.get("bits", "")
        emotes_raw     = tags.get("emotes", "")
        client_nonce   = tags.get("client-nonce", "")
        room_id        = tags.get("room-id", "")
        tmi_ts         = int(tags.get("tmi-sent-ts", int(time.time() * 1000)))
        flags          = tags.get("flags", "")  # banned phrases etc.

        # ── バッジ全取得 ────────────────────────────────────
        badge_type   = "none"
        badge_ver    = "1"
        badge_names  = []     # 全バッジ名リスト
        badges_raw   = tags.get("badges", "")
        if badges_raw:
            for b in badges_raw.split(","):
                if "/" in b:
                    bname, bver = b.split("/", 1)
                    badge_names.append(bname)
                    if badge_type == "none" and bname in BADGE_CDN:
                        badge_type = bname
                        badge_ver  = bver

        # ── エモート解析 (ID→位置マップ) ───────────────────
        emotes_list = []
        if emotes_raw:
            for e in emotes_raw.split("/"):
                if ":" in e:
                    eid, positions = e.split(":", 1)
                    emotes_list.append({"id": eid, "positions": positions.split(",")})

        def _fetch_translate_broadcast():
            # 1. Avatar + badge CDN URL
            avatar_url = self.cache.get_avatar(login_name, user_id) if self.client_id else ""
            badge_cdn  = self.cache.get_badge_url(badge_type)

            # 2. 言語検知 + 翻訳
            lang    = detect_lang(msg_content)
            ja_text = ""
            en_text = ""

            if lang == "ja":
                ja_text = msg_content
                en_text = translate_text(msg_content, "en")
            elif lang == "en":
                en_text = msg_content
                ja_text = translate_text(msg_content, "ja")
            else:
                ja_text = translate_text(msg_content, "ja")
                en_text = translate_text(msg_content, "en")

            # 3. WebSocket broadcast (OBS)
            ws_data = {
                "name":      display_name,
                "login":     login_name,
                "message":   msg_content,
                "ja":        ja_text,
                "en":        en_text,
                "lang":      lang,
                "badge":     badge_type,
                "badge_img": badge_cdn,
                "avatar":    avatar_url,
                "color":     color,
                "timestamp": tmi_ts,
                "is_first":  is_first,
                "bits":      bits or None,
            }
            if self.ws_loop and self.ws_running:
                asyncio.run_coroutine_threadsafe(self._broadcast(ws_data), self.ws_loop)

            # 4. Firebase push (web app 用)
            fb_data = {
                "display_name":    display_name,
                "login":           login_name,
                "text":            msg_content,
                "ja":              ja_text,
                "translated_en":   en_text if lang != "en" else "",
                "lang":            lang,
                "color":           color,
                "profile_image_url": avatar_url,
                "badges":          [badge_cdn] if badge_cdn else [],
                "badge_type":      badge_type,
                "user_id":         user_id,
                "timestamp":       tmi_ts,
                "is_first":        is_first,
            }
            if bits:
                fb_data["bits"] = int(bits)
            # None / 空値を除去
            fb_data = {k: v for k, v in fb_data.items() if v not in (None, "", [])}
            threading.Thread(target=push_chat_to_firebase, args=(fb_data,), daemon=True).start()

            # 5. VOICEVOX TTS (日本語テキストを優先)
            tts_text = ja_text if ja_text else msg_content
            _vvox.enqueue(tts_text)

            # 6. JSONL アーカイブ (LLM-readable)
            log_entry = {
                "ts":           datetime.now().isoformat(),
                "login":        login_name,
                "display_name": display_name,
                "color":        color,
                "badges":       badge_names,
                "user_id":      user_id,
                "msg_id":       msg_id,
                "room_id":      room_id,
                "lang":         lang,
                "message":      msg_content,
                "ja":           ja_text or None,
                "en":           en_text or None,
                "bits":         int(bits) if bits else None,
                "is_first":     is_first or None,
                "emotes":       emotes_list or None,
                "flags":        flags or None,
            }
            log_entry = {k: v for k, v in log_entry.items() if v is not None}
            try:
                with open(CHAT_JSONL, "a", encoding="utf-8") as f:
                    f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            except Exception:
                pass

            # 7. main_ui.py 向け構造化出力
            chat_json = {
                "display_name": display_name,
                "message":      msg_content,
                "ja":           ja_text,
                "lang":         lang,
                "color":        color,
                "badge":        badge_type,
                "is_first":     is_first,
                "bits":         bits or None,
                "timestamp":    tmi_ts,
            }
            print(f"[CHAT_JSON] {json.dumps(chat_json, ensure_ascii=False)}")

            # 8. 通知音 + log
            self._play_notification()
            suffix = f" → {ja_text[:30]}" if ja_text and lang != "ja" else ""
            img_status = "📷" if avatar_url else "🚫img"
            print(f"💬 [{badge_type}] {display_name}({login_name}/{user_id}) {img_status}: {msg_content}{suffix}")
            _send_log("Emerald_Rolex", f"💬 [{display_name}] img={'✓' if avatar_url else '✗'} {msg_content[:50]}")

        threading.Thread(target=_fetch_translate_broadcast, daemon=True).start()

    def _play_notification(self):
        try:
            if not HAS_WINSOUND:
                return
            cfg      = load_config()
            er_cfg   = cfg.get("emerald_rolex", {})
            enabled  = er_cfg.get("notify_enabled", True)
            if not enabled:
                return
            path = er_cfg.get("notify_sound", "").strip()
            if path and os.path.exists(path):
                _winsound.PlaySound(path, _winsound.SND_FILENAME | _winsound.SND_ASYNC)
            else:
                _winsound.MessageBeep(_winsound.MB_OK)
        except Exception:
            pass


if __name__ == "__main__":
    service = EmeraldRolexService()
    try:
        service.start()
    except KeyboardInterrupt:
        print("[EmeraldRolex] Shutdown.")
