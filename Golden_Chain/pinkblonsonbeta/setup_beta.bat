@echo off
chcp 65001 > nul
echo ===================================================
echo  Aquaread Beta - セットアップウィザード
echo ===================================================
echo.

echo [1/3] Pythonの確認をしています...
py --list > nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Pythonランチャー(py.exe)が見つかりません。
    echo python.orgからPythonをインストールしてください。
    pause
    exit /b
)
echo Python OK.
echo.

echo [2/3] 仮想環境(venv)を作成しています...
if not exist "venv" (
    py -3 -m venv venv
    echo 仮想環境を作成しました。
) else (
    echo 仮想環境は既に存在します。
)
echo.

echo [3/3] 必要なライブラリをインストールしています...
echo これには数分かかる場合があります。
venv\Scripts\python -m pip install --upgrade pip
venv\Scripts\python -m pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] インストールに失敗しました。
    pause
    exit /b
)

echo.
echo ===================================================
echo  セットアップ完了！
echo  「run_beta.bat」をダブルクリックして起動してください。
echo ===================================================
pause
