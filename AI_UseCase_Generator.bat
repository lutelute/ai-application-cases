@echo off
REM AI Use Case自動生成ツール - ダブルクリック実行用スクリプト
REM Windows用 .bat ファイル

title AI Use Case自動生成ツール
color 0a

echo.
echo 🚀 AI Use Case自動生成ツール
echo ==================================
echo.

REM スクリプトのディレクトリに移動
cd /d "%~dp0"

REM Python環境チェック
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Pythonが見つかりません。Pythonをインストールしてください。
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

echo ✅ Pythonが見つかりました

REM Claude CLI チェック
claude --version >nul 2>&1
if errorlevel 1 (
    echo ⚠️ Claude CLIが見つかりません
    set CLAUDE_AVAILABLE=false
) else (
    echo ✅ Claude CLIが利用可能です
    set CLAUDE_AVAILABLE=true
)

REM Gemini CLI チェック
gemini --version >nul 2>&1
if errorlevel 1 (
    echo ⚠️ Gemini CLIが見つかりません
    set GEMINI_AVAILABLE=false
) else (
    echo ✅ Gemini CLIが利用可能です
    set GEMINI_AVAILABLE=true
)

REM 少なくとも1つのAI CLIが必要
if "%CLAUDE_AVAILABLE%"=="false" if "%GEMINI_AVAILABLE%"=="false" (
    echo.
    echo ❌ Claude CLI または Gemini CLI のいずれかが必要です
    echo.
    echo インストール方法:
    echo • Claude CLI: https://github.com/anthropics/claude-code
    echo • Gemini CLI: npm install -g @google/generative-ai-cli
    echo.
    pause
    exit /b 1
)

echo.
echo 💻 AI Use Case自動生成ツールを起動します
echo.
python scripts\auto_usecase_generator.py

:end
echo.
echo 実行完了。
pause