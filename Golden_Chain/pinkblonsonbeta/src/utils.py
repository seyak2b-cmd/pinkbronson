import json
import os
import re
import traceback
from datetime import datetime, timedelta, timezone

# ══════════════════════════════════════════════════════════
# Sanitization
# ══════════════════════════════════════════════════════════

# プロンプトインジェクションの定型パターン（英語・日本語）
_INJECTION_RE = re.compile(
    r'(?:'
    # 英語系インジェクション
    r'ignore\s+(?:all\s+)?(?:previous|prior|above|earlier)\s+(?:instructions?|prompts?|rules?|constraints?)'
    r'|(?:you are now|act as|pretend (?:to be|you are)|roleplay as)'
    r'|new\s+(?:instruction|prompt|task|role)'
    r'|(?:system|user|assistant)\s*:'
    r'|<\s*/?(?:system|user|assistant|prompt|instruction)\s*>'
    r'|do anything now|developer mode|jailbreak|DAN\b'
    # 日本語系インジェクション
    r'|以前の指示を無視|指示を忘れ|ロールプレイ|あなたは今|キャラクターとして'
    r'|システムプロンプト|新しい指示|ルールを無視'
    r')',
    re.IGNORECASE,
)

def sanitize_for_prompt(text: str, max_len: int = 500) -> str:
    """
    外部入力テキスト（Twitchチャット・STT）をGeminiプロンプトに挿入する前にサニタイズする。

    - 長さ制限（デフォルト500文字）
    - 制御文字の除去（改行・タブは保持）
    - プロンプトインジェクション定型句を [FILTERED] に置換
    """
    if not isinstance(text, str) or not text:
        return ""
    text = text[:max_len]
    # 制御文字を除去（\n \t は保持）
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # プロンプトインジェクション定型句を無効化
    text = _INJECTION_RE.sub('[FILTERED]', text)
    return text.strip()


def sanitize_gemini_output(text: str, max_len: int = 1000) -> str:
    """
    GeminiのレスポンスをHTML・ファイルに出力する前にサニタイズする。

    - 長さ制限（デフォルト1000文字）
    - 制御文字の除去
    - HTMLタグの除去
    - javascript: / data: などの危険なURIスキームを無効化
    """
    if not isinstance(text, str) or not text:
        return ""
    text = text[:max_len]
    # 制御文字を除去
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # HTMLタグを除去
    text = re.sub(r'<[^>]{0,200}>', '', text)
    # 危険なURIスキームを無効化
    text = re.sub(r'(?i)(?:javascript|vbscript|data)\s*:', '[BLOCKED]:', text)
    return text.strip()

def load_config(project_root):
    """Load configuration from config.json and parent Pink Bronson config."""
    config_path = os.path.join(project_root, 'config.json')
    default_config = {
        'api_key': '',
        'copier_source': '',
        'summarizer_interval': 60,
        'summarizer_lookback': 666,
        'summarizer_prompt': '会話を3行で要約してください。',
        'title_gen_interval': 60,
        'title_gen_lookback': 60,
        'title_gen_prompt': 'タイトルを生成してください。',
        'facilitator_interval': 30,
        'facilitator_lookback': 180,
        'facilitator_prompt': '次の話題を提案してください。'
    }
    
    local_config = default_config.copy()
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                local_config.update(json.load(f))
        except Exception:
            pass

    # Override api_key with Pink Bronson's main config
    try:
        pb_config_path = os.path.normpath(os.path.join(project_root, '..', '..', 'config.json'))
        if os.path.exists(pb_config_path):
            with open(pb_config_path, 'r', encoding='utf-8') as f:
                pb_config = json.load(f)
                api_key = pb_config.get('api_keys', {}).get('gemini_key', '')
                if api_key:
                    local_config['api_key'] = api_key
    except Exception:
        pass

    return local_config

def log_error(log_file, message):
    """Log error to file with timestamp."""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass

def normalize_timestamp(ts_str):
    """Normalize timestamp string to datetime object."""
    try:
        if ts_str.endswith('Z'):
            ts_str_iso = ts_str[:-1] + '+00:00'
        else:
            ts_str_iso = ts_str
        return datetime.fromisoformat(ts_str_iso)
    except (ValueError, AttributeError):
        return None

def get_recent_text(primary_input_file, seconds):
    """Read cleantext.json and stt_text.json, merge, and get text from the last N seconds."""
    data_dir = os.path.dirname(primary_input_file)
    stt_file = os.path.join(data_dir, "stt_text.json")
    
    all_data = []
    
    def load_json_safe(file_path):
        if not os.path.exists(file_path):
            return []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = json.load(f)
                return content if isinstance(content, list) else []
        except:
            return []

    # Load both files
    all_data.extend(load_json_safe(primary_input_file))
    all_data.extend(load_json_safe(stt_file))
    
    if not all_data:
        return ""

    try:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=seconds)
        
        recent_items = []
        for item in all_data:
            ts_str = item.get('timestamp')
            raw_text = item.get('rawText')
            
            if not ts_str or not raw_text:
                continue
                
            item_time = normalize_timestamp(ts_str)
            if item_time and item_time > cutoff:
                recent_items.append((item_time, raw_text))
        
        # Sort by timestamp to maintain chronological order
        recent_items.sort(key=lambda x: x[0])
        
        return "\n".join([text for _, text in recent_items])
        
    except Exception:
        return ""

def update_process_status(name, state, fetch_time=None, details=None):
    """Update the status file for a specific process."""
    status_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "status")
    os.makedirs(status_dir, exist_ok=True)
    status_file = os.path.join(status_dir, f"{name}_status.json")
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Read existing data to preserve history
    history = []
    if os.path.exists(status_file):
        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                existing = json.load(f)
                history = existing.get('history', [])
        except:
            pass
            
    # Add new log entry
    log_entry = f"[{current_time.split(' ')[1]}] {state}"
    if details:
        log_entry += f": {details}"
    
    history.insert(0, log_entry)
    history = history[:5] # Keep last 5 entries
    
    data = {
        "state": state,
        "last_update": current_time,
        "pid": os.getpid(),
        "details": details,
        "history": history
    }
    if fetch_time:
        data["fetch_time"] = fetch_time
    elif os.path.exists(status_file):
         # Preserve fetch_time if not updating it
         try:
             with open(status_file, 'r', encoding='utf-8') as f:
                 old = json.load(f)
                 if "fetch_time" in old:
                     data["fetch_time"] = old["fetch_time"]
         except:
             pass

    try:
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def log_token_usage(model_name, prompt_tokens, candidate_tokens):
    """Log token usage to usage_log.json."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    log_file = os.path.join(data_dir, "usage_log.json")
    
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model": model_name,
        "prompt_tokens": prompt_tokens,
        "candidate_tokens": candidate_tokens,
        "total_tokens": prompt_tokens + candidate_tokens
    }

    # 料金の概算 (Gemini 2.0 Flash の例: Prompt ~$0.075/1M, Output ~$0.30/1M)
    cost = (prompt_tokens * 0.075 + candidate_tokens * 0.3) / 1000000
    print(f"[TOKEN] {model_name}: {entry['total_tokens']} tokens (P:{prompt_tokens}, C:{candidate_tokens}) - approx ${cost:.6f}")

    try:
        # Append to list (create if not exists)
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
                if not isinstance(logs, list):
                    logs = []
        else:
            logs = []
            
        logs.append(entry)
        
        # Keep last 1000 entries to avoid massive file
        if len(logs) > 1000:
            logs = logs[-1000:]
            
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
