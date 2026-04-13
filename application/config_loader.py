"""
application/config_loader.py
YAML設定ファイルの読み込み・バリデーション

セキュリティ:
- yaml.safe_load() のみ使用（任意コード実行を防止）
- クレデンシャルはYAMLに含めない（.envに保持）
"""
import os
import sys
import yaml
from string import Template

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")

# 必須フィールド定義
REQUIRED_AGENT_FIELDS = {"name", "display_name", "model", "prompt"}
REQUIRED_SLOT_FIELDS = {"model", "provider"}
REQUIRED_SYSTEM_PROMPTS = {"summarize", "rem_sleep", "slot_summary"}


def _load_yaml(filepath):
    """YAMLファイルを安全に読み込む"""
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_agents_config():
    """agents.yaml を読み込む。存在しなければ agents.example.yaml にフォールバック。"""
    primary = os.path.join(CONFIG_DIR, "agents.yaml")
    fallback = os.path.join(CONFIG_DIR, "agents.example.yaml")

    if os.path.exists(primary):
        print(f"📋 設定ファイル読み込み: {primary}")
        config = _load_yaml(primary)
    elif os.path.exists(fallback):
        print(f"⚠️ agents.yaml が見つかりません。agents.example.yaml にフォールバックします。")
        config = _load_yaml(fallback)
    else:
        print("🚨 致命的エラー: agents.yaml も agents.example.yaml も見つかりません。")
        sys.exit(1)

    _validate_agents_config(config)
    return config


def load_schedules_config():
    """schedules.yaml を読み込む。"""
    filepath = os.path.join(CONFIG_DIR, "schedules.yaml")
    if not os.path.exists(filepath):
        print("🚨 致命的エラー: schedules.yaml が見つかりません。")
        sys.exit(1)

    print(f"📋 スケジュール設定読み込み: {filepath}")
    config = _load_yaml(filepath)
    _validate_schedules_config(config)
    return config


def _validate_agents_config(config):
    """agents.yaml の必須フィールドを検証する"""
    # agents セクション
    agents = config.get("agents", {})
    if not agents:
        print("🚨 致命的エラー: agents.yaml に agents セクションがありません。")
        sys.exit(1)

    for agent_id, agent_def in agents.items():
        missing = REQUIRED_AGENT_FIELDS - set(agent_def.keys())
        if missing:
            print(f"🚨 致命的エラー: agents.{agent_id} に必須フィールドがありません: {missing}")
            sys.exit(1)

    # slots セクション
    slots = config.get("slots", {})
    for slot_id, slot_def in slots.items():
        missing = REQUIRED_SLOT_FIELDS - set(slot_def.keys())
        if missing:
            print(f"🚨 致命的エラー: slots.{slot_id} に必須フィールドがありません: {missing}")
            sys.exit(1)

    # system_prompts セクション
    system_prompts = config.get("system_prompts", {})
    missing = REQUIRED_SYSTEM_PROMPTS - set(system_prompts.keys())
    if missing:
        print(f"🚨 致命的エラー: system_prompts に必須キーがありません: {missing}")
        sys.exit(1)


def _validate_schedules_config(config):
    """schedules.yaml の必須フィールドを検証する"""
    if "triggers" not in config:
        print("🚨 致命的エラー: schedules.yaml に triggers セクションがありません。")
        sys.exit(1)
    if "timezone" not in config:
        print("🚨 致命的エラー: schedules.yaml に timezone が定義されていません。")
        sys.exit(1)


def render_prompt(template_str, **kwargs):
    """$variable 構文のテンプレートを安全にレンダリングする。
    未定義変数はエラーを出さず $variable のまま残る（safe_substitute）。"""
    tmpl = Template(template_str)
    return tmpl.safe_substitute(**kwargs)


def get_agent_location(agent_config):
    """エージェントの location を解決する。
    null の場合は .env の LOCATION を使用。"""
    location = agent_config.get("location")
    if location is None:
        return os.getenv("LOCATION")
    return location


def get_search_permissions(agent_config):
    """エージェントの検索権限リストを返す。
    ["*"] は全トリガーで検索許可を意味する。"""
    return agent_config.get("search_permissions", [])
