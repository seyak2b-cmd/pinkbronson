# -*- coding: utf-8 -*-
import sys
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try: sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

import tkinter as tk
from tkinter import scrolledtext, messagebox, colorchooser, filedialog
import subprocess
import threading
import os
import json
import webbrowser
try:
    import requests as _requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ══════════════════════════════════════════════════════════
#  90s INDUSTRIAL UI  —  BLUE_RAY-BAN  //  TRANSLATION MODULE
# ══════════════════════════════════════════════════════════
BG      = '#1C1C1C'
PANEL   = '#242424'
LCD_BG  = '#141800'
LCD_FG  = '#AABF00'
LCD_DIM = '#485400'
BORDER  = '#363636'
BTN_BG  = '#2A2A2A'
BTN_FG  = '#C4C4C4'
BTN_ACT = '#3A3A3A'
LED_ON  = '#33CC00'
LED_OFF = '#122200'
LED_RED = '#BB1100'
MUTED   = '#606060'
HEAD    = '#D0D0D0'
FONT    = 'VT323'
FONT_JP = 'Pixel Mplus 12'


def _load_custom_fonts():
    """VT323 / Pixel Mplus 12 / DotGothic16 を Windows API でロード。"""
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
    except Exception as e:
        print(f"[Font] load failed: {e}")

_load_custom_fonts()

_TRANS_LANGS = [
    ("日本語",    "ja"),
    ("English",   "en"),
    ("한국어",    "ko"),
    ("中文",      "zh"),
    ("Español",   "es"),
    ("Français",  "fr"),
    ("Deutsch",   "de"),
    ("Português", "pt"),
    ("Italiano",  "it"),
    ("Русский",   "ru"),
    ("العربية",   "ar"),
    ("ภาษาไทย",   "th"),
    ("Tiếng Việt","vi"),
    ("Indonesia",  "id"),
    ("Nederlands", "nl"),
    ("Polski",     "pl"),
    ("Türkçe",     "tr"),
    ("हिन्दी",     "hi"),
    ("Tagalog",    "tl"),
    ("Svenska",    "sv"),
]

_TTS_VOICES = [
    "Kore", "Aoede", "Charon", "Fenrir", "Puck",
    "Leda", "Zephyr", "Orus", "Autonoe", "Callirrhoe",
]

# Google Cloud TTS 料金 (USD / 100万文字)
_GCLOUD_TIER_PRICE = {
    'Standard': 4,
    'Wavenet':  16,
    'Neural2':  16,
    'Polyglot': 16,
    'Journey':  30,
    'Studio':   160,
}

# カスケードメニュー構造: (言語コード, [(モデル名, [サフィックス...])])
_GCLOUD_VOICE_GROUPS = [
    ('ja-JP', [
        ('Standard', list('ABCD')),
        ('Wavenet',  list('ABCD')),
        ('Neural2',  list('BCD')),
        ('Studio',   list('BD')),
    ]),
    ('en-US', [
        ('Standard', list('ABCDEFGHIJ')),
        ('Wavenet',  list('ABCDEFGHIJ')),
        ('Neural2',  ['A','C','D','E','F','G','H','I']),
        ('Journey',  ['D','F','O']),
        ('Studio',   ['O','Q']),
    ]),
    ('en-GB', [
        ('Wavenet',  list('ABCD')),
    ]),
    ('en-AU', [
        ('Wavenet',  list('ABCD')),
    ]),
    ('ko-KR', [
        ('Standard', list('ABCD')),
        ('Wavenet',  list('ABCD')),
        ('Neural2',  ['A']),
    ]),
    ('cmn-CN', [
        ('Wavenet',  list('ABCD')),
    ]),
    ('es-US', [
        ('Wavenet',  list('ABC')),
    ]),
    ('fr-FR', [
        ('Wavenet',  list('ABCD')),
    ]),
    ('de-DE', [
        ('Wavenet',  list('ABCD')),
    ]),
]

# 後方互換 / price lookup 用フラットリスト (グループ構造から自動生成)
_GCLOUD_VOICES = [
    f'{lang}-{tier}-{s}'
    for lang, tiers in _GCLOUD_VOICE_GROUPS
    for tier, suffixes in tiers
    for s in suffixes
]

# ボイス名から料金テキストを返す
def _gcloud_price_text(voice_name: str) -> str:
    for tier, price in _GCLOUD_TIER_PRICE.items():
        if f'-{tier}-' in voice_name:
            return f"${price}/1M chars  [{tier}]"
    return ""

_BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR   = os.path.dirname(_BASE_DIR)
CONFIG_PATH = os.path.join(_BASE_DIR, "..", "config.json")
TOKEN_PATH  = os.path.join(_BASE_DIR, "twitchtoken.txt")

if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)


# ── 設定 read/write ────────────────────────────────────────
def _read_config() -> dict:
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _write_config(cfg: dict):
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[CFG] config.json 書込エラー: {e}")


