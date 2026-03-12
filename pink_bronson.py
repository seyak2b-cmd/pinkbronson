"""
╔══════════════════════════════════════════════════════════╗
║   PINK BRONSON  -  The Master-Hub Producer               ║
║   v3.0  |  80s Neon Tokyo & Settings Edition             ║
╚══════════════════════════════════════════════════════════╝
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import os, json, threading, time, subprocess, queue, sys, wave, webbrowser
from datetime import datetime


def _try_load_dseg():
    """DSEG14 Classic フォントを Windows API でロードして返す。
    assets/fonts/ に TTF がなければ Courier New にフォールバック。"""
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'assets', 'fonts', 'DSEG14Classic-Regular.ttf'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'assets', 'fonts', 'DSEG7Classic-Regular.ttf'),
    ]
    try:
        import ctypes
        for fp in candidates:
            if os.path.exists(fp):
                ctypes.windll.gdi32.AddFontResourceExW(fp, 0x10, 0)
                name = 'DSEG14 Classic' if 'DSEG14' in fp else 'DSEG7 Classic'
                print(f"[Font] DSEG loaded: {name}")
                return name
    except Exception as e:
        print(f"[Font] DSEG load failed: {e}")
    return 'Courier New'


def _load_custom_fonts():
    """VT323 / Pixel Mplus 12 / DotGothic16 を Windows API でロード。
    assets/fonts/ に TTF がなければ Tkinter のシステムフォントフォールバックに委ねる。"""
    _here = os.path.dirname(os.path.abspath(__file__))
    fonts_dir = None
    for _ in range(6):
        candidate = os.path.join(_here, 'assets', 'fonts')
        if os.path.isdir(candidate):
            fonts_dir = candidate
            break
        _here = os.path.dirname(_here)
    if not fonts_dir:
        return
    try:
        import ctypes
        for fname in ('VT323-Regular.ttf', 'PixelMplus12-Regular.ttf', 'DotGothic16-Regular.ttf'):
            fp = os.path.join(fonts_dir, fname)
            if os.path.exists(fp):
                ctypes.windll.gdi32.AddFontResourceExW(fp, 0x10, 0)
                print(f"[Font] loaded: {fname}")
    except Exception as e:
        print(f"[Font] custom font load failed: {e}")

_load_custom_fonts()

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
        "bg_main":  "#C0C0C0",   # Win95 classic gray
        "bg_panel": "#D4D0C8",   # Win95 button face
        "bg_inset": "#FFFFFF",   # White (input fields)
        "fg_main":  "#000000",   # Black
        "fg_muted": "#808080",   # Gray
        "pink":     "#800000",   # Maroon
        "cyan":     "#000080",   # Navy blue
        "gold":     "#808000",   # Olive
        "emerald":  "#008000",   # Green
        "purple":   "#800080",   # Purple
        "btn_bg":   "#D4D0C8",   # Win95 button face
        "btn_act":  "#0000AA",   # Win95 selection blue
        "btn_stop": "#CC0000",   # Red
        "prog_bg":  "#000080",   # Navy progress bar
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
            try:
                _root = os.path.dirname(os.path.abspath(__file__))
                if _root not in sys.path: sys.path.insert(0, _root)
                from system_logger import send_system_log
                send_system_log("Pink Bronson STT", "Whisperモデル(base/cpu)のロードが完了しました。")
            except Exception: pass
            return True
        except Exception as e:
            print(f"AI モデルエラー: {e}")
            self.ui.after(0, lambda: self.ui.update_status("Model Error", "red"))
            try:
                _root = os.path.dirname(os.path.abspath(__file__))
                if _root not in sys.path: sys.path.insert(0, _root)
                from system_logger import send_system_log
                send_system_log("Pink Bronson STT", f"Whisperモデルロードエラー: {e}")
            except Exception: pass
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
            try:
                _root = os.path.dirname(os.path.abspath(__file__))
                if _root not in sys.path: sys.path.insert(0, _root)
                from system_logger import send_system_log
                send_system_log("Pink Bronson STT", f"マイク入力エラー: {e}")
            except Exception: pass

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
                
                try:
                    _root = os.path.dirname(os.path.abspath(__file__))
                    if _root not in sys.path: sys.path.insert(0, _root)
                    from system_logger import send_system_log
                    send_system_log("Pink Bronson STT", f"文字起こし成功[Whisper]: {text[:30]}...")
                except Exception: pass
        except Exception as e:
            print(f"文字起こしエラー: {e}")
            try:
                _root = os.path.dirname(os.path.abspath(__file__))
                if _root not in sys.path: sys.path.insert(0, _root)
                from system_logger import send_system_log
                send_system_log("Pink Bronson STT", f"Whisperエラー: {e}")
            except Exception: pass
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
                
                try:
                    _root = os.path.dirname(os.path.abspath(__file__))
                    if _root not in sys.path: sys.path.insert(0, _root)
                    from system_logger import send_system_log
                    send_system_log("Pink Bronson STT", f"文字起こし成功[Gemini]: {text[:30]}...")
                except Exception: pass
        except Exception as e:
            print(f"Gemini STT エラー: {e}")
            self.ui.after(0, lambda: self.ui.update_status("[Gemini] エラー", "red"))
            try:
                _root = os.path.dirname(os.path.abspath(__file__))
                if _root not in sys.path: sys.path.insert(0, _root)
                from system_logger import send_system_log
                send_system_log("Pink Bronson STT", f"Gemini API STTエラー: {e}")
            except Exception: pass
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
        self.geometry("420x1020")
        self.resizable(False, False)
        _th   = parent.theme
        _bg   = _th["bg_main"]
        _pan  = _th["bg_panel"]
        _inp  = _th["btn_bg"]
        _pink = _th["pink"]
        _cyan = _th["cyan"]
        _txt  = _th["fg_main"]
        self.configure(bg=_bg)
        self.attributes("-topmost", True)
        self.grab_set()

        lbl_font  = ("VT323", 10, "bold")
        entry_font = ("VT323", 11)

        def _section(label, color):
            tk.Label(self, text=label, bg=_bg, fg=color, font=lbl_font).pack(pady=(14, 2), anchor="w", padx=22)

        def _entry(show=None):
            e = tk.Entry(self, font=entry_font, show=show or "", bg=_inp, fg=_txt,
                         insertbackground=_cyan, relief="flat", bd=4)
            e.pack(fill=tk.X, padx=22)
            return e

        # Theme
        _section("THEME", _cyan)
        _sty = ttk.Style()
        _sty.configure("Settings.TCombobox",
                        fieldbackground=_inp, background=_pan,
                        foreground=_txt, selectbackground=_th["btn_act"],
                        selectforeground="#ffffff", arrowcolor=_cyan)
        _sty.map("Settings.TCombobox",
                 fieldbackground=[('readonly', 'focus', _inp), ('readonly', _inp)],
                 foreground=[('readonly', 'focus', '#ffffff'), ('readonly', _txt)],
                 selectbackground=[('readonly', _th["btn_act"])],
                 selectforeground=[('readonly', '#ffffff')])
        self.combo_theme = ttk.Combobox(self, values=["dark", "light"],
                                        state="readonly", style="Settings.TCombobox")
        self.combo_theme.pack(fill=tk.X, padx=22)
        self.combo_theme.set(self.config.get("theme", "dark"))
        self.option_add('*Settings.TCombobox*Listbox.background',       _inp)
        self.option_add('*Settings.TCombobox*Listbox.foreground',       _txt)
        self.option_add('*Settings.TCombobox*Listbox.selectBackground', _th["btn_act"])
        self.option_add('*Settings.TCombobox*Listbox.selectForeground', '#ffffff')

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

        # Notification Sound
        er_cfg = self.config.get("emerald_rolex", {})

        _section("NOTIFICATION SOUND", _cyan)
        notify_frame = tk.Frame(self, bg=_bg)
        notify_frame.pack(fill=tk.X, padx=22, pady=(0, 4))
        self._notify_enabled = tk.BooleanVar(value=er_cfg.get("notify_enabled", True))
        tk.Checkbutton(notify_frame, text="Enable notification sound",
                       variable=self._notify_enabled,
                       bg=_bg, fg=_txt, selectcolor=_inp, activebackground=_bg,
                       activeforeground=_txt, font=("VT323", 9)).pack(anchor="w")

        sound_row = tk.Frame(self, bg=_bg)
        sound_row.pack(fill=tk.X, padx=22, pady=(0, 2))
        self.ent_sound = tk.Entry(sound_row, font=entry_font, bg=_inp, fg=_txt,
                                  insertbackground=_cyan, relief="flat", bd=4)
        self.ent_sound.insert(0, er_cfg.get("notify_sound", ""))
        self.ent_sound.pack(side=tk.LEFT, fill=tk.X, expand=True)

        def _browse_sound():
            path = filedialog.askopenfilename(
                title="Select audio file",
                filetypes=[("WAV files", "*.wav"), ("All files", "*.*")])
            if path:
                self.ent_sound.delete(0, tk.END)
                self.ent_sound.insert(0, path)

        tk.Button(sound_row, text="Browse", command=_browse_sound,
                  bg=_pan, fg=_txt, font=("VT323", 9), relief="flat",
                  cursor="hand2", padx=6).pack(side=tk.LEFT, padx=(4, 0))

        vol_frame = tk.Frame(self, bg=_bg)
        vol_frame.pack(fill=tk.X, padx=22, pady=(2, 0))
        tk.Label(vol_frame, text="Volume:", bg=_bg, fg=_txt,
                 font=("VT323", 9)).pack(side=tk.LEFT)
        self._notify_vol = tk.DoubleVar(value=er_cfg.get("notify_volume", 1.0))
        tk.Scale(vol_frame, variable=self._notify_vol, from_=0.0, to=2.0,
                 resolution=0.1, orient=tk.HORIZONTAL, bg=_bg, fg=_txt,
                 troughcolor=_inp, highlightthickness=0,
                 activebackground=_cyan).pack(side=tk.LEFT, fill=tk.X, expand=True)

        def _test_sound():
            import winsound, threading
            path = self.ent_sound.get().strip()
            def _play():
                try:
                    if path and os.path.exists(path):
                        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                    else:
                        winsound.MessageBeep(winsound.MB_OK)
                except Exception as e:
                    print(f"[test sound] {e}")
            threading.Thread(target=_play, daemon=True).start()

        tk.Button(self, text="▶ Test Sound", command=_test_sound,
                  bg=_pan, fg=_cyan, font=("VT323", 9), relief="flat",
                  cursor="hand2").pack(pady=(4, 0), anchor="w", padx=22)

        # Startup AI greeting
        startup_cfg = self.config.get("startup", {})
        _DEFAULT_PROMPT = (
            "あなたは８０年代の東京のテレビディレクターです、イケイケでギラギラです。"
            "当時の業界用語（ザギンデシースーとかギロッポンまでタクるとか、テッペンちかいから"
            "巻きでいうなど）をつかってこれから配信する配信者を励ましてテンションをあげる言葉をなげかけてください"
        )

        _section("STARTUP AI GREETING", _cyan)
        greet_frame = tk.Frame(self, bg=_bg)
        greet_frame.pack(fill=tk.X, padx=22, pady=(0, 4))
        self._startup_greet = tk.BooleanVar(value=startup_cfg.get("ai_greet", False))
        tk.Checkbutton(greet_frame,
                       text="AI CALL & RESPONSE",
                       variable=self._startup_greet,
                       bg=_bg, fg=_txt, selectcolor=_inp,
                       activebackground=_bg, activeforeground=_txt,
                       font=("VT323", 9)).pack(anchor="w")

        _section("GREETING PROMPT", _cyan)
        self.txt_prompt = tk.Text(self, height=6, font=("VT323", 9),
                                  bg=_inp, fg=_txt, insertbackground=_cyan,
                                  relief="flat", bd=4, wrap=tk.WORD)
        self.txt_prompt.pack(fill=tk.X, padx=22)
        self.txt_prompt.insert("1.0", startup_cfg.get("greet_prompt", _DEFAULT_PROMPT))

        # SAVE
        _is_light = _th.get("mode") == "light"
        btn_save = tk.Button(
            self, text="SAVE & APPLY", command=self.save_cfg,
            bg="#C0C0C0" if _is_light else _cyan,
            fg="#000000" if _is_light else "#1a1b26",
            font=("VT323", 12, "bold"),
            relief="raised" if _is_light else "flat",
            cursor="hand2",
            activebackground="#A0A0A0" if _is_light else "#b4e4ff")
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
        er = self.config.setdefault("emerald_rolex", {})
        er["notify_enabled"] = self._notify_enabled.get()
        er["notify_sound"]   = self.ent_sound.get().strip()
        er["notify_volume"]  = round(self._notify_vol.get(), 1)
        startup = self.config.setdefault("startup", {})
        startup["ai_greet"]     = self._startup_greet.get()
        startup["greet_prompt"] = self.txt_prompt.get("1.0", tk.END).strip()
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
        self.geometry("400x960")
        self.resizable(True, True)
        self._topmost = True
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
        self._dseg_font = _try_load_dseg()

        self.widgets = {} # For dynamic theme application
        self._build()
        self.apply_theme()
        self._poll_config_changes()

        saved_mic = self.cfg.get("last_mic", "")
        if saved_mic and saved_mic in self.combo_mic["values"]:
            self.combo_mic.set(saved_mic)
        elif self.combo_mic["values"]:
            self.combo_mic.current(0)
            
        self._meter.start(self.combo_mic.get())
        self._poll_stt_result()
        self.after(800, self._run_startup_greet)

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

        # 画像右側の縦フレーム（タイトル上部 + ticker 下部）
        fr_right = tk.Frame(fr_header)
        fr_right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.widgets["fr_right"] = (fr_right, "bg_main")

        # ── 上段: タイトル + ボタン ──
        fr_top = tk.Frame(fr_right)
        fr_top.pack(side=tk.TOP, fill=tk.X)
        self.widgets["fr_top"] = (fr_top, "bg_main")

        # ボタンを RIGHT に先に pack（タイトルが押し出されないよう）
        self.btn_topmost = tk.Button(
            fr_top, text="▲", command=self.toggle_topmost,
            font=("VT323", 9, "bold"), relief="flat",
            cursor="hand2", padx=4, pady=1)
        self.btn_topmost.pack(side=tk.RIGHT, anchor="n", padx=(0, 0))
        self.widgets["btn_topmost"] = (self.btn_topmost, "btn_bg", "cyan")

        self.btn_set = tk.Button(
            fr_top, text="⚙", command=self.open_settings,
            font=("VT323", 9, "bold"), relief="flat",
            cursor="hand2", padx=4, pady=1)
        self.btn_set.pack(side=tk.RIGHT, anchor="n", padx=(0, 4))
        self.widgets["btn_set"] = (self.btn_set, "btn_bg", "cyan")

        fr_title_stack = tk.Frame(fr_top)
        fr_title_stack.pack(side=tk.LEFT)
        self.widgets["fr_title_stack"] = (fr_title_stack, "bg_main")

        self.lbl_title = tk.Label(
            fr_title_stack, text="PINK BRONSON",
            font=("VT323", 20, "bold"), anchor="w")
        self.lbl_title.pack(anchor="w")
        self.widgets["lbl_title"] = (self.lbl_title, "bg_main", "pink")

        self.lbl_sub = tk.Label(
            fr_title_stack, text="The Producer's Desk",
            font=("VT323", 9), anchor="w")
        self.lbl_sub.pack(anchor="w")
        self.widgets["lbl_sub"] = (self.lbl_sub, "bg_main", "cyan")

        # ── 下段: AI Greeting ticker（画像下端に揃う）──
        self._greet_text      = ""
        self._greet_x         = 0.0
        self._greet_ticker_id = None
        self.greet_canvas = tk.Canvas(fr_right, height=22, highlightthickness=0, bd=0)
        self.greet_canvas.pack(side=tk.BOTTOM, fill=tk.X)
        self.widgets["greet_canvas"] = (self.greet_canvas, "bg_main")

        # Neon separator line
        fr_sep = tk.Frame(self, height=2)
        fr_sep.pack(fill=tk.X, padx=16, pady=(0, 8))
        fr_sep.pack_propagate(False)
        self.widgets["fr_sep"] = (fr_sep, "pink")

        # ── MIC (LCD スタイル) ──
        _LCD_BG   = '#0A1400'
        _LCD_DIM  = '#1E3000'
        _LCD_FG   = '#7AAA00'
        _LCD_EDGE = '#2A4400'

        fr_mic_bezel = tk.Frame(self, bg=_LCD_EDGE, bd=0)
        fr_mic_bezel.pack(fill=tk.X, padx=20, pady=(10, 0))

        frame_mic = tk.Frame(fr_mic_bezel, bg=_LCD_BG)
        frame_mic.pack(fill=tk.X, padx=2, pady=2)

        self.lbl_mic = tk.Label(frame_mic, text="MIC SELECT",
                                font=("VT323", 9, "bold"), bg=_LCD_BG, fg=_LCD_FG)
        self.lbl_mic.pack(side=tk.LEFT, padx=(8, 0))

        self.combo_mic = ttk.Combobox(frame_mic, values=get_input_devices(),
                                      state="readonly", style="Mic.TCombobox")
        self.combo_mic.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8, pady=4)
        self.combo_mic.bind("<<ComboboxSelected>>", self._on_mic_change)

        # ── STT Backend ──
        fr_backend = tk.Frame(self)
        fr_backend.pack(fill=tk.X, padx=20, pady=(10, 0))
        self.widgets["fr_backend"] = (fr_backend, "bg_main")

        tk.Label(fr_backend, text="STT ENGINE", font=("VT323", 9, "bold")).pack(side=tk.LEFT)
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
                                    font=("VT323", 9), relief="flat", cursor="hand2")
        rb_whisper.pack(side=tk.LEFT, padx=(12, 0))
        self.widgets["rb_whisper"] = (rb_whisper, "bg_main", "fg_main")

        rb_gemini = tk.Radiobutton(fr_backend, text="Gemini API",
                                   variable=self.stt_backend_var, value="gemini",
                                   font=("VT323", 9), relief="flat", cursor="hand2")
        rb_gemini.pack(side=tk.LEFT, padx=(8, 0))
        self.widgets["rb_gemini"] = (rb_gemini, "bg_main", "cyan")

        # ── STT Controls ──
        self.lbl_status = tk.Label(self, text="STT: Stopped", font=("VT323", 10, "bold"))
        self.lbl_status.pack(pady=(10, 0))
        self.widgets["lbl_status"] = (self.lbl_status, "bg_main", "fg_main")
        _on_backend_change()   # lbl_status 作成後に初期表示を反映

        self.btn_stt = tk.Button(self, text="▶  START  /  ■  STOP", command=self.toggle_stt, font=("VT323", 11, "bold"), relief="flat", cursor="hand2")
        self.btn_stt.pack(fill=tk.X, padx=20, pady=(8,4), ipady=5)
        self.widgets["btn_stt"] = (self.btn_stt, "btn_bg", "fg_main", "btn_act")

        self._meter_level = 0
        fr_meter_bezel = tk.Frame(self, bg='#2A4400', bd=0)
        fr_meter_bezel.pack(fill=tk.X, padx=20, pady=(2, 12))
        self.meter_canvas = tk.Canvas(fr_meter_bezel, height=14, bg='#7AAA00',
                                      highlightthickness=0, bd=0)
        self.meter_canvas.pack(fill=tk.X, padx=2, pady=2)
        self.meter_canvas.bind('<Configure>', lambda _e: self._draw_meter_dots())

        # ── Latest Phrase ──
        self.lbl_late_title = tk.Label(self, text="LATEST PHRASE", font=("VT323", 8, "bold"))
        self.lbl_late_title.pack()
        self.widgets["lbl_late_title"] = (self.lbl_late_title, "bg_main", "gold")

        self.frame_lat = tk.Frame(self, bd=2, relief="groove")
        self.frame_lat.pack(fill=tk.X, padx=20, pady=(4, 12))
        self.widgets["frame_lat"] = (self.frame_lat, "bg_panel")

        self.lbl_latest = tk.Label(self.frame_lat, text="(Standby...)", font=("Pixel Mplus 12", 13, "bold"), wraplength=320, justify="center", height=2)
        self.lbl_latest.pack(padx=10, pady=8)
        self.widgets["lbl_latest"] = (self.lbl_latest, "bg_panel", "cyan")

        self.lbl_bloat = tk.Label(self, text="", font=("VT323", 8, "bold"), wraplength=340, justify="center")
        self.widgets["lbl_bloat"] = (self.lbl_bloat, "bg_main", "pink")

        # ── Monitor + Status ──
        self._build_status_panel()

        # ── Child Services ──
        self.fr_child = tk.LabelFrame(self, text=" CHILD SERVICES ", font=("VT323", 8, "bold"), bd=1)
        self.fr_child.pack(fill=tk.X, padx=20, pady=(8, 16), ipady=4)
        self.widgets["fr_child"] = (self.fr_child, "bg_main", "fg_muted")

        # 1. Golden_Chain (要約)
        self.btn_golden = tk.Button(self.fr_child, text="Launch Golden_Chain (Summarizer)", command=lambda: self.toggle_proc("Golden_Chain", "golden_chain.py"), font=("VT323", 10, "bold"), relief="flat", cursor="hand2")
        self.btn_golden.pack(fill=tk.X, padx=10, pady=(8, 4), ipady=3)
        self.widgets["btn_golden"] = (self.btn_golden, "bg_panel", "gold", "btn_act")

        # 2. Blue_RAY-BAN (各言語翻訳)
        fr_rayban = tk.Frame(self.fr_child, bg=self.theme.get("bg_panel", "#1A1A1A"))
        fr_rayban.pack(fill=tk.X, padx=10, pady=(4, 4))
        self.widgets["fr_rayban"] = (fr_rayban, "bg_panel")
        
        self.btn_rayban = tk.Button(fr_rayban, text="Launch Blue_RAY-BAN (Translator)", command=lambda: self.toggle_proc("Blue_RAY-BAN", "blue_rayban.py"), font=("VT323", 10, "bold"), relief="flat", cursor="hand2")
        self.btn_rayban.pack(fill=tk.X, expand=True, ipady=3)
        self.widgets["btn_rayban"] = (self.btn_rayban, "bg_panel", "cyan", "btn_act")

        # 3. Emerald_Rolex (Twitchチャット表示)
        fr_rolex = tk.Frame(self.fr_child, bg=self.theme.get("bg_panel", "#1A1A1A"))
        fr_rolex.pack(fill=tk.X, padx=10, pady=(4, 8))
        self.widgets["fr_rolex"] = (fr_rolex, "bg_panel")

        self.btn_rolex = tk.Button(fr_rolex, text="Launch Emerald_Rolex (Chat viewer)", command=lambda: self.toggle_proc("Emerald_Rolex", "emerald_rolex.py"), font=("VT323", 10, "bold"), relief="flat", cursor="hand2")
        self.btn_rolex.pack(fill=tk.X, expand=True, ipady=3)
        self.widgets["btn_rolex"] = (self.btn_rolex, "bg_panel", "emerald", "btn_act")

    # ══════════════════════════════════════════════════════
    #  MONITOR ボタン + STATUS パネル (LCD スタイル)
    # ══════════════════════════════════════════════════════
    def _build_status_panel(self):
        _LCD_BG   = '#0A1400'   # 液晶パネル背景
        _LCD_DIM  = '#1E3000'   # 非アクティブセグメント色
        _LCD_FG   = '#7AAA00'   # アクティブ文字
        _LCD_EDGE = '#2A4400'   # 外枠
        dseg = self._dseg_font

        # MONITOR ボタン
        monitor_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "monitor.html"))
        btn_mon = tk.Button(
            self, text="📊  MONITOR",
            command=lambda: webbrowser.open('file:///' + monitor_path.replace('\\', '/')),
            font=("VT323", 10, "bold"), relief="flat", cursor="hand2")
        btn_mon.pack(fill=tk.X, padx=20, pady=(0, 5), ipady=3)
        self.widgets["btn_monitor"] = (btn_mon, "bg_panel", "fg_main", "btn_act")

        # 外枠 (LCD っぽいベゼル)
        fr_bezel = tk.Frame(self, bg=_LCD_EDGE, bd=0)
        fr_bezel.pack(fill=tk.X, padx=20, pady=(0, 12))

        # LCD 内パネル
        fr_lcd = tk.Frame(fr_bezel, bg=_LCD_BG)
        fr_lcd.pack(fill=tk.X, padx=2, pady=2)
        fr_lcd.columnconfigure(1, weight=1)

        # タイトルバー
        fr_hdr = tk.Frame(fr_lcd, bg='#0F1E00', pady=2)
        fr_hdr.grid(row=0, column=0, columnspan=3, sticky='ew')
        tk.Label(fr_hdr, text='◀  SERVICE STATUS  ▶',
                 bg='#0F1E00', fg=_LCD_DIM,
                 font=('VT323', 8, 'bold')).pack(side='left', padx=8)

        # バッジ状態定義
        self._stat_colors = {
            'ok':  ('#006622', '#44FF88'),
            'snd': ('#003377', '#44CCFF'),
            'rcv': ('#774400', '#FFAA33'),
            'err': ('#660011', '#FF3355'),
            'off': (_LCD_BG,   _LCD_DIM),
        }
        self._stat_badge_text = {
            'ok':  ' OK ',
            'snd': ' SND',
            'rcv': ' RCV',
            'err': ' ERR',
            'off': '----',
        }
        self._stat_labels = {}

        wc  = self.cfg.get('web_config', {})
        api = self.cfg.get('api_keys', {})
        ai_name  = 'Gemini 2.0 Flash' if api.get('gemini_key') else 'Not configured'
        stt_name = 'Gemini API' if self.cfg.get('stt_backend') == 'gemini' else 'Whisper (local)'
        if wc.get('tts_engine') == 'google_cloud':
            tts_name = f"GCloud  {wc.get('gcloud_tts_voice', 'Wavenet')}"
        else:
            tts_name = f"Gemini TTS  {wc.get('tts_voice', 'Kore')}"

        rows = [
            ('ai',  'AI',  ai_name,  'ok' if api.get('gemini_key') else 'off'),
            ('stt', 'STT', stt_name, 'off'),
            ('tts', 'TTS', tts_name, 'off'),
        ]
        for i, (key, lbl_text, val_text, init) in enumerate(rows):
            data_row = 1 + i * 2   # 1,3,5  (偶数行はセパレータ用)

            # キーラベル (常時 dim)
            tk.Label(fr_lcd, text=lbl_text,
                     bg=_LCD_BG, fg=_LCD_DIM,
                     font=('VT323', 9, 'bold'), width=4, anchor='e'
                     ).grid(row=data_row, column=0, padx=(8, 4), pady=5, sticky='e')

            # 値ラベル (LCD グリーン)
            val_lbl = tk.Label(fr_lcd, text=val_text,
                               bg=_LCD_BG, fg=_LCD_FG,
                               font=('VT323', 9), anchor='w')
            val_lbl.grid(row=data_row, column=1, padx=(0, 4), pady=5, sticky='ew')

            # バッジ (DSEG フォント)
            badge = tk.Label(fr_lcd, text='----',
                             bg=_LCD_BG, fg=_LCD_DIM,
                             font=(dseg, 10, 'bold'), width=5, anchor='center')
            badge.grid(row=data_row, column=2, padx=(0, 8), pady=5)

            # 行区切り (最終行以外)
            if i < len(rows) - 1:
                tk.Frame(fr_lcd, bg=_LCD_DIM, height=1
                         ).grid(row=data_row + 1, column=0, columnspan=3,
                                sticky='ew', padx=6)

            self._stat_labels[key] = (val_lbl, badge)
            self._set_status(key, init)

    def _set_status(self, key, state, val_text=None):
        """key: 'ai'|'stt'|'tts'
           state: 'ok'|'snd'|'rcv'|'err'|'off'|None (None=テキストのみ更新)"""
        if not hasattr(self, '_stat_labels') or key not in self._stat_labels:
            return
        val_lbl, badge = self._stat_labels[key]
        if state is not None:
            bg, fg = self._stat_colors.get(state, self._stat_colors['off'])
            badge.config(text=self._stat_badge_text.get(state, '----'), bg=bg, fg=fg)
        if val_text is not None:
            val_lbl.config(text=val_text)

    def _poll_config_changes(self):
        """config.json を定期再読み込みし STATUS パネルの表示値を更新する。"""
        try:
            nc  = load_config()
            wc  = nc.get('web_config', {})
            api = nc.get('api_keys', {})
            ai_text  = 'Gemini 2.0 Flash' if api.get('gemini_key') else 'Not configured'
            stt_text = 'Gemini API' if nc.get('stt_backend') == 'gemini' else 'Whisper (local)'
            if wc.get('tts_engine') == 'google_cloud':
                tts_text = f"GCloud  {wc.get('gcloud_tts_voice', '?')}"
            else:
                tts_text = f"Gemini TTS  {wc.get('tts_voice', 'Kore')}"
            self._set_status('ai',  None, ai_text)
            self._set_status('stt', None, stt_text)
            self._set_status('tts', None, tts_text)
        except Exception:
            pass
        self.after(5000, self._poll_config_changes)

    def _set_font_recursive(self, parent, family):
        """ウィジェットツリーを再帰走査してフォントファミリーを置換する。"""
        import tkinter.font as tkfont
        for w in parent.winfo_children():
            try:
                f = w.cget("font")
                if f:
                    fa = tkfont.Font(font=f).actual()
                    w.config(font=(family, fa['size'], fa['weight']))
            except Exception:
                pass
            self._set_font_recursive(w, family)

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
        # MIC / Meter LCD スタイル (テーマ非依存・固定)
        sty.configure("Mic.TCombobox",
                      fieldbackground='#0A1400', background='#2A4400',
                      foreground='#7AAA00', selectbackground='#0A1400',
                      selectforeground='#AAFF44', arrowcolor='#7AAA00')
        sty.map("Mic.TCombobox",
                fieldbackground=[('readonly', 'focus', '#0A1400'), ('readonly', '#0A1400')],
                foreground=[('readonly', 'focus', '#AAFF44'), ('readonly', '#7AAA00')],
                selectforeground=[('readonly', '#AAFF44')],
                selectbackground=[('readonly', '#0A1400')])
        # MIC Combobox ドロップダウンリスト (OSネイティブ部分) の色
        self.option_add('*TCombobox*Listbox.background',        '#0A1400')
        self.option_add('*TCombobox*Listbox.foreground',        '#7AAA00')
        self.option_add('*TCombobox*Listbox.selectBackground',  '#1E3000')
        self.option_add('*TCombobox*Listbox.selectForeground',  '#AAFF44')

        if self.theme.get("mode") == "light":
            self._set_font_recursive(self, 'MS Gothic')

    def _run_startup_greet(self):
        startup = self.cfg.get("startup", {})
        if not startup.get("ai_greet", False):
            return
        gemini_key = self.cfg.get("api_keys", {}).get("gemini_key", "")
        prompt = startup.get("greet_prompt", "").strip()
        if not gemini_key or not prompt:
            return
        # テンプレート変数を展開
        now = datetime.now()
        prompt = prompt.replace("{current_time}", now.strftime("%H:%M"))
        prompt = prompt.replace("{date}",         now.strftime("%Y-%m-%d"))
        prompt = prompt.replace("{channel}",      self.cfg.get("api_keys", {}).get("twitch_channel", ""))
        self._show_greet("▶  Connecting to AI...  ◀")
        def _fetch():
            try:
                import google.generativeai as genai
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel("gemini-2.0-flash")
                print("[Greet] Calling Gemini...")
                resp = model.generate_content(prompt)
                try:
                    text = resp.text.strip()
                except Exception as te:
                    text = f"[Response parse error: {te}]"
                print(f"[Greet] Got response: {text[:60]}...")
                try:
                    from system_logger import send_system_log
                    send_system_log("AI Greeting", text)
                except Exception:
                    pass
                self.after(0, lambda t=text: self._show_greet(t))
            except Exception as e:
                print(f"[Greet] API error: {e}")
                self.after(0, lambda err=str(e): self._show_greet(f"[AI Error: {err}]"))
        threading.Thread(target=_fetch, daemon=True).start()

    def _show_greet(self, text: str):
        import re
        text = re.sub(r'\*+', '', text)          # ** markdown 除去
        text = re.sub(r'[\r\n]+', '　', text)    # 改行 → 全角スペース
        text = re.sub(r' {2,}', ' ', text).strip()
        self._greet_text = "   " + text + "   "
        if self._greet_ticker_id:
            self.after_cancel(self._greet_ticker_id)
            self._greet_ticker_id = None
        c = self.greet_canvas
        c.delete("all")
        w = c.winfo_width() or 400
        self._greet_x = float(w)
        c.create_text(self._greet_x, 11,
                      text=self._greet_text,
                      font=("VT323", 13), fill=self.theme.get("cyan", "#7dcfff"),
                      anchor="w", tags="ticker")
        self._animate_greet()

    def _animate_greet(self):
        if not self._greet_text:
            return
        c = self.greet_canvas
        c.move("ticker", -2, 0)
        coords = c.coords("ticker")
        if coords:
            bbox = c.bbox("ticker")
            if bbox and coords[0] + (bbox[2] - bbox[0]) < 0:
                # 1回流れ終わったら停止
                c.delete("ticker")
                self._greet_text = ""
                self._greet_ticker_id = None
                return
        self._greet_ticker_id = self.after(40, self._animate_greet)

    def toggle_topmost(self):
        self._topmost = not self._topmost
        self.attributes("-topmost", self._topmost)
        self.btn_topmost.config(text="▲" if self._topmost else "▽")

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
            try:
                _root = os.path.dirname(os.path.abspath(__file__))
                if _root not in sys.path: sys.path.insert(0, _root)
                from system_logger import send_system_log
                send_system_log("Pink Bronson Main", f"子プロセス終了: {name}")
            except Exception: pass
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
                    _cfg_paths = load_config().get("python_paths", {})
                    python_exe = _cfg_paths.get("blue_rayban", sys.executable)
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
            from system_logger import send_system_log as _slog
        except Exception:
            _slog = None
        _LOG_PREFIXES = ('[STT', '[SYS]', '[GC]', 'ERROR', 'Error', 'Exception',
                         'Traceback', 'WARNING', '[WARN', '起動', '終了', 'ONLINE', 'OFFLINE')
        try:
            for line in iter(proc.stdout.readline, ""):
                if not line: break
                line = line.strip()
                if not line: continue
                self.after(0, lambda n=name, l=line: self._append_child_log(n, l))
                if _slog and any(line.startswith(p) or p in line for p in _LOG_PREFIXES):
                    try:
                        _slog(name, line[:200])
                    except Exception:
                        pass
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
        """子プロセスのログをステータスバッジに反映する。"""
        t = text
        if name == "Blue_RAY-BAN":
            if "Gemini API 接続完了" in t or ("✅ Gemini" in t and "接続" in t):
                self._set_status('ai', 'ok')
            elif "[WebTTS] ✅" in t:
                self._set_status('tts', 'snd')
                self.after(2000, lambda: self._set_status('tts', 'ok'))
            elif "[WebTTS] ❌" in t:
                self._set_status('tts', 'err')
            elif "TRANSLATION MODULE  ONLINE" in t:
                self._set_status('tts', 'ok')
            elif "[STTWatcher] 🎤" in t or "[STT_RESULT]" in t:
                self._set_status('stt', 'rcv')
                self.after(1500, lambda: self._set_status('stt', 'ok'))
            elif "Firebase" in t and ("送信完了" in t or "OK" in t):
                self._set_status('ai', 'snd')
                self.after(1500, lambda: self._set_status('ai', 'ok'))
            elif ("ERROR" in t.upper() or "エラー" in t) and "Gemini" in t:
                self._set_status('ai', 'err')
        elif name == "Emerald_Rolex":
            if "IRC接続完了" in t or "ONLINE" in t:
                self._set_status('ai', 'ok')
            elif "ERROR" in t.upper() or "エラー" in t:
                pass  # Rolex error: no specific badge key

    # ── Thread-Safe Updaters ──
    def update_status(self, text: str, color: str):
        self.lbl_status.config(text=f"STT: {text}")
        if color == "red" or color == "tomato":
            self.lbl_status.config(fg=self.theme["pink"])
            self._set_status('stt', 'err')
        elif color == "lime" or color == "lightgreen":
            self.lbl_status.config(fg=self.theme["cyan"])
            self._set_status('stt', 'ok')
        elif color == "orange" or color == "yellow":
            self.lbl_status.config(fg=self.theme["gold"])
            self._set_status('stt', 'ok')

    def update_meter(self, vol: int):
        self._meter_level = vol
        self._draw_meter_dots()

    def _draw_meter_dots(self):
        c = self.meter_canvas
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 10:
            return
        c.delete('dot')
        n = 28
        dot_w = (w - 4) / n
        active = int(self._meter_level / 100 * n)
        for i in range(active):
            x1 = int(2 + i * dot_w) + 1
            x2 = int(2 + (i + 1) * dot_w) - 1
            c.create_rectangle(x1, 2, x2, h - 2, fill='#0A1400', outline='', tags='dot')

    def on_transcribed(self, text: str):
        self.lbl_latest.config(text=text)
        self._set_status('stt', 'snd')
        self.after(1500, lambda: self._set_status('stt', 'ok'))
        # Blue_RAY-BAN ブリッジファイルへ書き込み
        try:
            bridge = os.path.join(DATA_DIR, "stt_bridge.json")
            with open(bridge, "w", encoding="utf-8") as f:
                json.dump({"text": text, "timestamp": str(time.time())}, f, ensure_ascii=False)
        except Exception:
            pass

    def _poll_stt_result(self):
        """Blue_RAY-BAN の翻訳結果ファイルを監視してログに追記する。"""
        result_path = os.path.join(DATA_DIR, "stt_bridge_result.json")
        last_mtime = [0.0]
        def _check():
            try:
                if not os.path.exists(result_path):
                    return
                mtime = os.path.getmtime(result_path)
                if mtime == last_mtime[0]:
                    return
                last_mtime[0] = mtime
                with open(result_path, "r", encoding="utf-8") as f:
                    d = json.load(f)
                ja = d.get("text", "")
                en = d.get("en", "")
                if ja and en:
                    self._set_status('tts', 'rcv')
                    self.after(2000, lambda: self._set_status('tts', 'ok'))
            except Exception:
                pass
            self.after(1500, _check)
        self.after(1500, _check)

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
    try:
        from system_logger import send_system_log
        send_system_log("pink_bronson", "🚀 Pink Bronson 起動")
    except Exception:
        pass
    app = PinkBronsonUI(load_config())
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
