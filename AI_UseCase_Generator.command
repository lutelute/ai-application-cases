#!/bin/bash

# AI Use Case自動生成ツール - ダブルクリック実行用スクリプト
# macOS用 .command ファイル

# スクリプトのディレクトリに移動
cd "$(dirname "$0")"

# タイトル表示
echo "🚀 AI Use Case自動生成ツール"
echo "=================================="

# Python環境チェック
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3が見つかりません。Python 3をインストールしてください。"
    echo "https://www.python.org/downloads/"
    read -p "Enterキーで終了..."
    exit 1
fi

echo "✅ Python 3が見つかりました"

# Claude CLI チェック
if command -v claude &> /dev/null; then
    echo "✅ Claude CLIが利用可能です"
    CLAUDE_AVAILABLE=true
else
    echo "⚠️ Claude CLIが見つかりません"
    CLAUDE_AVAILABLE=false
fi

# Gemini CLI チェック
if command -v gemini &> /dev/null; then
    echo "✅ Gemini CLIが利用可能です"
    GEMINI_AVAILABLE=true
else
    echo "⚠️ Gemini CLIが見つかりません"
    GEMINI_AVAILABLE=false
fi

# 少なくとも1つのAI CLIが必要
if [ "$CLAUDE_AVAILABLE" = false ] && [ "$GEMINI_AVAILABLE" = false ]; then
    echo ""
    echo "❌ Claude CLI または Gemini CLI のいずれかが必要です"
    echo ""
    echo "インストール方法:"
    echo "• Claude CLI: https://github.com/anthropics/claude-code"
    echo "• Gemini CLI: npm install -g @google/generative-ai-cli"
    echo ""
    read -p "Enterキーで終了..."
    exit 1
fi

echo ""
echo "💻 AI Use Case自動生成ツールを起動します"
echo ""
python3 scripts/auto_usecase_generator.py

echo ""
echo "実行完了。"
read -p "Enterキーでウィンドウを閉じます..."