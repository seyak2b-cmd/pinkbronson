# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════╗
║  system_logger.py  –  PINK BRONSON 統合ログ共通モジュール    ║
║  Usage:                                                      ║
║    from system_logger import send_system_log                 ║
║    send_system_log("MyModule", "処理が完了しました")          ║
║                                                              ║
║  Firebase /system_logs へ非同期 POST する。                  ║
║  firebase_url 未指定時は config.json の api_keys.firebase_url ║
║  を自動参照。明示的に渡すことも可能（mainTST.py など）。      ║
╚══════════════════════════════════════════════════════════════╝
"""
import os
import json
import time
import threading
import requests

# Pink Bronson1.0/ ルートを基準にする
_BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
_CONFIG_PATH = os.path.join(_BASE_DIR, "config.json")


def _get_firebase_url() -> str:
    """config.json から firebase_url を読み出す。"""
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg.get("api_keys", {}).get("firebase_url", "")
    except Exception:
        return ""


def send_system_log(module: str, message: str, firebase_url: str = "") -> None:
    """
    Firebase Realtime Database の /system_logs へログを非同期 POST する。

    Parameters
    ----------
    module      : モジュール名 (例: "mainTST", "pink_bronson")
    message     : ログメッセージ
    firebase_url: Firebase DB の URL (省略時は config.json から自動取得)
    """
    url = firebase_url or _get_firebase_url()
    if not url:
        return  # Firebase URL 未設定ならサイレントスキップ

    payload = {
        "module":    module,
        "message":   message,
        "timestamp": int(time.time() * 1000),                  # Unix ms
        "ts_iso":    time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
    }

    def _send():
        try:
            requests.post(
                f"{url.rstrip('/')}/system_logs.json",
                json=payload,
                timeout=5,
            )
        except Exception:
            pass  # ログ送信失敗はサイレントに無視

    threading.Thread(target=_send, daemon=True).start()
