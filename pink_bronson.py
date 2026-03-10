"""
╔══════════════════════════════════════════════════════════╗
║   PINK BRONSON  -  The Master-Hub Producer               ║
║   v3.0  |  80s Neon Tokyo & Settings Edition             ║
╚══════════════════════════════════════════════════════════╝
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import os, json, threading, time, subprocess, queue, sys, wave
from datetime import datetime
from filelock import FileLock, Timeout
import sounddevice as sd
import numpy as np

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
from faster_whisper import WhisperModel

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ══════════════════════════════════════════════════════════
# 定数 / Constants
# ══════════════════════════════════════════════════════════
DATA_DIR        = "data"
ARCHIVE_DIR     = os.path.join(DATA_DIR, "archive")
TEMP_AUDIO_DIR  = os.path.join(DATA_DIR, "temp_audio")
CONFIG_FILE     = "config.json"
MAX_ENTRIES     = 100
BLOAT_WARN_MB   = 50
WHISPER_RATE    = 16000
ICON_PATH       = "bronson_icon.png"
BRONSON_IMG_PATH = os.path.join("Golden_Chain", "pinkblonsonbeta", "assets", "BronsonR.webp")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)
os.makedirs(TEMP_AUDIO_DIR, exist_ok=True)

# ── Tokyo Night Neon Themes ──
THEMES = {
    "dark": {
        "mode": "dark",
        "bg_main":  "#1a1b26",   # Tokyo Night – deep navy
        "bg_panel": "#24283b",   # Tokyo Night – panel navy
        "bg_inset": "#13141f",   # Deepest inset
        "fg_main":  "#c0caf5",   # Lavender text
        "fg_muted": "#565f89",   # Muted blue-gray
        "pink":     "#f7768e",   # Neon rose/red
        "cyan":     "#7dcfff",   # Neon sky-cyan
        "gold":     "#e0af68",   # Warm amber
        "emerald":  "#9ece6a",   # Neon leaf-green
        "purple":   "#bb9af7",   # Neon purple
        "btn_bg":   "#292e42",   # Button dark navy
        "btn_act":  "#3d59a1",   # Active – electric blue
        "btn_stop": "#3d1a24",   # Stop – deep crimson
        "prog_bg":  "#9ece6a",   # Progress green
    },
    "light": {
        "mode": "light",
        "bg_main":  "#e9e9f4",   # Soft lavender-white
        "bg_panel": "#ffffff",
        "bg_inset": "#f0f0fa",
        "fg_main":  "#1a1b26",
        "fg_muted": "#787c99",
        "pink":     "#c53b53",
        "cyan":     "#2e7de9",
        "gold":     "#8c6c3e",
        "emerald":  "#587539",
        "purple":   "#7847bd",
        "btn_bg":   "#d5d6e8",
        "btn_act":  "#a8aecb",
        "btn_stop": "#f4b8c3",
        "prog_bg":  "#587539",
    }
}

# ══════════════════════════════════════════════════════════
# 1. Config & Data Source
# ══════════════════════════════════════════════════════════
def get_session_path() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    return os.path.join(DATA_DIR, f"stream_{stamp}.json")

SESSION_FILE    = get_session_path()
LOCK_FILE       = SESSION_FILE + ".lock"
_stamp          = datetime.now().strftime("%Y%m%d_%H%M")
STT_ARCHIVE     = os.path.join(ARCHIVE_DIR, f"{_stamp}_stt.txt")

# アーカイブファイルにヘッダーを書き込む
try:
    with open(STT_ARCHIVE, "a", encoding="utf-8") as _f:
        _f.write(f"# Pink Bronson STT Archive  [{datetime.now().strftime('%Y-%m-%d %H:%M')}]\n")
except Exception as _e:
    print(f"[Warning] STT archive file could not be created: {_e}")

def load_config() -> dict:
    cfg = {
        "theme": "dark", "last_mic": "",
        "api_keys": {
            "twitch_token": "", "twitch_channel": "",
            "twitch_client_id": "", "twitch_client_secret": "",
            "gemini_key": "", "firebase_url": ""
        }
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                cfg.update(loaded)
                if "api_keys" not in cfg:
                    cfg["api_keys"] = {}
        except Exception:
            pass
    return cfg

def save_config(cfg: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"config.json 保存エラー: {e}")

def write_log(text: str) -> dict:
    new_entry = {"timestamp": str(time.time()), "text": text}
    # テキストアーカイブにも追記（日時付き）
    try:
        ts = datetime.now().strftime("%H:%M:%S")
        with open(STT_ARCHIVE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {text}\n")
    except Exception:
        pass
    retries = 5
    for attempt in range(retries):
        try:
            with FileLock(LOCK_FILE, timeout=1):
                entries = []
                if os.path.exists(SESSION_FILE):
                    with open(SESSION_FILE, encoding="utf-8") as f:
                        try:
                            entries = json.load(f)
                        except json.JSONDecodeError:
                            entries = []

                entries.append(new_entry)
                if len(entries) > MAX_ENTRIES:
                    entries = entries[-MAX_ENTRIES:]

                tmp = SESSION_FILE + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(entries, f, ensure_ascii=False, indent=2)
                os.replace(tmp, SESSION_FILE)  # アトミック置換（削除→リネームの競合を回避）
            return new_entry
        except Timeout:
            time.sleep(0.1)
        except Exception:
            break
    return new_entry

def get_session_size_mb() -> float:
    try:
        return os.path.getsize(SESSION_FILE) / (1024 * 1024)
    except FileNotFoundError:
        return 0.0

def get_input_devices() -> list[str]:
    devices = []
    try:
        hostapi = sd.default.hostapi
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0 and dev["hostapi"] == hostapi:
                devices.append(f"[{i}] {dev['name'].strip()}")
    except Exception:
        devices.append("[None] デフォルトマイク")
    return devices or ["[None] マイクが見つかりません"]

# ══════════════════════════════════════════════════════════
# 2. STT Engine
# ══════════════════════════════════════════════════════════
HALLUCINATIONS = [
    "ご視聴ありがとうございました", "ご視聴いただきありがとうございました",
    "チャンネル登録", "それではまた", "字幕:", "ありがとうございました"
]

class AudioProcessor:
    def __init__(self, ui_app):
        self.ui = ui_app
        self.model = None
        self.is_running = False
        self.device_id = None
        self._thread = None
        self.stt_backend = "whisper"   # "whisper" | "gemini"
        self.gemini_key = ""

    def _load_model(self) -> bool:
        self.ui.after(0, lambda: self.ui.update_status("Loading AI... (数秒)", "orange"))
        try:
            print("🚀 Whisper モデルを CPU モードで読み込みます...")
            self.model = WhisperModel("base", device="cpu", compute_type="int8")
            print("✨ Whisper モデル読み込み完了！")
            return True
        except Exception as e:
            print(f"AI モデルエラー: {e}")
            self.ui.after(0, lambda: self.ui.update_status("Model Error", "red"))
            return False

    def start(self, device_id: str | None = None,
              stt_backend: str = "whisper", gemini_key: str = ""):
        if self.is_running: return
        self.device_id = device_id
        self.stt_backend = stt_backend
        self.gemini_key = gemini_key
        self.is_running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.is_running = False
        self.ui.after(0, lambda: self.ui.update_status("Stopped", "red"))

    def _loop(self):
        if self.stt_backend == "gemini":
            pass  # モデルロード不要
        elif not self.model and not self._load_model():
            self.is_running = False
            return

        # バックエンドタグを使い回す（ステータスの一貫性を保つ）
        tag = "[Gemini]" if self.stt_backend == "gemini" else "[Whisper]"
        idle_msg = f"Running {tag} 待機中"
        self.ui.after(0, lambda m=idle_msg: self.ui.update_status(m, "lightgreen"))

        dev = None
        if self.device_id:
            try:
                dev = int(self.device_id.split("]")[0].replace("[", ""))
            except Exception:
                pass

        try:
            info = sd.query_devices(dev if dev is not None else sd.default.device[0])
            mic_rate = int(info["default_samplerate"])
        except Exception:
            mic_rate = 44100

        q = queue.Queue()
        def cb(indata, frames, t, status):
            q.put(bytes(indata))

        buf = b""
        silence = 0
        speaking = False
        block = max(mic_rate // 2, 1024)

        try:
            with sd.RawInputStream(samplerate=mic_rate, channels=1,
                                   dtype="int16", blocksize=block,
                                   callback=cb, device=dev):
                while self.is_running:
                    try:
                        chunk = q.get(timeout=1)
                        arr = np.frombuffer(chunk, dtype=np.int16)
                        rms = float(np.sqrt(np.mean(arr.astype(np.float32) ** 2)))

                        if rms > 800:
                            if not speaking:
                                self.ui.after(0, lambda t=tag: self.ui.update_status(f"🟢 {t} 聞き取り中", "lime"))
                            speaking = True
                            silence = 0
                            buf += chunk
                        elif speaking:
                            silence += 1
                            buf += chunk
                            if silence > 2:
                                self._transcribe(buf, mic_rate)
                                buf = b""
                                speaking = False
                                self.ui.after(0, lambda m=idle_msg: self.ui.update_status(m, "lightgreen"))
                    except queue.Empty:
                        pass
        except Exception as e:
            self.ui.after(0, lambda: self.ui.update_status("Mic Error", "red"))
            self.is_running = False

    def _transcribe(self, raw: bytes, mic_rate: int):
        self.ui.after(0, lambda: self.ui.update_status("⚙️ 文字起こし中", "yellow"))

        # 無音チェック（どちらのバックエンドでも共通）
        pcm_check = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        if np.max(np.abs(pcm_check)) < 0.05:
            self.ui.after(0, lambda: self.ui.update_status("Running (待機中)", "lightgreen"))
            return

        if self.stt_backend == "gemini":
            self._transcribe_gemini(raw, mic_rate)
            return

        # ── Whisper バックエンド ───────────────────────────
        pcm = pcm_check
        if mic_rate != WHISPER_RATE:
            n = int(len(pcm) * WHISPER_RATE / mic_rate)
            pcm = np.interp(np.linspace(0, len(pcm)-1, n), np.arange(len(pcm)), pcm).astype(np.float32)

        try:
            segs, _ = self.model.transcribe(pcm, beam_size=5, language="ja", vad_filter=True, condition_on_previous_text=False)
            text = "".join(s.text for s in segs).strip()

            for h in HALLUCINATIONS:
                if h in text and len(text) < len(h) + 10:
                    text = ""
                    break

            if text:
                write_log(text)
                self.ui.after(0, lambda t=text: self.ui.on_transcribed(t))
                mb = get_session_size_mb()
                if mb > BLOAT_WARN_MB:
                    self.ui.after(0, lambda m=mb: self.ui.show_bloat_warning(m))
        except Exception as e:
            print(f"文字起こしエラー: {e}")
        finally:
            self.ui.after(0, lambda: self.ui.update_status("Running (待機中)", "lightgreen"))

    def _transcribe_gemini(self, raw: bytes, mic_rate: int):
        """Gemini File API を使って文字起こし。"""
        tmp_path = os.path.join(TEMP_AUDIO_DIR, f"stt_{int(time.time())}.wav")
        try:
            import gemini_stt
            gemini_stt.save_wav(raw, mic_rate, tmp_path)
            text = gemini_stt.transcribe(tmp_path, self.gemini_key)

            if text:
                # Gemini は幻覚しにくいが念のため簡易チェック
                for h in HALLUCINATIONS:
                    if h in text and len(text) < len(h) + 10:
                        text = ""
                        break

            if text:
                write_log(text)
                self.ui.after(0, lambda t=text: self.ui.on_transcribed(t))
                mb = get_session_size_mb()
                if mb > BLOAT_WARN_MB:
                    self.ui.after(0, lambda m=mb: self.ui.show_bloat_warning(m))
        except Exception as e:
            print(f"Gemini STT エラー: {e}")
            self.ui.after(0, lambda: self.ui.update_status("[Gemini] エラー", "red"))
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            self.ui.after(0, lambda: self.ui.update_status("Running [Gemini] 待機中", "lightgreen"))

# ══════════════════════════════════════════════════════════
# 3. Mic Meter
# ══════════════════════════════════════════════════════════
class MicMeter:
    def __init__(self, ui_app):
        self.ui = ui_app
        self._running = False
        self._stream = None

    def start(self, device_id: str | None = None):
        self.stop()
        dev = None
        if device_id:
            try: dev = int(device_id.split("]")[0].replace("[", ""))
            except: pass
        try:
            info = sd.query_devices(dev if dev is not None else sd.default.device[0])
            rate = int(info["default_samplerate"])
        except Exception:
            rate = 44100
        try:
            self._stream = sd.InputStream(samplerate=rate, channels=1, dtype="int16", device=dev)
            self._stream.start()
            self._running = True
            threading.Thread(target=self._loop, daemon=True).start()
        except: pass

    def stop(self):
        self._running = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except: pass

    def _loop(self):
        while self._running:
            try:
                data, _ = self._stream.read(1024)
                rms = float(np.sqrt(np.mean(data.astype(np.float32) ** 2)))
                vol = min(int(rms / 3000 * 100), 100)
                self.ui.after(0, lambda v=vol: self.ui.update_meter(v))
            except: pass
            time.sleep(0.05)


# ══════════════════════════════════════════════════════════
# 4. Settings Window (Sub-Window)
# ══════════════════════════════════════════════════════════
class SettingsWindow(tk.Toplevel):
    def __init__(self, parent, config: dict, on_save_callback):
        super().__init__(parent)
        self.parent = parent
        self.config = config
        self.on_save = on_save_callback
        
        self.title("PRODUCER SETTINGS")
        self.geometry("420x660")
        self.resizable(False, False)
        _bg  = "#1a1b26"   # Tokyo Night bg
        _pan = "#24283b"   # panel
        _inp = "#292e42"   # input field bg
        _pink = "#f7768e"
        _cyan = "#7dcfff"
        _txt = "#c0caf5"
        self.configure(bg=_bg)
        self.attributes("-topmost", True)
        self.grab_set()

        lbl_font  = ("Helvetica", 10, "bold")
        entry_font = ("Courier", 10)

        def _section(label, color):
            tk.Label(self, text=label, bg=_bg, fg=color, font=lbl_font).pack(pady=(14, 2), anchor="w", padx=22)

        def _entry(show=None):
            e = tk.Entry(self, font=entry_font, show=show or "", bg=_inp, fg=_txt,
                         insertbackground=_cyan, relief="flat", bd=4)
            e.pack(fill=tk.X, padx=22)
            return e

        # Theme
        _section("THEME", _cyan)
        self.combo_theme = ttk.Combobox(self, values=["dark", "light"], state="readonly")
        self.combo_theme.pack(fill=tk.X, padx=22)
        self.combo_theme.set(self.config.get("theme", "dark"))

        # APIs
        keys = self.config.get("api_keys", {})

        _section("TWITCH TOKEN (OAuth)", _pink)
        self.ent_twitch = _entry(show="*")
        self.ent_twitch.insert(0, keys.get("twitch_token", ""))

        _section("TWITCH CHANNEL NAME", _pink)
        self.ent_channel = _entry()
        self.ent_channel.insert(0, keys.get("twitch_channel", ""))

        _section("TWITCH CLIENT-ID", _pink)
        self.ent_client_id = _entry(show="*")
        self.ent_client_id.insert(0, keys.get("twitch_client_id", ""))

        _section("TWITCH CLIENT-SECRET", _pink)
        self.ent_client_secret = _entry(show="*")
        self.ent_client_secret.insert(0, keys.get("twitch_client_secret", ""))

        _section("GEMINI API KEY", _pink)
        self.ent_gemini = _entry(show="*")
        self.ent_gemini.insert(0, keys.get("gemini_key", ""))

        _section("FIREBASE URL", _pink)
        self.ent_fire = _entry(show="*")
        self.ent_fire.insert(0, keys.get("firebase_url", ""))

        # SAVE
        btn_save = tk.Button(
            self, text="SAVE & APPLY", command=self.save_cfg,
            bg=_cyan, fg="#1a1b26", font=("Helvetica", 12, "bold"),
            relief="flat", cursor="hand2", activebackground="#b4e4ff")
        btn_save.pack(pady=28, fill=tk.X, padx=22, ipady=6)

    def save_cfg(self):
        new_theme = self.combo_theme.get()
        self.config["theme"] = new_theme
        self.config["api_keys"] = {
            "twitch_token":         self.ent_twitch.get().strip(),
            "twitch_channel":       self.ent_channel.get().strip(),
            "twitch_client_id":     self.ent_client_id.get().strip(),
            "twitch_client_secret": self.ent_client_secret.get().strip(),
            "gemini_key":           self.ent_gemini.get().strip(),
            "firebase_url":         self.ent_fire.get().strip()
        }
        save_config(self.config)
        self.on_save()
        self.destroy()

# ══════════════════════════════════════════════════════════
# 5. UI (Pink Bronson App)
# ══════════════════════════════════════════════════════════
class PinkBronsonUI(tk.Tk):
    def __init__(self, config: dict):
        super().__init__()
        self.cfg = config
        self.theme = THEMES[self.cfg.get("theme", "dark")]

        self.title("PINK BRONSON")
        self.geometry("400x940")
        self.resizable(False, True)
        self.attributes("-topmost", True)

        # Set App Icon if PIL is available
        if os.path.exists(ICON_PATH):
            try:
                if HAS_PIL:
                    icon_img = ImageTk.PhotoImage(Image.open(ICON_PATH))
                    self.wm_iconphoto(True, icon_img)
                else:
                    icon_img = tk.PhotoImage(file=ICON_PATH)
                    self.wm_iconphoto(True, icon_img)
            except Exception as e:
                print(f"アイコン読み込みエラー: {e}")

        self._stt = AudioProcessor(self)
        self._stt_restart_guard = False
        self._meter = MicMeter(self)
        self._procs = {
            "Golden_Chain": None,
            "Blue_RAY-BAN": None,
            "Emerald_Rolex": None
        }
        self._bloat_warned = False

        self.widgets = {} # For dynamic theme application
        self._build()
        self.apply_theme()

        saved_mic = self.cfg.get("last_mic", "")
        if saved_mic and saved_mic in self.combo_mic["values"]:
            self.combo_mic.set(saved_mic)
        elif self.combo_mic["values"]:
            self.combo_mic.current(0)
            
        self._meter.start(self.combo_mic.get())

    def _build(self):
        # ══ Tokyo Night Header ══════════════════════════════════
        fr_header = tk.Frame(self, pady=10)
        fr_header.pack(fill=tk.X, padx=16)
        self.widgets["fr_header"] = (fr_header, "bg_main")

        # BronsonR.webp – left side
        self._bronson_photo = None
        if HAS_PIL and os.path.exists(BRONSON_IMG_PATH):
            try:
                _img = Image.open(BRONSON_IMG_PATH).convert("RGBA")
                _w, _h = _img.size
                _new_h = 88
                _new_w = int(_w * _new_h / _h)
                _img = _img.resize((_new_w, _new_h), Image.LANCZOS)
                self._bronson_photo = ImageTk.PhotoImage(_img)
                lbl_img = tk.Label(fr_header, image=self._bronson_photo, bd=0)
                lbl_img.pack(side=tk.LEFT, padx=(0, 14))
                self.widgets["lbl_bronson"] = (lbl_img, "bg_main")
            except Exception as e:
                print(f"BronsonR load error: {e}")

        # Title + subtitle stack – center-left
        fr_title_stack = tk.Frame(fr_header)
        fr_title_stack.pack(side=tk.LEFT, fill=tk.Y)
        self.widgets["fr_title_stack"] = (fr_title_stack, "bg_main")

        self.lbl_title = tk.Label(
            fr_title_stack, text="PINK BRONSON",
            font=("Helvetica", 20, "bold"), anchor="w")
        self.lbl_title.pack(anchor="w")
        self.widgets["lbl_title"] = (self.lbl_title, "bg_main", "pink")

        self.lbl_sub = tk.Label(
            fr_title_stack, text="The Producer's Desk",
            font=("Helvetica", 9), anchor="w")
        self.lbl_sub.pack(anchor="w", pady=(1, 0))
        self.widgets["lbl_sub"] = (self.lbl_sub, "bg_main", "cyan")

        # Settings button – right side
        self.btn_set = tk.Button(
            fr_header, text="⚙", command=self.open_settings,
            font=("Helvetica", 13, "bold"), relief="flat",
            cursor="hand2", padx=8, pady=4)
        self.btn_set.pack(side=tk.RIGHT, anchor="n", padx=(0, 4))
        self.widgets["btn_set"] = (self.btn_set, "btn_bg", "cyan")

        # Neon separator line
        fr_sep = tk.Frame(self, height=2)
        fr_sep.pack(fill=tk.X, padx=16, pady=(0, 8))
        fr_sep.pack_propagate(False)
        self.widgets["fr_sep"] = (fr_sep, "pink")

        # ── MIC ──
        frame_mic = tk.Frame(self)
        frame_mic.pack(fill=tk.X, padx=20, pady=(10,0))
        self.widgets["frame_mic"] = (frame_mic, "bg_main")

        self.lbl_mic = tk.Label(frame_mic, text="MIC SELECT", font=("Helvetica", 9, "bold"))
        self.lbl_mic.pack(side=tk.LEFT)
        self.widgets["lbl_mic"] = (self.lbl_mic, "bg_main", "gold")

        self.combo_mic = ttk.Combobox(frame_mic, values=get_input_devices(), state="readonly", width=26)
        self.combo_mic.pack(side=tk.LEFT, padx=8)
        self.combo_mic.bind("<<ComboboxSelected>>", self._on_mic_change)

        # ── STT Backend ──
        fr_backend = tk.Frame(self)
        fr_backend.pack(fill=tk.X, padx=20, pady=(10, 0))
        self.widgets["fr_backend"] = (fr_backend, "bg_main")

        tk.Label(fr_backend, text="STT ENGINE", font=("Helvetica", 9, "bold")).pack(side=tk.LEFT)
        self.widgets["lbl_backend"] = (fr_backend.winfo_children()[0], "bg_main", "gold")

        self.stt_backend_var = tk.StringVar(value=self.cfg.get("stt_backend", "whisper"))

        def _on_backend_change(*_):
            if self._stt_restart_guard:
                return
            new_backend = self.stt_backend_var.get()
            tag = "[Gemini]" if new_backend == "gemini" else "[Whisper]"
            if not self._stt.is_running:
                self.lbl_status.config(text=f"STT: Stopped {tag}")
                return
            # Running — validate then restart with new engine
            api_key = self.cfg.get("api_keys", {}).get("gemini_key", "")
            if new_backend == "gemini" and not api_key:
                self._stt_restart_guard = True
                self.stt_backend_var.set("whisper")
                self._stt_restart_guard = False
                messagebox.showwarning(
                    "APIキー未設定",
                    "Gemini STT を使うには Settings でGemini APIキーを設定してください。")
                return
            mic = self.combo_mic.get()
            def _restart():
                self._stt.stop()
                self._stt.start(mic, stt_backend=new_backend, gemini_key=api_key)
            threading.Thread(target=_restart, daemon=True).start()

        self.stt_backend_var.trace_add("write", _on_backend_change)

        rb_whisper = tk.Radiobutton(fr_backend, text="Local Whisper",
                                    variable=self.stt_backend_var, value="whisper",
                                    font=("Helvetica", 9), relief="flat", cursor="hand2")
        rb_whisper.pack(side=tk.LEFT, padx=(12, 0))
        self.widgets["rb_whisper"] = (rb_whisper, "bg_main", "fg_main")

        rb_gemini = tk.Radiobutton(fr_backend, text="Gemini API",
                                   variable=self.stt_backend_var, value="gemini",
                                   font=("Helvetica", 9), relief="flat", cursor="hand2")
        rb_gemini.pack(side=tk.LEFT, padx=(8, 0))
        self.widgets["rb_gemini"] = (rb_gemini, "bg_main", "cyan")

        # ── STT Controls ──
        self.lbl_status = tk.Label(self, text="STT: Stopped", font=("Helvetica", 10, "bold"))
        self.lbl_status.pack(pady=(10, 0))
        self.widgets["lbl_status"] = (self.lbl_status, "bg_main", "fg_main")
        _on_backend_change()   # lbl_status 作成後に初期表示を反映

        self.btn_stt = tk.Button(self, text="▶  START  /  ■  STOP", command=self.toggle_stt, font=("Helvetica", 11, "bold"), relief="flat", cursor="hand2")
        self.btn_stt.pack(fill=tk.X, padx=20, pady=(8,4), ipady=5)
        self.widgets["btn_stt"] = (self.btn_stt, "btn_bg", "fg_main", "btn_act")

        self.meter_var = tk.IntVar(value=0)
        self.meter = ttk.Progressbar(self, orient="horizontal", length=330, mode="determinate", variable=self.meter_var)
        self.meter.pack(pady=(2, 12), padx=20)

        # ── Latest Phrase ──
        self.lbl_late_title = tk.Label(self, text="LATEST PHRASE", font=("Helvetica", 8, "bold"))
        self.lbl_late_title.pack()
        self.widgets["lbl_late_title"] = (self.lbl_late_title, "bg_main", "gold")

        self.frame_lat = tk.Frame(self, bd=2, relief="groove")
        self.frame_lat.pack(fill=tk.X, padx=20, pady=(4, 12))
        self.widgets["frame_lat"] = (self.frame_lat, "bg_panel")

        self.lbl_latest = tk.Label(self.frame_lat, text="(Standby...)", font=("Helvetica", 13, "bold"), wraplength=320, justify="center", height=2)
        self.lbl_latest.pack(padx=10, pady=8)
        self.widgets["lbl_latest"] = (self.lbl_latest, "bg_panel", "cyan")

        self.lbl_bloat = tk.Label(self, text="", font=("Helvetica", 8, "bold"), wraplength=340, justify="center")
        self.widgets["lbl_bloat"] = (self.lbl_bloat, "bg_main", "pink")

        # ── Session Log ──
        self.lbl_log_title = tk.Label(self, text="SESSION LOG", font=("Helvetica", 8, "bold"))
        self.lbl_log_title.pack()
        self.widgets["lbl_log_title"] = (self.lbl_log_title, "bg_main", "fg_muted")

        self.txt_log = scrolledtext.ScrolledText(self, font=("Helvetica", 10), wrap=tk.WORD, height=10, relief="flat", bd=0, insertbackground="white")
        self.txt_log.pack(fill=tk.BOTH, expand=True, padx=20, pady=(4,4))
        self.txt_log.insert(tk.END, "─── Session Started ───\n")
        
        self.txt_log.tag_configure("log_token", foreground="#00F0FF")
        self.txt_log.tag_configure("log_api", foreground="#AAFF00")
        self.txt_log.tag_configure("log_error", foreground="#FF007F")
        self.txt_log.tag_configure("log_warn", foreground="#FFD700")
        self.txt_log.tag_configure("log_default", foreground="#CCCCCC")

        self.txt_log.configure(state="disabled")
        self.widgets["txt_log"] = (self.txt_log, "bg_inset", "fg_main")

        # ── Child Services ──
        self.fr_child = tk.LabelFrame(self, text=" CHILD SERVICES ", font=("Helvetica", 8, "bold"), bd=1)
        self.fr_child.pack(fill=tk.X, padx=20, pady=(8, 16), ipady=4)
        self.widgets["fr_child"] = (self.fr_child, "bg_main", "fg_muted")

        # 1. Golden_Chain (要約)
        self.btn_golden = tk.Button(self.fr_child, text="Launch Golden_Chain (Summarizer)", command=lambda: self.toggle_proc("Golden_Chain", "golden_chain.py"), font=("Helvetica", 10, "bold"), relief="flat", cursor="hand2")
        self.btn_golden.pack(fill=tk.X, padx=10, pady=(8, 4), ipady=3)
        self.widgets["btn_golden"] = (self.btn_golden, "bg_panel", "gold", "btn_act")

        # 2. Blue_RAY-BAN (各言語翻訳)
        fr_rayban = tk.Frame(self.fr_child, bg=self.theme.get("bg_panel", "#1A1A1A"))
        fr_rayban.pack(fill=tk.X, padx=10, pady=(4, 4))
        self.widgets["fr_rayban"] = (fr_rayban, "bg_panel")
        
        self.btn_rayban = tk.Button(fr_rayban, text="Launch Blue_RAY-BAN (Translator)", command=lambda: self.toggle_proc("Blue_RAY-BAN", "blue_rayban.py"), font=("Helvetica", 10, "bold"), relief="flat", cursor="hand2")
        self.btn_rayban.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        self.widgets["btn_rayban"] = (self.btn_rayban, "bg_panel", "cyan", "btn_act")

        self.btn_rayban_set = tk.Button(fr_rayban, text="⚙️ Setting", command=self._open_rayban_settings, font=("Helvetica", 9, "bold"), relief="flat", cursor="hand2")
        self.btn_rayban_set.pack(side=tk.RIGHT, padx=(5,0), ipady=3)
        self.widgets["btn_rayban_set"] = (self.btn_rayban_set, "btn_bg", "cyan", "btn_act")

        # 3. Emerald_Rolex (Twitchチャット表示)
        fr_rolex = tk.Frame(self.fr_child, bg=self.theme.get("bg_panel", "#1A1A1A"))
        fr_rolex.pack(fill=tk.X, padx=10, pady=(4, 8))
        self.widgets["fr_rolex"] = (fr_rolex, "bg_panel")
        
        self.btn_rolex = tk.Button(fr_rolex, text="Launch Emerald_Rolex (Chat viewer)", command=lambda: self.toggle_proc("Emerald_Rolex", "emerald_rolex.py"), font=("Helvetica", 10, "bold"), relief="flat", cursor="hand2")
        self.btn_rolex.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        self.widgets["btn_rolex"] = (self.btn_rolex, "bg_panel", "emerald", "btn_act")

        self.btn_rolex_set = tk.Button(fr_rolex, text="⚙️ Setting", command=self._open_rolex_settings, font=("Helvetica", 9, "bold"), relief="flat", cursor="hand2")
        self.btn_rolex_set.pack(side=tk.RIGHT, padx=(5,0), ipady=3)
        self.widgets["btn_rolex_set"] = (self.btn_rolex_set, "btn_bg", "emerald", "btn_act")

    def _open_rayban_settings(self):
        import webbrowser
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Blue_Rayban", "settings.html")
        webbrowser.open(f"file:///{path.replace(os.sep, '/')}")

    def _open_rolex_settings(self):
        import webbrowser
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Emerald_Rolex", "settings.html")
        webbrowser.open(f"file:///{path.replace(os.sep, '/')}")

    def apply_theme(self):
        """Applies colors to all registered widgets based on current self.theme"""
        self.configure(bg=self.theme["bg_main"])
        for widget, bg_key, *args in self.widgets.values():
            bg = self.theme.get(bg_key, self.theme["bg_main"])
            fg = self.theme.get(args[0], self.theme["fg_main"]) if len(args) > 0 else None
            act = self.theme.get(args[1], None) if len(args) > 1 else None
            
            w_opts = {"bg": bg}
            if fg: w_opts["fg"] = fg
            if act: w_opts["activebackground"] = act

            try:
                widget.config(**w_opts)
                # Radiobutton はインジケーター内の selectcolor も合わせる
                if isinstance(widget, tk.Radiobutton):
                    widget.config(
                        selectcolor=self.theme.get("bg_panel", "#1F1528"),
                        activeforeground=self.theme.get("cyan", "#00F0FF"),
                    )
            except Exception:
                pass

        sty = ttk.Style()
        sty.theme_use("default")
        sty.configure("TCombobox", fieldbackground=self.theme["bg_panel"], background=self.theme["bg_panel"], foreground=self.theme["fg_main"])
        sty.configure("pb.Horizontal.TProgressbar", background=self.theme["prog_bg"], thickness=10)

    def open_settings(self):
        SettingsWindow(self, self.cfg, self.on_settings_saved)

    def on_settings_saved(self):
        self.cfg = load_config()
        self.theme = THEMES[self.cfg.get("theme", "dark")]
        self.apply_theme()

    # ── Events ──
    def _on_mic_change(self, _event):
        mic = self.combo_mic.get()
        self._meter.start(mic)
        self.cfg["last_mic"] = mic
        save_config(self.cfg)

    def toggle_stt(self):
        if self._stt.is_running:
            self._stt.stop()
        else:
            mic = self.combo_mic.get()
            backend = self.stt_backend_var.get()
            api_key = self.cfg.get("api_keys", {}).get("gemini_key", "")
            if backend == "gemini" and not api_key:
                messagebox.showwarning(
                    "APIキー未設定",
                    "Gemini STT を使うには Settings でGemini APIキーを設定してください。")
                return
            self.cfg["last_mic"] = mic
            self.cfg["stt_backend"] = backend
            save_config(self.cfg)
            self._stt.start(mic, stt_backend=backend, gemini_key=api_key)

    def toggle_proc(self, name: str, script: str = ""):
        proc = self._procs.get(name)
        
        # ボタンと色の判定
        if name == "Golden_Chain":
            btn = self.btn_golden
            color_fg = "gold"
            full_name = "Golden_Chain (Summarizer)"
        elif name == "Blue_RAY-BAN":
            btn = self.btn_rayban
            color_fg = "cyan"
            full_name = "Blue_RAY-BAN (Translator)"
        else:
            btn = self.btn_rolex
            color_fg = "emerald"
            full_name = "Emerald_Rolex (Chat viewer)"
            
        if proc and proc.poll() is None:
            # 起動中 → 停止
            if os.name == 'nt':
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                proc.terminate()
            self._procs[name] = None
            btn.config(text=f"Launch {full_name}", bg=self.theme["bg_panel"], fg=self.theme[color_fg])
        else:
            # 停止中 → 起動
            try:
                base = os.path.dirname(os.path.abspath(__file__))
                if name == "Golden_Chain":
                    app_dir = os.path.join(base, "Golden_Chain", "pinkblonsonbeta")
                    python_exe = os.path.join(app_dir, "venv", "Scripts", "python.exe")
                    main_script = os.path.join(app_dir, "src", "main_ui.py")
                elif name == "Blue_RAY-BAN":
                    app_dir = os.path.join(base, "Blue_Rayban")
                    python_exe = r"C:\Users\seyak\AppData\Local\Python\bin\python.exe"
                    if not os.path.exists(python_exe):
                        python_exe = sys.executable  # フォールバック
                    main_script = os.path.join(app_dir, "main_ui.py")
                else:  # Emerald_Rolex
                    app_dir = os.path.join(base, "Emerald_Rolex")
                    python_exe = sys.executable
                    main_script = os.path.join(app_dir, "main_ui.py")

                if not os.path.exists(python_exe):
                    self.after(0, lambda n=name: messagebox.showerror(
                        "起動エラー",
                        f"{n} の venv が見つかりません。\n"
                        f"該当フォルダの setup_beta.bat を先に実行してください。\n\n"
                        f"探したパス: {python_exe}"
                    ))
                    return
                if not os.path.exists(main_script):
                    self.after(0, lambda n=name, s=main_script: messagebox.showerror(
                        "起動エラー", f"{n} のスクリプトが見つかりません:\n{s}"
                    ))
                    return

                p = subprocess.Popen(
                    [python_exe, main_script],
                    cwd=app_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    encoding="utf-8",
                    errors="replace"
                )
                self._procs[name] = p
                btn.config(text=f"■ Stop {full_name}", bg=self.theme["btn_stop"], fg="#FFFFFF")
                threading.Thread(target=self._read_child_output, args=(name, p), daemon=True).start()
            except Exception as e:
                messagebox.showerror("起動エラー", f"{name} の起動に失敗しました:\n{e}")

    def _read_child_output(self, name: str, proc: subprocess.Popen):
        try:
            for line in iter(proc.stdout.readline, ""):
                if not line: break
                line = line.strip()
                if not line: continue
                self.after(0, lambda n=name, l=line: self._append_child_log(n, l))
        except Exception:
            pass
        finally:
            self.after(0, lambda n=name: self._on_child_exit(n))
            
    def _on_child_exit(self, name: str):
        if self._procs.get(name) is not None:
            self._procs[name] = None
            if name == "Golden_Chain":
                btn = self.btn_golden
                color_fg = "gold"
                full_name = "Golden_Chain (Summarizer)"
            elif name == "Blue_RAY-BAN":
                btn = self.btn_rayban
                color_fg = "cyan"
                full_name = "Blue_RAY-BAN (Translator)"
            else:
                btn = self.btn_rolex
                color_fg = "emerald"
                full_name = "Emerald_Rolex (Chat viewer)"
            btn.config(text=f"Launch {full_name}", bg=self.theme["bg_panel"], fg=self.theme[color_fg])
            self._append_child_log(name, f"[System] {full_name} UI closed.")
            
    def _append_child_log(self, name: str, text: str):
        now = datetime.now().strftime("%H:%M:%S")
        tag = "log_default"
        text_upper = text.upper()
        if "[TOKEN]" in text_upper: tag = "log_token"
        elif "[API]" in text_upper: tag = "log_api"
        elif "[ERROR]" in text_upper or "EXCEPTION" in text_upper or "TRACEBACK" in text_upper: tag = "log_error"
        elif "[WARN]" in text_upper: tag = "log_warn"
        
        self.txt_log.configure(state="normal")
        self.txt_log.insert(tk.END, f"[{now}] [{name}] {text}\n", tag)
        self.txt_log.see(tk.END)
        self.txt_log.configure(state="disabled")

    # ── Thread-Safe Updaters ──
    def update_status(self, text: str, color: str):
        self.lbl_status.config(text=f"STT: {text}")
        if color == "red" or color == "tomato": self.lbl_status.config(fg=self.theme["pink"])
        elif color == "lime" or color == "lightgreen": self.lbl_status.config(fg=self.theme["cyan"])
        elif color == "orange" or color == "yellow": self.lbl_status.config(fg=self.theme["gold"])

    def update_meter(self, vol: int):
        self.meter_var.set(vol)

    def on_transcribed(self, text: str):
        engine_tag = "[G]" if self._stt.stt_backend == "gemini" else "[L]"
        self.lbl_latest.config(text=text)
        now = datetime.now().strftime("%H:%M:%S")
        self.txt_log.configure(state="normal")
        self.txt_log.insert(tk.END, f"[{now}]{engine_tag} {text}\n")
        self.txt_log.see(tk.END)
        self.txt_log.configure(state="disabled")

    def show_bloat_warning(self, mb: float):
        if not self._bloat_warned:
            self._bloat_warned = True
            self.lbl_bloat.config(text=f"⚠️ {mb:.1f} MB: ログが肥大化しています！", fg=self.theme["pink"])
            self.lbl_bloat.pack(fill=tk.X, padx=20, pady=4)

    def on_closing(self):
        self._meter.stop()
        self._stt.stop()
        for p in self._procs.values():
            if p and p.poll() is None: p.terminate()
        self.cfg["last_mic"] = self.combo_mic.get()
        save_config(self.cfg)
        self.destroy()

if __name__ == "__main__":
    app = PinkBronsonUI(load_config())
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
