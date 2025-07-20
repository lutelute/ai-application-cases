#!/usr/bin/env python3
"""
AI Use Case自動生成スクリプト
GitHubリンクからユースケースMDファイルを自動生成する
"""

import os
import sys
import subprocess
import json
import re
import time
import tempfile
import shutil
from datetime import datetime
from urllib.parse import urlparse
import argparse

# requestsの代替として標準ライブラリを使用
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.request
    import urllib.error
    HAS_REQUESTS = False

class ProgressBar:
    """シンプルなプログレスバー表示"""
    def __init__(self, width=40):
        self.width = width
        self.current = 0
        
    def show(self, message="処理中"):
        """アニメーション付きプログレス表示"""
        chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        char = chars[self.current % len(chars)]
        self.current += 1
        print(f"\r{char} {message}...", end="", flush=True)
        time.sleep(0.1)
    
    def finish(self, message="完了"):
        """プログレス完了"""
        print(f"\r✅ {message}")

def extract_clean_output(raw_output):
    """AIの出力から主要なコンテンツ（JSONやMarkdown）を抽出・整形する"""
    
    # 1. ```json ... ``` ブロックを検索
    json_search = re.search(r"```(json)?\s*(\{.*?\})\s*```", raw_output, re.DOTALL)
    if json_search:
        try:
            json.loads(json_search.group(2))
            return json_search.group(2)
        except json.JSONDecodeError:
            pass

    # 2. YAMLフロントマター付きのMarkdown全体を検索
    md_search = re.search(r"^---\s*\n.*?\n---\s*\n.*", raw_output, re.DOTALL)
    if md_search:
        return md_search.group(0)

    # 3. ```markdown ... ``` ブロックを検索
    md_block_search = re.search(r"```markdown\s*(.*?)\s*```", raw_output, re.DOTALL)
    if md_block_search:
        return md_block_search.group(1)

    # 4. JSONオブジェクトを直接検索（最後の手段）
    json_start = raw_output.find('{')
    json_end = raw_output.rfind('}') + 1
    if json_start != -1 and json_end > json_start:
        potential_json = raw_output[json_start:json_end]
        try:
            json.loads(potential_json)
            return potential_json
        except json.JSONDecodeError:
            pass

    # 5. 何も見つからない場合は、前後の空白を除去してそのまま返す
    return raw_output.strip()


