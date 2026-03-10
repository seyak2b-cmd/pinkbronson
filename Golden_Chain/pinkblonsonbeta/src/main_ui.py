# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import subprocess
import os
import json
import html
import webbrowser
import google.generativeai as genai
from datetime import datetime, timezone
from obs_helper import OBSDisplayHelper
from PIL import Image, ImageTk
import platform
import sys
import threading
from audio_processor import AudioProcessor
from analytics_helper import AnalyticsHelper
from stream_analyzer import list_sessions, session_label, read_file, analyze, DEFAULT_PROMPT


class AquareadControlPanel:
    def __init__(self, root):
        self.root = root
        self.root.title("Golden_Chain")

        # ウィンドウサイズ設定
        window_width = 1280
        window_height = 900

        # 画面サイズを取得
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()

        # ウィンドウを画面中央に配置
        center_x = int((screen_width - window_width) / 2)
        center_y = int((screen_height - window_height) / 2)

        # ジオメトリを設定（サイズと位置）
        self.root.geometry(
            f"{window_width}x{window_height}+{center_x}+{center_y}")

        # 最小サイズを設定
        self.root.minsize(1024, 700)

        # ウィンドウのリサイズを許可
        self.root.resizable(True, True)

        # Cleanup on exit
        self.root.protocol("WM_DELETE_WINDOW", self.cleanup_on_exit)

        # Get paths
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.dirname(self.base_dir)
        self.log_dir = os.path.join(self.project_root, 'logs')
        self.cleaner_error_file = os.path.join(
            self.log_dir, 'cleaner_error.txt')

        # Process tracking
        self.processes = {
            'summarizer': None,
            'title_gen': None,
            'facilitator': None,
            'stt': None
        }

        # Config file
        self.config_file = os.path.join(self.project_root, 'config.json')
        self.load_config()

        # Initialize OBS Helper
        self.obs_helper = OBSDisplayHelper(
            self.project_root, self.config, self.save_config)

        # Initialize Audio Processor
        self.audio_processor = AudioProcessor(self.config, self.project_root)

        # Initialize Analytics Helper
        self.analytics_helper = AnalyticsHelper(self.project_root)

        # Apply initial theme
        self.apply_theme()

        # Kill orphaned processes from previous runs
        print("DEBUG: Killing orphaned processes...")
        self.kill_orphaned_processes()
        print("DEBUG: Orphaned processes killed.")

        # Create UI with tabs
        self.create_ui()

        # Start status update loop
        self.update_status()
        self.update_clock()
        self.update_outputs()
        self.update_volume_meter()
        # Schedule cleaner
        self.schedule_cleaner()

        # Show splash screen (Disabled)
        # print("DEBUG: Calling show_splash...")
        # self.show_splash()

    def show_splash(self):
        print("DEBUG: show_splash entered.")
        """Show splash screen before main window."""
        self.root.withdraw()  # Hide main window
        print("DEBUG: Main window withdrawn.")

        splash = tk.Toplevel(self.root)
        splash.overrideredirect(True)  # No window frame

        # Splash size
        width = 800
        height = 600

        # Center splash
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        splash.geometry(f'{width}x{height}+{x}+{y}')
        splash.configure(bg='#1a1b26')

        try:
            # Try to load splash image
            # Check assets folder first
            splash_path = os.path.join(
                self.base_dir, '..', 'assets', 'splash.png')
            if not os.path.exists(splash_path):
                # Fallback to local script dir if not found (development)
                splash_path = os.path.join(self.base_dir, 'splash.png')

            if os.path.exists(splash_path):
                image = Image.open(splash_path)
                # Resize to fit nicely
                image = image.resize((800, 600), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(image)

                label = tk.Label(splash, image=photo, bg='#1a1b26', bd=0)
                label.image = photo  # Keep reference
                label.pack(fill='both', expand=True)
            else:
                # Text fallback
                tk.Label(splash, text="AQUAREAD", font=('Courier New', 40, 'bold'),
                         fg='#7aa2f7', bg='#1a1b26').pack(expand=True)
                tk.Label(splash, text="Loading...", font=('Courier New', 14),
                         fg='#a9b1d6', bg='#1a1b26').pack(pady=20)
        except Exception as e:
            print(f"Splash error: {e}")
            tk.Label(splash, text="AQUAREAD", font=('Courier New', 40, 'bold'),
                     fg='#7aa2f7', bg='#1a1b26').pack(expand=True)

        # Close splash after 3 seconds
        def close_splash():
            print("DEBUG: close_splash called!")
            splash.destroy()
            print("DEBUG: Splash destroyed.")
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            print("DEBUG: Main window deiconified and lifted.")
            self.root.update()

        print("DEBUG: Scheduling close_splash in 3000ms")
        self.root.after(3000, close_splash)

    def kill_orphaned_processes(self):
        """Kill processes from previous runs that might still be alive."""
        # We'll use subprocess 'taskkill' or 'kill' logic
        # Check status files for PIDs
        for name in self.processes:
            try:
                status_path = os.path.join(
                    self.project_root, 'data', 'status', f'{name}_status.json')
                if os.path.exists(status_path):
                    with open(status_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    pid = data.get('pid')
                    if pid:
                        try:
                            print(
                                f"Cleaning up orphaned {name} (PID: {pid})...")
                            if platform.system() == 'Windows':
                                subprocess.run(['taskkill',
                                                '/F',
                                                '/PID',
                                                str(pid)],
                                               stdout=subprocess.DEVNULL,
                                               stderr=subprocess.DEVNULL)
                            else:
                                subprocess.run(['kill', '-9', str(pid)],
                                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        except BaseException:
                            pass
            except Exception as e:
                print(f"Error checking orphans for {name}: {e}")

    def cleanup_on_exit(self):
        """Stop all processes and exit."""
        if messagebox.askokcancel(
            "Quit",
                "Are you sure you want to quit? All processes will be stopped."):
            self.stop_all_processes(force=True)
            self.root.destroy()

    def stop_all_processes(self, force=False):
        """Helper to stop all known and orphaned processes."""
        # First stop what we know
        for name in self.processes:
            if self.processes[name] is not None:
                try:
                    self.stop_process(name)
                except BaseException:
                    pass

        # Then force sweep orphans if requested
        if force:
            self.kill_orphaned_processes()
            # Also ensure copier is dead
            try:
                if platform.system() == 'Windows':
                    subprocess.run(['taskkill',
                                    '/F',
                                    '/IM',
                                    'powershell.exe'],
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
                else:
                    # On Mac/Linux, copier might be running via pwsh or python
                    # wrapper
                    pass
            except BaseException:
                pass

    def load_config(self):
        """Load configuration from file."""
        default_config = {
            'api_key': '',  # APIキーはデフォルトで空にする
            'copier_source': 'C:\\Users\\seyak\\AppData\\Roaming\\Aqua Voice\\settings.json',
            'summarizer_interval': 60,
            'summarizer_lookback': 666,
            'summarizer_prompt': '会話を3行で要約してください。',
            'title_gen_interval': 60,
            'title_gen_lookback': 60,
            'title_gen_prompt': 'タイトルを生成してください。',
            'facilitator_interval': 30,
            'facilitator_lookback': 180,
            'facilitator_prompt': '次の話題を提案してください。',
            'theme_mode': 'light'
        }

        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # デフォルト設定とマージ（新しいキーを追加）
                    self.config = {**default_config, **loaded_config}
            except (json.JSONDecodeError, IOError) as e:
                print(f"設定ファイルの読み込みに失敗しました: {e}")
                self.config = default_config
                messagebox.showwarning("警告",
                                       f"設定ファイルの読み込みに失敗しました。\nデフォルト設定を使用します。")
        else:
            self.config = default_config
            self.save_config()

        # Pink Bronsonのメイン設定からAPIキーを取得
        try:
            pb_config_path = os.path.normpath(
                os.path.join(self.project_root, '..', '..', 'config.json'))
            if os.path.exists(pb_config_path):
                with open(pb_config_path, 'r', encoding='utf-8') as f:
                    pb_config = json.load(f)
                    api_key = pb_config.get('api_keys', {}).get('gemini_key', '')
                    if api_key:
                        self.config['api_key'] = api_key
        except Exception as e:
            print(f"Pink BronsonのAPIキー読み込みエラー: {e}")

    def get_pink_bronson_mic_id(self):
        """Pink BronsonのconfigからマイクデバイスIDを取得する。"""
        try:
            pb_config_path = os.path.normpath(
                os.path.join(self.project_root, '..', '..', 'config.json'))
            if os.path.exists(pb_config_path):
                with open(pb_config_path, 'r', encoding='utf-8') as f:
                    pb_config = json.load(f)
                mic_str = pb_config.get('last_mic', '')
                if mic_str and mic_str.startswith('['):
                    end_idx = mic_str.find(']')
                    if end_idx != -1:
                        device_id_str = mic_str[1:end_idx]
                        if device_id_str != 'None':
                            return int(device_id_str)
        except Exception as e:
            print(f"Pink Bronsonのマイク設定読み込みエラー: {e}")
        return None

    def save_config(self):
        """Save configuration to file."""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

    def apply_theme(self):
        """Apply 90s industrial machine UI theme."""
        # ── Palette ──────────────────────────────────────────
        self.bg_color        = '#1C1C1C'   # outer body
        self.frame_bg        = '#242424'   # panel surface
        self.frame_border    = '#383838'   # panel edges
        self.fg_color        = '#AABF00'   # phosphor green (LCD text)
        self.fg_secondary    = '#607000'   # dim phosphor
        self.accent_blue     = '#AABF00'   # re-use phosphor for accent
        self.accent_cyan     = '#C8DC00'   # bright phosphor highlight
        self.accent_purple   = '#8A9F00'   # mid phosphor
        self.accent_green    = '#44BB00'   # LED green (running)
        self.accent_red      = '#BB2200'   # LED red (error/stop)
        self.entry_bg        = '#141800'   # LCD background
        self.entry_border    = '#383838'
        self.text_on_button  = '#C4C4C4'   # button label text

        style = ttk.Style()
        style.theme_use('clam')

        # Base
        style.configure('.',
                        background=self.bg_color,
                        foreground='#C0C0C0',
                        font=('Courier New', 9))

        # Label
        style.configure('TLabel',
                        background=self.bg_color,
                        foreground='#A0A0A0',
                        font=('Courier New', 9))

        # Button — raised bevel, monochrome
        style.configure('TButton',
                        background='#2A2A2A',
                        foreground=self.text_on_button,
                        borderwidth=2,
                        relief='raised',
                        padding=[10, 4],
                        font=('Courier New', 9, 'bold'))
        style.map('TButton',
                  background=[('active', '#3A3A3A'), ('pressed', '#1E1E1E')],
                  foreground=[('active', '#E0E0E0'), ('pressed', '#909090')])

        # LabelFrame — groove border, dark panel
        style.configure('TLabelframe',
                        background=self.frame_bg,
                        foreground='#909090',
                        borderwidth=2,
                        bordercolor=self.frame_border,
                        relief='groove')
        style.configure('TLabelframe.Label',
                        background=self.frame_bg,
                        foreground='#909090',
                        font=('Courier New', 8, 'bold'))

        # Notebook (Tab)
        style.configure('TNotebook',
                        background=self.bg_color,
                        borderwidth=1)
        style.configure('TNotebook.Tab',
                        background='#282828',
                        foreground='#707070',
                        padding=[12, 4],
                        font=('Courier New', 9))
        style.map('TNotebook.Tab',
                  background=[('selected', self.frame_bg)],
                  foreground=[('selected', '#C0C0C0')])

        # Frame
        style.configure('TFrame', background=self.bg_color)

        # Entry / Spinbox — LCD style
        style.configure('TEntry',
                        fieldbackground=self.entry_bg,
                        foreground=self.fg_color,
                        bordercolor=self.frame_border,
                        lightcolor=self.frame_border,
                        darkcolor=self.frame_border,
                        insertcolor=self.fg_color,
                        borderwidth=1,
                        font=('Courier New', 9))

        style.configure('TSpinbox',
                        fieldbackground=self.entry_bg,
                        foreground=self.fg_color,
                        bordercolor=self.frame_border,
                        arrowcolor='#707070',
                        borderwidth=1,
                        font=('Courier New', 9))

        # Progressbar — LED green fill on dark track
        style.configure('green.Horizontal.TProgressbar',
                        troughcolor='#1A1A1A',
                        background=self.accent_green,
                        bordercolor=self.frame_border,
                        lightcolor=self.accent_green,
                        darkcolor='#228800')

        # Separator
        style.configure('TSeparator', background=self.frame_border)

        # Radiobutton
        style.configure('TRadiobutton',
                        background=self.bg_color,
                        foreground='#909090',
                        font=('Courier New', 9))
        style.map('TRadiobutton',
                  background=[('active', self.bg_color)],
                  foreground=[('active', '#C0C0C0')])

        self.root.configure(bg=self.bg_color)

    def create_ui(self):
        """Create the main UI with tabs."""
        # Create notebook (tabbed interface)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=2, pady=2)

        # Tab 1: Main Control
        self.main_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.main_tab, text='Main Control')
        self.create_main_tab()

        # Tab 2: Analytics
        self.api_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.api_tab, text='📊 Analytics')
        self.create_api_tab()

        # Tab 3: OBS Display
        self.obs_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.obs_tab, text='OBS Display')
        self.create_obs_tab()

        # Tab 4: Archive Analyzer
        self.archive_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.archive_tab, text='📊 Archive')
        self.create_archive_tab()

    def create_main_tab(self):
        """Create the main control tab."""
        # ── Top bar: time + quit on the right ──────────────────
        top_bar = ttk.Frame(self.main_tab)
        top_bar.pack(fill='x', padx=10, pady=(4, 0))

        self.current_time_var = tk.StringVar(value="--:--:--")
        ttk.Label(top_bar, textvariable=self.current_time_var,
                  font=('Courier New', 11, 'bold'),
                  foreground=self.accent_cyan).pack(side='right', padx=(6, 0))
        ttk.Label(top_bar, text="SYS:",
                  font=('Courier New', 8)).pack(side='right')
        ttk.Button(top_bar, text="QUIT",
                   command=self.cleanup_on_exit).pack(side='right', padx=(0, 14))

        # --- Input Source Section (full width) ---
        self.input_frame = ttk.LabelFrame(
            self.main_tab, text="Input Source Control", padding=4)
        self.input_frame.pack(fill='x', padx=10, pady=(2, 0))

        # --- マイク入力 (Pink Bronsonの設定と共有) ---
        mic_ctrl_frame = ttk.Frame(self.input_frame)
        mic_ctrl_frame.pack(fill='x', expand=True)

        m_ctrl_frame = ttk.Frame(mic_ctrl_frame)
        m_ctrl_frame.pack(fill='x', pady=2)

        ttk.Label(
            m_ctrl_frame,
            text="Microphone (STT) Status:",
            font=('Courier New', 10, 'bold')).pack(side='left', padx=5)
        self.stt_status_var = tk.StringVar(value="Inactive")
        self.stt_status_label = ttk.Label(
            m_ctrl_frame, textvariable=self.stt_status_var,
            font=('Courier New', 12, 'bold'), foreground='#606060')
        self.stt_status_label.pack(side='left', padx=5)

        ttk.Separator(m_ctrl_frame, orient='vertical').pack(
            side='left', fill='y', padx=10, pady=2)

        ttk.Button(
            m_ctrl_frame,
            text="🎤 START Listening",
            command=lambda: self.start_process('stt')).pack(side='left', padx=5)
        ttk.Button(
            m_ctrl_frame,
            text="⏹ STOP Listening",
            command=lambda: self.stop_process('stt')).pack(side='left', padx=5)

        # STT Backend selector
        backend_frame = ttk.Frame(mic_ctrl_frame)
        backend_frame.pack(fill='x', pady=(4, 0), padx=5)
        ttk.Label(backend_frame, text="STT Engine:",
                  font=('Courier New', 8, 'bold')).pack(side='left')
        self.stt_backend_var = tk.StringVar(
            value=self.config.get('stt_backend', 'whisper'))

        def _gc_backend_change(*_):
            if not self.audio_processor.is_running:
                tag = "[Gemini]" if self.stt_backend_var.get() == "gemini" else "[Whisper]"
                self.stt_status_var.set(f"Inactive {tag}")

        self.stt_backend_var.trace_add("write", _gc_backend_change)

        ttk.Radiobutton(
            backend_frame, text="Local Whisper",
            variable=self.stt_backend_var, value='whisper').pack(side='left', padx=(8, 0))
        ttk.Radiobutton(
            backend_frame, text="✨ Gemini API",
            variable=self.stt_backend_var, value='gemini').pack(side='left', padx=(6, 0))

        _gc_backend_change()   # 初期表示

        # Volume Meter
        vol_frame = ttk.Frame(mic_ctrl_frame)
        vol_frame.pack(fill='x', pady=2, padx=5)
        ttk.Label(vol_frame, text="Level:", font=('Courier New', 8)).pack(side='left')

        style = ttk.Style()
        style.configure("green.Horizontal.TProgressbar", foreground='green', background='green')

        self.mic_vol_bar = ttk.Progressbar(
            vol_frame, orient='horizontal', mode='determinate', length=200,
            style="green.Horizontal.TProgressbar")
        self.mic_vol_bar.pack(side='left', fill='x', expand=True, padx=5)

        ttk.Label(
            mic_ctrl_frame,
            text="* マイクは Pink Bronson の設定と共有されます。",
            font=('Courier New', 8), foreground='#606060').pack(anchor='w', padx=5)

        # --- Shared Data Flow Info ---
        flow_frame = ttk.LabelFrame(
            self.input_frame,
            text="Data Flow Monitor",
            padding=3)
        flow_frame.pack(fill='x', pady=2)

        self.cleantext_file_var = tk.StringVar(
            value=os.path.join(
                self.project_root,
                'data',
                'cleantext.json'))

        # Output info
        output_info_frame = ttk.Frame(flow_frame)
        output_info_frame.pack(fill='x')
        ttk.Label(
            output_info_frame,
            text="Target File:",
            font=(
                'Courier New',
                9,
                'bold')).pack(
            side='left')
        ttk.Label(
            output_info_frame,
            textvariable=self.cleantext_file_var,
            foreground='#AABF00',
            font=(
                'Courier New',
                8)).pack(
            side='left',
            padx=5)

        self.cleantext_time_var = tk.StringVar(value="Updated: --:--:--")
        ttk.Label(
            output_info_frame,
            textvariable=self.cleantext_time_var,
            font=(
                'Courier New',
                8),
            foreground='#606060').pack(
            side='left',
            padx=10)

        self.cleantext_entries_var = tk.StringVar(value="Entries: 0")
        ttk.Label(
            output_info_frame,
            textvariable=self.cleantext_entries_var,
            font=(
                'Courier New',
                8),
            foreground='#606060').pack(
            side='left',
            padx=10)

        # Row 2: Recent Input Preview
        preview_frame = ttk.LabelFrame(
            self.main_tab, text="Recent Input (Real-time)", padding=3)
        preview_frame.pack(fill='x', padx=10, pady=(2, 2))
        self.cleantext_display = scrolledtext.ScrolledText(
            preview_frame, height=3, width=100, wrap='word',
            bg=self.entry_bg, fg=self.fg_color,
            insertbackground=self.accent_blue,
            selectbackground=self.accent_blue,
            selectforeground=self.text_on_button,
            borderwidth=1,
            relief='solid',
            highlightthickness=1,
            highlightbackground=self.entry_border,
            highlightcolor=self.accent_blue)
        self.cleantext_display.pack(fill='both', expand=True)

        # --- Bottom Section: Generators ---
        generators_frame = ttk.Frame(self.main_tab)
        generators_frame.pack(fill='both', expand=True, padx=10, pady=(2, 4))

        # Create three columns
        self.create_generator_panel(
            generators_frame, 'summarizer', 'Summarizer (要約)', 0)
        self.create_generator_panel(
            generators_frame,
            'title_gen',
            'Title Generator (タイトル)',
            1)
        self.create_generator_panel(
            generators_frame,
            'facilitator',
            'Facilitator (司会)',
            2)


    def create_api_tab(self):
        """Create the Analytics tab."""
        # Top Summary Section for Real-time Cost
        summary_frame = ttk.LabelFrame(
            self.api_tab,
            text="Real-time Cost Estimate",
            padding=15)
        summary_frame.pack(fill='x', padx=10, pady=(10, 0))

        cost_container = ttk.Frame(summary_frame)
        cost_container.pack(fill='x')

        self.today_cost_var = tk.StringVar(value="Today's Cost: $0.000000")
        ttk.Label(cost_container, textvariable=self.today_cost_var, font=('Courier New', 14, 'bold'), foreground=self.accent_red).pack(side='left', padx=20)

        self.total_cost_var = tk.StringVar(value="Total Cost: $0.000000")
        ttk.Label(cost_container, textvariable=self.total_cost_var, font=('Courier New', 12), foreground=self.fg_secondary).pack(side='left', padx=20)

        # Usage Statistics section
        usage_frame = ttk.LabelFrame(
            self.api_tab,
            text="API Usage Logs",
            padding=10)
        usage_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Usage display
        self.usage_text = scrolledtext.ScrolledText(
            usage_frame, height=20, width=80, wrap='word',
            bg=self.entry_bg, fg=self.fg_color,
            insertbackground=self.accent_blue,
            selectbackground=self.accent_blue,
            selectforeground=self.text_on_button,
            borderwidth=1,
            relief='solid',
            highlightthickness=1,
            highlightbackground=self.entry_border,
            highlightcolor=self.accent_blue)
        self.usage_text.pack(fill='both', expand=True, pady=5)

        # Refresh button
        btn_frame = ttk.Frame(usage_frame)
        btn_frame.pack(pady=5)
        ttk.Button(
            btn_frame,
            text="Refresh Usage Stats",
            command=self.refresh_usage_stats).pack(
            side='left',
            padx=5)
        ttk.Button(
            btn_frame,
            text="📊 Open Analytics (Graph)",
            command=self.open_analytics).pack(
            side='left',
            padx=5)

        # Initial load
        self.refresh_usage_stats()
        self.update_analytics_summary()

    def update_analytics_summary(self):
        """Parse usage_log.json and update the real-time cost labels every 5 seconds."""
        try:
            log_path = os.path.join(self.project_root, 'data', 'usage_log.json')
            if os.path.exists(log_path):
                with open(log_path, 'r', encoding='utf-8') as f:
                    logs = json.load(f)

                total_cost = 0.0
                today_cost = 0.0
                today_str = datetime.now().strftime("%Y-%m-%d")

                for entry in logs:
                    prompt_tokens = entry.get('prompt_tokens', 0)
                    candidate_tokens = entry.get('candidate_tokens', 0)
                    
                    # Gemini 2.0 Flash pricing estimate
                    # Prompt: ~$0.075 / 1M, Output: ~$0.30 / 1M
                    cost = (prompt_tokens * 0.075 + candidate_tokens * 0.3) / 1000000

                    total_cost += cost
                    if entry.get('timestamp', '').startswith(today_str):
                        today_cost += cost

                self.today_cost_var.set(f"Today's Cost: ${today_cost:.6f}")
                self.total_cost_var.set(f"Total Cost: ${total_cost:.6f}")
        except Exception as e:
            print(f"Update analytics error: {e}")

        # Re-schedule after 5000 ms (5 seconds)
        self.root.after(5000, self.update_analytics_summary)

    def refresh_usage_stats(self):
        """Refresh API usage statistics."""
        self.usage_text.delete('1.0', 'end')

        api_key = self.config.get('api_key', '')
        if not api_key:
            self.usage_text.insert(
                '1.0', "API Key not configured. Please set your API key first.")
            return

        try:
            genai.configure(api_key=api_key)

            # Get model info
            self.usage_text.insert('end', "=== Gemini API Information ===\n\n")
            self.usage_text.insert(
                'end', f"API Key: {'*' * (len(api_key) - 8) + api_key[-8:]}\n")
            self.usage_text.insert(
                'end', f"Last Updated: {
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            # List available models
            self.usage_text.insert('end', "=== Available Models ===\n")
            try:
                models = genai.list_models()
                for model in models:
                    if 'generateContent' in model.supported_generation_methods:
                        self.usage_text.insert('end', f"• {model.name}\n")
                        self.usage_text.insert(
                            'end', f"  Display Name: {
                                model.display_name}\n")
                        if hasattr(model, 'description'):
                            self.usage_text.insert(
                                'end', f"  Description: {
                                    model.description}\n")
                        self.usage_text.insert('end', "\n")
            except Exception as e:
                self.usage_text.insert(
                    'end', f"Could not list models: {e}\n\n")

            # Rate limits info
            self.usage_text.insert(
                'end', "=== Rate Limits (Gemini 2.0 Flash Free Tier) ===\n")
            self.usage_text.insert('end', "• Requests per minute (RPM): 15\n")
            self.usage_text.insert('end', "• Requests per day (RPD): 1,500\n")
            self.usage_text.insert(
                'end', "• Tokens per minute (TPM): 1,000,000\n\n")

            self.usage_text.insert(
                'end', "Note: Actual usage statistics are not available via API.\n")
            self.usage_text.insert(
                'end', "Please check https://aistudio.google.com/ for detailed usage.\n")

        except Exception as e:
            self.usage_text.insert(
                'end', f"Error fetching API information: {e}\n")
            self.usage_text.insert(
                'end', "\nPlease verify your API key is correct.")

        # === Load Usage Logs from File ===
        self.usage_text.insert('end', "\n" + "=" * 40 + "\n")
        self.usage_text.insert('end', "=== Usage Statistics (Estimated) ===\n")

        try:
            log_path = os.path.join(
                self.project_root, 'data', 'usage_log.json')
            if os.path.exists(log_path):
                with open(log_path, 'r', encoding='utf-8') as f:
                    logs = json.load(f)

                if not logs:
                    self.usage_text.insert(
                        'end', "No usage data logged yet.\n")
                    return

                total_tokens = 0
                today_tokens = 0
                today_str = datetime.now().strftime("%Y-%m-%d")

                # Calculate totals
                for entry in logs:
                    t = entry.get('total_tokens', 0)
                    total_tokens += t
                    if entry.get('timestamp', '').startswith(today_str):
                        today_tokens += t

                # Display basic stats
                self.usage_text.insert(
                    'end', f"Total Tokens Used (All time): {
                        total_tokens:,}\n")
                self.usage_text.insert(
                    'end', f"Total Tokens Used (Today):    {
                        today_tokens:,}\n\n")

                # Display recent entries
                self.usage_text.insert('end', "--- Recent Activity ---\n")
                for entry in logs[-10:]:
                    ts = entry.get('timestamp', '')[11:]  # Time only
                    model = entry.get('model', 'unknown')
                    prompt = entry.get('prompt_tokens', 0)
                    resp = entry.get('candidate_tokens', 0)
                    total = entry.get('total_tokens', 0)
                    self.usage_text.insert(
                        'end', f"[{ts}] {model}: {total} tokens (In:{prompt}/Out:{resp})\n")
            else:
                self.usage_text.insert(
                    'end', "No usage log file found (usage_log.json).\n")
        except Exception as e:
            self.usage_text.insert('end', f"Error loading usage logs: {e}\n")

    def open_analytics(self):
        """Generate and open analytics report."""
        success, msg = self.analytics_helper.generate_and_open_report()
        if not success:
            messagebox.showerror("Error", f"Failed to open analytics: {msg}")

    def create_generator_panel(self, parent, name, title, column):
        """Create a control panel for a generator script."""
        frame = ttk.LabelFrame(parent, text=title, padding=6)
        frame.grid(row=0, column=column, sticky='nsew', padx=4)
        parent.columnconfigure(column, weight=1)
        parent.rowconfigure(0, weight=1)

        # --- Header: Status & Controls ---
        header_frame = ttk.Frame(frame)
        header_frame.pack(fill='x', pady=(0, 3))

        # Start/Stop Buttons
        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side='right')
        ttk.Button(
            btn_frame,
            text="Start",
            width=6,
            command=lambda: self.start_process(name)).pack(
            side='left',
            padx=2)
        ttk.Button(
            btn_frame,
            text="Stop",
            width=6,
            command=lambda: self.stop_process(name)).pack(
            side='left',
            padx=2)

        # Status Label
        status_var = tk.StringVar(value="Stopped")
        setattr(self, f'{name}_status_var', status_var)
        status_label = ttk.Label(
            header_frame, textvariable=status_var, font=(
                'Courier New', 10, 'bold'), foreground='#BB2200')
        status_label.pack(side='left', padx=5)
        setattr(self, f'{name}_status_label', status_label)

        ttk.Separator(frame, orient='horizontal').pack(fill='x', pady=2)

        # --- Timestamps ---
        info_frame = ttk.Frame(frame)
        info_frame.pack(fill='x')
        fetch_time_var = tk.StringVar(value="Fetch: --:--:--")
        output_time_var = tk.StringVar(value="Output: --:--:--")
        setattr(self, f'{name}_fetch_time_var', fetch_time_var)
        setattr(self, f'{name}_output_time_var', output_time_var)

        ttk.Label(
            info_frame,
            textvariable=fetch_time_var,
            font=(
                'Courier New',
                8)).pack(
            side='left',
            padx=(
                0,
                 10))
        ttk.Label(
            info_frame,
            textvariable=output_time_var,
            font=(
                'Courier New',
                8)).pack(
            side='left')

        # --- Recent Logs (New 3 lines) ---
        log_frame = ttk.LabelFrame(frame, text="Process Logs", padding=2)
        log_frame.pack(fill='x', pady=2)
        log_list = tk.Listbox(
            log_frame, height=3, font=('Consolas', 8),
            bg=self.entry_bg, fg=self.fg_color,
            selectbackground=self.accent_blue,
            selectforeground=self.text_on_button,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=self.entry_border,
            highlightcolor=self.accent_blue)
        log_list.pack(fill='x', expand=True)
        setattr(self, f'{name}_log_list', log_list)

        # --- Settings Area ---
        settings_frame = ttk.LabelFrame(frame, text="Settings", padding=5)
        settings_frame.pack(fill='x', pady=5)

        # Interval & Lookback
        grid_frame = ttk.Frame(settings_frame)
        grid_frame.pack(fill='x')

        ttk.Label(grid_frame, text="Interval(s):").pack(side='left')
        interval_var = tk.IntVar(value=self.config.get(f'{name}_interval', 60))
        setattr(self, f'{name}_interval_var', interval_var)
        ttk.Spinbox(
            grid_frame,
            from_=5,
            to=300,
            textvariable=interval_var,
            width=5).pack(
            side='left',
            padx=5)

        ttk.Label(
            grid_frame,
            text="Lookback(s):").pack(
            side='left',
            padx=(
                10,
                0))
        default_lookback = 60 if name == 'title_gen' else (
            666 if name == 'summarizer' else 180)
        lookback_var = tk.IntVar(
            value=self.config.get(
                f'{name}_lookback',
                default_lookback))
        setattr(self, f'{name}_lookback_var', lookback_var)
        ttk.Spinbox(
            grid_frame,
            from_=10,
            to=3600,
            textvariable=lookback_var,
            width=5).pack(
            side='left',
            padx=5)

        # Prompt
        prompt_header_frame = ttk.Frame(settings_frame)
        prompt_header_frame.pack(fill='x', pady=(5, 0))
        ttk.Label(prompt_header_frame, text="Prompt:").pack(side='left')
        ttk.Button(
            prompt_header_frame,
            text="✏️ Edit",
            width=6,
            command=lambda: self.open_prompt_editor(name)).pack(
            side='right')

        prompt_text = scrolledtext.ScrolledText(
            settings_frame, height=3, width=20, wrap='word',
            bg=self.entry_bg, fg=self.fg_color,
            insertbackground=self.accent_blue,
            selectbackground=self.accent_blue,
            selectforeground=self.text_on_button,
            borderwidth=1,
            relief='solid',
            highlightthickness=1,
            highlightbackground=self.entry_border,
            highlightcolor=self.accent_blue)
        prompt_text.pack(fill='x', pady=2)
        prompt_text.insert('1.0', self.config.get(f'{name}_prompt', ''))
        setattr(self, f'{name}_prompt_text', prompt_text)

        if name == 'title_gen':
            fake_news_header_frame = ttk.Frame(settings_frame)
            fake_news_header_frame.pack(fill='x', pady=(5, 0))
            ttk.Label(fake_news_header_frame, text="無音時用プロンプト (Fake News Prompt):").pack(side='left')
            
            fake_news_prompt_text = scrolledtext.ScrolledText(
                settings_frame, height=4, width=20, wrap='word',
                bg=self.entry_bg, fg=self.fg_color,
                insertbackground=self.accent_blue,
                selectbackground=self.accent_blue,
                selectforeground=self.text_on_button,
                borderwidth=1,
                relief='solid',
                highlightthickness=1,
                highlightbackground=self.entry_border,
                highlightcolor=self.accent_blue)
            fake_news_prompt_text.pack(fill='x', pady=2)
            
            default_fake_news = (
                "発話がないため、架空の嘘ニュースを生成すること。\n"
                "・誰も傷つけない、毒にも薬にもならない内容にする。\n"
                "・動物や自然、日常の不思議をテーマに。\n"
                "・【FAKE NEWS】を頭につけること。"
            )
            fake_news_prompt_text.insert('1.0', self.config.get('title_gen_fake_news_prompt', default_fake_news))
            setattr(self, 'title_gen_fake_news_prompt_text', fake_news_prompt_text)

        ttk.Button(
            settings_frame,
            text="Save Settings",
            command=lambda: self.save_generator_config(name)).pack(
            pady=2)

        # --- Output Display ---
        ttk.Label(frame, text="Output:").pack(anchor='w', pady=(5, 0))
        output_text = scrolledtext.ScrolledText(
            frame, height=5, width=30, wrap='word', state='disabled',
            bg=self.frame_bg, fg=self.fg_color,
            insertbackground=self.accent_blue,
            selectbackground=self.accent_blue,
            selectforeground=self.text_on_button,
            borderwidth=1,
            relief='solid',
            highlightthickness=1,
            highlightbackground=self.entry_border,
            highlightcolor=self.accent_blue)
        output_text.pack(fill='both', expand=True, pady=2)
        setattr(self, f'{name}_output_text', output_text)


    def save_generator_config(self, name):
        """Save configuration for a specific generator."""
        if hasattr(self, f'{name}_interval_var'):
            self.config[f'{name}_interval'] = getattr(
                self, f'{name}_interval_var').get()
        if hasattr(self, f'{name}_lookback_var'):
            self.config[f'{name}_lookback'] = getattr(
                self, f'{name}_lookback_var').get()
        if hasattr(self, f'{name}_prompt_text'):
            self.config[f'{name}_prompt'] = getattr(
                self, f'{name}_prompt_text').get('1.0', 'end-1c')
        if name == 'title_gen' and hasattr(self, 'title_gen_fake_news_prompt_text'):
            self.config['title_gen_fake_news_prompt'] = getattr(
                self, 'title_gen_fake_news_prompt_text').get('1.0', 'end-1c')

        self.save_config()
        messagebox.showinfo("Success", f"{name} settings saved!")

    def start_process(self, name):
        """Start a process."""
        if self.processes[name] is not None:
            messagebox.showwarning("Warning", f"{name} is already running!")
            return

        try:
            if name == 'stt':
                # Pink Bronsonの設定からマイクIDを取得
                device_id = self.get_pink_bronson_mic_id()
                backend = getattr(self, 'stt_backend_var',
                                  tk.StringVar(value='whisper')).get()
                api_key = self.config.get('api_key', '') if backend == 'gemini' else ''
                if backend == 'gemini' and not api_key:
                    messagebox.showwarning(
                        'APIキー未設定',
                        'Gemini STT を使うには API Settings タブでAPIキーを設定してください。')
                    return
                self.audio_processor.stt_backend = backend
                self.audio_processor.gemini_api_key = api_key
                self.config['stt_backend'] = backend
                self.save_config()
                self.audio_processor.start(device_id=device_id)
                label = "Listening (Gemini)" if backend == 'gemini' else "Listening"
                self.stt_status_var.set(label)
                self.stt_status_label.config(foreground='#44BB00')
                return

            script_path = os.path.join(self.base_dir, f'{name}.py')
            python_exe = sys.executable
            creation_flags = 0
            if platform.system() == 'Windows':
                creation_flags = 0x08000000  # CREATE_NO_WINDOW
            process = subprocess.Popen(
                [python_exe, script_path],
                creationflags=creation_flags
            )

            self.processes[name] = process
            messagebox.showinfo("Success", f"{name} started!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start {name}: {e}")

    def stop_process(self, name):
        """Stop a process."""
        if name == 'stt':
            self.audio_processor.stop()
            tag = "[Gemini]" if self.stt_backend_var.get() == 'gemini' else "[Whisper]"
            self.stt_status_var.set(f"Inactive {tag}")
            self.stt_status_label.config(foreground='#606060')
            self.mic_vol_bar['value'] = 0
            return

        # Try stopping via process handle
        if self.processes[name] is not None:
            try:
                process = self.processes[name]
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                self.processes[name] = None
                messagebox.showinfo("Success", f"{name} stopped!")
                return
            except Exception as e:
                print(f"Error stopping {name} via handle: {e}")
                self.processes[name] = None

        # Fallback: Try stopping via PID file (for orphans or lost handles)
        try:
            status_path = os.path.join(
                self.project_root,
                'data',
                'status',
                f'{name}_status.json')
            if os.path.exists(status_path):
                with open(status_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                pid = data.get('pid')
                if pid:
                    if platform.system() == 'Windows':
                        subprocess.run(['taskkill',
                                        '/F',
                                        '/PID',
                                        str(pid)],
                                       stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL,
                                       check=False)
                    else:
                        subprocess.run(['kill',
                                        '-9',
                                        str(pid)],
                                       stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL,
                                       check=False)
                    messagebox.showinfo(
                        "Success", f"{name} stopped (force killed PID {pid})!")
                    return
        except Exception as e:
            print(f"Error stopping {name} via PID: {e}")

        # If we reach here, we assume it's stopped
        messagebox.showinfo("Info", f"{name} appears to be already stopped.")

    def update_clock(self):
        """Update current time display."""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.current_time_var.set(current_time)
        self.root.after(1000, self.update_clock)

    def update_volume_meter(self):
        """Fast update loop (50ms) for the microphone volume meter."""
        try:
            if hasattr(self, 'audio_processor') and self.audio_processor.is_running:
                # Add a bit of smoothing to the volume animation
                target_vol = self.audio_processor.current_volume * 100
                current_vol = self.mic_vol_bar['value']
                # Move 50% towards target for visual smoothing
                new_vol = current_vol + (target_vol - current_vol) * 0.5
                self.mic_vol_bar['value'] = new_vol
            elif hasattr(self, 'mic_vol_bar'):
                self.mic_vol_bar['value'] = 0
        except BaseException:
            pass
        self.root.after(50, self.update_volume_meter)

    def update_outputs(self):
        """Update output displays and cleantext preview."""
        # Update Copier Data Flow file information
        try:
            # Update cleantext file info (data/cleantext.json)
            cleantext_path = os.path.join(
                self.project_root, 'data', 'cleantext.json')
            if os.path.exists(cleantext_path):
                mtime = os.path.getmtime(cleantext_path)
                time_str = datetime.fromtimestamp(
                    mtime).strftime('%Y-%m-%d %H:%M:%S')
                self.cleantext_time_var.set(f"Last updated: {time_str}")

                # Count entries
                try:
                    with open(cleantext_path, 'r', encoding='utf-8-sig') as f:
                        data = json.load(f)
                        count = len(data) if isinstance(data, list) else 0
                        self.cleantext_entries_var.set(f"Entries: {count}")
                except BaseException:
                    self.cleantext_entries_var.set(
                        "Entries: Error reading file")
            else:
                self.cleantext_time_var.set("Last updated: File not found")
                self.cleantext_entries_var.set("Entries: 0")
        except Exception as e:
            # Silently fail for file info updates
            pass

        # Update recent input preview (merging cleantext.json and stt_text.json)
        try:
            cleantext_path = os.path.join(self.project_root, 'data', 'cleantext.json')
            stt_path = os.path.join(self.project_root, 'data', 'stt_text.json')
            
            all_data = []
            
            def load_json_safe(file_path):
                if not os.path.exists(file_path):
                    return []
                try:
                    with open(file_path, 'r', encoding='utf-8-sig') as f:
                        content = json.load(f)
                        return content if isinstance(content, list) else []
                except:
                    return []
                    
            all_data.extend(load_json_safe(cleantext_path))
            all_data.extend(load_json_safe(stt_path))
            
            if all_data:
                # Filter out bad entries and parse timestamps
                valid_items = []
                for item in all_data:
                    if isinstance(item, dict):
                        ts = item.get('timestamp')
                        text = item.get('rawText')
                        if ts and text:
                            try:
                                dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                                valid_items.append({'dt': dt, 'ts_str': dt.strftime('%H:%M:%S'), 'text': text})
                            except:
                                valid_items.append({'dt': datetime.min.replace(tzinfo=timezone.utc), 'ts_str': ts, 'text': text})
                
                # Sort descending to get the 3 most recent
                valid_items.sort(key=lambda x: x['dt'], reverse=True)
                recent = valid_items[:3]
                
                # Reverse again back to chronological order (oldest of the 3 first) for display
                recent.reverse()
                
                preview = ""
                for item in recent:
                    preview += f"[{item['ts_str']}] {item['text']}\n"
                    
                self.cleantext_display.delete('1.0', 'end')
                if preview:
                    self.cleantext_display.insert('1.0', preview.strip())
                else:
                    self.cleantext_display.insert('1.0', "No recent input data")
            else:
                self.cleantext_display.delete('1.0', 'end')
                self.cleantext_display.insert('1.0', "No input from mic or voice yet.")
                
        except Exception as e:
            self.cleantext_display.delete('1.0', 'end')
            self.cleantext_display.insert('1.0', f"Preview Error: {e}")

        # Check for system errors (cleaner.py)
        if os.path.exists(self.cleaner_error_file):
            try:
                with open(self.cleaner_error_file, 'r', encoding='utf-8') as f:
                    error_msg = f.read()
                if error_msg:
                    self.cleantext_display.insert(
                        '1.0', f"⚠️ SYSTEM ERROR:\n{error_msg}\n\n", 'error')
                    self.cleantext_display.tag_config(
                        'error', foreground='#BB2200', font=(
                            'Courier New', 10, 'bold'))
            except BaseException:
                pass

        # Update generator outputs and logs
        for name in ['summarizer', 'title_gen', 'facilitator']:

            # --- Output File Handling ---
            try:
                output_file_map = {
                    'summarizer': 'summary.txt',
                    'title_gen': 'title.txt',
                    'facilitator': 'facilitator.txt'
                }
                output_path = os.path.join(
                    self.project_root, 'output', output_file_map[name])

                output_text = getattr(self, f'{name}_output_text')
                output_time_var = getattr(self, f'{name}_output_time_var')

                # Check actual running state
                is_running = (
                    self.processes[name] is not None) and (
                    self.processes[name].poll() is None)

                if not is_running:
                    # Stopped State
                    output_text.config(state='normal')
                    output_text.delete('1.0', 'end')
                    output_text.insert('1.0', "=== STAND BY (STOPPED) ===")
                    output_text.config(state='disabled')
                    output_time_var.set("Output: --:--:--")
                else:
                    # Running State
                    if os.path.exists(output_path):
                        with open(output_path, 'r', encoding='utf-8') as f:
                            content = f.read()

                        output_text.config(state='normal')
                        output_text.delete('1.0', 'end')
                        output_text.insert('1.0', content)
                        output_text.config(state='disabled')

                        mtime = os.path.getmtime(output_path)
                        output_time = datetime.fromtimestamp(
                            mtime).strftime('%H:%M:%S')
                        output_time_var.set(f"Output: {output_time}")
            except BaseException:
                pass

            # --- Status & Logs Handling ---
            try:
                status_path = os.path.join(
                    self.project_root, 'data', 'status', f'{name}_status.json')
                status_var = getattr(self, f'{name}_status_var')
                fetch_var = getattr(self, f'{name}_fetch_time_var')
                log_list = getattr(self, f'{name}_log_list')

                if not is_running:
                    # Clear logs or show stopped
                    log_list.delete(0, 'end')
                    log_list.insert('end', "Process Stopped")
                    fetch_var.set("Fetch: --:--:--")
                else:
                    if os.path.exists(status_path):
                        with open(status_path, 'r', encoding='utf-8') as f:
                            status_data = json.load(f)

                        state = status_data.get('state', '')
                        fetch_time = status_data.get('fetch_time', '')
                        history = status_data.get('history', [])

                        # Update detailed status
                        if state:
                            status_var.set(f"Running ({state})")

                        # Update fetch time
                        if fetch_time:
                            fetch_var.set(f"Fetch: {fetch_time}")

                        # Update logs
                        log_list.delete(0, 'end')
                        for entry in history:
                            log_list.insert('end', entry)
            except BaseException:
                pass

        # Update OBS JS files (for local file access workaround)
        if hasattr(self, 'obs_helper'):
            self.obs_helper.update_js_files()

        # Schedule next update (only if window is still alive)
        try:
            self.root.after(2000, self.update_outputs)
        except Exception:
            pass

    def refresh_mics(self):
        """Refresh the list of microphones in the UI."""
        devices = AudioProcessor.get_input_devices()
        self.mic_combo['values'] = devices
        if devices:
            self.mic_device_var.set(devices[0])
        messagebox.showinfo("Success", "Microphone list refreshed.")

    def open_prompt_editor(self, name):
        """Open a popup window to edit the prompt."""
        editor = tk.Toplevel(self.root)
        editor.title(f"Edit Prompt: {name}")
        editor.geometry("600x500")
        editor.configure(bg=self.bg_color)

        # Get current text
        prompt_text_widget = getattr(self, f'{name}_prompt_text')
        current_text = prompt_text_widget.get('1.0', 'end-1c')

        # Text Area
        text_area = scrolledtext.ScrolledText(
            editor, wrap='word', font=('Courier New', 10),
            bg=self.entry_bg, fg=self.fg_color,
            insertbackground=self.accent_blue,
            selectbackground=self.accent_blue,
            selectforeground=self.text_on_button,
            borderwidth=1,
            relief='solid',
            highlightthickness=1,
            highlightbackground=self.entry_border,
            highlightcolor=self.accent_blue)
        text_area.pack(fill='both', expand=True, padx=10, pady=10)
        text_area.insert('1.0', current_text)

        # Buttons
        btn_frame = ttk.Frame(editor)
        btn_frame.pack(fill='x', padx=10, pady=10)

        def save_close():
            new_text = text_area.get('1.0', 'end-1c')
            prompt_text_widget.delete('1.0', 'end')
            prompt_text_widget.insert('1.0', new_text)
            self.save_generator_config(name)
            editor.destroy()

        ttk.Button(
            btn_frame,
            text="Save & Close",
            command=save_close).pack(
            side='right',
            padx=5)
        ttk.Button(
            btn_frame,
            text="Cancel",
            command=editor.destroy).pack(
            side='right',
            padx=5)

    def schedule_cleaner(self):
        """Run cleaner.py periodically."""
        try:
            script_path = os.path.join(self.base_dir, 'cleaner.py')
            python_exe = sys.executable

            creation_flags = 0
            if platform.system() == 'Windows':
                creation_flags = 0x08000000

            subprocess.Popen(
                [python_exe, script_path],
                creationflags=creation_flags
            )
        except Exception as e:
            print(f"Failed to run cleaner: {e}")

        # Run every hour (3600000 ms)
        self.root.after(3600000, self.schedule_cleaner)

    def create_appearance_tab(self):
        """Create appearance settings tab."""
        frame = ttk.LabelFrame(
            self.appearance_tab,
            text="Theme Settings",
            padding=20)
        frame.pack(padx=20, pady=20, fill='both', expand=True)

        ttk.Label(
            frame,
            text="Select Theme Mode:",
            font=(
                'Courier New',
                12)).pack(
            anchor='w',
            pady=10)

        self.theme_var = tk.StringVar(
            value=self.config.get(
                'theme_mode', 'light'))

        ttk.Radiobutton(
            frame,
            text="Light Mode",
            variable=self.theme_var,
            value='light').pack(
            anchor='w',
            padx=20)
        ttk.Radiobutton(
            frame,
            text="Dark Mode",
            variable=self.theme_var,
            value='dark').pack(
            anchor='w',
            padx=20)

        ttk.Button(
            frame,
            text="Apply & Save Theme",
            command=self.save_theme_config).pack(
            pady=20)

        ttk.Label(
            frame,
            text="※ Please restart the application for the best experience after changing themes.",
            foreground='#606060').pack()

    def save_theme_config(self):
        """Save theme settings and apply."""
        self.config['theme_mode'] = self.theme_var.get()
        self.save_config()
        self.apply_theme()
        messagebox.showinfo("Theme Saved", "Theme settings saved.")

    def update_status(self):
        """Update status indicators."""
        for name in self.processes.keys():
            if name == 'stt':
                # STT は AudioProcessor で管理。subprocess ループから除外
                continue
            status_var = getattr(self, f'{name}_status_var')

            # Identify the specific label widget to update color
            target_label = None
            if name == 'copier':
                if hasattr(self, 'copier_status_label'):
                    target_label = self.copier_status_label
            else:
                if hasattr(self, f'{name}_status_label'):
                    target_label = getattr(self, f'{name}_status_label')

            if self.processes[name] is not None:
                exit_code = self.processes[name].poll()
                if exit_code is None:
                    # Process is running
                    if "Stopped" in status_var.get():
                        status_var.set("Running")

                    if target_label:
                        target_label.configure(foreground=self.accent_green)
                else:
                    # Process has stopped
                    self.processes[name] = None
                    if exit_code == 0:
                        status_var.set("Stopped (Completed)")
                    else:
                        status_var.set(f"Stopped (Error: {exit_code})")
                    if target_label:
                        target_label.configure(foreground=self.accent_red)
            else:
                status_var.set("Stopped")
                if target_label:
                    target_label.configure(foreground=self.accent_red)

        # Schedule next update
        self.root.after(1000, self.update_status)

    def _update_label_color(self, widget, target_var, color):
        """Deprecated: colors are now handled directly in update_status."""
        pass
    # ========== OBS Display Tab Functions ==========

    def create_obs_tab(self):
        """Create the OBS Display configuration tab with sub-tabs for each output."""
        # Instructions
        info_frame = ttk.LabelFrame(
            self.obs_tab,
            text="📺 OBS Browser Source Setup",
            padding=10)
        info_frame.pack(fill='x', padx=10, pady=10)

        info_text = (
            "You can generate individual HTML files for each output file (Title, Summary, Facilitator).\n"
            "1. Edit CSS and JavaScript in each tab\n"
            "2. Click 'Generate HTML' to create the file\n"
            "3. Add output/obs_title.html etc. as a Browser Source in OBS")
        ttk.Label(info_frame, text=info_text, justify='left').pack(anchor='w')

        # Display Style
        style_frame = ttk.Frame(self.obs_tab)
        style_frame.pack(fill='x', padx=10, pady=(0, 5))
        ttk.Label(style_frame, text="Display Style:").pack(side='left')

        self.obs_style_var = tk.StringVar(
            value=self.config.get(
                'obs_style', 'standard'))
        style_combo = ttk.Combobox(
            style_frame,
            textvariable=self.obs_style_var,
            values=[
                'standard',
                'character'],
            state='readonly',
            width=15)
        style_combo.pack(side='left', padx=10)
        style_combo.bind('<<ComboboxSelected>>', self.on_style_change)

        ttk.Button(
            style_frame,
            text="Apply Style & Regenerate",
            command=self.apply_obs_style).pack(
            side='left',
            padx=10)
        ttk.Label(
            style_frame,
            text="* 'character' uses bloson.png",
            font=(
                'Courier New',
                8),
            foreground='#606060').pack(
            side='left',
            padx=5)

        # Create sub-notebook for each output type
        self.obs_notebook = ttk.Notebook(self.obs_tab)
        self.obs_notebook.pack(fill='both', expand=True, padx=10, pady=5)

        # Create tabs for each output type
        self.create_obs_output_tab('summary', '📝 Summary')
        self.create_obs_output_tab('title', '🏷️ Title')
        self.create_obs_output_tab('facilitator', '💡 Facilitator')

    def create_obs_output_tab(self, output_type, tab_label):
        """Create a tab for a specific output type with CSS/JS editors."""
        # Create tab frame
        tab_frame = ttk.Frame(self.obs_notebook)
        self.obs_notebook.add(tab_frame, text=tab_label)

        # File path display
        path_frame = ttk.Frame(tab_frame)
        path_frame.pack(fill='x', padx=10, pady=5)
        ttk.Label(
            path_frame,
            text="Output File:",
            font=(
                'Courier New',
                9,
                'bold')).pack(
            side='left',
            padx=5)
        html_path = self.obs_helper.get_html_path(output_type)
        ttk.Label(
            path_frame,
            text=html_path,
            foreground='#AABF00').pack(
            side='left')

        # Main editor area
        editor_frame = ttk.Frame(tab_frame)
        editor_frame.pack(fill='both', expand=True, padx=10, pady=5)

        # Left side: CSS Editor
        css_frame = ttk.LabelFrame(
            editor_frame, text="🎨 CSS Styles", padding=10)
        css_frame.pack(side='left', fill='both', expand=True, padx=(0, 5))

        css_editor = scrolledtext.ScrolledText(
            css_frame, height=20, wrap='none', font=(
                'Consolas', 10))
        css_editor.pack(fill='both', expand=True)
        setattr(self, f'obs_{output_type}_css_editor', css_editor)

        # Right side: JavaScript Editor
        js_frame = ttk.LabelFrame(
            editor_frame, text="⚡ JavaScript", padding=10)
        js_frame.pack(side='left', fill='both', expand=True, padx=(5, 0))

        js_editor = scrolledtext.ScrolledText(
            js_frame, height=20, wrap='none', font=(
                'Consolas', 10))
        js_editor.pack(fill='both', expand=True)
        setattr(self, f'obs_{output_type}_js_editor', js_editor)

        # Load settings or use defaults
        saved_css, saved_js = self.obs_helper.load_settings(output_type)
        if saved_css:
            css_editor.insert('1.0', saved_css)
        else:
            css_editor.insert(
                '1.0', self.obs_helper.get_default_css(output_type))

        if saved_js:
            js_editor.insert('1.0', saved_js)
        else:
            js_editor.insert(
                '1.0', self.obs_helper.get_default_js(output_type))

        # Bottom buttons
        button_frame = ttk.Frame(tab_frame)
        button_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(
            button_frame,
            text="🔄 Generate HTML",
            command=lambda: self.generate_obs_output_html(output_type)).pack(
            side='left',
            padx=5)

        ttk.Button(
            button_frame,
            text="👁️ Preview in Browser",
            command=lambda: self.preview_obs_output_html(output_type)).pack(
            side='left',
            padx=5)

        ttk.Button(
            button_frame,
            text="💾 Save CSS/JS Settings",
            command=lambda: self.save_obs_output_settings(output_type)).pack(
            side='left',
            padx=5)

        ttk.Button(
            button_frame,
            text="🔙 Load Default",
            command=lambda: self.load_default_obs_output_styles(output_type)).pack(
            side='left',
            padx=5)

    def generate_obs_output_html(self, output_type):
        """Generate HTML for a specific output type."""
        try:
            css_editor = getattr(self, f'obs_{output_type}_css_editor')
            js_editor = getattr(self, f'obs_{output_type}_js_editor')

            custom_css = css_editor.get('1.0', 'end-1c')
            custom_js = js_editor.get('1.0', 'end-1c')

            success, result = self.obs_helper.generate_html(
                output_type, custom_css, custom_js)

            if success:
                messagebox.showinfo("Success",
                                    f"OBS HTML generated successfully!\n\n"
                                    f"File: {result}\n\n"
                                    f"Add this file as a Browser Source in OBS:\n"
                                    f"1. Add Source → Browser\n"
                                    f"2. Local File: {result}\n"
                                    f"3. Width: 800, Height: 200 (adjust as needed)")
            else:
                messagebox.showerror(
                    "Error", f"Failed to generate OBS HTML: {result}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate OBS HTML: {e}")

    def preview_obs_output_html(self, output_type):
        """Preview HTML for a specific output type."""
        if self.obs_helper.preview_html(output_type):
            pass  # Successfully opened
        else:
            messagebox.showwarning(
                "Warning", f"OBS HTML for {output_type} not found. Please generate it first.")

    def save_obs_output_settings(self, output_type):
        """Save CSS/JS settings for a specific output type."""
        try:
            css_editor = getattr(self, f'obs_{output_type}_css_editor')
            js_editor = getattr(self, f'obs_{output_type}_js_editor')

            css_content = css_editor.get('1.0', 'end-1c')
            js_content = js_editor.get('1.0', 'end-1c')

            self.obs_helper.save_settings(output_type, css_content, js_content)
            messagebox.showinfo(
                "Success", f"{output_type} CSS/JS settings saved!")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    def load_default_obs_output_styles(self, output_type):
        """Reset to default CSS and JS for a specific output type."""
        try:
            css_editor = getattr(self, f'obs_{output_type}_css_editor')
            js_editor = getattr(self, f'obs_{output_type}_js_editor')

            css_editor.delete('1.0', 'end')
            css_editor.insert(
                '1.0', self.obs_helper.get_default_css(output_type))

            js_editor.delete('1.0', 'end')
            js_editor.insert(
                '1.0', self.obs_helper.get_default_js(output_type))

            messagebox.showinfo("Success", "Default styles loaded!")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load defaults: {e}")

    def on_style_change(self, event=None):
        """Handle style change."""
        pass

    def apply_obs_style(self):
        """Apply selected style and regenerate HTML."""
        style = self.obs_style_var.get()
        self.config['obs_style'] = style
        self.save_config()
        self.recreate_obs_html()
        messagebox.showinfo(
            "Style Applied",
            f"Switched to {style} mode.\nHTML files regenerated.")

    def recreate_obs_html(self):
        """Regenerate all OBS HTML files with current style."""
        for out_type in ['summary', 'title', 'facilitator']:
            # Load CSS/JS
            css, js = self.obs_helper.load_settings(out_type)
            style = self.config.get('obs_style', 'standard')

            if not css:
                if style == 'character':
                    css = self.obs_helper.get_character_css(out_type)
                else:
                    css = self.obs_helper.get_default_css(out_type)

            # Smart Switch: If switching to character mode but CSS looks like
            # standard, switch it
            if style == 'character' and 'box-shadow: 0 5px 20px' in (
                    css or ''):
                css = self.obs_helper.get_character_css(out_type)

            # Smart Switch: If switching to standard but CSS looks like
            # character, switch it
            if style == 'standard' and 'bubble-container' in (css or ''):
                css = self.obs_helper.get_default_css(out_type)

            if not js:
                js = self.obs_helper.get_default_js(out_type)

            self.obs_helper.generate_html(out_type, css, js, style_mode=style)


    # ── Archive Analyzer Tab ──────────────────────────────────────────────────
    def create_archive_tab(self):
        """Create the archive analyzer tab."""
        self._archive_sessions: dict = {}
        self._archive_analysis_running = False

        tab = self.archive_tab
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=2)
        tab.rowconfigure(0, weight=1)

        # ── Left panel: session list ──────────────────────────────────────────
        left = tk.Frame(tab, bg=self.bg_color)
        left.grid(row=0, column=0, sticky='nsew', padx=(8, 4), pady=8)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(2, weight=1)

        tk.Label(left, text='📁 配信セッション', bg=self.bg_color,
                 fg=self.fg_color, font=('Courier New', 11, 'bold')).grid(
            row=0, column=0, sticky='w', pady=(0, 4))

        refresh_btn = tk.Button(
            left, text='🔄 更新', bg=self.accent_blue, fg=self.text_on_button,
            relief='flat', padx=8, command=self._refresh_archive_sessions)
        refresh_btn.grid(row=0, column=1, sticky='e', pady=(0, 4))
        left.columnconfigure(1, weight=0)

        # Session listbox
        list_frame = tk.Frame(left, bg=self.entry_border)
        list_frame.grid(row=2, column=0, columnspan=2, sticky='nsew')
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.archive_listbox = tk.Listbox(
            list_frame, bg=self.entry_bg, fg=self.fg_color,
            selectbackground=self.accent_blue, selectforeground='#ffffff',
            relief='flat', borderwidth=0, font=('Consolas', 10),
            activestyle='none')
        self.archive_listbox.grid(row=0, column=0, sticky='nsew')
        sb = tk.Scrollbar(list_frame, orient='vertical',
                          command=self.archive_listbox.yview)
        sb.grid(row=0, column=1, sticky='ns')
        self.archive_listbox.config(yscrollcommand=sb.set)
        self.archive_listbox.bind('<<ListboxSelect>>', self._on_session_select)

        # Checkboxes for log type
        chk_frame = tk.Frame(left, bg=self.bg_color)
        chk_frame.grid(row=3, column=0, columnspan=2, sticky='w', pady=(6, 0))
        self._use_stt  = tk.BooleanVar(value=True)
        self._use_chat = tk.BooleanVar(value=True)
        tk.Checkbutton(chk_frame, text='STTログを使用', variable=self._use_stt,
                       bg=self.bg_color, fg=self.fg_color,
                       selectcolor=self.entry_bg,
                       activebackground=self.bg_color).pack(side='left')
        tk.Checkbutton(chk_frame, text='チャットログを使用',
                       variable=self._use_chat,
                       bg=self.bg_color, fg=self.fg_color,
                       selectcolor=self.entry_bg,
                       activebackground=self.bg_color).pack(side='left')

        # Log preview
        tk.Label(left, text='📄 ログプレビュー', bg=self.bg_color,
                 fg=self.fg_color, font=('Courier New', 10, 'bold')).grid(
            row=4, column=0, columnspan=2, sticky='w', pady=(10, 2))

        left.rowconfigure(5, weight=1)
        preview_frame = tk.Frame(left, bg=self.entry_border)
        preview_frame.grid(row=5, column=0, columnspan=2, sticky='nsew')
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)

        self.archive_preview = tk.Text(
            preview_frame, bg=self.entry_bg, fg=self.fg_color,
            relief='flat', borderwidth=0, font=('Consolas', 9),
            state='disabled', wrap='word')
        self.archive_preview.grid(row=0, column=0, sticky='nsew')
        psb = tk.Scrollbar(preview_frame, orient='vertical',
                           command=self.archive_preview.yview)
        psb.grid(row=0, column=1, sticky='ns')
        self.archive_preview.config(yscrollcommand=psb.set)

        # ── Right panel: prompt + result ─────────────────────────────────────
        right = tk.Frame(tab, bg=self.bg_color)
        right.grid(row=0, column=1, sticky='nsew', padx=(4, 8), pady=8)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        right.rowconfigure(4, weight=2)

        tk.Label(right, text='✏️ 解析プロンプト', bg=self.bg_color,
                 fg=self.fg_color, font=('Courier New', 11, 'bold')).grid(
            row=0, column=0, sticky='w', pady=(0, 2))

        prompt_frame = tk.Frame(right, bg=self.entry_border)
        prompt_frame.grid(row=1, column=0, sticky='nsew', pady=(0, 6))
        prompt_frame.columnconfigure(0, weight=1)
        prompt_frame.rowconfigure(0, weight=1)

        self.archive_prompt_text = tk.Text(
            prompt_frame, bg=self.entry_bg, fg=self.fg_color,
            relief='flat', borderwidth=0, font=('Courier New', 10),
            wrap='word', height=10)
        self.archive_prompt_text.grid(row=0, column=0, sticky='nsew')
        psb2 = tk.Scrollbar(prompt_frame, orient='vertical',
                             command=self.archive_prompt_text.yview)
        psb2.grid(row=0, column=1, sticky='ns')
        self.archive_prompt_text.config(yscrollcommand=psb2.set)
        self.archive_prompt_text.insert('1.0', DEFAULT_PROMPT)

        # Button row
        btn_frame = tk.Frame(right, bg=self.bg_color)
        btn_frame.grid(row=2, column=0, sticky='ew', pady=(0, 6))

        self.archive_run_btn = tk.Button(
            btn_frame, text='🔍 解析実行',
            bg=self.accent_green, fg=self.text_on_button,
            relief='flat', padx=14, pady=4, font=('Courier New', 11, 'bold'),
            command=self._run_archive_analysis)
        self.archive_run_btn.pack(side='left')

        self.archive_reset_btn = tk.Button(
            btn_frame, text='↩ プロンプトをリセット',
            bg=self.frame_bg, fg=self.fg_color,
            relief='flat', padx=10, pady=4,
            command=self._reset_archive_prompt)
        self.archive_reset_btn.pack(side='left', padx=(8, 0))

        self.archive_save_btn = tk.Button(
            btn_frame, text='💾 結果を保存',
            bg=self.accent_cyan, fg=self.text_on_button,
            relief='flat', padx=10, pady=4,
            command=self._save_archive_result)
        self.archive_save_btn.pack(side='right')

        self.archive_status_label = tk.Label(
            right, text='', bg=self.bg_color, fg=self.accent_cyan,
            font=('Courier New', 9))
        self.archive_status_label.grid(row=3, column=0, sticky='w', pady=(0, 2))

        # Result area
        tk.Label(right, text='📊 解析結果', bg=self.bg_color,
                 fg=self.fg_color, font=('Courier New', 11, 'bold')).grid(
            row=3, column=0, sticky='w', pady=(0, 2))

        result_frame = tk.Frame(right, bg=self.entry_border)
        result_frame.grid(row=4, column=0, sticky='nsew')
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)

        self.archive_result_text = tk.Text(
            result_frame, bg=self.entry_bg, fg=self.fg_color,
            relief='flat', borderwidth=0, font=('Courier New', 10),
            state='disabled', wrap='word')
        self.archive_result_text.grid(row=0, column=0, sticky='nsew')
        rsb = tk.Scrollbar(result_frame, orient='vertical',
                           command=self.archive_result_text.yview)
        rsb.grid(row=0, column=1, sticky='ns')
        self.archive_result_text.config(yscrollcommand=rsb.set)

        # Initial load
        self._refresh_archive_sessions()

    def _refresh_archive_sessions(self):
        self._archive_sessions = list_sessions()
        self.archive_listbox.delete(0, 'end')
        for sid in self._archive_sessions:
            label = session_label(sid)
            types = list(self._archive_sessions[sid].keys())
            badge = ''.join(['S' if 'stt' in types else '', 'C' if 'chat' in types else ''])
            self.archive_listbox.insert('end', f'[{badge}] {label}')
        if not self._archive_sessions:
            self.archive_listbox.insert('end', '（アーカイブなし）')

    def _on_session_select(self, event=None):
        sel = self.archive_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        sids = list(self._archive_sessions.keys())
        if idx >= len(sids):
            return
        sid = sids[idx]
        files = self._archive_sessions[sid]

        preview_lines = []
        for log_type in ('stt', 'chat'):
            if log_type in files:
                content = read_file(files[log_type])
                lines = content.splitlines()[:30]
                header = '=== STT ===' if log_type == 'stt' else '=== Chat ==='
                preview_lines.append(header)
                preview_lines.extend(lines)
                if len(content.splitlines()) > 30:
                    preview_lines.append('...')
                preview_lines.append('')

        self.archive_preview.config(state='normal')
        self.archive_preview.delete('1.0', 'end')
        self.archive_preview.insert('1.0', '\n'.join(preview_lines))
        self.archive_preview.config(state='disabled')

    def _run_archive_analysis(self):
        if self._archive_analysis_running:
            return

        sel = self.archive_listbox.curselection()
        if not sel:
            messagebox.showwarning('選択なし', 'セッションを選択してください。')
            return

        idx = sel[0]
        sids = list(self._archive_sessions.keys())
        if idx >= len(sids):
            return
        sid = sids[idx]
        files = self._archive_sessions[sid]

        api_key = self.config.get('api_key', '').strip()
        if not api_key:
            messagebox.showerror('APIキー未設定', 'API SettingsタブでAPIキーを設定してください。')
            return

        stt_content  = read_file(files['stt'])  if (self._use_stt.get()  and 'stt'  in files) else ''
        chat_content = read_file(files['chat']) if (self._use_chat.get() and 'chat' in files) else ''
        custom_prompt = self.archive_prompt_text.get('1.0', 'end').strip()

        self._archive_analysis_running = True
        self.archive_run_btn.config(state='disabled', text='⏳ 解析中…')
        self.archive_status_label.config(text='Geminiに送信中…')

        self.archive_result_text.config(state='normal')
        self.archive_result_text.delete('1.0', 'end')
        self.archive_result_text.config(state='disabled')

        def _worker():
            try:
                result = analyze(stt_content, chat_content, api_key, custom_prompt)
            except Exception as e:
                result = f'❌ エラー: {e}'
            self.root.after(0, lambda: self._on_analysis_done(result))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_analysis_done(self, result: str):
        self._archive_analysis_running = False
        self.archive_run_btn.config(state='normal', text='🔍 解析実行')
        self.archive_status_label.config(text='✅ 解析完了')

        self.archive_result_text.config(state='normal')
        self.archive_result_text.delete('1.0', 'end')
        self.archive_result_text.insert('1.0', result)
        self.archive_result_text.config(state='disabled')

    def _reset_archive_prompt(self):
        self.archive_prompt_text.delete('1.0', 'end')
        self.archive_prompt_text.insert('1.0', DEFAULT_PROMPT)

    def _save_archive_result(self):
        content = self.archive_result_text.get('1.0', 'end').strip()
        if not content:
            messagebox.showinfo('保存', '保存する内容がありません。')
            return
        path = filedialog.asksaveasfilename(
            defaultextension='.txt',
            filetypes=[('テキストファイル', '*.txt'), ('すべてのファイル', '*.*')],
            initialfile=f'archive_analysis_{datetime.now().strftime("%Y%m%d_%H%M")}.txt')
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            messagebox.showinfo('保存完了', f'保存しました:\n{path}')
        except Exception as e:
            messagebox.showerror('保存エラー', str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = AquareadControlPanel(root)
    root.mainloop()
