@echo off
chcp 65001 > nul
echo Aquaread Beta を起動しています...

if not exist "venv" (
    echo [ERROR] 仮想環境が見つかりません。
    echo 先に「setup_beta.bat」を実行してください。
    pause
    exit /b
)

echo アプリケーションを開始します...
venv\Scripts\python src\main_ui.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] アプリケーションがエラーで終了しました。
    pause
)