class MultiStageAnalyzer:

    """高精度多段階分析エンジン（Gemini/Claude対応）"""
    
    def __init__(self, github_url, repo_name, temp_dir, cli_outputs_dir, ai_provider="gemini"):
        self.github_url = github_url
        self.repo_name = repo_name
        self.temp_dir = temp_dir
        self.cli_outputs_dir = cli_outputs_dir
        self.ai_provider = ai_provider
        self.analysis_data = {}
        
    def save_stage_data(self, stage, data):
        """段階別データを一時保存"""
        stage_file = os.path.join(self.temp_dir, f"stage_{stage}.json")
        with open(stage_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def load_stage_data(self, stage):
        """段階別データを読み込み"""
        stage_file = os.path.join(self.temp_dir, f"stage_{stage}.json")
        if os.path.exists(stage_file):
            with open(stage_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    def execute_ai_analysis(self, prompt, stage_name):
        """AI CLIを実行して分析（Gemini/Claude）"""
        try:
            print(f"\n🔍 {stage_name} - {self.ai_provider.upper()}分析実行中...")
            
            # プログレスバー
            progress = ProgressBar()
            import threading
            stop_progress = threading.Event()
            
            def show_progress():
                while not stop_progress.is_set():
                    progress.show(f"{stage_name}")
            
            progress_thread = threading.Thread(target=show_progress)
            progress_thread.daemon = True
            progress_thread.start()
            
            # AI CLI実行
            if self.ai_provider == "gemini":
                cmd = ["gemini", "chat", "--prompt", prompt]
                timeout = 300  # 5分
            elif self.ai_provider == "claude":
                cmd = ["claude", prompt]
                timeout = 300  # 5分
            else:
                raise ValueError(f"Unsupported AI provider: {self.ai_provider}")
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=timeout
            )
            
            stop_progress.set()
            progress_thread.join(timeout=0.5)
            
            # CLIの生出力を保存
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            raw_output_filename = f"{timestamp}_{self.repo_name}_{stage_name.replace(':', '_')}.log"
            raw_output_path = os.path.join(self.cli_outputs_dir, raw_output_filename)
            
            log_content = f"""# AI Analysis Log

- **Repository**: {self.github_url}
- **AI Provider**: {self.ai_provider}
- **Stage**: {stage_name}
- **Timestamp**: {timestamp}

## Prompt

```
{prompt}
```

## Raw STDOUT

```
{result.stdout}
```

## Raw STDERR

```
{result.stderr}
```
"""
            with open(raw_output_path, 'w', encoding='utf-8') as f:
                f.write(log_content)

            if result.returncode == 0:
                progress.finish(f"{stage_name} 完了")
                # 整形された出力を返す
                return extract_clean_output(result.stdout)
            else:
                progress.finish(f"{stage_name} 失敗")
                print(f"❌ エラー: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            stop_progress.set()
            progress.finish(f"{stage_name} タイムアウト")
            return None
        except Exception as e:
            print(f"❌ {stage_name} エラー: {str(e)}")
            return None
    
    def stage_1_basic_analysis(self):
        """Stage 1: 基本情報収集"""
        prompt = f"""
GitHubリポジトリの基本情報を収集・分析してください。

📂 対象リポジトリ: {self.github_url}

## Stage 1: 基本情報収集タスク

以下の情報を詳細に調査・分析してください：

### 1. リポジトリ基本情報
- プロジェクト名、説明、目的
- 主要言語とフレームワーク
- ライセンス、作成日、最終更新日
- コントリビューター情報
- スター数、フォーク数、Issue数

### 2. プロジェクト構造分析
- ディレクトリ構造の詳細把握
- 主要ファイルとその役割
- 設定ファイル（package.json, requirements.txt等）
- ドキュメント構造（README, docs等）

### 3. 技術スタック特定
- 使用言語とバージョン
- 依存ライブラリ・フレームワーク
- 開発ツール・ビルドシステム
- デプロイ方法

### 4. AI/ML技術の予備調査
- 機械学習関連ライブラリの使用
- AI API（OpenAI、Google AI等）の利用
- データ処理・分析ツール
- モデル学習・推論コード

## 出力形式
以下のJSON形式で結果を出力してください：

```json
{{
  "basic_info": {{
    "name": "プロジェクト名",
    "description": "詳細な説明",
    "purpose": "主な目的",
    "language": "主要言語",
    "license": "ライセンス",
    "created": "作成日",
    "updated": "最終更新日",
    "contributors": ["contributor1", "contributor2"],
    "stats": {{
      "stars": 0,
      "forks": 0,
      "issues": 0
    }}
  }},
  "structure": {{
    "directories": ["dir1", "dir2"],
    "key_files": ["file1", "file2"],
    "config_files": ["config1", "config2"],
    "docs": ["README.md", "docs/"]
  }},
  "tech_stack": {{
    "languages": ["Python", "JavaScript"],
    "frameworks": ["React", "Flask"],
    "dependencies": ["numpy", "pandas"],
    "tools": ["webpack", "pytest"]
  }},
  "ai_ml_indicators": {{
    "ml_libraries": ["tensorflow", "scikit-learn"],
    "ai_apis": ["openai", "google-ai"],
    "data_tools": ["pandas", "numpy"],
    "model_files": ["model.pkl", "weights.h5"]
  }}
}}
```

詳細な調査を実行してください。
        """
        
        result = self.execute_ai_analysis(prompt, "Stage 1: 基本情報収集")
        if result:
            try:
                # JSONデータを抽出
                json_data = json.loads(result)
                self.save_stage_data("1_basic", json_data)
                return json_data
            except json.JSONDecodeError:
                print("⚠️ Stage 1 JSON解析エラー、生データを保存")
                self.save_stage_data("1_basic_raw", {"raw_output": result})
        return None
    
    def stage_2_deep_code_analysis(self):
        """Stage 2: 詳細コード分析"""
        stage1_data = self.load_stage_data("1_basic")
        
        prompt = f"""
GitHubリポジトリの詳細コード分析を実行してください。

📂 対象リポジトリ: {self.github_url}

## Stage 2: 詳細コード分析タスク

Stage 1で収集した基本情報：
{json.dumps(stage1_data, ensure_ascii=False, indent=2) if stage1_data else "Stage 1データなし"}

### 詳細分析項目：

1. **コアロジック分析**
   - 主要アルゴリズムの実装方法
   - データフロー・処理フロー
   - 設計パターンの使用状況

2. **AI/ML機能の詳細調査**
   - モデル学習・推論コード
   - データ前処理・後処理
   - パフォーマンス最適化手法

3. **アーキテクチャ分析**
   - システム全体の構成
   - モジュール間の依存関係
   - API設計・インターフェース

4. **品質・保守性評価**
   - コード品質（可読性、保守性）
   - テストカバレッジ
   - エラーハンドリング

## 出力形式（JSON）：

```json
{{
  "core_logic": {{
    "main_algorithms": ["algorithm1", "algorithm2"],
    "data_flow": "データの流れの説明",
    "design_patterns": ["pattern1", "pattern2"]
  }},
  "ai_ml_details": {{
    "model_types": ["CNN", "transformer"],
    "training_process": "学習プロセスの説明",
    "inference_method": "推論方法の説明",
    "data_preprocessing": "前処理の詳細",
    "performance_optimization": "最適化手法"
  }},
  "architecture": {{
    "system_design": "システム設計の説明",
    "module_dependencies": {{"module1": ["dep1", "dep2"]}},
    "api_design": "API設計の詳細"
  }},
  "quality_assessment": {{
    "code_quality": "品質評価",
    "test_coverage": "テストカバレッジ",
    "error_handling": "エラーハンドリング評価",
    "maintainability": "保守性評価"
  }}
}}
```

詳細なコード分析を実行してください。
        """
        
        result = self.execute_ai_analysis(prompt, "Stage 2: 詳細コード分析")
        if result:
            try:
                json_data = json.loads(result)
                self.save_stage_data("2_deep_analysis", json_data)
                return json_data
            except json.JSONDecodeError:
                print("⚠️ Stage 2 JSON解析エラー、生データを保存")
                self.save_stage_data("2_deep_analysis_raw", {"raw_output": result})
        return None
    
    def stage_3_consistency_check(self):
        """Stage 3: 整合性チェックと補完"""
        stage1_data = self.load_stage_data("1_basic")
        stage2_data = self.load_stage_data("2_deep_analysis")
        
        prompt = f"""
これまでの分析結果の整合性をチェックし、不足情報を補完してください。

📂 対象リポジトリ: {self.github_url}

## Stage 3: 整合性チェック・補完タスク

### これまでの分析結果：

**Stage 1 基本情報：**
{json.dumps(stage1_data, ensure_ascii=False, indent=2) if stage1_data else "データなし"}

**Stage 2 詳細分析：**
{json.dumps(stage2_data, ensure_ascii=False, indent=2) if stage2_data else "データなし"}

### チェック・補完項目：

1. **データ整合性チェック**
   - Stage 1とStage 2の情報に矛盾がないか
   - 技術スタックと実装の整合性
   - 依存関係の正確性

2. **不足情報の特定・補完**
   - 見落とした重要な機能
   - 追加の技術要素
   - 重要なファイル・設定

3. **AI/MLユースケースの再評価**
   - AI技術の活用度合い
   - 実用性・革新性の評価
   - 技術的難易度の判定

## 出力形式（JSON）：

```json
{{
  "consistency_check": {{
    "inconsistencies": ["矛盾点1", "矛盾点2"],
    "verified_facts": ["確認済み事実1", "確認済み事実2"],
    "confidence_score": 0.85
  }},
  "補完情報": {{
    "additional_features": ["機能1", "機能2"],
    "missing_tech_stack": ["技術1", "技術2"],
    "important_files": ["ファイル1", "ファイル2"]
  }},
  "ai_usecase_assessment": {{
    "ai_integration_level": "high/medium/low",
    "innovation_score": 0.8,
    "technical_complexity": "high/medium/low",
    "practical_value": "high/medium/low"
  }}
}}
```

詳細な整合性チェックと補完を実行してください。
        """
        
        result = self.execute_ai_analysis(prompt, "Stage 3: 整合性チェック")
        if result:
            try:
                json_data = json.loads(result)
                self.save_stage_data("3_consistency", json_data)
                return json_data
            except json.JSONDecodeError:
                print("⚠️ Stage 3 JSON解析エラー、生データを保存")
                self.save_stage_data("3_consistency_raw", {"raw_output": result})
        return None
    
    def stage_4_deep_insights(self):
        """Stage 4: ディープ分析・洞察"""
        stage1_data = self.load_stage_data("1_basic")
        stage2_data = self.load_stage_data("2_deep_analysis")
        stage3_data = self.load_stage_data("3_consistency")
        
        prompt = f"""
プロジェクトのディープ分析と洞察を提供してください。

📂 対象リポジトリ: {self.github_url}

## 累積分析データ：

**Stage 1 基本情報：**
{json.dumps(stage1_data, ensure_ascii=False, indent=2) if stage1_data else "データなし"}

**Stage 2 詳細分析：**
{json.dumps(stage2_data, ensure_ascii=False, indent=2) if stage2_data else "データなし"}

**Stage 3 整合性チェック：**
{json.dumps(stage3_data, ensure_ascii=False, indent=2) if stage3_data else "データなし"}

## Stage 4: ディープ分析・洞察タスク

### 深層分析項目：

1. **課題・問題点の特定**
   - 技術的制約・ボトルネック
   - 設計上の問題
   - 実装の改善点

2. **ユースケース価値の深掘り**
   - 市場での位置づけ
   - 競合との差別化要因
   - 実世界での応用可能性

3. **将来展望・拡張性**
   - 技術進化への対応
   - スケーラビリティ
   - 新機能追加の可能性

4. **学習・教育価値**
   - 技術学習の参考価値
   - ベストプラクティス
   - アンチパターンの事例

## 出力形式（JSON）：

```json
{{
  "challenges_and_issues": {{
    "technical_constraints": ["制約1", "制約2"],
    "design_problems": ["問題1", "問題2"],
    "improvement_areas": ["改善点1", "改善点2"]
  }},
  "usecase_value": {{
    "market_position": "市場での位置づけ",
    "differentiation": ["差別化要因1", "差別化要因2"],
    "real_world_applications": ["応用例1", "応用例2"],
    "target_users": ["ユーザー層1", "ユーザー層2"]
  }},
  "future_prospects": {{
    "scalability": "スケーラビリティ評価",
    "extensibility": "拡張性評価",
    "tech_evolution_readiness": "技術進化への対応度",
    "potential_features": ["将来機能1", "将来機能2"]
  }},
  "educational_value": {{
    "learning_value": "学習価値の説明",
    "best_practices": ["ベストプラクティス1", "ベストプラクティス2"],
    "anti_patterns": ["アンチパターン1", "アンチパターン2"],
    "skill_level_required": "必要スキルレベル"
  }}
}}
```

深い洞察と分析を提供してください。
        """
        
        result = self.execute_ai_analysis(prompt, "Stage 4: ディープ分析")
        if result:
            try:
                json_data = json.loads(result)
                self.save_stage_data("4_deep_insights", json_data)
                return json_data
            except json.JSONDecodeError:
                print("⚠️ Stage 4 JSON解析エラー、生データを保存")
                self.save_stage_data("4_deep_insights_raw", {"raw_output": result})
        return None
    
    def stage_5_final_synthesis(self):
        """Stage 5: 最終統合・MDドキュメント生成"""
        # 全段階のデータを読み込み
        all_data = {}
        for stage in ["1_basic", "2_deep_analysis", "3_consistency", "4_deep_insights"]:
            data = self.load_stage_data(stage)
            if data:
                all_data[stage] = data
        
        prompt = f"""
全ての分析結果を統合し、高品質なAIユースケースMarkdownドキュメントを生成してください。

📂 対象リポジトリ: {self.github_url}

## 全分析データ統合：

{json.dumps(all_data, ensure_ascii=False, indent=2)}

## Stage 5: 最終統合・ドキュメント生成

### 要求仕様：

1. **YAMLフロントマター（必須）**
```yaml
---
title: "[簡潔で魅力的なタイトル]"
summary: "[1-2文の的確な概要]"
category: "[開発プロセス自動化/データ分析/画像処理/自然言語処理/機械学習/ウェブ開発/その他]"
industry: "[IT・ソフトウェア/製造業/金融/ヘルスケア/教育/エンタメ/その他]"
createdAt: "{datetime.now().strftime('%Y-%m-%d')}"
updatedAt: "{datetime.now().strftime('%Y-%m-%d')}"
status: "[開発中/完了/実験的/アーカイブ/メンテナンス中]"
github_link: "{self.github_url}"
contributors:
  - "[実際のコントリビューター名]"
tags:
  - "[技術タグ1]"
  - "[技術タグ2]"
---
```

2. **Markdownドキュメント構造**
- # プロジェクトタイトル
- ## 概要
- ## 課題・ニーズ
- ## AI技術
- ## 実装フロー
- ## 主要機能
- ## 技術的詳細
- ## 期待される効果
- ## リスク・課題
- ## 応用・展開可能性
- ## コントリビューター
- ## 参考リンク

### 品質要件：
- 全分析データを活用した包括的な内容
- 技術的正確性と読みやすさの両立
- AIユースケースとしての価値を明確に表現
- 具体的で実用的な情報を含む

完全なMarkdownドキュメントを生成してください。
        """
        
        result = self.execute_ai_analysis(prompt, "Stage 5: 最終統合")
        if result:
            self.save_stage_data("5_final_output", {"markdown": result})
            # 最終出力に詳細ログへの参照を追加
            final_md = result
            log_dir = os.path.relpath(self.cli_outputs_dir, self.project_root)
            final_md += f"\n\n---\n*This document was generated by an AI assistant. For detailed analysis logs, see the `{log_dir}` directory.*"
            return final_md
        return None
    
    def execute_full_analysis(self):
        """全段階の分析を実行"""
        print(f"\n🚀 {self.ai_provider.upper()}多段階分析を開始します")
        print("=" * 60)
        
        # Stage 1: 基本情報収集
        print("\n[Stage 1/5] 基本情報収集")
        print("-" * 40)
        stage1_result = self.stage_1_basic_analysis()
        
        # Stage 2: 詳細コード分析
        print("\n[Stage 2/5] 詳細コード分析")
        print("-" * 40)
        stage2_result = self.stage_2_deep_code_analysis()
        
        # Stage 3: 整合性チェック
        print("\n[Stage 3/5] 整合性チェック・補完")
        print("-" * 40)
        stage3_result = self.stage_3_consistency_check()
        
        # Stage 4: ディープ分析
        print("\n[Stage 4/5] ディープ分析・洞察")
        print("-" * 40)
        stage4_result = self.stage_4_deep_insights()
        
        # Stage 5: 最終統合
        print("\n[Stage 5/5] 最終統合・ドキュメント生成")
        print("-" * 40)
        final_result = self.stage_5_final_synthesis()
        
        print("\n" + "=" * 60)
        print(f"🎉 {self.ai_provider.upper()}多段階分析完了！")
        
        return final_result

class UseCaseGenerator:
    def __init__(self, project_root):
        self.project_root = project_root
        self.use_cases_dir = os.path.join(project_root, "use-cases")
        self.scripts_dir = os.path.join(project_root, "scripts")
        self.cli_outputs_dir = os.path.join(project_root, ".cli_outputs")
        os.makedirs(self.cli_outputs_dir, exist_ok=True)
        
    def print_header(self):
        """ヘッダー表示"""
        print("=" * 60)
        print("🚀 AI Use Case自動生成ツール")
        print("=" * 60)
        
    def print_step(self, step, total, message):
        """ステップ表示"""
        print(f"\n[{step}/{total}] {message}")
        print("-" * 40)
        
    def check_github_auth(self):
        """GitHub認証状態をチェック"""
        try:
            # GitHub CLIの認証状態確認
            result = subprocess.run(["gh", "auth", "status"], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ GitHub CLI認証済み")
                return True
            else:
                print("⚠️ GitHub CLI未認証")
                return False
        except FileNotFoundError:
            print("⚠️ GitHub CLIが見つかりません")
            return False
        except Exception:
            return False
    
    def check_repo_accessibility(self, owner, repo):
        """リポジトリのアクセス可能性をチェック"""
        try:
            # GitHub API でリポジトリ情報を取得
            api_url = f"https://api.github.com/repos/{owner}/{repo}"
            
            if HAS_REQUESTS:
                # requestsを使用
                response = requests.get(api_url, timeout=10)
                status_code = response.status_code
                if status_code == 200:
                    repo_data = response.json()
                    return True, "public", repo_data
            else:
                # 標準ライブラリを使用
                try:
                    with urllib.request.urlopen(api_url, timeout=10) as response:
                        if response.status == 200:
                            repo_data = json.loads(response.read().decode())
                            return True, "public", repo_data
                        status_code = response.status
                except urllib.error.HTTPError as e:
                    status_code = e.code
                except urllib.error.URLError:
                    print("⚠️ ネットワーク接続エラー")
                    return False, "network_error", None
            
            if status_code == 404:
                # 404の場合、プライベートリポジトリの可能性
                print("🔒 プライベートリポジトリが検出されました")
                
                # GitHub CLI で認証済みの場合は再試行
                if self.check_github_auth():
                    try:
                        # gh api を使用して認証付きでアクセス
                        result = subprocess.run(
                            ["gh", "api", f"repos/{owner}/{repo}"],
                            capture_output=True, text=True, timeout=10
                        )
                        if result.returncode == 0:
                            repo_data = json.loads(result.stdout)
                            return True, "private", repo_data
                        else:
                            return False, "no_access", None
                    except Exception:
                        return False, "no_access", None
                else:
                    return False, "private_no_auth", None
            else:
                return False, "error", None
                
        except Exception as e:
            print(f"⚠️ API確認エラー: {str(e)}")
            return False, "error", None
    
    def handle_private_repo_access(self, owner, repo):
        """プライベートリポジトリのアクセス問題を処理"""
        print("\n" + "="*60)
        print("🔒 プライベートリポジトリアクセスの問題")
        print("="*60)
        
        print(f"\nリポジトリ '{owner}/{repo}' はプライベートです。")
        print("AIが分析するためには、以下のいずれかの方法が必要です：")
        
        print("\n📋 解決方法:")
        print("1. 【推奨】リポジトリを一時的にPublicにする")
        print("2. GitHub CLIで認証する")
        print("3. アクセス可能なPublicリポジトリを使用する")
        
        print("\n" + "-"*50)
        print("1️⃣ リポジトリをPublicにする方法:")
        print("-"*50)
        print("1. GitHubでリポジトリページを開く")
        print(f"   → https://github.com/{owner}/{repo}")
        print("2. [Settings] タブをクリック")
        print("3. 下部の [Danger Zone] まで移動")
        print("4. [Change visibility] → [Change to public] を選択")
        print("5. 確認メッセージに従って変更")
        print("💡 分析後に再度Privateに戻すことができます")
        
        print("\n" + "-"*50)
        print("2️⃣ GitHub CLI認証する方法:")
        print("-"*50)
        print("1. GitHub CLIをインストール:")
        print("   • macOS: brew install gh")
        print("   • Windows: winget install --id GitHub.cli")
        print("2. 認証を実行:")
        print("   gh auth login")
        print("3. ブラウザで認証手順に従う")
        
        print("\n" + "-"*50)
        print("3️⃣ 他の選択肢:")
        print("-"*50)
        print("• PublicなサンプルリポジトリのURLを使用")
        print("• フォークしてPublicリポジトリとして公開")
        
        # ユーザーの選択を求める
        print("\n" + "="*60)
        while True:
            choice = input("どのように進めますか？ [1: Public化完了/2: 認証完了/3: 別URL/q: 終了]: ").strip().lower()
            
            if choice == "1":
                print("\n🔄 リポジトリがPublicになったか確認中...")
                accessible, repo_type, repo_data = self.check_repo_accessibility(owner, repo)
                if accessible and repo_type == "public":
                    print("✅ リポジトリがPublicになりました！")
                    return True
                else:
                    print("❌ まだPrivateです。Public化を完了してから再試行してください。")
                    continue
                    
            elif choice == "2":
                print("\n🔄 GitHub CLI認証状態を確認中...")
                if self.check_github_auth():
                    accessible, repo_type, repo_data = self.check_repo_accessibility(owner, repo)
                    if accessible:
                        print("✅ 認証済みでアクセス可能です！")
                        return True
                    else:
                        print("❌ 認証はされていますが、リポジトリにアクセスできません。")
                        print("💡 リポジトリの所有者でない場合は、アクセス権限が必要です。")
                        continue
                else:
                    print("❌ まだ認証されていません。'gh auth login' を実行してから再試行してください。")
                    continue
                    
            elif choice == "3":
                return False  # 新しいURLの入力に戻る
                
            elif choice == "q":
                print("🚪 処理を終了します。")
                sys.exit(0)
            else:
                print("❌ 無効な選択です。1, 2, 3, または q を入力してください。")
    
    def validate_github_url(self, url):
        """GitHubURLの妥当性チェック（アクセス可能性も含む）"""
        parsed = urlparse(url)
        if parsed.netloc != 'github.com':
            return False, "GitHub URLではありません"
        
        path_parts = parsed.path.strip('/').split('/')
        if len(path_parts) < 2:
            return False, "有効なリポジトリURLではありません"
        
        owner, repo = path_parts[0], path_parts[1]
        
        # .git 拡張子を削除
        if repo.endswith('.git'):
            repo = repo[:-4]
        
        print(f"🔍 リポジトリアクセス確認中: {owner}/{repo}")
        
        # リポジトリのアクセス可能性をチェック
        accessible, repo_type, repo_data = self.check_repo_accessibility(owner, repo)
        
        if accessible:
            if repo_type == "public":
                print(f"✅ Publicリポジトリ: アクセス可能")
            elif repo_type == "private":
                print(f"✅ Privateリポジトリ: 認証済みでアクセス可能")
            return True, f"{owner}/{repo}"
        else:
            if repo_type == "private_no_auth":
                # プライベートリポジトリのアクセス問題を処理
                if self.handle_private_repo_access(owner, repo):
                    return True, f"{owner}/{repo}"
                else:
                    return False, "新しいURLを入力してください"
            elif repo_type == "no_access":
                return False, f"リポジトリ '{owner}/{repo}' にアクセスできません（権限不足）"
            elif repo_type == "network_error":
                return False, "ネットワーク接続エラー。インターネット接続を確認してください"
            else:
                return False, f"リポジトリ '{owner}/{repo}' が見つからないか、アクセスできません"
    
    def load_prompt_template(self):
        """プロンプトテンプレートを読み込み"""
        template_path = os.path.join(self.scripts_dir, "prompt_template.md")
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            print(f"⚠️ プロンプトテンプレートが見つかりません: {template_path}")
            return None
    
    def call_ai_cli(self, github_url, repo_name, ai_config):
        """AI CLIを呼び出してユースケース分析を実行"""
        
        ai_provider = ai_config.get('provider', 'gemini')
        precision = ai_config.get('precision', 'high')
        
        providers = ["gemini", "claude"] if ai_provider == "auto" else [ai_provider]
        
        for provider in providers:
            try:
                print(f"\n🤖 {provider.upper()} AI でリポジトリ分析開始")
                print(f"📂 対象リポジトリ: {repo_name}")
                
                if precision == "high":
                    # 高精度多段階分析
                    print(f"🔬 高精度多段階分析モード")
                    print(f"⏱️  予想時間: 10-15分（5段階分析）")
                    
                    # 一時ディレクトリを作成
                    with tempfile.TemporaryDirectory(prefix=f"{provider}_analysis_") as temp_dir:
                        analyzer = MultiStageAnalyzer(github_url, repo_name, temp_dir, self.cli_outputs_dir, provider)
                        result = analyzer.execute_full_analysis()
                        
                        if result:
                            print(f"\n📄 {provider.upper()}多段階分析結果:")
                            print("-" * 50)
                            # 最初の500文字を表示
                            preview = result[:500] + "..." if len(result) > 500 else result
                            print(preview)
                            print("-" * 50)
                            print(f"📊 総文字数: {len(result):,} 文字")
                            print(f"💾 分析データ保存: 一時ディレクトリ")
                            
                            return result
                        else:
                            print(f"❌ {provider.upper()}多段階分析に失敗しました")
                            if ai_provider != "auto":
                                return None
                            continue
                
                elif precision == "fast":
                    # 高速単発分析
                    print(f"⚡ 高速単発分析モード")
                    print(f"⏱️  予想時間: 1-3分")
                    
                    # 簡潔プロンプト構築
                    prompt = f"""
あなたはAIユースケース分析の専門家です。
GitHubリポジトリ {github_url} を効率的に分析して、統一されたフォーマットでユースケースドキュメントを生成します。

## 分析要求：
1. リポジトリの基本情報（目的、技術スタック、主要機能）
2. AI/ML技術の使用状況を特定
3. YAMLメタデータ付きMarkdownドキュメントを生成

## YAMLメタデータ構造（必須）：
```yaml
---
title: "[プロジェクトタイトル]"
summary: "[1-2文の概要]"
category: "[カテゴリ]"
industry: "[業界]"
createdAt: "{datetime.now().strftime('%Y-%m-%d')}"
updatedAt: "{datetime.now().strftime('%Y-%m-%d')}"
status: "[ステータス]"
github_link: "{github_url}"
contributors:
  - "[コントリビューター]"
tags:
  - "[技術タグ]"
---
```

{repo_name} リポジトリの効率的な分析を実行し、高品質なユースケースドキュメントを生成してください。
                    """
                    
                    # プログレスバー開始
                    progress = ProgressBar()
                    
                    # 非同期でプログレス表示
                    import threading
                    stop_progress = threading.Event()
                    
                    def show_progress():
                        while not stop_progress.is_set():
                            progress.show(f"{provider.upper()}高速分析中")
                    
                    progress_thread = threading.Thread(target=show_progress)
                    progress_thread.daemon = True
                    progress_thread.start()
                    
                    # AI CLI実行
                    if provider == "gemini":
                        cmd = ["gemini", "chat", "--prompt", prompt]
                        timeout = 120  # 2分
                    elif provider == "claude":
                        cmd = ["claude", prompt]
                        timeout = 120  # 2分
                    else:
                        continue
                    
                    result = subprocess.run(
                        cmd, 
                        capture_output=True, 
                        text=True, 
                        timeout=timeout
                    )
                    
                    # プログレス停止
                    stop_progress.set()
                    progress_thread.join(timeout=0.5)
                    
                    if result.returncode == 0:
                        progress.finish(f"{provider.upper()}高速分析完了")
                        
                        # 出力の詳細表示
                        output = extract_clean_output(result.stdout)
                        print(f"\n📄 {provider.upper()}高速分析結果:")
                        print("-" * 50)
                        # 最初の500文字を表示
                        preview = output[:500] + "..." if len(output) > 500 else output
                        print(preview)
                        print("-" * 50)
                        print(f"📊 総文字数: {len(output):,} 文字")
                        
                        return output
                    else:
                        progress.finish(f"{provider.upper()}高速分析失敗")
                        print(f"\n❌ {provider.upper()}実行エラー:")
                        print(f"終了コード: {result.returncode}")
                        if result.stderr:
                            print(f"エラー内容:\n{result.stderr}")
                        if result.stdout:
                            print(f"出力内容:\n{result.stdout}")
                        
                        if ai_provider != "auto":
                            return None
                        continue
                    
            except subprocess.TimeoutExpired:
                print(f"\n⏰ {provider.upper()}実行がタイムアウトしました")
                if ai_provider != "auto":
                    return None
                print(f"🔄 次のプロバイダーを試行します...")
                continue
            except FileNotFoundError:
                print(f"\n⚠️ {provider.upper()} CLIが見つかりません")
                print(f"インストール方法:")
                if provider == "claude":
                    print("- Claude CLI: https://github.com/anthropics/claude-code")
                else:
                    print("- Gemini CLI: npm install -g @google/generative-ai-cli")
                    
                if ai_provider != "auto":
                    return None
                print(f"🔄 次のプロバイダーを試行します...")
                continue
            except Exception as e:
                print(f"\n❌ {provider.upper()}で予期しないエラー: {str(e)}")
                if ai_provider != "auto":
                    return None
                print(f"🔄 次のプロバイダーを試行します...")
                continue
        
        print("\n❌ 利用可能なAI CLIが見つかりませんでした")
        print("\n💡 以下のいずれかをインストールしてください:")
        print("• Gemini CLI: npm install -g @google/generative-ai-cli")
        print("• Claude CLI: https://github.com/anthropics/claude-code")
        return None
    
    def extract_repo_name(self, github_url):
        """GitHubURLからリポジトリ名を抽出"""
        parsed = urlparse(github_url)
        path_parts = parsed.path.strip('/').split('/')
        return path_parts[1] if len(path_parts) >= 2 else "unknown_repo"
    
    def sanitize_filename(self, filename):
        """ファイル名に使用できない文字を除去"""
        return re.sub(r'[^\w\-_\.]', '_', filename)
    
    def save_usecase_file(self, content, repo_name):
        """生成されたユースケースファイルを保存"""
        os.makedirs(self.use_cases_dir, exist_ok=True)
        
        filename = f"{self.sanitize_filename(repo_name)}.md"
        filepath = os.path.join(self.use_cases_dir, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ ユースケースファイル保存: {filepath}")
            return filepath
        except Exception as e:
            print(f"❌ ファイル保存エラー: {str(e)}")
            return None
    
    def auto_git_operations(self, filepath, repo_name):
        """Git add, commit, push を自動実行"""
        try:
            os.chdir(self.project_root)
            
            print(f"\n[4/5] Git操作を実行中")
            print("-" * 40)
            
            # git status確認
            print("📊 Git状態確認中...")
            status_result = subprocess.run(["git", "status", "--porcelain"], 
                                         capture_output=True, text=True)
            if status_result.stdout.strip():
                print(f"変更ファイル数: {len(status_result.stdout.strip().split())}")
            
            # git add
            print("📁 ファイルをステージング中...")
            add_result = subprocess.run(["git", "add", filepath], 
                                      capture_output=True, text=True)
            if add_result.returncode != 0:
                print(f"⚠️ git add警告: {add_result.stderr}")
                return False
            
            print("✅ ファイルステージング完了")
            
            # commit message作成
            commit_msg = f"""feat: Add AI use case for {repo_name}

🤖 Generated with AI Use Case Generator

- Repository: {repo_name}
- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- Auto-generated content with AI analysis

Co-Authored-By: AI Assistant <noreply@ai-assistant.com>"""
            
            # git commit
            print("💾 コミット作成中...")
            commit_result = subprocess.run(["git", "commit", "-m", commit_msg], 
                                         capture_output=True, text=True)
            if commit_result.returncode == 0:
                print("✅ コミット完了")
                commit_hash = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                           capture_output=True, text=True).stdout.strip()
                print(f"📝 コミットハッシュ: {commit_hash}")
            else:
                print(f"⚠️ git commit警告: {commit_result.stderr}")
                if "nothing to commit" in commit_result.stdout:
                    print("💡 コミットする変更がありません")
                    return True
                return False
            
            # git push
            print("🚀 リモートにプッシュ中...")
            push_result = subprocess.run(["git", "push"], 
                                       capture_output=True, text=True)
            if push_result.returncode == 0:
                print("✅ プッシュ完了")
                print("🌐 リモートリポジトリに反映されました")
            else:
                print(f"⚠️ git push警告: {push_result.stderr}")
                print("💡 手動でプッシュが必要かもしれません: git push")
                return True  # commitは成功したのでTrueを返す
                
            return True
            
        except Exception as e:
            print(f"❌ Git操作エラー: {str(e)}")
            return False
    
    def generate_usecase(self, github_url, ai_config, auto_git=True):
        """メイン処理：GitHubURLからユースケース生成"""
        
        self.print_header()
        
        # URL検証
        self.print_step(1, 5, "URL検証")
        is_valid, repo_info = self.validate_github_url(github_url)
        if not is_valid:
            print(f"❌ URL検証エラー: {repo_info}")
            return False
        
        repo_name = self.extract_repo_name(github_url)
        print(f"✅ 有効なGitHubリポジトリ: {repo_name}")
        
        # AI CLI呼び出し
        self.print_step(2, 5, "AIによる分析・生成")
        content = self.call_ai_cli(github_url, repo_name, ai_config)
        if not content:
            print("\n❌ ユースケース生成に失敗しました")
            return False
        
        # ファイル保存
        self.print_step(3, 5, "ファイル保存")
        filepath = self.save_usecase_file(content, repo_name)
        if not filepath:
            return False
        
        print(f"✅ ファイル保存完了: {os.path.basename(filepath)}")
        
        # Git操作
        if auto_git:
            success = self.auto_git_operations(filepath, repo_name)
            if not success:
                print("⚠️ Git操作で問題が発生しましたが、ファイル生成は完了しています")
        
        # 完了報告
        self.print_step(5, 5, "完了")
        print("🎉 ユースケース生成が正常に完了しました！")
        print(f"📄 生成ファイル: {filepath}")
        
        if auto_git:
            print("🔄 Gitに自動コミット・プッシュ済み")
        else:
            print("💡 手動でGit操作を行ってください:")
            print(f"   git add {filepath}")
            print(f"   git commit -m 'Add use case for {repo_name}'")
            print(f"   git push")
        
        print("\n" + "=" * 60)
        return True

def main():
    parser = argparse.ArgumentParser(description='GitHubリポジトリからAIユースケースを自動生成')
    parser.add_argument('github_url', nargs='?', help='GitHubリポジトリURL')
    parser.add_argument('--project-root', default='.', help='プロジェクトルートディレクトリ')
    parser.add_argument('--ai-provider', choices=['gemini', 'claude', 'auto'], default='gemini', 
                       help='使用するAI CLI (default: gemini)')
    parser.add_argument('--precision', choices=['fast', 'high'], default='high',
                       help='分析精度モード (default: high)')
    parser.add_argument('--no-git', action='store_true', 
                       help='Git操作をスキップ（ファイル生成のみ）')
    
    args = parser.parse_args()
    
    # インタラクティブモード
    if not args.github_url:
        print("🚀 AI Use Case自動生成ツール")
        print("=" * 50)
        
        # URL入力ループ（プライベートリポジトリ対応）
        while True:
            github_url = input("GitHubリポジトリURLを入力してください: ").strip()
            
            if not github_url:
                print("❌ URLが入力されていません")
                continue
            
            # URL検証（アクセス可能性チェック含む）
            generator = UseCaseGenerator(args.project_root)
            is_valid, result = generator.validate_github_url(github_url)
            
            if is_valid:
                break
            elif result == "新しいURLを入力してください":
                print("\n🔄 新しいURLを入力してください。")
                continue
            else:
                print(f"❌ {result}")
                retry = input("別のURLを試しますか？ [Y/n]: ").strip().lower()
                if retry not in ['', 'y', 'yes']:
                    sys.exit(1)
                continue
            
        # AI Provider & 精度選択
        print("\n🤖 AI分析オプション選択:")
        print("1. Gemini 高精度（多段階分析・10-15分）")
        print("2. Gemini 高速（単発分析・1-3分）")
        print("3. Claude 高精度（多段階分析・10-15分）")
        print("4. Claude 高速（単発分析・1-3分）")
        print("5. 自動選択（高精度）")
        
        choice = input("選択してください [1-5, default: 1]: ").strip()
        
        ai_config_map = {
            "1": {"provider": "gemini", "precision": "high"},
            "2": {"provider": "gemini", "precision": "fast"},
            "3": {"provider": "claude", "precision": "high"},
            "4": {"provider": "claude", "precision": "fast"},
            "5": {"provider": "auto", "precision": "high"},
            "": {"provider": "gemini", "precision": "high"}
        }
        ai_config = ai_config_map.get(choice, {"provider": "gemini", "precision": "high"})
        
        # Git操作選択
        git_choice = input("\nGit操作を自動実行しますか？ [Y/n]: ").strip().lower()
        auto_git = git_choice in ['', 'y', 'yes']
    else:
        github_url = args.github_url
        ai_config = {"provider": args.ai_provider, "precision": args.precision}
        auto_git = not args.no_git
        
        # コマンドライン引数の場合もURL検証を実行
        generator = UseCaseGenerator(args.project_root)
        is_valid, result = generator.validate_github_url(github_url)
        if not is_valid:
            if result == "新しいURLを入力してください":
                print("❌ プライベートリポジトリアクセスがキャンセルされました")
            else:
                print(f"❌ URL検証エラー: {result}")
            sys.exit(1)
    
    # ジェネレーター初期化・実行
    generator = UseCaseGenerator(args.project_root)
    
    if generator.generate_usecase(github_url, ai_config, auto_git):
        sys.exit(0)
    else:
        print("\n💡 ヒント:")
        print("- Claude CLI: https://github.com/anthropics/claude-code")
        print("- Gemini CLI: npm install -g @google/generative-ai-cli")
        sys.exit(1)

def run_tests():    print("\n--- Running basic tests ---")    # Test case 1: Pure JSON output    json_output = '{\"key\": \"value\", \"number\": 123}'    test_input_1 = f"Some text before.\n```json\n{json_output}\n```\nSome text after."    expected_output_1 = json_output    assert extract_clean_output(test_input_1) == expected_output_1, f"Test 1 failed: {extract_clean_output(test_input_1)}"    print("✅ Test 1 (JSON in code block) passed.")    # Test case 2: Pure Markdown output    md_output = "# Title\n\n- Item 1\n- Item 2"    test_input_2 = f"```markdown\n{md_output}\n```"    expected_output_2 = md_output    assert extract_clean_output(test_input_2) == expected_output_2, f"Test 2 failed: {extract_clean_output(test_input_2)}"    print("✅ Test 2 (Markdown in code block) passed.")    # Test case 3: YAML front matter Markdown    yaml_md_output = "---\ntitle: \"Test\"\n---\n# Content\nThis is content."    test_input_3 = f"Some preamble.\n{yaml_md_output}\nSome postamble."    expected_output_3 = yaml_md_output    assert extract_clean_output(test_input_3) == expected_output_3, f"Test 3 failed: {extract_clean_output(test_input_3)}"    print("✅ Test 3 (YAML front matter Markdown) passed.")    # Test case 4: Mixed content, should prioritize JSON    mixed_output = f"Some text.\n```json\n{json_output}\n```\n```markdown\n{md_output}\n```"    expected_output_4 = json_output    assert extract_clean_output(mixed_output) == expected_output_4, f"Test 4 failed: {extract_clean_output(mixed_output)}"    print("✅ Test 4 (Mixed content - JSON priority) passed.")    # Test case 5: No code blocks, just plain text    plain_text_output = "This is just plain text with no special blocks."    assert extract_clean_output(plain_text_output) == plain_text_output, f"Test 5 failed: {extract_clean_output(plain_text_output)}"    print("✅ Test 5 (Plain text) passed.")    # Test case 6: JSON directly without code block    direct_json_output = '{\"status\": \"success\", \"data\": [1, 2, 3]}'    assert extract_clean_output(direct_json_output) == direct_json_output, f"Test 6 failed: {extract_clean_output(direct_json_output)}"    print("✅ Test 6 (Direct JSON) passed.")    print("--- All basic tests passed! ---")if __name__ == "__main__":    parser = argparse.ArgumentParser(description='GitHubリポジトリからAIユースケースを自動生成')    parser.add_argument('github_url', nargs='?', help='GitHubリポジトリURL')    parser.add_argument('--project-root', default='.', help='プロジェクトルートディレクトリ')    parser.add_argument('--ai-provider', choices=['gemini', 'claude', 'auto'], default='gemini',                        help='使用するAI CLI (default: gemini)')    parser.add_argument('--precision', choices=['fast', 'high'], default='high',                       help='分析精度モード (default: high)')    parser.add_argument('--no-git', action='store_true',                        help='Git操作をスキップ（ファイル生成のみ）')    parser.add_argument('--test', action='store_true',                        help='Run basic tests and exit')        args = parser.parse_args()    if args.test:        run_tests()        sys.exit(0)    # インタラクティブモード    if not args.github_url:        print("🚀 AI Use Case自動生成ツール")        print("=" * 50)                # URL入力ループ（プライベートリポジトリ対応）        while True:            github_url = input("GitHubリポジトリURLを入力してください: ").strip()                        if not github_url:                print("❌ URLが入力されていません")                continue                        # URL検証（アクセス可能性チェック含む）            generator = UseCaseGenerator(args.project_root)            is_valid, result = generator.validate_github_url(github_url)                        if is_valid:                break            elif result == "新しいURLを入力してください":                print("\n🔄 新しいURLを入力してください。")                continue            else:                print(f"❌ {result}")                retry = input("別のURLを試しますか？ [Y/n]: ").strip().lower()                if retry not in ['', 'y', 'yes']:                    sys.exit(1)                continue                    # AI Provider & 精度選択        print("\n🤖 AI分析オプション選択:")        print("1. Gemini 高精度（多段階分析・10-15分）")        print("2. Gemini 高速（単発分析・1-3分）")        print("3. Claude 高精度（多段階分析・10-15分）")        print("4. Claude 高速（単発分析・1-3分）")        print("5. 自動選択（高精度）")                choice = input("選択してください [1-5, default: 1]: ").strip()                ai_config_map = {            "1": {"provider": "gemini", "precision": "high"},            "2": {"provider": "gemini", "precision": "fast"},            "3": {"provider": "claude", "precision": "high"},            "4": {"provider": "claude", "precision": "fast"},            "5": {"provider": "auto", "precision": "high"},            "": {"provider": "gemini", "precision": "high"}        }        ai_config = ai_config_map.get(choice, {"provider": "gemini", "precision": "high"})                # Git操作選択        git_choice = input("\nGit操作を自動実行しますか？ [Y/n]: ").strip().lower()        auto_git = git_choice in ['', 'y', 'yes']    else:        github_url = args.github_url        ai_config = {"provider": args.ai_provider, "precision": args.precision}        auto_git = not args.no_git                # コマンドライン引数の場合もURL検証を実行        generator = UseCaseGenerator(args.project_root)        is_valid, result = generator.validate_github_url(github_url)        if not is_valid:            if result == "新しいURLを入力してください":                print("❌ プライベートリポジトリアクセスがキャンセルされました")            else:                print(f"❌ URL検証エラー: {result}")            sys.exit(1)        # ジェネレーター初期化・実行    generator = UseCaseGenerator(args.project_root)        if generator.generate_usecase(github_url, ai_config, auto_git):        sys.exit(0)    else:        print("\n💡 ヒント:")        print("- Claude CLI: https://github.com/anthropics/claude-code")        print("- Gemini CLI: npm install -g @google/generative-ai-cli")        sys.exit(1)