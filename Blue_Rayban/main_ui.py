# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import scrolledtext, messagebox
import subprocess
import threading
import sys
import os
import json

# ══════════════════════════════════════════════════════════
#  90s INDUSTRIAL UI  —  BLUE_RAY-BAN  //  TRANSLATION MODULE
# ══════════════════════════════════════════════════════════
BG      = '#1C1C1C'   # outer body
PANEL   = '#242424'   # panel surface
LCD_BG  = '#141800'   # LCD screen dark bg
LCD_FG  = '#AABF00'   # phosphor green text
LCD_DIM = '#485400'   # dim phosphor (secondary)
BORDER  = '#363636'   # panel edges
BTN_BG  = '#2A2A2A'   # button face
BTN_FG  = '#C4C4C4'   # button text
BTN_ACT = '#3A3A3A'   # button hover
LED_ON  = '#33CC00'   # green LED
LED_OFF = '#122200'   # LED inactive
LED_RED = '#BB1100'   # red LED / error
MUTED   = '#606060'   # muted label text
HEAD    = '#D0D0D0'   # header text
FONT    = 'Courier New'


_TTS_ENGINES = ["OFF", "VOICEVOX", "GEMINI"]

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.json")

def _read_tts_engine() -> str:
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f).get('tts', {}).get('engine', 'off').upper()
    except Exception:
        return 'OFF'

def _write_tts_engine(engine: str):
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        cfg.setdefault('tts', {})['engine'] = engine.lower()
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[TTS] config.json 書込エラー: {e}")


class BlueRaybanUI:
    def __init__(self, root):
        self.root = root
        self.root.title("BLUE_RAY-BAN  //  TRANSLATION MODULE")
        self.root.geometry("900x540")
        self.root.minsize(700, 380)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self.cleanup_on_exit)

        self.process = None
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.script_path = os.path.join(self.base_dir, "mainTST.py")

        self._build_ui()
        self.root.after(100, self.start_process)

    # ── Build ──────────────────────────────────────────────
    def _build_ui(self):
        # Header bar
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

        # Control strip
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

        # Control buttons
        for label, cmd, fg in [
            ("START",    self.start_process, BTN_FG),
            ("STOP",     self.stop_process,  BTN_FG),
        ]:
            tk.Button(fr_ctrl, text=label, command=cmd,
                      bg=BTN_BG, fg=fg, font=(FONT, 9, 'bold'),
                      relief='raised', bd=2, padx=16, pady=4,
                      cursor='hand2', activebackground=BTN_ACT,
                      activeforeground=BTN_FG).pack(side='left', padx=4)

        # Divider
        tk.Frame(fr_ctrl, bg=BORDER, width=2).pack(
            side='left', fill='y', padx=12, pady=4)

        tk.Button(fr_ctrl, text="SETTINGS",
                  command=self.open_settings,
                  bg=BTN_BG, fg=MUTED, font=(FONT, 9),
                  relief='raised', bd=2, padx=12, pady=4,
                  cursor='hand2', activebackground=BTN_ACT,
                  activeforeground=BTN_FG).pack(side='left')

        # ── TTS トグル ──────────────────────────────────────
        tk.Frame(fr_ctrl, bg=BORDER, width=2).pack(
            side='left', fill='y', padx=10, pady=4)

        tk.Label(fr_ctrl, text="TTS:",
                 bg=BG, fg=LCD_DIM, font=(FONT, 8)).pack(side='left')

        current_tts = _read_tts_engine()
        self._tts_var = tk.StringVar(value=current_tts)
        self._tts_btn = tk.Button(
            fr_ctrl, textvariable=self._tts_var,
            command=self.cycle_tts,
            bg=BTN_BG, fg=LCD_FG, font=(FONT, 8, 'bold'),
            relief='raised', bd=2, padx=10, pady=4,
            cursor='hand2', activebackground=BTN_ACT,
            activeforeground=LCD_FG, width=8)
        self._tts_btn.pack(side='left', padx=2)

        # ── MOBILE 表示ボタン ───────────────────────────────
        tk.Frame(fr_ctrl, bg=BORDER, width=2).pack(
            side='left', fill='y', padx=8, pady=4)

        tk.Button(fr_ctrl, text="📱 MOBILE",
                  command=self.open_mobile,
                  bg=BTN_BG, fg=MUTED, font=(FONT, 9),
                  relief='raised', bd=2, padx=10, pady=4,
                  cursor='hand2', activebackground=BTN_ACT,
                  activeforeground=BTN_FG).pack(side='left')

        tk.Frame(self.root, bg=BORDER, height=1).pack(
            fill='x', padx=18, pady=(0, 6))

        # LCD log panel
        fr_lcd_wrap = tk.Frame(self.root, bg=BORDER, bd=1, relief='groove')
        fr_lcd_wrap.pack(fill='both', expand=True, padx=16, pady=(0, 16))

        fr_lcd_head = tk.Frame(fr_lcd_wrap, bg=PANEL, pady=3)
        fr_lcd_head.pack(fill='x')
        tk.Label(fr_lcd_head, text="PROCESS LOG",
                 bg=PANEL, fg=LCD_DIM, font=(FONT, 8)).pack(
            side='left', padx=10)

        self.log_text = scrolledtext.ScrolledText(
            fr_lcd_wrap,
            bg=LCD_BG, fg=LCD_FG,
            font=(FONT, 10),
            insertbackground=LCD_FG,
            selectbackground=LCD_DIM,
            selectforeground=LCD_FG,
            state='disabled', bd=0, relief='flat')
        self.log_text.pack(fill='both', expand=True, padx=8, pady=(2, 8))

    # ── TTS サイクル ───────────────────────────────────────
    def cycle_tts(self):
        current = self._tts_var.get()
        try:
            idx = _TTS_ENGINES.index(current)
        except ValueError:
            idx = 0
        next_engine = _TTS_ENGINES[(idx + 1) % len(_TTS_ENGINES)]
        self._tts_var.set(next_engine)
        _write_tts_engine(next_engine)

        # LED 色を TTS 状態で変える
        if next_engine == 'OFF':
            self._tts_btn.config(fg=LCD_DIM)
        else:
            self._tts_btn.config(fg=LCD_FG)

        self.log_message(f"[SYS] TTS ENGINE → {next_engine}\n")

    def open_mobile(self):
        mobile_html = os.path.join(self.base_dir, "mobile.html")
        if os.path.exists(mobile_html):
            import webbrowser
            webbrowser.open(f"file:///{mobile_html.replace(chr(92), '/')}")
        else:
            messagebox.showwarning("NOT FOUND", "mobile.html not found.")

    # ── LED helper ─────────────────────────────────────────
    def _set_led(self, state: str):
        color = {'on': LED_ON, 'off': LED_OFF, 'error': LED_RED}.get(state, LED_OFF)
        self._led_canvas.itemconfig(self._led_oval, fill=color)

    # ── Actions ────────────────────────────────────────────
    def open_settings(self):
        settings_html = os.path.join(self.base_dir, "settings.html")
        if os.path.exists(settings_html):
            import webbrowser
            webbrowser.open(f"file:///{settings_html.replace(chr(92), '/')}")
        else:
            messagebox.showwarning("NOT FOUND", "settings.html not found.")

    def log_message(self, message):
        self.log_text.config(state='normal')
        self.log_text.insert('end', message)
        self.log_text.see('end')
        self.log_text.config(state='disabled')
        sys.stdout.write(message)
        sys.stdout.flush()

    def _read_output(self, pipe):
        for line in iter(pipe.readline, ''):
            if not line:
                break
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
