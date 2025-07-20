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
import base64
import getpass

# 暗号化機能（オプショナル）
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

# requestsの代替として標準ライブラリを使用
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.request
    import urllib.error
    HAS_REQUESTS = False

class APIKeyManager:
    """APIキーの暗号化保存・復号化を管理"""
    
    def __init__(self, config_dir):
        self.config_dir = config_dir
        self.key_file = os.path.join(config_dir, ".api_keys.enc")
        os.makedirs(config_dir, exist_ok=True)
        
    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """パスワードから暗号化キーを導出"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))
    
    def save_api_key(self, service: str, api_key: str, password: str):
        """APIキーを暗号化して保存"""
        if not HAS_CRYPTOGRAPHY:
            print("⚠️ 暗号化ライブラリが利用できません。'pip install cryptography' でインストールしてください")
            return False
        
        try:
            # 既存のキーファイルを読み込むか、新規作成
            data = {}
            salt = os.urandom(16)
            
            if os.path.exists(self.key_file):
                # 既存ファイルから塩を読み込み
                with open(self.key_file, 'rb') as f:
                    salt = f.read(16)
                    encrypted_data = f.read()
                
                # 復号化して既存データを取得
                key = self._derive_key(password, salt)
                fernet = Fernet(key)
                decrypted_data = fernet.decrypt(encrypted_data)
                data = json.loads(decrypted_data.decode())
            
            # 新しいAPIキーを追加
            data[service] = api_key
            
            # 暗号化して保存
            key = self._derive_key(password, salt)
            fernet = Fernet(key)
            encrypted_data = fernet.encrypt(json.dumps(data).encode())
            
            with open(self.key_file, 'wb') as f:
                f.write(salt)
                f.write(encrypted_data)
            
            print(f"✅ {service} APIキーを暗号化保存しました")
            return True
            
        except Exception as e:
            print(f"❌ APIキー保存エラー: {e}")
            return False
    
    def load_api_key(self, service: str, password: str) -> str:
        """暗号化されたAPIキーを復号化して取得"""
        if not HAS_CRYPTOGRAPHY:
            return None
        
        try:
            if not os.path.exists(self.key_file):
                return None
            
            with open(self.key_file, 'rb') as f:
                salt = f.read(16)
                encrypted_data = f.read()
            
            key = self._derive_key(password, salt)
            fernet = Fernet(key)
            decrypted_data = fernet.decrypt(encrypted_data)
            data = json.loads(decrypted_data.decode())
            
            return data.get(service)
            
        except Exception:
            return None
    
    def has_stored_keys(self) -> bool:
        """保存されたAPIキーファイルが存在するか確認"""
        return os.path.exists(self.key_file)

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
    
    # 1. YAMLフロントマター付きのMarkdown全体を検索（最優先）
    md_search = re.search(r"^---\s*\n.*?\n---\s*\n.*", raw_output, re.DOTALL)
    if md_search:
        return md_search.group(0)

    # 2. ```markdown ... ``` ブロックを検索
    md_block_search = re.search(r"```markdown\s*(.*?)\s*```", raw_output, re.DOTALL)
    if md_block_search:
        return md_block_search.group(1)

    # 3. ```json ... ``` ブロックを検索
    json_search = re.search(r"```(json)?\s*(\{.*?\})\s*```", raw_output, re.DOTALL)
    if json_search:
        try:
            json.loads(json_search.group(2))
            return json_search.group(2)
        except json.JSONDecodeError:
            pass

    # 4. JSONオブジェクトを直接検索（より包括的な検索）
    # 複数行にわたるJSONを処理
    lines = raw_output.split('\n')
    json_lines = []
    in_json = False
    brace_count = 0
    
    for line in lines:
        # JSONの開始を検出
        if '{' in line and not in_json:
            in_json = True
            brace_count = line.count('{') - line.count('}')
            json_lines.append(line)
        elif in_json:
            brace_count += line.count('{') - line.count('}')
            json_lines.append(line)
            # JSONの終了を検出
            if brace_count <= 0:
                break
    
    if json_lines:
        potential_json = '\n'.join(json_lines)
        # 最初の{から最後の}までを抽出
        start_idx = potential_json.find('{')
        end_idx = potential_json.rfind('}') + 1
        if start_idx != -1 and end_idx > start_idx:
            potential_json = potential_json[start_idx:end_idx]
            try:
                json.loads(potential_json)
                return potential_json
            except json.JSONDecodeError:
                pass

    # 5. 単純なJSONオブジェクト検索（元の方法）
    json_start = raw_output.find('{')
    json_end = raw_output.rfind('}') + 1
    if json_start != -1 and json_end > json_start:
        potential_json = raw_output[json_start:json_end]
        try:
            json.loads(potential_json)
            return potential_json
        except json.JSONDecodeError:
            pass

    # 6. 何も見つからない場合は、前後の空白を除去してそのまま返す
    return raw_output.strip()


class MultiStageAnalyzer:
    """高精度多段階分析エンジン（Gemini/Claude対応）"""
    
    def __init__(self, github_url, repo_name, temp_dir, cli_outputs_dir, ai_provider="gemini", openai_api_key=None):
        self.github_url = github_url
        self.repo_name = repo_name
        self.temp_dir = temp_dir
        self.cli_outputs_dir = cli_outputs_dir
        self.ai_provider = ai_provider
        self.openai_api_key = openai_api_key
        self.analysis_data = {}
        self.project_root = os.path.dirname(cli_outputs_dir)
        
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
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    timeout=timeout
                )
            elif self.ai_provider == "claude":
                cmd = ["claude", prompt]
                timeout = 300  # 5分
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    timeout=timeout
                )
            elif self.ai_provider == "chatgpt":
                # ChatGPT API呼び出し
                result = self._call_chatgpt_api(prompt)
                timeout = 300  # 5分
            else:
                raise ValueError(f"Unsupported AI provider: {self.ai_provider}")
            
            stop_progress.set()
            progress_thread.join(timeout=0.5)
            
            # CLIの生出力をログファイルに保存
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_stage_name = re.sub(r'[^\w\-_]', '_', stage_name)
            raw_output_filename = f"{timestamp}_{self.repo_name}_{safe_stage_name}.log"
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
                # クォータエラーかどうかチェック
                if "Quota exceeded" in result.stderr or "429" in result.stderr:
                    print(f"⚠️ {self.ai_provider.upper()} APIクォータ制限に達しました")
                    print(f"💡 別のAIプロバイダーを試すか、時間をおいて再実行してください")
                else:
                    print(f"❌ エラー: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            stop_progress.set()
            progress.finish(f"{stage_name} タイムアウト")
            print(f"⏰ {self.ai_provider.upper()} {stage_name} がタイムアウトしました")
            return None
        except Exception as e:
            stop_progress.set()
            progress.finish(f"{stage_name} エラー")
            print(f"❌ {self.ai_provider.upper()} {stage_name} でエラーが発生しました: {e}")
            return None
    
    def _call_chatgpt_api(self, prompt):
        """ChatGPT APIを呼び出す"""
        try:
            if not self.openai_api_key:
                raise ValueError("OpenAI API key is required for ChatGPT")
            
            if not HAS_REQUESTS:
                raise ValueError("requests library is required for ChatGPT API")
            
            headers = {
                "Authorization": f"Bearer {self.openai_api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": "gpt-4o",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 4000,
                "temperature": 0.7
            }
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=300
            )
            
            if response.status_code == 200:
                result_data = response.json()
                content = result_data['choices'][0]['message']['content']
                
                # subprocess.run結果と同じ形式にラップ
                class MockResult:
                    def __init__(self, stdout, stderr="", returncode=0):
                        self.stdout = stdout
                        self.stderr = stderr
                        self.returncode = returncode
                
                return MockResult(content)
            else:
                error_msg = f"ChatGPT API error: {response.status_code} - {response.text}"
                return MockResult("", error_msg, 1)
                
        except Exception as e:
            return MockResult("", str(e), 1)
    
    def stage_1_basic_analysis(self):
        """Stage 1: 基本情報収集"""
        prompt = f"""
