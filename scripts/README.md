# AI Use Case自動生成システム

GitHubリポジトリからAIユースケースドキュメントを自動生成するPythonスクリプトです。

## 概要

このツールは、GitHubリポジトリのURLを入力するだけで、統一されたフォーマットのAIユースケースドキュメントを自動生成します。Claude CLIまたはGemini CLIを使用してリポジトリを分析し、適切なYAMLメタデータと構造化されたMarkdownドキュメントを作成します。

## 機能

- **自動リポジトリ分析**: README、コード、依存関係の詳細分析
- **AI技術特定**: 機械学習、LLM、CV、NLP等の使用技術を自動識別
- **統一フォーマット**: プロジェクト全体で一貫したメタデータ構造
- **複数AI CLI対応**: Claude CLI、Gemini CLI、または自動選択
- **インタラクティブモード**: 対話形式での簡単操作

## 必要環境

### Python
- Python 3.7以上
- 標準ライブラリのみ使用（追加インストール不要）

### AI CLI（いずれか必須）
- **Claude CLI**: [インストール方法](https://github.com/anthropics/claude-code)
- **Gemini CLI**: `npm install -g @google/generative-ai-cli`

## インストール

```bash
# リポジトリをクローン
git clone https://github.com/your-username/ai-use-case.git
cd ai-use-case

# スクリプトを実行可能にする
chmod +x scripts/auto_usecase_generator.py
```

## 使用方法

### 1. インタラクティブモード（推奨）

```bash
python scripts/auto_usecase_generator.py
```

実行すると以下の対話が開始されます：
```
🚀 AI Use Case自動生成ツール
==================================================
GitHubリポジトリURLを入力してください: https://github.com/username/repository

AI Provider選択:
1. Claude CLI
2. Gemini CLI
3. 自動選択（推奨）
選択してください [1-3, default: 3]: 
```

### 2. コマンドライン引数

```bash
# 基本的な使用方法
python scripts/auto_usecase_generator.py https://github.com/username/repository

# AI Providerを指定
python scripts/auto_usecase_generator.py --ai-provider claude https://github.com/username/repository

# プロジェクトルートを指定
python scripts/auto_usecase_generator.py --project-root /path/to/project https://github.com/username/repository
```

### 3. コマンドライン引数オプション

```bash
python scripts/auto_usecase_generator.py --help
```

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `github_url` | GitHubリポジトリURL | - |
| `--project-root` | プロジェクトルートディレクトリ | `.` |
| `--ai-provider` | 使用するAI CLI (`claude`/`gemini`/`auto`) | `auto` |

## 生成されるファイル

### ファイル配置
```
use-cases/
└── repository_name.md  # 生成されるユースケースファイル
```

### YAMLメタデータ構造
```yaml
---
title: "プロジェクトの簡潔なタイトル"
summary: "1-2文の概要説明"
category: "開発プロセス自動化/データ分析/画像処理/自然言語処理/機械学習/ウェブ開発/その他"
industry: "IT・ソフトウェア/製造業/金融/ヘルスケア/教育/エンタメ/その他"
createdAt: "2025-01-20"
updatedAt: "2025-01-20"
status: "開発中/完了/実験的/アーカイブ/メンテナンス中"
github_link: "https://github.com/username/repository"
contributors:
  - "コントリビューター名"
tags:
  - "AI"
  - "Python"
  - "機械学習"
---
```

### Markdownドキュメント構造
1. **概要**: プロジェクトの詳細説明
2. **課題・ニーズ**: 解決する問題と市場ニーズ
3. **AI技術**: 使用技術、モデル、技術スタック
4. **実装フロー**: ステップバイステップの処理フロー
5. **主要機能**: 具体的な機能一覧
6. **期待される効果**: 定量的・定性的効果
7. **リスク・課題**: 技術的制約と将来課題
8. **技術的詳細**: アーキテクチャ、データフロー
9. **応用・展開可能性**: 他分野への応用
10. **コントリビューター**: 貢献者一覧
11. **参考リンク**: 関連資料

## トラブルシューティング

### AI CLIが見つからない場合
```bash
# Claude CLIのインストール確認
claude --version

# Gemini CLIのインストール確認
gemini --version
```

### 生成に失敗する場合
1. **ネットワーク接続**の確認
2. **GitHubリポジトリURL**の正確性を確認
3. **AI CLI認証**が適切に設定されているか確認
4. **タイムアウト**の場合は再実行

### よくあるエラー

| エラー | 原因 | 解決方法 |
|-------|------|----------|
| `URL検証エラー` | 無効なGitHubURL | 正しいGitHubリポジトリURLを入力 |
| `Claude CLI実行エラー` | Claude CLI未インストール | Claude CLIをインストール |
| `タイムアウト` | ネットワークまたは大きなリポジトリ | 再実行または小さなリポジトリで試行 |

## カスタマイズ

### プロンプトテンプレートの編集
`scripts/prompt_template.md`を編集することで、生成されるドキュメントの構造や内容をカスタマイズできます。

### 新しいAI Provider追加
`call_ai_cli`メソッドに新しいプロバイダーのロジックを追加できます。

## 開発者向け情報

### ファイル構成
```
scripts/
├── auto_usecase_generator.py  # メインスクリプト
├── prompt_template.md         # プロンプトテンプレート
└── README.md                  # このファイル
```

### 主要クラス・メソッド
- `UseCaseGenerator`: メインクラス
  - `validate_github_url()`: URL検証
  - `call_ai_cli()`: AI CLI呼び出し
  - `save_usecase_file()`: ファイル保存
  - `generate_usecase()`: メイン処理

## ライセンス

このプロジェクトのライセンスに従います。

## コントリビューション

1. Forkしてブランチを作成
2. 変更を実装
3. テストを実行
4. Pull Requestを作成

## 更新履歴

- **v1.0**: 初回リリース
  - Claude CLI対応
  - Gemini CLI対応
  - 自動プロバイダー選択
  - インタラクティブモード