def _get_firebase_url() -> str:
    """twitchtoken.txt を優先、なければ config.json から取得"""
    try:
        if os.path.exists(TOKEN_PATH):
            with open(TOKEN_PATH, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('FIREBASE_DATABASE_URL='):
                        url = line[len('FIREBASE_DATABASE_URL='):].strip()
                        if url:
                            return url
    except Exception:
        pass
    return _read_config().get('api_keys', {}).get('firebase_url', '')


# ── Win95 ライトテーマ ─────────────────────────────────────
_W95 = {
    'BG':      '#C0C0C0',
    'PANEL':   '#D4D0C8',
    'LCD_BG':  '#FFFFFF',
    'LCD_FG':  '#000000',
    'LCD_DIM': '#808080',
    'BORDER':  '#808080',
    'BTN_BG':  '#D4D0C8',
    'BTN_FG':  '#000000',
    'BTN_ACT': '#0000AA',
    'LED_ON':  '#00AA00',
    'LED_OFF': '#A0A0A0',
    'LED_RED': '#CC0000',
    'MUTED':   '#505050',
    'HEAD':    '#000000',
    'FONT':    'MS Gothic',
    'FONT_JP': 'MS Gothic',
}

def _setup_theme():
    cfg = _read_config()
    if cfg.get('theme', 'dark').lower() == 'light':
        g = globals()
        for k, v in _W95.items():
            g[k] = v

_setup_theme()



# ══════════════════════════════════════════════════════════
#  Main UI
# ══════════════════════════════════════════════════════════
class BlueRaybanUI:
    def __init__(self, root):
        self.root = root
        self.root.title("BLUE_RAY-BAN  //  TRANSLATION MODULE")
        self.root.geometry("900x780")
        self.root.minsize(700, 420)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self.cleanup_on_exit)
        self._topmost = False

        self.process   = None
        self.base_dir  = _BASE_DIR
        self.script_path = os.path.join(self.base_dir, "mainTST.py")

        self._cfg_open    = False
        self._cfg_frame   = None   # 設定パネル (tk.Frame)
        self._log_wrap    = None   # LCD ログパネル (設定パネルの before= に使う)

        # LATEST PHRASE の翻訳先ラベル (TRANS LANG に連動)
        _init_code = _read_config().get('web_config', {}).get('translation_target', 'en').upper()
        self._stt_lang_label_var = tk.StringVar(value=_init_code + ':')

        self._build_ui()
        self.root.after(100, self.start_process)

    # ══════════════════════════════════════════════════════
    #  UI 構築
    # ══════════════════════════════════════════════════════
    def _build_ui(self):
        # ── ヘッダー ──────────────────────────────────────
        fr_head = tk.Frame(self.root, bg=PANEL, pady=5)
        fr_head.pack(fill='x')

        tk.Label(fr_head, text="BLUE_RAY-BAN",
                 bg=PANEL, fg=HEAD, font=(FONT, 13, 'bold')).pack(side='left', padx=16)
        tk.Label(fr_head, text="TRANSLATION MODULE  //  UNIT-01",
                 bg=PANEL, fg=MUTED, font=(FONT, 8)).pack(side='left', padx=4)

        tk.Button(fr_head, text="[ QUIT ]",
                  command=self.cleanup_on_exit,
                  bg=BTN_BG, fg=LED_RED, font=(FONT, 9, 'bold'),
                  relief='raised', bd=2, padx=10, pady=2,
                  cursor='hand2', activebackground=BTN_ACT,
                  activeforeground=LED_RED).pack(side='right', padx=12, pady=4)

        self._top_btn = tk.Button(fr_head, text="▽",
                  command=self.toggle_topmost,
                  bg=BTN_BG, fg=HEAD, font=(FONT, 11, 'bold'),
                  relief='raised', bd=2, padx=6, pady=2,
                  cursor='hand2', activebackground=BTN_ACT,
                  activeforeground=HEAD)
        self._top_btn.pack(side='right', padx=4, pady=4)

        tk.Frame(self.root, bg=BORDER, height=2).pack(fill='x')

        # ── コントロールストリップ ─────────────────────────
        fr_ctrl = tk.Frame(self.root, bg=BG, pady=10)
        fr_ctrl.pack(fill='x', padx=18)

        # LED
        self._led_canvas = tk.Canvas(fr_ctrl, width=16, height=16,
                                     bg=BG, highlightthickness=0)
        self._led_canvas.pack(side='left', padx=(0, 8))
        self._led_oval = self._led_canvas.create_oval(
            2, 2, 14, 14, fill=LED_OFF, outline='#1A1A1A', width=1)

        self.status_var = tk.StringVar(value="STANDBY")
        tk.Label(fr_ctrl, textvariable=self.status_var,
                 bg=BG, fg=MUTED, font=(FONT, 10, 'bold'),
                 width=14, anchor='w').pack(side='left')

        for label, cmd, fg in [
            ("START", self.start_process, BTN_FG),
            ("STOP",  self.stop_process,  BTN_FG),
        ]:
            tk.Button(fr_ctrl, text=label, command=cmd,
                      bg=BTN_BG, fg=fg, font=(FONT, 9, 'bold'),
                      relief='raised', bd=2, padx=16, pady=4,
                      cursor='hand2', activebackground=BTN_ACT,
                      activeforeground=BTN_FG).pack(side='left', padx=4)

        # MOBILE
        tk.Frame(fr_ctrl, bg=BORDER, width=2).pack(side='left', fill='y', padx=8, pady=4)
        tk.Button(fr_ctrl, text="WEB APP",
                  command=self.open_mobile,
                  bg=BTN_BG, fg=MUTED, font=(FONT, 9),
                  relief='raised', bd=2, padx=10, pady=4,
                  cursor='hand2', activebackground=BTN_ACT,
                  activeforeground=BTN_FG).pack(side='left')

        # CONFIG トグル
        tk.Frame(fr_ctrl, bg=BORDER, width=2).pack(side='left', fill='y', padx=8, pady=4)
        self._cfg_btn_var = tk.StringVar(value="CONFIG")
        tk.Button(fr_ctrl, textvariable=self._cfg_btn_var,
                  command=self.toggle_config,
                  bg='#1A1A2E', fg='#7FAAFF', font=(FONT, 9, 'bold'),
                  relief='raised', bd=2, padx=10, pady=4,
                  cursor='hand2', activebackground='#252545',
                  activeforeground='#AACCFF').pack(side='left')

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill='x', padx=18, pady=(0, 4))

        # ── STT 最終発話パネル ─────────────────────────────
        fr_stt = tk.Frame(self.root, bg=LCD_BG, bd=2, relief='groove')
        fr_stt.pack(fill='x', padx=16, pady=(0, 6))
        fr_stt.columnconfigure(1, weight=1)

        tk.Label(fr_stt, text="◀ LATEST PHRASE ▶",
                 bg=LCD_BG, fg=LCD_DIM, font=(FONT, 7, 'bold'),
                 anchor='w').grid(row=0, column=0, columnspan=2, padx=8, pady=(4, 0), sticky='w')

        tk.Label(fr_stt, text="JA:", bg=LCD_BG, fg=LCD_DIM,
                 font=(FONT, 9, 'bold'), width=4, anchor='e'
                 ).grid(row=1, column=0, padx=(8, 4), pady=3, sticky='e')
        self._stt_ja_var = tk.StringVar(value="—")
        tk.Label(fr_stt, textvariable=self._stt_ja_var,
                 bg=LCD_BG, fg=LCD_FG, font=(FONT, 12, 'bold'),
                 anchor='w', wraplength=700).grid(row=1, column=1, padx=(0, 8), pady=3, sticky='ew')

        tk.Label(fr_stt, textvariable=self._stt_lang_label_var, bg=LCD_BG, fg=LCD_DIM,
                 font=(FONT, 9, 'bold'), width=4, anchor='e'
                 ).grid(row=2, column=0, padx=(8, 4), pady=(0, 6), sticky='e')
        self._stt_en_var = tk.StringVar(value="—")
        tk.Label(fr_stt, textvariable=self._stt_en_var,
                 bg=LCD_BG, fg='#E8FF80', font=(FONT, 12, 'bold'),
                 anchor='w', wraplength=700).grid(row=2, column=1, padx=(0, 8), pady=(0, 6), sticky='ew')

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill='x', padx=18, pady=(0, 4))

        # ── 設定パネル (非表示で構築) ────────────────────────
        self._cfg_frame = self._build_config_panel()

        # ── LCD ログパネル ─────────────────────────────────
        self._log_wrap = tk.Frame(self.root, bg=BORDER, bd=1, relief='groove')
        self._log_wrap.pack(fill='both', expand=True, padx=16, pady=(0, 16))

        fr_lcd_head = tk.Frame(self._log_wrap, bg=PANEL, pady=3)
        fr_lcd_head.pack(fill='x')
        tk.Label(fr_lcd_head, text="PROCESS LOG",
                 bg=PANEL, fg=LCD_DIM, font=(FONT, 8)).pack(side='left', padx=10)

        self.log_text = scrolledtext.ScrolledText(
            self._log_wrap,
            bg=LCD_BG, fg=LCD_FG, font=(FONT_JP, 10),
            insertbackground=LCD_FG, selectbackground=LCD_DIM,
            selectforeground=LCD_FG, state='disabled', bd=0, relief='flat')
        self.log_text.pack(fill='both', expand=True, padx=8, pady=(2, 8))

    # ══════════════════════════════════════════════════════
    #  設定パネル構築
    # ══════════════════════════════════════════════════════
    def _build_config_panel(self) -> tk.Frame:
        outer = tk.Frame(self.root, bg=BORDER, bd=1, relief='groove')
        # ← pack はしない。toggle_config で行う

        inner = tk.Frame(outer, bg=BG)
        inner.pack(fill='both', expand=True, padx=2, pady=2)

        hdr = tk.Frame(inner, bg=PANEL, pady=3)
        hdr.pack(fill='x')
        tk.Label(hdr, text="⚙  CONFIGURATION  //  WEB APP SETTINGS",
                 bg=PANEL, fg=LCD_DIM, font=(FONT, 8, 'bold')).pack(side='left', padx=10)

        cols = tk.Frame(inner, bg=BG)
        cols.pack(fill='both', expand=True, padx=8, pady=6)

        cfg = _read_config()
        wc  = cfg.get('web_config', {})

        # ─── WEB APP 設定 (full width) ─────────────────────
        wf = tk.LabelFrame(cols, text="  WEB APP  //  seya-chat-trans  ",
                           bg=BG, fg='#7FAAFF', font=(FONT, 8, 'bold'),
                           bd=1, relief='groove')
        wf.pack(fill='both', expand=True)

        lang_labels = [l[0] for l in _TRANS_LANGS]
        lang_codes  = [l[1] for l in _TRANS_LANGS]

        r = 0
        # ── TRANS LANG (最上部, 目立つ) ──────────────────────
        tk.Label(wf, text="TRANSLATE:", bg=BG, fg=LCD_FG,
                 font=(FONT, 8, 'bold')).grid(row=r, column=0, sticky='e', padx=(8, 4), pady=6)
        trans_row = tk.Frame(wf, bg=BG)
        trans_row.grid(row=r, column=1, columnspan=2, sticky='w', padx=(0, 8), pady=6)
        tk.Label(trans_row, text="JA  →", bg=BG, fg=LCD_FG,
                 font=(FONT, 10, 'bold')).pack(side='left', padx=(0, 6))
        cur_lang  = wc.get('translation_target', 'en')
        cur_label = lang_labels[lang_codes.index(cur_lang)] if cur_lang in lang_codes else 'English'
        self._trans_lang_var = tk.StringVar(value=cur_label)
        lang_menu = tk.OptionMenu(trans_row, self._trans_lang_var, *lang_labels)
        lang_menu.config(bg=BTN_BG, fg=LCD_FG, font=(FONT, 9, 'bold'),
                         activebackground=BTN_ACT, activeforeground=LCD_FG,
                         relief='raised', bd=1, highlightthickness=0, width=12)
        lang_menu['menu'].config(bg=BTN_BG, fg=LCD_FG, font=(FONT, 9, 'bold'))
        lang_menu.pack(side='left')
        # TTS LANG は TRANS LANG に自動追従 (別ロウ不要)
        cur_tts_lang = wc.get('tts_language', 'en')
        cur_tts_label = lang_labels[lang_codes.index(cur_tts_lang)] if cur_tts_lang in lang_codes else 'English'
        self._tts_lang_var = tk.StringVar(value=cur_tts_label)
        self._trans_lang_var.trace_add('write', self._on_trans_lang_change)

        r += 1
        # PAGE ID
        tk.Label(wf, text="PAGE ID:", bg=BG, fg=MUTED,
                 font=(FONT, 8)).grid(row=r, column=0, sticky='e', padx=(8, 4), pady=4)
        page_id_row = tk.Frame(wf, bg=BG)
        page_id_row.grid(row=r, column=1, columnspan=2, sticky='ew', padx=(0, 8), pady=4)
        self._page_id_var = tk.StringVar(value=wc.get('page_id', ''))
        tk.Entry(page_id_row, textvariable=self._page_id_var,
                 bg='#1E2010', fg='#7FAAFF', insertbackground='#7FAAFF',
                 font=(FONT, 9), width=16, relief='flat', bd=1).pack(side='left')
        tk.Label(page_id_row, text="(empty = main page)",
                 bg=BG, fg=MUTED, font=(FONT, 7)).pack(side='left', padx=(6, 0))

        r += 1
        # WEB AUDIO ON/OFF
        tk.Label(wf, text="WEB AUDIO:", bg=BG, fg=MUTED,
                 font=(FONT, 8)).grid(row=r, column=0, sticky='e', padx=(8, 4), pady=4)
        self._web_audio_var = tk.BooleanVar(value=wc.get('tts_audio_enabled', True))
        audio_frame = tk.Frame(wf, bg=BG)
        audio_frame.grid(row=r, column=1, sticky='w', padx=(0, 8), pady=4)
        tk.Radiobutton(audio_frame, text="ON", variable=self._web_audio_var, value=True,
                       bg=BG, fg=LED_ON, selectcolor='#122200', font=(FONT, 8, 'bold'),
                       activebackground=BG).pack(side='left', padx=(0, 6))
        tk.Radiobutton(audio_frame, text="OFF", variable=self._web_audio_var, value=False,
                       bg=BG, fg=MUTED, selectcolor='#122200', font=(FONT, 8, 'bold'),
                       activebackground=BG).pack(side='left')

        r += 1
        # TTS ENGINE
        tk.Label(wf, text="TTS ENGINE:", bg=BG, fg=MUTED,
                 font=(FONT, 8)).grid(row=r, column=0, sticky='e', padx=(8, 4), pady=4)
        cur_engine = wc.get('tts_engine', 'gemini')
        self._tts_engine_var = tk.StringVar(value='GEMINI' if cur_engine == 'gemini' else 'G.CLOUD')
        eng_frame = tk.Frame(wf, bg=BG)
        eng_frame.grid(row=r, column=1, sticky='w', padx=(0, 8), pady=4)
        tk.Radiobutton(eng_frame, text="GEMINI", variable=self._tts_engine_var, value='GEMINI',
                       bg=BG, fg='#7FAAFF', selectcolor='#0A0A1E', font=(FONT, 8, 'bold'),
                       activebackground=BG,
                       command=self._on_tts_engine_change).pack(side='left', padx=(0, 10))
        tk.Radiobutton(eng_frame, text="G.CLOUD WAVENET", variable=self._tts_engine_var, value='G.CLOUD',
                       bg=BG, fg='#7FAAFF', selectcolor='#0A0A1E', font=(FONT, 8, 'bold'),
                       activebackground=BG,
                       command=self._on_tts_engine_change).pack(side='left')

        r += 1
        # ── TTS VOICE (Gemini) ─────────────────────────────
        self._voice_label = tk.Label(wf, text="TTS VOICE:", bg=BG, fg=MUTED, font=(FONT, 8))
        self._voice_label.grid(row=r, column=0, sticky='e', padx=(8, 4), pady=4)
        cur_voice = wc.get('tts_voice', 'Kore')
        self._tts_voice_var = tk.StringVar(value=cur_voice)
        self._gemini_voice_menu = tk.OptionMenu(wf, self._tts_voice_var, *_TTS_VOICES)
        self._gemini_voice_menu.config(bg=BTN_BG, fg='#7FAAFF', font=(FONT, 8),
                                       activebackground=BTN_ACT, activeforeground='#7FAAFF',
                                       relief='raised', bd=1, highlightthickness=0, width=14)
        self._gemini_voice_menu['menu'].config(bg=BTN_BG, fg='#7FAAFF', font=(FONT, 8))
        self._gemini_voice_menu.grid(row=r, column=1, sticky='w', padx=(0, 4), pady=4)

        # Gemini 料金ラベル (固定)
        self._gemini_price_lbl = tk.Label(wf, text="preview pricing",
                                          bg=BG, fg='#555566', font=(FONT, 7))
        self._gemini_price_lbl.grid(row=r, column=2, sticky='w', padx=(0, 8), pady=4)

        # ── TTS VOICE (Google Cloud) — カスケードメニュー ──
        cur_gcloud = wc.get('gcloud_tts_voice', 'ja-JP-Wavenet-A')
        self._gcloud_voice_var = tk.StringVar(value=cur_gcloud)
        self._gcloud_voice_btn = self._make_gcloud_menubutton(wf)
        self._gcloud_voice_btn.grid(row=r, column=1, sticky='w', padx=(0, 4), pady=4)

        # G.Cloud 動的料金ラベル
        self._gcloud_price_var = tk.StringVar(value=_gcloud_price_text(cur_gcloud))
        self._gcloud_price_lbl = tk.Label(wf, textvariable=self._gcloud_price_var,
                                          bg=BG, fg='#AABB55', font=(FONT, 7, 'bold'))
        self._gcloud_price_lbl.grid(row=r, column=2, sticky='w', padx=(0, 8), pady=4)
        self._gcloud_voice_var.trace_add('write', self._on_gcloud_voice_change)

        r += 1
        # ── VOLUME ─────────────────────────────────────────
        tk.Label(wf, text="VOLUME:", bg=BG, fg=MUTED,
                 font=(FONT, 8)).grid(row=r, column=0, sticky='e', padx=(8, 4), pady=4)
        vol_frame = tk.Frame(wf, bg=BG)
        vol_frame.grid(row=r, column=1, columnspan=2, sticky='ew', padx=(0, 8), pady=4)
        cur_vol = int(wc.get('tts_volume', 100))
        self._vol_var = tk.IntVar(value=cur_vol)
        self._vol_label_var = tk.StringVar(value=f"{cur_vol}%")
        tk.Scale(vol_frame, variable=self._vol_var, from_=0, to=200,
                 orient='horizontal', length=200, resolution=5,
                 bg=BG, fg=LCD_FG, troughcolor='#1E2010', highlightthickness=0,
                 activebackground=LCD_FG, sliderrelief='flat',
                 command=lambda v: self._vol_label_var.set(f"{int(float(v))}%")
                 ).pack(side='left')
        tk.Label(vol_frame, textvariable=self._vol_label_var,
                 bg=BG, fg=LCD_FG, font=(FONT, 9, 'bold'), width=5).pack(side='left', padx=(6, 0))
        tk.Label(vol_frame, text="(100=normal, 200=+gain)",
                 bg=BG, fg=MUTED, font=(FONT, 7)).pack(side='left', padx=(4, 0))

        r += 1
        # ── SA JSON (G.CLOUD専用) ──────────────────────────
        self._gcloud_sa_label = tk.Label(wf, text="SA JSON:", bg=BG, fg=MUTED, font=(FONT, 8))
        self._gcloud_sa_label.grid(row=r, column=0, sticky='e', padx=(8, 4), pady=4)
        sa_path = wc.get('gcloud_sa_json_path', '') or os.getenv('GOOGLE_SA_JSON_PATH', '')
        self._gcloud_sa_var = tk.StringVar(value=sa_path)
        self._sa_row_frame = tk.Frame(wf, bg=BG)
        self._sa_row_frame.grid(row=r, column=1, columnspan=2, sticky='ew', padx=(0, 8), pady=4)
        tk.Entry(self._sa_row_frame, textvariable=self._gcloud_sa_var,
                 bg='#1E2010', fg='#7FAAFF', insertbackground='#7FAAFF',
                 font=(FONT, 8), width=30, relief='flat', bd=1).pack(side='left', fill='x', expand=True)
        tk.Button(self._sa_row_frame, text="browse", command=self._browse_sa_json,
                  bg=BTN_BG, fg=MUTED, font=(FONT, 7),
                  relief='flat', bd=0, padx=4, pady=1,
                  cursor='hand2', activebackground=BTN_ACT).pack(side='left', padx=(4, 0))

        # 初期表示切替
        self._on_tts_engine_change()

        r += 1
        # TTS STYLE PROMPT
        tk.Label(wf, text="TTS STYLE:", bg=BG, fg=MUTED,
                 font=(FONT, 8)).grid(row=r, column=0, sticky='e', padx=(8, 4), pady=4)
        self._tts_style_var = tk.StringVar(value=wc.get('tts_style_prompt', ''))
        tk.Entry(wf, textvariable=self._tts_style_var,
                 bg='#1E2010', fg='#7FAAFF', insertbackground='#7FAAFF',
                 font=(FONT, 9), width=36, relief='flat', bd=1
                 ).grid(row=r, column=1, columnspan=2, sticky='ew', padx=(0, 8), pady=4)

        r += 1
        # UI COLOR
        tk.Label(wf, text="UI COLOR:", bg=BG, fg=MUTED,
                 font=(FONT, 8)).grid(row=r, column=0, sticky='e', padx=(8, 4), pady=4)
        color_row = tk.Frame(wf, bg=BG)
        color_row.grid(row=r, column=1, sticky='w', padx=(0, 8), pady=4)
        self._ui_color_var = tk.StringVar(value=wc.get('ui_primary_color', '#AABF00'))
        tk.Entry(color_row, textvariable=self._ui_color_var,
                 bg='#1E2010', fg=LCD_FG, insertbackground=LCD_FG,
                 font=(FONT, 9), width=9, relief='flat', bd=1).pack(side='left', padx=(0, 4))
        self._color_preview = tk.Canvas(color_row, width=20, height=20,
                                        bg=self._ui_color_var.get(),
                                        highlightthickness=1, highlightbackground=BORDER)
        self._color_preview.pack(side='left', padx=(0, 4))
        tk.Button(color_row, text="pick", command=self._pick_color,
                  bg=BTN_BG, fg=LCD_FG, font=(FONT, 7),
                  relief='flat', bd=0, padx=4, pady=1,
                  cursor='hand2', activebackground=BTN_ACT
                  ).pack(side='left')
        self._ui_color_var.trace_add('write', self._on_color_entry_change)

        r += 1
        # UI THEME
        tk.Label(wf, text="UI THEME:", bg=BG, fg=MUTED,
                 font=(FONT, 8)).grid(row=r, column=0, sticky='e', padx=(8, 4), pady=4)
        self._ui_theme_var = tk.StringVar(value=wc.get('ui_theme', 'dark').upper())
        theme_menu = tk.OptionMenu(wf, self._ui_theme_var, "DARK", "LIGHT")
        theme_menu.config(bg=BTN_BG, fg=LCD_FG, font=(FONT, 8),
                          activebackground=BTN_ACT, activeforeground=LCD_FG,
                          relief='raised', bd=1, highlightthickness=0, width=6)
        theme_menu['menu'].config(bg=BTN_BG, fg=LCD_FG, font=(FONT, 8))
        theme_menu.grid(row=r, column=1, sticky='w', padx=(0, 8), pady=4)

        r += 1
        # PUSH ボタン
        btn_w = tk.Frame(wf, bg=BG)
        btn_w.grid(row=r, column=0, columnspan=3, pady=(4, 8), padx=8, sticky='ew')
        self._push_status_var = tk.StringVar(value="")
        tk.Label(btn_w, textvariable=self._push_status_var,
                 bg=BG, fg=LCD_DIM, font=(FONT, 7)).pack(side='left', padx=(0, 8))
        tk.Button(btn_w, text="PUSH TO FIREBASE",
                  command=self._push_web_config,
                  bg='#1A2A1A', fg=LED_ON, font=(FONT, 8, 'bold'),
                  relief='raised', bd=1, padx=10, pady=3,
                  cursor='hand2', activebackground='#243424'
                  ).pack(side='right')

        wf.columnconfigure(1, weight=1)
        wf.columnconfigure(2, weight=0)

        return outer

    # ══════════════════════════════════════════════════════
    #  最前面トグル
    # ══════════════════════════════════════════════════════
    def toggle_topmost(self):
        self._topmost = not self._topmost
        self.root.attributes('-topmost', self._topmost)
        self._top_btn.config(text="▲" if self._topmost else "▽")

    # ══════════════════════════════════════════════════════
    #  CONFIG パネルトグル
    # ══════════════════════════════════════════════════════
    def toggle_config(self):
        if self._cfg_open:
            self._cfg_frame.pack_forget()
            self._cfg_open = False
            self._cfg_btn_var.set("CONFIG")
        else:
            self._cfg_frame.pack(fill='x', padx=16, pady=(0, 6),
                                 before=self._log_wrap)
            self._cfg_open = True
            self._cfg_btn_var.set("▲ CONFIG")

    # ══════════════════════════════════════════════════════
    #  Web 設定メソッド
    # ══════════════════════════════════════════════════════

    def _make_gcloud_menubutton(self, parent) -> tk.Menubutton:
        """G.Cloud 音声選択用カスケード Menubutton を生成して返す。
        言語ごとにサブメニューを持ち、各サブメニューにモデル別グループを表示。
        """
        # Menu widget 用スタイル (bg/fg はウィジェット本体に設定)
        _MK = {'bg': BTN_BG, 'fg': '#7FAAFF',
               'activebackground': BTN_ACT, 'activeforeground': '#AACCFF'}

        mb = tk.Menubutton(parent, textvariable=self._gcloud_voice_var,
                           bg=BTN_BG, fg='#7FAAFF', font=(FONT, 8),
                           relief='raised', bd=1, width=24, anchor='w',
                           activebackground=BTN_ACT, activeforeground='#AACCFF',
                           indicatoron=True)
        top = tk.Menu(mb, tearoff=0, font=(FONT, 8), **_MK)
        mb['menu'] = top

        for lang, tiers in _GCLOUD_VOICE_GROUPS:
            lang_menu = tk.Menu(top, tearoff=0, font=(FONT, 8), **_MK)
            top.add_cascade(label=lang, menu=lang_menu)
            first = True
            for tier, suffixes in tiers:
                if not first:
                    lang_menu.add_separator()
                first = False
                # tier ヘッダー (非選択、font のみ指定)
                lang_menu.add_command(
                    label=f'── {tier} ──',
                    state='disabled',
                    font=(FONT, 7))
                for s in suffixes:
                    v = f'{lang}-{tier}-{s}'
                    lang_menu.add_command(
                        label=f'  {tier}-{s}',
                        font=(FONT, 8),
                        command=lambda vv=v: self._gcloud_voice_var.set(vv))
        return mb

    def _on_trans_lang_change(self, *_):
        """TRANS LANG 変更時に TTS LANG を自動同期し LATEST PHRASE ラベルも更新."""
        label = self._trans_lang_var.get()
        self._tts_lang_var.set(label)
        ll = [l[0] for l in _TRANS_LANGS]
        lc = [l[1] for l in _TRANS_LANGS]
        code = lc[ll.index(label)].upper() if label in ll else 'TL'
        self._stt_lang_label_var.set(code + ':')

    def _on_tts_engine_change(self, *_):
        """エンジン切替時にボイスメニュー・料金ラベル・SA JSON行を切替。"""
        if self._tts_engine_var.get() == 'G.CLOUD':
            self._gemini_voice_menu.grid_remove()
            self._gemini_price_lbl.grid_remove()
            self._gcloud_voice_btn.grid()
            self._gcloud_price_lbl.grid()
            self._gcloud_sa_label.grid()
            self._sa_row_frame.grid()
        else:
            self._gcloud_voice_btn.grid_remove()
            self._gcloud_price_lbl.grid_remove()
            self._gcloud_sa_label.grid_remove()
            self._sa_row_frame.grid_remove()
            self._gemini_voice_menu.grid()
            self._gemini_price_lbl.grid()

    def _on_gcloud_voice_change(self, *_):
        """G.Cloud ボイス変更時に料金ラベルを更新。"""
        self._gcloud_price_var.set(_gcloud_price_text(self._gcloud_voice_var.get()))

    def _browse_sa_json(self):
        path = filedialog.askopenfilename(
            title="サービスアカウント JSON を選択",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if path:
            self._gcloud_sa_var.set(path)

    def _pick_color(self):
        result = colorchooser.askcolor(color=self._ui_color_var.get(),
                                       title="UI Primary Color")
        if result and result[1]:
            self._ui_color_var.set(result[1])
            try:
                self._color_preview.config(bg=result[1])
            except Exception:
                pass

    def _on_color_entry_change(self, *_):
        c = self._ui_color_var.get()
        if len(c) == 7 and c.startswith('#'):
            try:
                self._color_preview.config(bg=c)
            except Exception:
                pass

    def _push_web_config(self):
        if not HAS_REQUESTS:
            self.log_message("[WEB] requests 未インストール\n")
            return
        lang_labels = [l[0] for l in _TRANS_LANGS]
        lang_codes  = [l[1] for l in _TRANS_LANGS]

        label     = self._trans_lang_var.get()
        lang_code = lang_codes[lang_labels.index(label)] if label in lang_labels else 'ja'

        tts_label = self._tts_lang_var.get()
        tts_lang  = lang_codes[lang_labels.index(tts_label)] if tts_label in lang_labels else 'en'

        engine_val = 'google_cloud' if self._tts_engine_var.get() == 'G.CLOUD' else 'gemini'
        page_id    = self._page_id_var.get().strip()
        web_cfg = {
            'tts_audio_enabled':   self._web_audio_var.get(),
            'tts_engine':          engine_val,
            'tts_voice':           self._tts_voice_var.get(),
            'gcloud_tts_voice':    self._gcloud_voice_var.get(),
            'gcloud_sa_json_path': self._gcloud_sa_var.get().strip(),
            'tts_volume':          self._vol_var.get(),
            'tts_language':        tts_lang,
            'tts_style_prompt':    self._tts_style_var.get().strip(),
            'translation_target':  lang_code,
            'ui_primary_color':    self._ui_color_var.get(),
            'ui_theme':            self._ui_theme_var.get().lower(),
            'page_id':             page_id,
        }

        # config.json に保存
        cfg = _read_config()
        cfg['web_config'] = web_cfg
        _write_config(cfg)

        # Firebase に送信
        firebase_url = _get_firebase_url()
        if not firebase_url:
            self._push_status_var.set("⚠ Firebase URL 未設定")
            self.log_message("[WEB] ❌ Firebase URL が設定されていません\n")
            return

        self._push_status_var.set("送信中...")

        def _do():
            try:
                # Firebase Auth トークン取得
                params = {}
                try:
                    from firebase_auth import FirebaseAuth as _FA
                    _cfg2 = _read_config()
                    _fba  = _cfg2.get('firebase_auth', {})
                    _ak   = _fba.get('api_key', '') or _cfg2.get('api_keys', {}).get('firebase_api_key', '')
                    _em   = _fba.get('email', '')
                    _pw   = _fba.get('password', '')
                    if _ak and _em and _pw:
                        params = _FA(_ak, _em, _pw).params()
                except Exception:
                    pass

                cfg_key = f'web_app_{page_id}' if page_id else 'web_app'
                url = f"{firebase_url.rstrip('/')}/config/{cfg_key}.json"
                r = _requests.put(url, json=web_cfg, params=params, timeout=8)
                r.raise_for_status()
                self.root.after(0, self._push_status_var.set, "✅ 送信完了")
                self.root.after(0, self.log_message,
                                f"[WEB] ✅ Firebase /config/{cfg_key} 更新完了\n")
                self.root.after(3000, self._push_status_var.set, "")
            except Exception as e:
                self.root.after(0, self._push_status_var.set, "❌ 失敗")
                self.root.after(0, self.log_message,
                                f"[WEB] ❌ Firebase 送信失敗: {e}\n")

        threading.Thread(target=_do, daemon=True).start()

    def open_mobile(self):
        page_id = getattr(self, '_page_id_var', None)
        page_id = page_id.get().strip() if page_id else ''
        url = "https://seya-chat-trans.web.app/"
        if page_id:
            url += f"?page={page_id}"
        webbrowser.open(url)

    # ── LED ────────────────────────────────────────────────
    def _set_led(self, state: str):
        color = {'on': LED_ON, 'off': LED_OFF, 'error': LED_RED}.get(state, LED_OFF)
        self._led_canvas.itemconfig(self._led_oval, fill=color)

    # ── ログ出力 ───────────────────────────────────────────
    def log_message(self, message):
        self.log_text.config(state='normal')
        self.log_text.insert('end', message)
        self.log_text.see('end')
        self.log_text.config(state='disabled')
        try:
            sys.stdout.write(message)
            sys.stdout.flush()
        except (UnicodeEncodeError, Exception):
            try:
                sys.stdout.buffer.write(message.encode('utf-8', errors='replace'))
                sys.stdout.buffer.flush()
            except Exception:
                pass

    # ── プロセス出力読み取り ────────────────────────────────
    def _read_output(self, pipe):
        for line in iter(pipe.readline, ''):
            if not line:
                break
            if line.startswith('[STT_RESULT]'):
                self.root.after(0, self._update_stt_panel, line.strip())
            else:
                self.root.after(0, self.log_message, line)
        pipe.close()

    def _update_stt_panel(self, line: str):
        try:
            body = line[len('[STT_RESULT]'):].strip()
            ja_part, en_part = body.split(' | ', 1)
            ja = ja_part[3:] if ja_part.startswith('JA=') else ja_part
            en = en_part[3:] if en_part.startswith('EN=') else en_part
            self._stt_ja_var.set(ja)
            en_disp = en if en and en != '(no translation)' else '—'
            self._stt_en_var.set(en_disp)
            self.log_message(f"[STT] {ja}  →  {en_disp}\n")
        except Exception:
            pass

    # ── プロセス管理 ───────────────────────────────────────
    def start_process(self):
        if self.process and self.process.poll() is None:
            return
        if not os.path.exists(self.script_path):
            messagebox.showerror("ERROR", f"Script not found:\n{self.script_path}")
            return
        try:
            env = {**os.environ, 'PYTHONUNBUFFERED': '1'}
            self.process = subprocess.Popen(
                [sys.executable, self.script_path],
                cwd=self.base_dir,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, encoding='utf-8', errors='replace',
                env=env
            )
            threading.Thread(target=self._read_output,
                             args=(self.process.stdout,), daemon=True).start()
            self.status_var.set("ACTIVE")
            self._set_led('on')
            self.log_message("[SYS] TRANSLATION MODULE  ONLINE\n")
        except Exception as e:
            messagebox.showerror("ERROR", f"Failed to start: {e}")
            self._set_led('error')

    def stop_process(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
        self.status_var.set("STANDBY")
        self._set_led('off')
        self.log_message("[SYS] TRANSLATION MODULE  OFFLINE\n")

    def cleanup_on_exit(self):
        self.stop_process()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = BlueRaybanUI(root)
    root.mainloop()