GitHubリポジトリ {self.github_url} を分析して、以下のJSON形式で回答してください。

重要：必ずJSONのみで回答し、説明や追加テキストは含めないでください。

{{
  "repository_name": "リポジトリ名",
  "description": "リポジトリの説明",
  "main_purpose": "主な目的",
  "tech_stack": {{
    "languages": ["言語1", "言語2"],
    "frameworks": ["フレームワーク1", "フレームワーク2"],
    "libraries": ["ライブラリ1", "ライブラリ2"]
  }},
  "file_structure": {{
    "key_directories": ["ディレクトリ1", "ディレクトリ2"],
    "important_files": ["ファイル1", "ファイル2"]
  }},
  "documentation": {{
    "has_readme": true,
    "readme_quality": "良好",
    "other_docs": ["ドキュメント1", "ドキュメント2"]
  }},
  "contributors": ["コントリビューター1", "コントリビューター2"],
  "license": "ライセンス名"
}}
        """
        
        result = self.execute_ai_analysis(prompt, "Stage 1: 基本情報収集")
        if result:
            try:
                # JSONデータを抽出
                json_data = json.loads(result)
                self.save_stage_data("1_basic", json_data)
                return json_data
            except json.JSONDecodeError:
                print("⚠️ Stage 1 JSON解析エラー、フォールバック用データを生成")
                # フォールバック用の基本データを生成
                fallback_data = {
                    "repository_name": self.repo_name,
                    "description": "GitHub repository analysis",
                    "main_purpose": "Code repository",
                    "tech_stack": {
                        "languages": ["Unknown"],
                        "frameworks": ["Unknown"],
                        "libraries": ["Unknown"]
                    },
                    "file_structure": {
                        "key_directories": ["Unknown"],
                        "important_files": ["Unknown"]
                    },
                    "documentation": {
                        "has_readme": True,
                        "readme_quality": "Unknown",
                        "other_docs": ["Unknown"]
                    },
                    "contributors": ["Unknown"],
                    "license": "Unknown"
                }
                self.save_stage_data("1_basic", fallback_data)
                self.save_stage_data("1_basic_raw", {"raw_output": result})
                print("✅ フォールバックデータを使用してStage 2に継続")
                return fallback_data
        return None
    
    def stage_2_deep_code_analysis(self):
        """Stage 2: 詳細コード分析"""
        stage1_data = self.load_stage_data("1_basic")
        
        if not stage1_data:
            print("⚠️ Stage 1データが利用できません。Stage 2をスキップします。")
            return None
        
        prompt = f"""
リポジトリ {self.github_url} のコードを詳細に分析してください。

## Stage 1で得られた基本情報：
{json.dumps(stage1_data, ensure_ascii=False, indent=2)}

