import json
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone
from utils import normalize_timestamp

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")

SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
CLEANTEXT_FILE = os.path.join(DATA_DIR, "cleantext.json")
ERROR_LOG_FILE = os.path.join(LOG_DIR, "cleaner_error.txt")

def log_error(message):
    """Log error to file."""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(ERROR_LOG_FILE, "w", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}")
    except Exception:
        pass

def clear_error_log():
    """Clear error log on success."""
    if os.path.exists(ERROR_LOG_FILE):
        try:
            os.remove(ERROR_LOG_FILE)
        except Exception:
            pass

def process_settings():
    """
    settings.jsonからデータを抽出し、24時間以内のデータのみをcleantext.jsonに保存
    """
    if not os.path.exists(SETTINGS_FILE):
        log_error(f"{SETTINGS_FILE} が見つかりません")
        print(f"Error: {SETTINGS_FILE} not found")
        return

    try:
        # Load settings.json
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            settings_data = json.load(f)
        
        history = settings_data.get('history', [])
        if not isinstance(history, list):
            history = []
            
        # Current time and cutoff
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(hours=24)
        
        # Extract and Filter
        clean_data = []
        for item in history:
            if not isinstance(item, dict):
                continue
                
            ts_str = item.get('timestamp')
            raw_text = item.get('rawText')
            
            if not ts_str or not raw_text:
                continue
            
            # Normalize and check time
            item_time = normalize_timestamp(ts_str)
            if item_time:
                # Keep if newer than cutoff
                if item_time > cutoff_time:
                    clean_data.append({
                        'timestamp': ts_str,
                        'rawText': raw_text
                    })
        
        # Safe Write to cleantext.json (Atomic write)
        temp_file = CLEANTEXT_FILE + ".tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(clean_data, f, indent=2, ensure_ascii=False)
        
        if os.path.exists(CLEANTEXT_FILE):
            os.remove(CLEANTEXT_FILE)
        os.rename(temp_file, CLEANTEXT_FILE)
        
        print(f"Success: Processed {len(clean_data)} entries.")
        clear_error_log()
        
    except Exception as e:
        error_msg = f"Cleaner failed: {e}\n{traceback.format_exc()}"
        print(error_msg)
        log_error(error_msg)
        sys.exit(1)

if __name__ == "__main__":
    process_settings()
