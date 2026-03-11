# -*- coding: utf-8 -*-
import sys
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try: sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

import tkinter as tk
from tkinter import scrolledtext, messagebox, colorchooser
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
FONT    = 'Courier New'

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

_BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(_BASE_DIR, "..", "config.json")
TOKEN_PATH  = os.path.join(_BASE_DIR, "twitchtoken.txt")


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



# ══════════════════════════════════════════════════════════
#  Main UI
# ══════════════════════════════════════════════════════════
class BlueRaybanUI:
    def __init__(self, root):
        self.root = root
        self.root.title("BLUE_RAY-BAN  //  TRANSLATION MODULE")
        self.root.geometry("900x580")
        self.root.minsize(700, 420)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self.cleanup_on_exit)

        self.process   = None
        self.base_dir  = _BASE_DIR
        self.script_path = os.path.join(self.base_dir, "mainTST.py")

        self._cfg_open    = False
        self._cfg_frame   = None   # 設定パネル (tk.Frame)
        self._log_wrap    = None   # LCD ログパネル (設定パネルの before= に使う)

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
        tk.Button(fr_ctrl, text="MOBILE",
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

        tk.Label(fr_stt, text="EN:", bg=LCD_BG, fg=LCD_DIM,
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
            bg=LCD_BG, fg=LCD_FG, font=(FONT, 10),
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
        # TTS VOICE
        tk.Label(wf, text="TTS VOICE:", bg=BG, fg=MUTED,
                 font=(FONT, 8)).grid(row=r, column=0, sticky='e', padx=(8, 4), pady=4)
        cur_voice = wc.get('tts_voice', 'Kore')
        self._tts_voice_var = tk.StringVar(value=cur_voice)
        voice_menu = tk.OptionMenu(wf, self._tts_voice_var, *_TTS_VOICES)
        voice_menu.config(bg=BTN_BG, fg='#7FAAFF', font=(FONT, 8),
                          activebackground=BTN_ACT, activeforeground='#7FAAFF',
                          relief='raised', bd=1, highlightthickness=0, width=10)
        voice_menu['menu'].config(bg=BTN_BG, fg='#7FAAFF', font=(FONT, 8))
        voice_menu.grid(row=r, column=1, sticky='w', padx=(0, 8), pady=4)

        r += 1
        # TTS LANGUAGE
        tk.Label(wf, text="TTS LANG:", bg=BG, fg=MUTED,
                 font=(FONT, 8)).grid(row=r, column=0, sticky='e', padx=(8, 4), pady=4)
        cur_tts_lang = wc.get('tts_language', 'en')
        cur_tts_label = lang_labels[lang_codes.index(cur_tts_lang)] if cur_tts_lang in lang_codes else 'English'
        self._tts_lang_var = tk.StringVar(value=cur_tts_label)
        tts_lang_menu = tk.OptionMenu(wf, self._tts_lang_var, *lang_labels)
        tts_lang_menu.config(bg=BTN_BG, fg='#7FAAFF', font=(FONT, 8),
                             activebackground=BTN_ACT, activeforeground='#7FAAFF',
                             relief='raised', bd=1, highlightthickness=0, width=10)
        tts_lang_menu['menu'].config(bg=BTN_BG, fg='#7FAAFF', font=(FONT, 8))
        tts_lang_menu.grid(row=r, column=1, sticky='w', padx=(0, 8), pady=4)

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
        # TRANS LANG
        tk.Label(wf, text="TRANS LANG:", bg=BG, fg=MUTED,
                 font=(FONT, 8)).grid(row=r, column=0, sticky='e', padx=(8, 4), pady=4)
        cur_lang  = wc.get('translation_target', 'ja')
        cur_label = lang_labels[lang_codes.index(cur_lang)] if cur_lang in lang_codes else lang_labels[0]
        self._trans_lang_var = tk.StringVar(value=cur_label)
        lang_menu = tk.OptionMenu(wf, self._trans_lang_var, *lang_labels)
        lang_menu.config(bg=BTN_BG, fg=LCD_FG, font=(FONT, 8),
                         activebackground=BTN_ACT, activeforeground=LCD_FG,
                         relief='raised', bd=1, highlightthickness=0, width=10)
        lang_menu['menu'].config(bg=BTN_BG, fg=LCD_FG, font=(FONT, 8))
        lang_menu.grid(row=r, column=1, sticky='w', padx=(0, 8), pady=4)

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

        return outer

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

        web_cfg = {
            'tts_audio_enabled':  self._web_audio_var.get(),
            'tts_voice':          self._tts_voice_var.get(),
            'tts_language':       tts_lang,
            'tts_style_prompt':   self._tts_style_var.get().strip(),
            'translation_target': lang_code,
            'ui_primary_color':   self._ui_color_var.get(),
            'ui_theme':           self._ui_theme_var.get().lower(),
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
                url = f"{firebase_url.rstrip('/')}/config/web_app.json"
                r = _requests.put(url, json=web_cfg, timeout=8)
                r.raise_for_status()
                self.root.after(0, self._push_status_var.set, "✅ 送信完了")
                self.root.after(0, self.log_message,
                                f"[WEB] ✅ Firebase /config/web_app 更新完了\n")
                self.root.after(3000, self._push_status_var.set, "")
            except Exception as e:
                self.root.after(0, self._push_status_var.set, "❌ 失敗")
                self.root.after(0, self.log_message,
                                f"[WEB] ❌ Firebase 送信失敗: {e}\n")

        threading.Thread(target=_do, daemon=True).start()

    def open_mobile(self):
        mobile_html = os.path.join(self.base_dir, "mobile.html")
        if os.path.exists(mobile_html):
            webbrowser.open(f"file:///{mobile_html.replace(chr(92), '/')}")
        else:
            messagebox.showwarning("NOT FOUND", "mobile.html not found.")

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
