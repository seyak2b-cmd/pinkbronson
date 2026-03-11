╔══════════════════════════════════════════════════════════════════════╗
║   PINK BRONSON 1.0  —  使い方ガイド                                 ║
╚══════════════════════════════════════════════════════════════════════╝

Twitch配信者向けのプロデューサーデスク。
マイク音声をリアルタイムでSTT → 翻訳 → Web表示する総合ツール。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
■ 初回セットアップ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. config.json を編集して認証情報を入力する

   {
     "api_keys": {
       "twitch_token":         "oauth:xxxxxxxx",   ← Twitchのアクセストークン
       "twitch_channel":       "あなたのチャンネル名",
       "twitch_client_id":     "xxxxxxxx",
       "twitch_client_secret": "xxxxxxxx",
       "gemini_key":           "AIzaSy...",        ← Google AI StudioのAPIキー
       "firebase_url":         "https://xxx.firebasedatabase.app",
       "firebase_api_key":     "AIzaSy..."
     },
     "firebase_auth": {
       "api_key":   "AIzaSy...",    ← firebase_api_keyと同じ値でOK
       "email":     "xxx@xxx.com",  ← FirebaseのEmail認証ユーザー
       "password":  "xxxxx"
     },
     "python_paths": {
       "blue_rayban": "C:\\Users\\あなた\\AppData\\Local\\Python\\bin\\python.exe"
                       ← Blue_Rayban起動に使うPython。不明なら削除するとsys.executableを使う
     }
   }

2. Blue_Rayban/twitchtoken.txt を編集する (任意、config.jsonより優先)

   TWITCH_ACCESS_TOKEN=oauth:xxxxxxxx
   TWITCH_CHANNEL=あなたのチャンネル名
   FIREBASE_DATABASE_URL=https://xxx.firebasedatabase.app
   AI_API_KEY=AIzaSy...
   FIREBASE_API_KEY=AIzaSy...
   FIREBASE_AUTH_EMAIL=xxx@xxx.com
   FIREBASE_AUTH_PASSWORD=xxxxx

   ※ config.json だけ設定すれば twitchtoken.txt は空でも動作する。
   ※ twitchtoken.txt に値があればそちらが優先される。

3. Golden_Chain の初回セットアップ (初回のみ)

   Golden_Chain/pinkblonsonbeta/setup_beta.bat を実行する
   → venv 作成 + 依存ライブラリインストールが自動で行われる

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
■ 起動方法
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  python pink_bronson.py

メインハブのウィンドウが開く。
各ツールはそこから起動ボタンで立ち上げる。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
■ 各ツールの役割と操作
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────────────────────────────────────────────────┐
│  PINK BRONSON (メインハブ)                               │
│  pink_bronson.py                                         │
├─────────────────────────────────────────────────────────┤
│  ・マイクを選択して REC ボタンで録音 + STT 開始          │
│  ・発話テキストがリアルタイムで表示される                │
│  ・各ツールの起動/停止ボタンがある                       │
│  ・⚙ ボタン: テーマ・マイク・STTなどの設定              │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  BLUE_RAY-BAN (翻訳 + Firebase中継)                     │
│  Blue_Rayban/mainTST.py (main_ui.py 経由で起動)         │
├─────────────────────────────────────────────────────────┤
│  ・START: Twitch IRC への接続 + 各ウォッチャー起動       │
│  ・STOP: 切断                                            │
│  ・MOBILE: スマホ用ページ (mobile.html) をブラウザで開く │
│  ・CONFIG: Webビューア設定パネルを開閉                   │
│    - TTS VOICE / TTS LANG / TRANS LANG / UI COLOR       │
│    - PUSH TO FIREBASE で seya-chat-trans.web.app に反映 │
│  ・STT最新発話パネル: 直近のマイク発話が JA/EN で表示   │
│                                                          │
│  内部で動いていること:                                   │
│  ・STT発話 → 英訳 → Firebase /stt_en, /stt_history      │
│  ・STT発話 → Gemini TTS → Firebase → Webで音声再生      │
│  ・Golden_Chain出力 → Firebase /golden_chain/...         │
│  ・mobile.html投稿 → 翻訳 → Firebase + Twitchチャット   │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  EMERALD_ROLEX (Twitchチャット取得)                      │
│  Emerald_Rolex/emerald_rolex.py (main_ui.py 経由で起動) │
├─────────────────────────────────────────────────────────┤
│  ・START: Twitch IRC 接続 + Firebase 送信開始            │
│  ・STOP: 切断                                            │
│  ・VOICEVOX: VOICEVOX設定パネルを開閉                    │
│    - ON/OFF, サーバーURL, 話者ID, 音量                   │
│    - LIST: VOICEVOXに接続して話者一覧を取得              │
│    - TEST: テスト発声                                    │
│    - SAVE: config.json に保存                            │
│  ・コントロールパネルにライブチャットが最新6件表示        │
│                                                          │
│  内部で動いていること:                                   │
│  ・Twitch IRC (justinfan匿名) で全チャットを受信         │
│  ・JA/EN 翻訳 → Firebase /chats (Webビューアに表示)     │
│  ・VOICEVOX が有効なら日本語テキストを読み上げ           │
│  ・チャットを JSONL でアーカイブ (data/archive/)         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  GOLDEN_CHAIN (会話要約)                                 │
│  Golden_Chain/pinkblonsonbeta/src/main_ui.py             │
├─────────────────────────────────────────────────────────┤
│  ・START: STT テキストの監視 + 要約生成を開始            │
│  ・Gemini で一定間隔ごとに要約/タイトル/ファシリ提案を生成│
│  ・生成結果は output/ に txt で保存                      │
│  ・Blue_Rayban の GoldenChainWatcher が検知して Firebase │
│    /golden_chain/ に送信 → Webビューアに表示            │
└─────────────────────────────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
■ 配信中の標準的な使い方
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1. pink_bronson.py を起動
  2. Emerald_Rolex を START
     → Twitchチャットが Firebase に流れ始める
  3. Blue_Rayban を START
     → STT監視・GoldenChain監視・ViewerQueue監視が起動
  4. pink_bronson.py でマイクを選択して REC
     → STT開始。発話がリアルタイムで翻訳・送信される
  5. Golden_Chain を START (任意)
     → 会話の要約・タイトルを自動生成

  ブラウザで https://seya-chat-trans.web.app/ を開くと
  チャット翻訳・STT・Golden_Chain出力がリアルタイムで確認できる。

  スマホで見たい場合は Blue_Rayban の MOBILE ボタンで
  mobile.html をブラウザで開く。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
