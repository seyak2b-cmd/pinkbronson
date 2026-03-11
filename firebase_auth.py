"""
Pink Bronson — Firebase Authentication Manager
Firebase Email/Password 認証で ID トークンを自動管理する共有モジュール。

使い方 (Python側):
    from firebase_auth import FirebaseAuth
    _fb_auth = FirebaseAuth.from_config(load_config())  # config.json から
    _fb_auth = FirebaseAuth.from_env(api_key, email, password)  # 環境変数から

    # requests 呼び出し時
    requests.get(url, params=_fb_auth.params(), timeout=5)
    requests.post(url, json=data, params=_fb_auth.params(), timeout=5)
"""
import time
import threading
import requests

_TOKEN_MARGIN = 300  # トークン失効の5分前に更新


class FirebaseAuth:
    """Firebase Email/Password 認証トークンを自動管理するクラス。"""

    def __init__(self, api_key: str, email: str, password: str):
        self._api_key        = api_key
        self._email          = email
        self._password       = password
        self._id_token: str  = ""
        self._refresh_token: str = ""
        self._expires_at: float  = 0.0
        self._lock = threading.Lock()
        self._sign_in()

    # ── 内部: サインイン ──────────────────────────────────────
    def _sign_in(self) -> bool:
        try:
            url = (
                "https://identitytoolkit.googleapis.com/v1/"
                f"accounts:signInWithPassword?key={self._api_key}"
            )
            resp = requests.post(url, json={
                "email":             self._email,
                "password":          self._password,
                "returnSecureToken": True,
            }, timeout=10)
            resp.raise_for_status()
            d = resp.json()
            self._id_token      = d["idToken"]
            self._refresh_token = d["refreshToken"]
            self._expires_at    = time.time() + int(d["expiresIn"]) - _TOKEN_MARGIN
            print(f"[FirebaseAuth] ✅ サインイン完了 ({self._email})")
            return True
        except Exception as e:
            print(f"[FirebaseAuth] ❌ サインイン失敗: {e}")
            return False

    # ── 内部: トークン更新 ────────────────────────────────────
    def _refresh(self) -> bool:
        if not self._refresh_token:
            return self._sign_in()
        try:
            url = f"https://securetoken.googleapis.com/v1/token?key={self._api_key}"
            resp = requests.post(url, json={
                "grant_type":    "refresh_token",
                "refresh_token": self._refresh_token,
            }, timeout=10)
            resp.raise_for_status()
            d = resp.json()
            self._id_token      = d["id_token"]
            self._refresh_token = d["refresh_token"]
            self._expires_at    = time.time() + int(d["expires_in"]) - _TOKEN_MARGIN
            print("[FirebaseAuth] 🔄 トークン更新完了")
            return True
        except Exception as e:
            print(f"[FirebaseAuth] ⚠️ リフレッシュ失敗 → 再サインイン: {e}")
            return self._sign_in()

    # ── 公開: トークン取得 ────────────────────────────────────
    def get_token(self) -> str:
        with self._lock:
            if not self._id_token or time.time() >= self._expires_at:
                self._refresh()
            return self._id_token

    def params(self) -> dict:
        """requests の params= に渡す辞書 {"auth": <idToken>} を返す。"""
        tok = self.get_token()
        return {"auth": tok} if tok else {}

    # ── クラスメソッド: 設定から生成 ──────────────────────────
    @classmethod
    def from_config(cls, cfg: dict) -> 'FirebaseAuth | None':
        """config.json の firebase_auth セクションからインスタンス生成。"""
        a        = cfg.get("firebase_auth", {})
        api_key  = a.get("api_key",  "").strip()
        email    = a.get("email",    "").strip()
        password = a.get("password", "").strip()
        if not all([api_key, email, password]):
            print("[FirebaseAuth] ⚠️ config.json に firebase_auth が未設定です")
            return None
        return cls(api_key, email, password)

    @classmethod
    def from_env(cls, api_key: str, email: str, password: str) -> 'FirebaseAuth | None':
        """環境変数からインスタンス生成。"""
        if not all([api_key.strip(), email.strip(), password.strip()]):
            print("[FirebaseAuth] ⚠️ Firebase Auth 環境変数が未設定です")
            return None
        return cls(api_key.strip(), email.strip(), password.strip())
