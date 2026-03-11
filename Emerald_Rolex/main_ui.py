# -*- coding: utf-8 -*-
import sys
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try: sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

import tkinter as tk
from tkinter import scrolledtext, messagebox
import subprocess, threading, os, json, webbrowser

try:
    import requests as _req
    HAS_REQ = True
except ImportError:
    HAS_REQ = False

# ══════════════════════════════════════════════════════════
#  90s INDUSTRIAL UI — EMERALD_ROLEX // CHAT MONITOR
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
EM_GRN  = '#00FF88'  # Emerald accent

_BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(_BASE_DIR, "..", "config.json")

def _read_cfg() -> dict:
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def _write_cfg(cfg: dict):
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[CFG] write error: {e}")


class EmeraldRolexUI:
    MAX_CHAT = 6  # チャット表示の最大行数

    def __init__(self, root):
        self.root = root
        self.root.title("EMERALD_ROLEX  //  CHAT MONITOR")
        self.root.geometry("860x640")
        self.root.minsize(660, 420)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self.cleanup_on_exit)

        self.process     = None
        self.base_dir    = _BASE_DIR
        self.script_path = os.path.join(self.base_dir, "emerald_rolex.py")

        self._vvox_open  = False
        self._vvox_frame = None
        self._chat_items = []   # list of (display_name, message, ja, lang, badge)

        self._build_ui()
        self.root.after(100, self.start_process)

    # ══════════════════════════════════════════════════════
    #  UI 構築
    # ══════════════════════════════════════════════════════
    def _build_ui(self):
        # ── ヘッダー ─────────────────────────────────────
        fr_head = tk.Frame(self.root, bg=PANEL, pady=5)
        fr_head.pack(fill='x')
        tk.Label(fr_head, text="EMERALD_ROLEX",
                 bg=PANEL, fg=EM_GRN, font=(FONT, 13, 'bold')).pack(side='left', padx=16)
        tk.Label(fr_head, text="CHAT MONITOR  //  UNIT-01",
                 bg=PANEL, fg=MUTED, font=(FONT, 8)).pack(side='left', padx=4)
        tk.Button(fr_head, text="[ QUIT ]", command=self.cleanup_on_exit,
                  bg=BTN_BG, fg=LED_RED, font=(FONT, 9, 'bold'),
                  relief='raised', bd=2, padx=10, pady=2,
                  cursor='hand2', activebackground=BTN_ACT,
                  activeforeground=LED_RED).pack(side='right', padx=12, pady=4)
        tk.Frame(self.root, bg=BORDER, height=2).pack(fill='x')

        # ── コントロールストリップ ─────────────────────
        fr_ctrl = tk.Frame(self.root, bg=BG, pady=10)
        fr_ctrl.pack(fill='x', padx=18)

        self._led_canvas = tk.Canvas(fr_ctrl, width=16, height=16, bg=BG, highlightthickness=0)
        self._led_canvas.pack(side='left', padx=(0, 8))
        self._led_oval = self._led_canvas.create_oval(2, 2, 14, 14, fill=LED_OFF,
                                                      outline='#1A1A1A', width=1)
        self.status_var = tk.StringVar(value="STANDBY")
        tk.Label(fr_ctrl, textvariable=self.status_var,
                 bg=BG, fg=MUTED, font=(FONT, 10, 'bold'),
                 width=12, anchor='w').pack(side='left')

        for label, cmd in [("START", self.start_process), ("STOP", self.stop_process)]:
            tk.Button(fr_ctrl, text=label, command=cmd,
                      bg=BTN_BG, fg=BTN_FG, font=(FONT, 9, 'bold'),
                      relief='raised', bd=2, padx=16, pady=4,
                      cursor='hand2', activebackground=BTN_ACT,
                      activeforeground=BTN_FG).pack(side='left', padx=4)

        tk.Frame(fr_ctrl, bg=BORDER, width=2).pack(side='left', fill='y', padx=10, pady=4)

        # VOICEVOX トグル
        self._vvox_btn_var = tk.StringVar(value="VOICEVOX")
        tk.Button(fr_ctrl, textvariable=self._vvox_btn_var,
                  command=self.toggle_vvox,
                  bg='#1A1A2E', fg=EM_GRN, font=(FONT, 9, 'bold'),
                  relief='raised', bd=2, padx=10, pady=4,
                  cursor='hand2', activebackground='#252545',
                  activeforeground='#AAFFCC').pack(side='left')

        tk.Label(fr_ctrl, text="WS :8765",
                 bg=BG, fg=LCD_DIM, font=(FONT, 8)).pack(side='right')
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill='x', padx=18, pady=(0, 4))

        # ── チャット表示パネル ────────────────────────
        fr_chat_wrap = tk.Frame(self.root, bg=BORDER, bd=1, relief='groove')
        fr_chat_wrap.pack(fill='x', padx=16, pady=(0, 4))

        fr_chat_head = tk.Frame(fr_chat_wrap, bg=PANEL, pady=3)
        fr_chat_head.pack(fill='x')
        tk.Label(fr_chat_head, text="◀ LIVE CHAT  //  JA TRANSLATION ▶",
                 bg=PANEL, fg=LCD_DIM, font=(FONT, 7, 'bold')).pack(side='left', padx=10)

        self._chat_frame = tk.Frame(fr_chat_wrap, bg=LCD_BG)
        self._chat_frame.pack(fill='x', padx=4, pady=4)

        # ── VOICEVOX パネル (非表示で構築) ───────────
        self._vvox_frame = self._build_vvox_panel()

        # ── ログパネル ─────────────────────────────────
        self._log_wrap = tk.Frame(self.root, bg=BORDER, bd=1, relief='groove')
        self._log_wrap.pack(fill='both', expand=True, padx=16, pady=(0, 16))

        fr_log_head = tk.Frame(self._log_wrap, bg=PANEL, pady=3)
        fr_log_head.pack(fill='x')
        tk.Label(fr_log_head, text="PROCESS LOG",
                 bg=PANEL, fg=LCD_DIM, font=(FONT, 8)).pack(side='left', padx=10)

        self.log_text = scrolledtext.ScrolledText(
            self._log_wrap, bg=LCD_BG, fg=LCD_FG, font=(FONT, 10),
            insertbackground=LCD_FG, selectbackground=LCD_DIM,
            selectforeground=LCD_FG, state='disabled', bd=0, relief='flat')
        self.log_text.pack(fill='both', expand=True, padx=8, pady=(2, 8))

    # ══════════════════════════════════════════════════════
    #  VOICEVOX パネル
    # ══════════════════════════════════════════════════════
    def _build_vvox_panel(self) -> tk.Frame:
        outer = tk.Frame(self.root, bg=BORDER, bd=1, relief='groove')
        inner = tk.Frame(outer, bg=BG)
        inner.pack(fill='both', expand=True, padx=2, pady=2)

        hdr = tk.Frame(inner, bg=PANEL, pady=3)
        hdr.pack(fill='x')
        tk.Label(hdr, text="⚙  VOICEVOX  //  TTS SETTINGS",
                 bg=PANEL, fg=EM_GRN, font=(FONT, 8, 'bold')).pack(side='left', padx=10)

        body = tk.Frame(inner, bg=BG)
        body.pack(fill='x', padx=10, pady=6)

        cfg  = _read_cfg()
        er   = cfg.get("emerald_rolex", {})

        # ON/OFF
        self._vvox_enabled_var = tk.BooleanVar(value=er.get("voicevox_enabled", False))
        row0 = tk.Frame(body, bg=BG)
        row0.pack(fill='x', pady=2)
        tk.Label(row0, text="TTS:", bg=BG, fg=MUTED, font=(FONT, 8), width=10, anchor='e').pack(side='left')
        tk.Radiobutton(row0, text="ON",  variable=self._vvox_enabled_var, value=True,
                       bg=BG, fg=LED_ON, selectcolor='#122200', font=(FONT, 8, 'bold'),
                       activebackground=BG).pack(side='left', padx=(4, 10))
        tk.Radiobutton(row0, text="OFF", variable=self._vvox_enabled_var, value=False,
                       bg=BG, fg=MUTED, selectcolor='#122200', font=(FONT, 8, 'bold'),
                       activebackground=BG).pack(side='left')

        # VOICEVOX URL
        row1 = tk.Frame(body, bg=BG)
        row1.pack(fill='x', pady=2)
        tk.Label(row1, text="SERVER:", bg=BG, fg=MUTED, font=(FONT, 8), width=10, anchor='e').pack(side='left')
        self._vvox_url_var = tk.StringVar(value=er.get("voicevox_url", "http://localhost:50021"))
        tk.Entry(row1, textvariable=self._vvox_url_var,
                 bg='#1E2010', fg=LCD_FG, insertbackground=LCD_FG,
                 font=(FONT, 9), width=28, relief='flat', bd=1).pack(side='left', padx=4)

        # Speaker ID + list
        row2 = tk.Frame(body, bg=BG)
        row2.pack(fill='x', pady=2)
        tk.Label(row2, text="SPEAKER:", bg=BG, fg=MUTED, font=(FONT, 8), width=10, anchor='e').pack(side='left')
        self._vvox_spk_var = tk.StringVar(value=str(er.get("voicevox_speaker", 1)))
        tk.Spinbox(row2, from_=0, to=999, textvariable=self._vvox_spk_var,
                   bg='#1E2010', fg=LCD_FG, insertbackground=LCD_FG,
                   font=(FONT, 9), width=5, buttonbackground=BTN_BG, relief='flat'
                   ).pack(side='left', padx=4)
        tk.Button(row2, text="LIST", command=self._fetch_speakers,
                  bg=BTN_BG, fg=MUTED, font=(FONT, 8),
                  relief='raised', bd=1, padx=6, pady=1,
                  cursor='hand2', activebackground=BTN_ACT).pack(side='left', padx=4)
        self._spk_name_var = tk.StringVar(value="")
        tk.Label(row2, textvariable=self._spk_name_var,
                 bg=BG, fg=LCD_DIM, font=(FONT, 8)).pack(side='left', padx=4)

        # Speaker listbox (compact, hidden until LIST pressed)
        self._spk_listbox = tk.Listbox(body, bg='#1E2010', fg=LCD_FG, font=(FONT, 8),
                                       height=4, selectbackground=LCD_DIM,
                                       selectforeground=LCD_FG, relief='flat', bd=0)
        self._spk_listbox.bind('<<ListboxSelect>>', self._on_spk_select)

        # Volume
        row3 = tk.Frame(body, bg=BG)
        row3.pack(fill='x', pady=2)
        tk.Label(row3, text="VOLUME:", bg=BG, fg=MUTED, font=(FONT, 8), width=10, anchor='e').pack(side='left')
        self._vol_var = tk.DoubleVar(value=float(er.get("voicevox_volume", 1.0)))
        vol_scale = tk.Scale(row3, from_=0.0, to=2.0, resolution=0.05,
                             variable=self._vol_var, orient='horizontal',
                             bg=BG, fg=LCD_FG, troughcolor=LCD_BG,
                             highlightthickness=0, length=180,
                             font=(FONT, 7))
        vol_scale.pack(side='left', padx=4)
        self._vol_label = tk.Label(row3, textvariable=self._vol_var,
                                   bg=BG, fg=LCD_FG, font=(FONT, 8), width=4)
        self._vol_label.pack(side='left')

        # Buttons
        row_btn = tk.Frame(body, bg=BG)
        row_btn.pack(fill='x', pady=(4, 2))
        self._vvox_status_var = tk.StringVar(value="")
        tk.Label(row_btn, textvariable=self._vvox_status_var,
                 bg=BG, fg=LCD_DIM, font=(FONT, 7)).pack(side='left')
        tk.Button(row_btn, text="▶ TEST", command=self._test_vvox,
                  bg=BTN_BG, fg=EM_GRN, font=(FONT, 8, 'bold'),
                  relief='raised', bd=1, padx=10, pady=2,
                  cursor='hand2', activebackground=BTN_ACT).pack(side='right', padx=(4, 0))
        tk.Button(row_btn, text="SAVE", command=self._save_vvox,
                  bg=BTN_BG, fg=BTN_FG, font=(FONT, 8, 'bold'),
                  relief='raised', bd=1, padx=10, pady=2,
                  cursor='hand2', activebackground=BTN_ACT).pack(side='right')

        return outer

    def toggle_vvox(self):
        if self._vvox_open:
            self._vvox_frame.pack_forget()
            self._vvox_open = False
            self._vvox_btn_var.set("VOICEVOX")
        else:
            self._vvox_frame.pack(fill='x', padx=16, pady=(0, 4),
                                  before=self._log_wrap)
            self._vvox_open = True
            self._vvox_btn_var.set("▲ VOICEVOX")

    # ── VOICEVOX メソッド ─────────────────────────────────
    def _fetch_speakers(self):
        if not HAS_REQ:
            return
        url = self._vvox_url_var.get().rstrip("/")
        self._spk_listbox.delete(0, 'end')
        self._spk_listbox.pack(padx=10, pady=(0, 4), fill='x')

        def _do():
            try:
                r = _req.get(f"{url}/speakers", timeout=5)
                r.raise_for_status()
                self.root.after(0, self._populate_spk_list, r.json())
            except Exception as e:
                self.root.after(0, self.log_message, f"[VVOX] LIST error: {e}\n")

        threading.Thread(target=_do, daemon=True).start()

    def _populate_spk_list(self, speakers: list):
        self._spk_listbox.delete(0, 'end')
        for sp in speakers:
            name = sp.get("name", "?")
            for st in sp.get("styles", []):
                self._spk_listbox.insert('end', f"[{st['id']}] {name} / {st.get('name','')}")
        self.log_message(f"[VVOX] {len(speakers)} speakers loaded\n")

    def _on_spk_select(self, _event):
        sel = self._spk_listbox.curselection()
        if not sel: return
        item = self._spk_listbox.get(sel[0])
        try:
            sid = item.split(']')[0].lstrip('[').strip()
            self._vvox_spk_var.set(sid)
            self._spk_name_var.set(item.split('] ', 1)[-1] if '] ' in item else "")
        except Exception: pass

    def _test_vvox(self):
        if not HAS_REQ:
            return
        url     = self._vvox_url_var.get().rstrip("/")
        speaker = self._vvox_spk_var.get()
        volume  = float(self._vol_var.get())
        text    = "テスト。ボイスボックス接続確認中。"

        def _do():
            try:
                import urllib.parse, winsound, tempfile, os as _os
                enc = urllib.parse.quote(text, safe='')
                r1  = _req.post(f"{url}/audio_query?text={enc}&speaker={speaker}", timeout=10)
                r1.raise_for_status()
                aq  = r1.json()
                aq["volumeScale"] = max(0.0, min(2.0, volume))
                r2  = _req.post(f"{url}/synthesis?speaker={speaker}", json=aq,
                                headers={"Content-Type":"application/json","Accept":"audio/wav"},
                                timeout=20)
                r2.raise_for_status()
                tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
                tmp.write(r2.content)
                tmp.close()
                try:
                    winsound.PlaySound(tmp.name, winsound.SND_FILENAME)
                finally:
                    try: _os.unlink(tmp.name)
                    except: pass
                self.root.after(0, self._vvox_status_var.set, "✅ TEST OK")
                self.root.after(0, self.log_message, f"[VVOX] ✅ Test OK (speaker={speaker})\n")
            except Exception as e:
                self.root.after(0, self._vvox_status_var.set, f"❌ {e}")
                self.root.after(0, self.log_message, f"[VVOX] ❌ Test failed: {e}\n")
            self.root.after(3000, self._vvox_status_var.set, "")

        threading.Thread(target=_do, daemon=True).start()
        self._vvox_status_var.set("Testing...")

    def _save_vvox(self):
        cfg = _read_cfg()
        cfg.setdefault("emerald_rolex", {}).update({
            "voicevox_enabled": self._vvox_enabled_var.get(),
            "voicevox_url":     self._vvox_url_var.get().strip(),
            "voicevox_speaker": int(self._vvox_spk_var.get()),
            "voicevox_volume":  round(float(self._vol_var.get()), 2),
        })
        _write_cfg(cfg)
        self._vvox_status_var.set("✅ Saved")
        self.log_message("[VVOX] ✅ Settings saved to config.json\n")
        self.root.after(2000, self._vvox_status_var.set, "")

    # ══════════════════════════════════════════════════════
    #  チャット表示
    # ══════════════════════════════════════════════════════
    def _update_chat_panel(self, item: dict):
        """item: {display_name, message, ja, lang, color, badge}"""
        self._chat_items.append(item)
        if len(self._chat_items) > self.MAX_CHAT:
            self._chat_items.pop(0)

        for w in self._chat_frame.winfo_children():
            w.destroy()

        for i, it in enumerate(self._chat_items):
            is_latest = (i == len(self._chat_items) - 1)
            row_bg    = '#1C2000' if is_latest else LCD_BG
            fg_main   = '#FFFFFF' if is_latest else LCD_FG
            fg_sub    = '#AABF00' if is_latest else LCD_DIM

            row = tk.Frame(self._chat_frame, bg=row_bg,
                           highlightthickness=1 if is_latest else 0,
                           highlightbackground=EM_GRN if is_latest else LCD_BG)
            row.pack(fill='x', padx=2, pady=1)

            # バッジ + 名前
            hdr = tk.Frame(row, bg=row_bg)
            hdr.pack(fill='x', padx=6, pady=(2, 0))
            badge = it.get("badge", "none")
            badge_sym = {"broadcaster": "🔴", "moderator": "🟢",
                         "vip": "🟣", "subscriber": "⭐"}.get(badge, "")
            name_str = f"{badge_sym} {it['display_name']}" if badge_sym else it['display_name']
            bits = it.get("bits")
            if bits:
                name_str += f"  💎{bits}"
            first = it.get("is_first", False)
            if first:
                name_str += "  🆕"
            tk.Label(hdr, text=name_str,
                     bg=row_bg, fg=fg_main, font=(FONT, 8, 'bold'),
                     anchor='w').pack(side='left')
            lang = it.get("lang", "")
            if lang:
                tk.Label(hdr, text=f"[{lang}]",
                         bg=row_bg, fg=fg_sub, font=(FONT, 7)).pack(side='right', padx=2)

            # 原文
            tk.Label(row, text=it.get("message", ""),
                     bg=row_bg, fg=fg_main, font=(FONT, 9),
                     anchor='w', wraplength=760, justify='left'
                     ).pack(fill='x', padx=8, pady=(0, 1))

            # 日本語訳
            ja = it.get("ja", "")
            if ja and ja != it.get("message", ""):
                tk.Label(row, text=f"🇯🇵 {ja}",
                         bg=row_bg, fg='#88AAFF', font=(FONT, 9),
                         anchor='w', wraplength=760, justify='left'
                         ).pack(fill='x', padx=8, pady=(0, 3))

    # ══════════════════════════════════════════════════════
    #  LED + log
    # ══════════════════════════════════════════════════════
    def _set_led(self, state: str):
        c = {'on': LED_ON, 'off': LED_OFF, 'error': LED_RED}.get(state, LED_OFF)
        self._led_canvas.itemconfig(self._led_oval, fill=c)

    def log_message(self, message: str):
        self.log_text.config(state='normal')
        self.log_text.insert('end', message)
        self.log_text.see('end')
        self.log_text.config(state='disabled')
        try:
            sys.stdout.buffer.write(message.encode('utf-8', 'replace'))
            sys.stdout.flush()
        except Exception:
            pass

    # ══════════════════════════════════════════════════════
    #  subprocess 管理
    # ══════════════════════════════════════════════════════
    def _read_output(self, pipe):
        for line in iter(pipe.readline, ''):
            if not line:
                break
            line_s = line.rstrip('\n')
            # [CHAT_JSON] パース → チャットパネル更新
            if line_s.startswith("[CHAT_JSON] "):
                try:
                    item = json.loads(line_s[len("[CHAT_JSON] "):])
                    self.root.after(0, self._update_chat_panel, item)
                except Exception:
                    pass
                # ログには表示しない (チャットパネルで見える)
                continue
            self.root.after(0, self.log_message, line)
        pipe.close()

    def start_process(self):
        if self.process and self.process.poll() is None:
            return
        if not os.path.exists(self.script_path):
            messagebox.showerror("ERROR", f"Script not found:\n{self.script_path}")
            return
        try:
            self.process = subprocess.Popen(
                [sys.executable, self.script_path],
                cwd=self.base_dir,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, encoding='utf-8', errors='replace'
            )
            threading.Thread(target=self._read_output,
                             args=(self.process.stdout,), daemon=True).start()
            self.status_var.set("ACTIVE")
            self._set_led('on')
            self.log_message("[SYS] CHAT MONITOR ONLINE\n")
        except Exception as e:
            messagebox.showerror("ERROR", f"Failed to start: {e}")
            self._set_led('error')

    def stop_process(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try: self.process.wait(timeout=3)
            except subprocess.TimeoutExpired: self.process.kill()
            self.process = None
        self.status_var.set("STANDBY")
        self._set_led('off')
        self.log_message("[SYS] CHAT MONITOR OFFLINE\n")

    def cleanup_on_exit(self):
        self.stop_process()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = EmeraldRolexUI(root)
    root.mainloop()
