# AI Use Case Database

AIのユースケースを体系的に管理するためのObsidianデータベースです。DB Folderプラグインを使用してNotion風のデータベース機能を提供します。

## 必要なプラグイン

### 必須プラグイン
1. **DB Folder** - Notion風のデータベース機能
   - コミュニティプラグインから「DB Folder」を検索してインストール

### 推奨プラグイン
1. **Dataview** - 高度なクエリとデータ操作
   - DB Folderと組み合わせることで動的なビューを作成可能
2. **Templates** - テンプレート機能（標準プラグイン）

## セットアップ手順

1. Obsidianでこのフォルダを開く
2. 設定 > コミュニティプラグイン > 閲覧 で「DB Folder」を検索・インストール
3. 必要に応じて「Dataview」プラグインもインストール
4. プラグインを有効化
5. `use-cases/`フォルダでDB Folderのデータベースビューを作成

## 構造

- `.obsidian/templates/` - Obsidianテンプレートファイル
- `use-cases/` - 各ユースケースのマークダウンファイル
- `attachments/` - 画像やその他のファイル

## 使い方

1. `use-cases/`フォルダでDB Folderを使用してデータベースビューを作成
2. テンプレートを使用して新しいユースケースを作成
3. データベースビューでフィルタリング・ソート・検索を活用
4. タグやリンクを活用して関連性を整理

## テンプレート

- `AIユースケーステンプレート.md` - 基本的なユースケース記録用テンプレート

## 自動生成ツール

このプロジェクトには、GitHubリポジトリからAIユースケースを自動生成するPythonスクリプトが含まれています。

### 対応AI

1. **Claude CLI** - 推奨（無料、高精度）
2. **Gemini CLI** - 高速（無料、但しクォータ制限有）
3. **ChatGPT API** - 安定（APIキー必要、有料）

### セットアップ

```bash
# 依存関係のインストール
pip install -r requirements.txt

# AI CLIツールのインストール（お好みで）
# Claude CLI: https://github.com/anthropics/claude-code
# Gemini CLI: npm install -g @google/generative-ai-cli
# ChatGPT: OpenAI APIキーのみ必要
```

### 使い方

```bash
# インタラクティブモード
python scripts/auto_usecase_generator.py

# コマンドライン引数
python scripts/auto_usecase_generator.py https://github.com/user/repo

# ChatGPT使用（APIキー暗号化保存可能）
python scripts/auto_usecase_generator.py --ai-provider chatgpt
```

### セキュリティ

- ChatGPT APIキーは暗号化して安全に保存
- `.config/`フォルダは.gitignoreで除外済み
- APIキーがGitHubに公開される心配なし

## DB Folderの活用

- **フォルダベース**: `use-cases/`フォルダ内のファイルを自動的にデータベース化
- **メタデータ表示**: フロントマターの情報を列として表示
- **フィルタリング**: カテゴリ、業界、ステータスでフィルタ
- **編集**: データベースビューから直接ノートを編集可能