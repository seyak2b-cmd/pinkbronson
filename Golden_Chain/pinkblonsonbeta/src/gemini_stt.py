# -*- coding: utf-8 -*-
"""
gemini_stt.py
Gemini File API を使った音声ファイルの STT モジュール。
Golden_Chain の audio_processor.py から呼び出される。
"""
import os
import time
import google.generativeai as genai

_PROMPT = (
    "この音声を文字起こししてください。"
    "話者が実際に発した言葉をそのまま書き起こしてください。"
    "句読点は自然に付けてください。"
    "余計な説明・注釈・ラベルは不要です。文字起こし結果のみを返してください。"
)


def transcribe(audio_path: str, api_key: str, language_hint: str = "") -> str:
    """
    WAV ファイルを Gemini File API に送り、文字起こしテキストを返す。

    Returns:
        文字起こし結果（空文字列の場合もある）
    Raises:
        ValueError : api_key が空
        FileNotFoundError : audio_path が存在しない
        Exception  : API 通信エラー等
    """
    if not api_key:
        raise ValueError("Gemini APIキーが設定されていません。")
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"音声ファイルが見つかりません: {audio_path}")

    genai.configure(api_key=api_key)

    prompt = _PROMPT
    if language_hint:
        prompt += f"\n主要言語ヒント: {language_hint}"

    audio_file = None
    try:
        audio_file = genai.upload_file(audio_path, mime_type="audio/wav")

        # ACTIVE 状態になるまで最大 5 秒待機
        for _ in range(10):
            state = str(getattr(audio_file, "state", "ACTIVE")).upper()
            if "ACTIVE" in state or state == "2":
                break
            time.sleep(0.5)
            audio_file = genai.get_file(audio_file.name)

        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content([audio_file, prompt])
        return (getattr(response, "text", None) or "").strip()

    finally:
        # アップロードしたファイルを必ず削除（課金抑制）
        if audio_file:
            try:
                genai.delete_file(audio_file.name)
            except Exception:
                pass