## 詳細分析項目：
1. コードの品質・構造分析
2. アーキテクチャパターンの特定
3. 設計原則の適用状況
4. テストカバレッジと品質
5. セキュリティ上の考慮事項
6. パフォーマンス特性
7. 拡張性・保守性の評価

## 回答形式：
以下のJSON形式で厳密に回答してください：

```json
{{
  "code_quality": {{
    "overall_rating": "優秀/良好/普通/改善必要",
    "code_style": "一貫性の評価",
    "documentation": "コメント・ドキュメントの評価"
  }},
  "architecture": {{
    "pattern": "アーキテクチャパターン名",
    "design_principles": ["原則1", "原則2"],
    "modularity": "モジュール性の評価"
  }},
  "testing": {{
    "has_tests": true/false,
    "test_coverage": "カバレッジ推定",
    "test_quality": "テスト品質評価"
  }},
  "security": {{
    "security_practices": ["実践1", "実践2"],
    "potential_risks": ["リスク1", "リスク2"]
  }},
  "performance": {{
    "optimization_level": "最適化レベル",
    "bottlenecks": ["ボトルネック1", "ボトルネック2"]
  }},
  "maintainability": {{
    "code_complexity": "複雑度評価",
    "extensibility": "拡張性評価",
    "refactoring_needs": ["改善点1", "改善点2"]
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
                print("⚠️ Stage 2 JSON解析エラー、フォールバック用データを生成")
                fallback_data = {
                    "code_quality": {
                        "overall_rating": "普通",
                        "code_style": "Unknown",
                        "documentation": "Unknown"
                    },
                    "architecture": {
                        "pattern": "Unknown",
                        "design_principles": ["Unknown"],
                        "modularity": "Unknown"
                    },
                    "testing": {
                        "has_tests": False,
                        "test_coverage": "Unknown",
                        "test_quality": "Unknown"
                    },
                    "security": {
                        "security_practices": ["Unknown"],
                        "potential_risks": ["Unknown"]
                    },
                    "performance": {
                        "optimization_level": "Unknown",
                        "bottlenecks": ["Unknown"]
                    },
                    "maintainability": {
                        "code_complexity": "Unknown",
                        "extensibility": "Unknown",
                        "refactoring_needs": ["Unknown"]
                    }
                }
                self.save_stage_data("2_deep_analysis", fallback_data)
                self.save_stage_data("2_deep_analysis_raw", {"raw_output": result})
                print("✅ フォールバックデータを使用してStage 3に継続")
                return fallback_data
        return None
    
    def stage_3_consistency_check(self):
        """Stage 3: 整合性チェックと補完"""
        stage1_data = self.load_stage_data("1_basic")
        stage2_data = self.load_stage_data("2_deep_analysis")
        
        if not stage1_data or not stage2_data:
            print("⚠️ 前段階のデータが不足しています。Stage 3をスキップします。")
            return None
        
        prompt = f"""
これまでの分析結果の整合性をチェックし、不足情報を補完してください。

## Stage 1 基本情報：
{json.dumps(stage1_data, ensure_ascii=False, indent=2)}

## Stage 2 詳細分析：
{json.dumps(stage2_data, ensure_ascii=False, indent=2)}

## チェック・補完項目：
1. 情報の整合性確認
2. 不足している技術的詳細の補完
3. AI/ML技術の使用状況の特定
4. ビジネス価値・実用性の評価
5. 競合優位性の分析
6. 改善提案の具体化

## 回答形式：
以下のJSON形式で厳密に回答してください：

```json
{{
  "consistency_check": {{
    "data_consistency": "整合性評価",
    "contradictions": ["矛盾点1", "矛盾点2"],
    "missing_info": ["不足情報1", "不足情報2"]
  }},
  "ai_ml_usage": {{
    "uses_ai_ml": true/false,
    "ai_technologies": ["技術1", "技術2"],
    "ml_frameworks": ["フレームワーク1", "フレームワーク2"],
    "ai_applications": ["用途1", "用途2"]
  }},
  "business_value": {{
    "target_users": ["ユーザー1", "ユーザー2"],
    "business_problems": ["課題1", "課題2"],
    "value_proposition": "価値提案",
    "market_potential": "市場ポテンシャル"
  }},
  "competitive_advantage": {{
    "unique_features": ["特徴1", "特徴2"],
    "differentiation": "差別化要因",
    "innovation_level": "革新性レベル"
  }},
  "improvement_suggestions": ["改善案1", "改善案2"]
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
                print("⚠️ Stage 3 JSON解析エラー、フォールバック用データを生成")
                fallback_data = {
                    "consistency_check": {
                        "data_consistency": "普通",
                        "contradictions": ["Unknown"],
                        "missing_info": ["Unknown"]
                    },
                    "ai_ml_usage": {
                        "uses_ai_ml": False,
                        "ai_technologies": ["Unknown"],
                        "ml_frameworks": ["Unknown"],
                        "ai_applications": ["Unknown"]
                    },
                    "business_value": {
                        "target_users": ["Unknown"],
                        "business_problems": ["Unknown"],
                        "value_proposition": "Unknown",
                        "market_potential": "Unknown"
                    },
                    "competitive_advantage": {
                        "unique_features": ["Unknown"],
                        "differentiation": "Unknown",
                        "innovation_level": "Unknown"
                    },
                    "improvement_suggestions": ["Unknown"]
                }
                self.save_stage_data("3_consistency", fallback_data)
                self.save_stage_data("3_consistency_raw", {"raw_output": result})
                print("✅ フォールバックデータを使用してStage 4に継続")
                return fallback_data
        return None
    
    def stage_4_deep_insights(self):
        """Stage 4: ディープ分析・洞察"""
        stage1_data = self.load_stage_data("1_basic")
        stage2_data = self.load_stage_data("2_deep_analysis")
        stage3_data = self.load_stage_data("3_consistency")
        
        if not all([stage1_data, stage2_data, stage3_data]):
            print("⚠️ 前段階のデータが不足しています。Stage 4をスキップします。")
            return None
        
        prompt = f"""
これまでの全分析結果を統合し、深い洞察と戦略的視点を提供してください。

## 統合データ：
### Stage 1 基本情報：
{json.dumps(stage1_data, ensure_ascii=False, indent=2)}

### Stage 2 詳細分析：
{json.dumps(stage2_data, ensure_ascii=False, indent=2)}

### Stage 3 整合性・補完：
{json.dumps(stage3_data, ensure_ascii=False, indent=2)}

## 深い洞察項目：
1. 技術的革新性と将来性
2. 実装の複雑さと実現可能性
3. スケーラビリティとパフォーマンス予測
4. リスク分析と対策
5. 投資対効果と ROI 予測
6. 他分野への応用可能性
7. 業界トレンドとの整合性

## 回答形式：
以下のJSON形式で厳密に回答してください：

```json
{{
  "innovation_analysis": {{
    "innovation_level": "革新レベル（1-10）",
    "future_potential": "将来性評価",
    "technology_maturity": "技術成熟度",
    "adoption_barriers": ["導入障壁1", "導入障壁2"]
  }},
  "implementation_complexity": {{
    "complexity_rating": "複雑度（1-10）",
    "development_time": "開発期間予測",
    "required_expertise": ["必要専門知識1", "必要専門知識2"],
    "infrastructure_needs": ["インフラ要件1", "インフラ要件2"]
  }},
  "scalability_performance": {{
    "scalability_potential": "スケーラビリティポテンシャル",
    "performance_bottlenecks": ["ボトルネック1", "ボトルネック2"],
    "optimization_opportunities": ["最適化機会1", "最適化機会2"]
  }},
  "risk_analysis": {{
    "technical_risks": ["技術リスク1", "技術リスク2"],
    "business_risks": ["ビジネスリスク1", "ビジネスリスク2"],
    "mitigation_strategies": ["対策1", "対策2"]
  }},
  "roi_analysis": {{
    "investment_level": "投資レベル",
    "expected_returns": "期待収益",
    "payback_period": "投資回収期間",
    "cost_benefit_ratio": "コストベネフィット比"
  }},
  "application_potential": {{
    "other_industries": ["適用可能業界1", "適用可能業界2"],
    "extension_possibilities": ["拡張可能性1", "拡張可能性2"],
    "ecosystem_impact": "エコシステムへの影響"
  }},
  "industry_alignment": {{
    "current_trends": ["トレンド1", "トレンド2"],
    "market_timing": "市場タイミング評価",
    "competitive_landscape": "競合状況"
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
                print("⚠️ Stage 4 JSON解析エラー、フォールバック用データを生成")
                fallback_data = {
                    "innovation_analysis": {
                        "innovation_level": "5",
                        "future_potential": "普通",
                        "technology_maturity": "普通",
                        "adoption_barriers": ["Unknown"]
                    },
                    "implementation_complexity": {
                        "complexity_rating": "5",
                        "development_time": "Unknown",
                        "required_expertise": ["Unknown"],
                        "infrastructure_needs": ["Unknown"]
                    },
                    "scalability_performance": {
                        "scalability_potential": "普通",
                        "performance_bottlenecks": ["Unknown"],
                        "optimization_opportunities": ["Unknown"]
                    },
                    "risk_analysis": {
                        "technical_risks": ["Unknown"],
                        "business_risks": ["Unknown"],
                        "mitigation_strategies": ["Unknown"]
                    },
                    "roi_analysis": {
                        "investment_level": "普通",
                        "expected_returns": "Unknown",
                        "payback_period": "Unknown",
                        "cost_benefit_ratio": "Unknown"
                    },
                    "application_potential": {
                        "other_industries": ["Unknown"],
                        "extension_possibilities": ["Unknown"],
                        "ecosystem_impact": "Unknown"
                    },
                    "industry_alignment": {
                        "current_trends": ["Unknown"],
                        "market_timing": "普通",
                        "competitive_landscape": "Unknown"
                    }
                }
                self.save_stage_data("4_deep_insights", fallback_data)
                self.save_stage_data("4_deep_insights_raw", {"raw_output": result})
                print("✅ フォールバックデータを使用してStage 5に継続")
                return fallback_data
        return None
    
    def stage_5_final_synthesis(self):
        """Stage 5: 最終統合・MDドキュメント生成"""
        # 全段階のデータを読み込み
        stage1_data = self.load_stage_data("1_basic")
        stage2_data = self.load_stage_data("2_deep_analysis")
        stage3_data = self.load_stage_data("3_consistency")
        stage4_data = self.load_stage_data("4_deep_insights")
        
        # 既存の良いサンプルを参考例として読み込み
        sample_usecase = self._load_sample_usecase()
        template = self._load_template()
        
        prompt = f"""
あなたはAIユースケース分析の専門家です。GitHubリポジトリを分析して、高品質なユースケースドキュメントを作成してください。

## 分析対象
- **リポジトリ**: {self.github_url}
- **プロジェクト名**: {self.repo_name}

## 利用可能な分析データ
{self._format_analysis_data_for_prompt(stage1_data, stage2_data, stage3_data, stage4_data)}

## 参考フォーマット（良いサンプル）
{sample_usecase}

## 必須要求事項

1. **厳密なYAMLフロントマター**（以下の形式を必ず使用）：
```yaml
---
title: "[具体的で分かりやすいプロジェクトタイトル]"
summary: "[1-2文の簡潔で的確な概要]"
category: "[適切なカテゴリ：AIユースケース/Web開発/データ分析/モバイルアプリ/ツール/ライブラリ/その他]"
industry: "[対象業界：IT・ソフトウェア/製造業/金融/ヘルスケア/教育/エンタメ/その他]"
createdAt: {datetime.now().strftime('%Y-%m-%d')}
updatedAt: {datetime.now().strftime('%Y-%m-%d')}
status: "[開発中/完了/実験的/アーカイブ/メンテナンス中]"
github_link: {self.github_url}
contributors:
  - "[実際のコントリビューター名]"
tags:
  - "[主要技術タグ1]"
  - "[主要技術タグ2]"
  - "[主要技術タグ3]"
---
```

2. **高品質なMarkdown構造**：
- リポジトリの実際の内容に基づいた正確な分析
- 技術的詳細の具体性
- 実用的価値の明確化
- 読みやすく構造化された文章

3. **品質基準**：
- 分析データを活用した具体的な内容
- 技術的正確性の重視
- AIエラーメッセージや不要な情報は含めない
- プロフェッショナルで読みやすい文章

4. **禁止事項**：
- エラーメッセージの混入
- 不完全な情報での推測
- テンプレート的な汎用表現の多用

完全で高品質なMarkdownドキュメントを生成してください。
        """
        
        result = self.execute_ai_analysis(prompt, "Stage 5: 最終統合")
        if result:
            self.save_stage_data("5_final_output", {"markdown": result})
            return result
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
    
    def _load_sample_usecase(self):
        """良いサンプルのユースケースを読み込み"""
        try:
            sample_path = os.path.join(self.project_root, "use-cases", "AIエージェントによるプロジェクト初期構築支援.md")
            if os.path.exists(sample_path):
                with open(sample_path, 'r', encoding='utf-8') as f:
                    return f.read()
        except:
            pass
        return ""
    
    def _load_template(self):
        """テンプレートファイルを読み込み"""
        try:
            template_path = os.path.join(os.path.dirname(self.temp_dir), "../scripts/usecase_template.md")
            if os.path.exists(template_path):
                with open(template_path, 'r', encoding='utf-8') as f:
                    return f.read()
        except:
            pass
        return ""
    
    def _format_analysis_data_for_prompt(self, stage1_data, stage2_data, stage3_data, stage4_data):
        """分析データをプロンプト用に整形"""
        formatted = []
        
        if stage1_data:
            formatted.append("### 基本情報:")
            formatted.append(f"- リポジトリ名: {stage1_data.get('repository_name', 'Unknown')}")
            formatted.append(f"- 説明: {stage1_data.get('description', 'Unknown')}")
            formatted.append(f"- 目的: {stage1_data.get('main_purpose', 'Unknown')}")
            if stage1_data.get('tech_stack'):
                tech = stage1_data['tech_stack']
                formatted.append(f"- 主要言語: {', '.join(tech.get('languages', []))}")
                formatted.append(f"- フレームワーク: {', '.join(tech.get('frameworks', []))}")
        
        if stage3_data and stage3_data.get('ai_ml_usage'):
            ai_usage = stage3_data['ai_ml_usage']
            formatted.append("### AI/ML技術:")
            formatted.append(f"- AI/ML使用: {'はい' if ai_usage.get('uses_ai_ml') else 'いいえ'}")
            if ai_usage.get('ai_technologies'):
                formatted.append(f"- AI技術: {', '.join(ai_usage.get('ai_technologies', []))}")
        
        if stage4_data and stage4_data.get('innovation_analysis'):
            innovation = stage4_data['innovation_analysis']
            formatted.append("### 革新性:")
            formatted.append(f"- 革新レベル: {innovation.get('innovation_level', 'Unknown')}")
            formatted.append(f"- 将来性: {innovation.get('future_potential', 'Unknown')}")
        
        return "\n".join(formatted) if formatted else "分析データが利用できません。リポジトリを直接調査して分析してください。"
    
    def _load_reference_usecase(self):
        """高速分析用の参考ユースケースを読み込み"""
        try:
            sample_path = os.path.join(self.project_root, "use-cases", "AIエージェントによるプロジェクト初期構築支援.md")
            if os.path.exists(sample_path):
                with open(sample_path, 'r', encoding='utf-8') as f:
                    return f.read()
        except:
            pass
        return ""

class UseCaseGenerator:
    def __init__(self, project_root):
        self.project_root = project_root
        self.use_cases_dir = os.path.join(project_root, "use-cases")
        self.scripts_dir = os.path.join(project_root, "scripts")
        self.cli_outputs_dir = os.path.join(project_root, ".cli_outputs")
        self.config_dir = os.path.join(project_root, ".config")
        self.api_manager = APIKeyManager(self.config_dir)
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
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def check_repo_accessibility(self, owner, repo):
        """リポジトリのアクセス可能性をチェック"""
        
        if HAS_REQUESTS:
            try:
                # GitHub API経由でリポジトリ情報を取得
                url = f"https://api.github.com/repos/{owner}/{repo}"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    repo_data = response.json()
                    if repo_data.get("private", False):
                        return True, "private", repo_data
                    else:
                        return True, "public", repo_data
                elif response.status_code == 404:
                    # プライベートリポジトリまたは存在しないリポジトリ
                    return False, "private_or_not_found", None
                else:
                    return False, "no_access", None
                    
            except requests.RequestException:
                return False, "network_error", None
        else:
            # urllib.requestを使用したフォールバック
            try:
                import urllib.request
                import urllib.error
                
                url = f"https://api.github.com/repos/{owner}/{repo}"
                req = urllib.request.Request(url)
                
                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status == 200:
                        import json
                        repo_data = json.loads(response.read().decode())
                        if repo_data.get("private", False):
                            return True, "private", repo_data
                        else:
                            return True, "public", repo_data
                            
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return False, "private_or_not_found", None
                else:
                    return False, "no_access", None
            except Exception:
                return False, "network_error", None
        
        return False, "unknown_error", None
    
    def handle_private_repo_access(self, owner, repo):
        """プライベートリポジトリのアクセス処理"""
        print(f"\n🔒 プライベートリポジトリ '{owner}/{repo}' が検出されました")
        
        # GitHub CLI認証状態確認
        if not self.check_github_auth():
            print("\n⚠️ GitHub CLI認証が必要です")
            print("以下のコマンドで認証してください:")
            print("  gh auth login")
            
            choice = input("\n今すぐ認証しますか？ [Y/n]: ").strip().lower()
            if choice in ['', 'y', 'yes']:
                try:
                    subprocess.run(["gh", "auth", "login"], check=True)
                    print("✅ 認証が完了しました")
                    return True
                except (subprocess.CalledProcessError, FileNotFoundError):
                    print("❌ 認証に失敗しました")
                    return False
            else:
                print("📌 別の方法:")
                print("1. リポジトリをPublicに変更する")
                print("2. アクセス権限のあるアカウントで認証する")
                return False
        else:
            print("✅ GitHub CLI認証済み - プライベートリポジトリにアクセス可能です")
            return True
    
    def extract_repo_name(self, github_url):
        """GitHubURLからリポジトリ名を抽出"""
        parsed = urlparse(github_url)
        path_parts = parsed.path.strip('/').split('/')
        if len(path_parts) >= 2:
            return f"{path_parts[0]}_{path_parts[1]}"
        return "unknown_repo"
    
    def validate_github_url(self, github_url):
        """GitHubURLの検証とアクセス可能性チェック"""
        
        # URL形式の基本チェック
        if not github_url.startswith(('https://github.com/', 'http://github.com/', 'github.com/')):
            return False, "有効なGitHubURLを入力してください（例: https://github.com/user/repo）"
        
        # URLの正規化
        if not github_url.startswith('http'):
            github_url = 'https://' + github_url
        
        try:
            parsed = urlparse(github_url)
            path_parts = parsed.path.strip('/').split('/')
            
            if len(path_parts) < 2:
                return False, "URLにユーザー名とリポジトリ名が含まれていません"
            
            owner, repo = path_parts[0], path_parts[1]
            
            # .git拡張子を削除
            if repo.endswith('.git'):
                repo = repo[:-4]
        except Exception:
            return False, "URLの解析に失敗しました"
        
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
            if repo_type == "private_or_not_found":
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
    
    def get_chatgpt_api_key(self, save_option=True):
        """ChatGPT APIキーを取得（暗号化保存可能）"""
        # まず保存されたキーを確認
        if self.api_manager.has_stored_keys():
            try:
                password = getpass.getpass("保存されたAPIキーを復号化するためのパスワードを入力してください: ")
                api_key = self.api_manager.load_api_key("openai", password)
                if api_key:
                    print("✅ 保存されたChatGPT APIキーを読み込みました")
                    return api_key
                else:
                    print("❌ パスワードが間違っているか、APIキーが保存されていません")
            except KeyboardInterrupt:
                print("\n🔄 新しいAPIキーの入力に切り替えます")
        
        # 新しいAPIキーを入力
        print("\n🔑 ChatGPT API設定")
        print("OpenAI APIキーは https://platform.openai.com/api-keys で取得できます")
        
        while True:
            api_key = getpass.getpass("OpenAI APIキーを入力してください (sk-...): ").strip()
            
            if not api_key:
                print("❌ APIキーが入力されていません")
                continue
            
            if not api_key.startswith("sk-"):
                print("❌ 無効なAPIキー形式です。正しいOpenAI APIキーを入力してください")
                continue
            
            break
        
        # 保存オプション
        if save_option and HAS_CRYPTOGRAPHY:
            save = input("\nAPIキーを暗号化して保存しますか？ [Y/n]: ").strip().lower()
            if save in ['', 'y', 'yes']:
                password = getpass.getpass("暗号化用パスワードを設定してください: ")
                confirm_password = getpass.getpass("パスワードを再入力してください: ")
                
                if password == confirm_password:
                    if self.api_manager.save_api_key("openai", api_key, password):
                        print("💾 次回から同じパスワードで自動読み込み可能です")
                else:
                    print("⚠️ パスワードが一致しませんでした。今回のみ使用します")
        elif save_option:
            print("\n⚠️ 暗号化保存機能を使用するには 'pip install cryptography' が必要です")
        
        return api_key
    
    def call_ai_cli(self, github_url, repo_name, ai_config):
        """AI CLIを呼び出してユースケース分析を実行"""
        
        ai_provider = ai_config.get('provider', 'gemini')
        precision = ai_config.get('precision', 'high')
        openai_api_key = ai_config.get('openai_api_key')
        
        providers = ["claude", "gemini"] if ai_provider == "auto" else [ai_provider]
        
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
                        analyzer = MultiStageAnalyzer(github_url, repo_name, temp_dir, self.cli_outputs_dir, provider, openai_api_key)
                        result = analyzer.execute_full_analysis()
                        
                        if result:
                            print(f"\n📄 {provider.upper()}多段階分析結果:")
                            print("-" * 50)
                            # 最初の500文字を表示
                            preview = result[:500] + "..." if len(result) > 500 else result
                            print(preview)
                            print("-" * 50)
                            print(f"📊 総文字数: {len(result):,} 文字")
                            print(f"💾 分析ログ保存: {os.path.relpath(self.cli_outputs_dir, self.project_root)}")
                            
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
                    
                    # 良いサンプルを読み込み
                    sample_usecase = self._load_reference_usecase()
                    
                    # 改善された高速分析プロンプト
                    prompt = f"""
あなたはAIユースケース分析の専門家です。GitHubリポジトリ {github_url} を効率的に分析して、高品質なユースケースドキュメントを生成してください。

## 参考フォーマット（良い例）
{sample_usecase}

## 必須要求事項

1. **厳密なYAMLフロントマター**：
```yaml
---
title: "[具体的で分かりやすいプロジェクトタイトル]"
summary: "[1-2文の簡潔で的確な概要]"
category: "[適切なカテゴリ：AIユースケース/Web開発/データ分析/モバイルアプリ/ツール/ライブラリ/その他]"
industry: "[対象業界：IT・ソフトウェア/製造業/金融/ヘルスケア/教育/エンタメ/その他]"
createdAt: {datetime.now().strftime('%Y-%m-%d')}
updatedAt: {datetime.now().strftime('%Y-%m-%d')}
status: "[開発中/完了/実験的/アーカイブ/メンテナンス中]"
github_link: {github_url}
contributors:
  - "[実際のコントリビューター名]"
tags:
  - "[主要技術タグ1]"
  - "[主要技術タグ2]"
  - "[主要技術タグ3]"
---
```

2. **高品質なMarkdown構造**：
- リポジトリの実際の内容に基づいた正確な分析
- 技術的詳細の具体性
- 実用的価値の明確化
- 読みやすく構造化された文章

## 必須セクション
- # プロジェクトタイトル
- ## 概要
- ## 課題・ニーズ  
- ## AI技術（AI/ML使用時）または ## 技術スタック
- ## 実装フロー
- ## 主要機能
- ## 技術的詳細
- ## 期待される効果
- ## リスク・課題
- ## 応用・展開可能性
- ## コントリビューター
- ## 参考リンク

完全で高品質なMarkdownドキュメントを生成してください。
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
                        result = subprocess.run(
                            cmd, 
                            capture_output=True, 
                            text=True, 
                            timeout=timeout
                        )
                    elif provider == "claude":
                        cmd = ["claude", prompt]
                        timeout = 120  # 2分
                        result = subprocess.run(
                            cmd, 
                            capture_output=True, 
                            text=True, 
                            timeout=timeout
                        )
                    elif provider == "chatgpt":
                        # ChatGPT API呼び出し用のアナライザーを作成
                        temp_analyzer = MultiStageAnalyzer(github_url, repo_name, "/tmp", self.cli_outputs_dir, provider, openai_api_key)
                        result = temp_analyzer._call_chatgpt_api(prompt)
                    else:
                        continue
                    
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
                        print(f"❌ {provider.upper()}エラー: {result.stderr}")
                        if ai_provider != "auto":
                            return None
                        continue
                
            except subprocess.TimeoutExpired:
                print(f"⏰ {provider.upper()}がタイムアウトしました")
                if ai_provider != "auto":
                    return None
                continue
            except Exception as e:
                print(f"❌ {provider.upper()}でエラーが発生しました: {e}")
                if ai_provider != "auto":
                    return None
                continue
        
        return None
    
    def save_usecase_file(self, content, repo_name):
        """ユースケースファイルを保存"""
        try:
            # use-casesディレクトリが存在しない場合は作成
            os.makedirs(self.use_cases_dir, exist_ok=True)
            
            # ファイル名作成（安全な文字のみ使用）
            safe_repo_name = re.sub(r'[^\w\-_]', '_', repo_name)
            filename = f"{safe_repo_name}.md"
            filepath = os.path.join(self.use_cases_dir, filename)
            
            # ファイル保存
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return filepath
            
        except Exception as e:
            print(f"❌ ファイル保存エラー: {e}")
            return None
    
    def auto_git_operations(self, filepath, repo_name):
        """Git操作の自動実行"""
        try:
            self.print_step(4, 5, "Git操作")
            
            # Git add
            print("📝 ファイルをステージングエリアに追加中...")
            subprocess.run(["git", "add", filepath], check=True, cwd=self.project_root)
            
            # Git commit
            commit_message = f"feat: Add use case for {repo_name}\n\n🤖 Generated with [Claude Code](https://claude.ai/code)\n\nCo-Authored-By: Claude <noreply@anthropic.com>"
            print("💾 変更をコミット中...")
            
            subprocess.run([
                "git", "commit", "-m", commit_message
            ], check=True, cwd=self.project_root)
            
            # Git push
            print("🚀 リモートリポジトリにプッシュ中...")
            subprocess.run(["git", "push"], check=True, cwd=self.project_root)
            
            print("✅ Git操作が正常に完了しました")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Git操作エラー: {e}")
            return False
        except Exception as e:
            print(f"❌ 予期しないエラー: {e}")
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

def run_tests():
    """基本的なテスト関数"""
    print("\n--- Running basic tests ---")
    
    # Test case 1: Pure JSON output
    json_output = '{"key": "value", "number": 123}'
    test_input_1 = f"Some text before.\n```json\n{json_output}\n```\nSome text after."
    expected_output_1 = json_output
    assert extract_clean_output(test_input_1) == expected_output_1, f"Test 1 failed: {extract_clean_output(test_input_1)}"
    print("✅ Test 1 (JSON in code block) passed.")
    
    # Test case 2: Pure Markdown output
    md_output = "# Title\n\n- Item 1\n- Item 2"
    test_input_2 = f"```markdown\n{md_output}\n```"
    expected_output_2 = md_output
    assert extract_clean_output(test_input_2) == expected_output_2, f"Test 2 failed: {extract_clean_output(test_input_2)}"
    print("✅ Test 2 (Markdown in code block) passed.")
    
    # Test case 3: YAML front matter Markdown
    yaml_md_output = "---\ntitle: \"Test\"\n---\n# Content\nThis is content."
    test_input_3 = f"Some preamble.\n{yaml_md_output}\nSome postamble."
    expected_output_3 = yaml_md_output
    assert extract_clean_output(test_input_3) == expected_output_3, f"Test 3 failed: {extract_clean_output(test_input_3)}"
    print("✅ Test 3 (YAML front matter Markdown) passed.")
    
    # Test case 4: Mixed content, should prioritize YAML front matter
    mixed_output = f"Some text.\n{yaml_md_output}\n```json\n{json_output}\n```"
    expected_output_4 = yaml_md_output
    assert extract_clean_output(mixed_output) == expected_output_4, f"Test 4 failed: {extract_clean_output(mixed_output)}"
    print("✅ Test 4 (Mixed content - YAML front matter priority) passed.")
    
    # Test case 5: No code blocks, just plain text
    plain_text_output = "This is just plain text with no special blocks."
    assert extract_clean_output(plain_text_output) == plain_text_output, f"Test 5 failed: {extract_clean_output(plain_text_output)}"
    print("✅ Test 5 (Plain text) passed.")
    
    print("--- All basic tests passed! ---")

def main():
    parser = argparse.ArgumentParser(description='GitHubリポジトリからAIユースケースを自動生成')
    parser.add_argument('github_url', nargs='?', help='GitHubリポジトリURL')
    parser.add_argument('--project-root', default='.', help='プロジェクトルートディレクトリ')
    parser.add_argument('--ai-provider', choices=['gemini', 'claude', 'chatgpt', 'auto'], default='claude', 
                       help='使用するAI CLI (default: claude)')
    parser.add_argument('--openai-api-key', 
                       help='ChatGPT用OpenAI APIキー（省略時は対話式入力）')
    parser.add_argument('--precision', choices=['fast', 'high'], default='high',
                       help='分析精度モード (default: high)')
    parser.add_argument('--no-git', action='store_true', 
                       help='Git操作をスキップ（ファイル生成のみ）')
    parser.add_argument('--test', action='store_true',
                       help='Run basic tests and exit')
    
    args = parser.parse_args()
    
    if args.test:
        run_tests()
        sys.exit(0)
    
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
        print("3. Claude 高精度（多段階分析・10-15分）⭐ 推奨")
        print("4. Claude 高速（単発分析・1-3分）")
        print("5. ChatGPT 高精度（多段階分析・10-15分）🔑 APIキー必要")
        print("6. ChatGPT 高速（単発分析・1-3分）🔑 APIキー必要")
        print("7. 自動選択（高精度）")
        
        choice = input("選択してください [1-7, default: 3]: ").strip()
        
        ai_config_map = {
            "1": {"provider": "gemini", "precision": "high"},
            "2": {"provider": "gemini", "precision": "fast"},
            "3": {"provider": "claude", "precision": "high"},
            "4": {"provider": "claude", "precision": "fast"},
            "5": {"provider": "chatgpt", "precision": "high"},
            "6": {"provider": "chatgpt", "precision": "fast"},
            "7": {"provider": "auto", "precision": "high"},
            "": {"provider": "claude", "precision": "high"}
        }
        ai_config = ai_config_map.get(choice, {"provider": "claude", "precision": "high"})
        
        # ChatGPTが選択された場合、APIキーを取得
        if ai_config["provider"] == "chatgpt":
            api_key = generator.get_chatgpt_api_key()
            ai_config["openai_api_key"] = api_key
        
        # Git操作選択
        git_choice = input("\nGit操作を自動実行しますか？ [Y/n]: ").strip().lower()
        auto_git = git_choice in ['', 'y', 'yes']
    else:
        github_url = args.github_url
        ai_config = {"provider": args.ai_provider, "precision": args.precision}
        auto_git = not args.no_git
        
        # ChatGPTが指定された場合、APIキーを処理
        if args.ai_provider == "chatgpt":
            if args.openai_api_key:
                ai_config["openai_api_key"] = args.openai_api_key
            else:
                generator = UseCaseGenerator(args.project_root)
                api_key = generator.get_chatgpt_api_key()
                ai_config["openai_api_key"] = api_key
        
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

if __name__ == "__main__":
    main()