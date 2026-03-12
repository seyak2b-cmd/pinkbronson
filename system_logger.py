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
_BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
_CONFIG_PATH = os.path.join(_BASE_DIR, "config.json")
_TOKEN_PATH  = os.path.join(_BASE_DIR, "Blue_Rayban", "twitchtoken.txt")

# 認証トークンキャッシュ (有効期限 55分)
_auth_cache = {"token": None, "expires_at": 0}
_auth_lock  = threading.Lock()


def _load_dotenv_simple(path: str) -> dict:
    """twitchtoken.txt を簡易パース (key=value)。"""
    result = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    result[k.strip()] = v.strip()
    except Exception:
        pass
    return result


def _get_firebase_creds() -> dict:
    """Firebase 接続情報を twitchtoken.txt → config.json の順で取得。"""
    env = _load_dotenv_simple(_TOKEN_PATH)
    cfg = {}
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        pass
    api_keys = cfg.get("api_keys", {})
    return {
        "url":      env.get("FIREBASE_DATABASE_URL") or api_keys.get("firebase_url", ""),
        "api_key":  env.get("FIREBASE_API_KEY") or api_keys.get("firebase_api_key", ""),
        "email":    env.get("FIREBASE_AUTH_EMAIL", ""),
        "password": env.get("FIREBASE_AUTH_PASSWORD", ""),
    }


def _get_firebase_url() -> str:
    return _get_firebase_creds()["url"]


def _get_auth_token() -> str:
    """Firebase idToken を取得（キャッシュ付き）。認証失敗時は空文字。"""
    with _auth_lock:
        if _auth_cache["token"] and time.time() < _auth_cache["expires_at"]:
            return _auth_cache["token"]

        creds = _get_firebase_creds()
        if not creds["email"] or not creds["password"]:
            return ""
        try:
            r = requests.post(
                f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
                f"?key={creds['api_key']}",
                json={"email": creds["email"], "password": creds["password"],
                      "returnSecureToken": True},
                timeout=8,
            )
            token = r.json().get("idToken", "")
            if token:
                _auth_cache["token"]      = token
                _auth_cache["expires_at"] = time.time() + 55 * 60
            return token
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
        return

    payload = {
        "module":    module,
        "message":   message,
        "timestamp": int(time.time() * 1000),
        "ts_iso":    time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
    }

    def _send():
        try:
            token    = _get_auth_token()
            endpoint = f"{url.rstrip('/')}/system_logs.json"
            if token:
                endpoint += f"?auth={token}"
            requests.post(endpoint, json=payload, timeout=5)
        except Exception:
            pass

    threading.Thread(target=_send, daemon=True).start()