■ VOICEVOX を使う場合
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1. voicevox/ フォルダ内の VOICEVOX エンジンを起動しておく
     (デフォルト: http://localhost:50021)
  2. Emerald_Rolex の VOICEVOX パネルで設定
     - TTS: ON
     - SERVER: http://localhost:50021
     - SPEAKER: 話者IDを入力 (LIST ボタンで確認可能)
     - SAVE で保存

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
■ Web TTS (Gemini音声) を使う場合
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Blue_Rayban の CONFIG パネルで設定:
    - WEB AUDIO: ON
    - TTS VOICE: Kore / Aoede など好みの声を選択
    - TTS LANG: 再生する言語 (ja=日本語 / en=英語)
    - PUSH TO FIREBASE で適用

  STT でマイクに話すたびに Gemini が音声合成して
  seya-chat-trans.web.app のブラウザタブで再生される。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
■ システム監視
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  monitor.html をブラウザで開くと、全モジュールのログが
  Firebase /system_logs からリアルタイムで確認できる。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
■ OBS での使い方 (現在の構成)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  チャット表示は seya-chat-trans.web.app をブラウザソースとして使用。
  OBS用ローカルHTMLは現在削除済み (再作成予定)。

  ブラウザソース設定:
    URL: https://seya-chat-trans.web.app/
    幅: 任意  高さ: 任意

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
■ config.json — 主要設定リファレンス
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  cross_tool.obs_ws_enabled    (true/false)
    Emerald_Rolex の WebSocket サーバー (ws://localhost:8765) の起動制御。
    OBS用ローカルHTMLを使う場合は true にする。現在は false。

  cross_tool.golden_chain_firebase    (true/false)
    Golden_Chain の出力を Firebase に送信するかどうか。
    false にすると /golden_chain/ への書き込みを停止する。

  emerald_rolex.voicevox_enabled      (true/false)
    起動時の VOICEVOX 初期状態。UIからも変更可能。

  emerald_rolex.notify_enabled        (true/false)
    チャット着信音のON/OFF。

  emerald_rolex.notify_sound          (ファイルパス)
    着信音のWAVファイルパス。空にするとWindowsデフォルト音。

  python_paths.blue_rayban            (パス文字列)
    Blue_Rayban 起動に使う python.exe の絶対パス。
    空または存在しない場合は sys.executable (メインと同じPython) を使用。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
■ よくあるトラブル
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q: Blue_Rayban が起動しない
A: config.json の python_paths.blue_rayban を確認。
   不明な場合はその行ごと削除すると sys.executable で起動する。

Q: Twitchチャットが Firebase に届かない
A: Emerald_Rolex の START を確認。config.json の
   twitch_token / twitch_channel が正しいか確認。

Q: STT が動かない
A: pink_bronson.py でマイクが正しく選択されているか確認。
   faster-whisper がインストールされているか確認。

Q: Gemini 翻訳が動かない
A: config.json の gemini_key (または twitchtoken.txt の AI_API_KEY)
   が正しいか確認。

Q: Golden_Chain が起動しない
A: setup_beta.bat を先に実行して venv を作成する。

Q: VOICEVOX から音が出ない
A: voicevox/ のエンジンが起動しているか確認。
   Emerald_Rolex の VOICEVOX パネルで TTS: ON になっているか確認。
   TEST ボタンで接続確認できる。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
■ ファイル構成の詳細は stracture.txt を参照
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
