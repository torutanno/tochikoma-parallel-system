"""
infrastructure/llm_providers.py
YAML設定に基づくLLMインスタンスの生成

ファクトリ関数パターン: モジュールレベルの即時初期化ではなく、
config を受け取ってLLM辞書を返す。
"""
import os
from dotenv import load_dotenv
from langchain_google_vertexai import ChatVertexAI
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

load_dotenv()


def _resolve_location(config_entry):
    """location を解決する。null の場合は .env の LOCATION を使用。"""
    location = config_entry.get("location")
    if location is None:
        return os.getenv("LOCATION")
    return location


def create_llms(agents_config):
    """agents.yaml の定義に基づき、全LLMインスタンスを生成して返す。

    Returns:
        dict: {"worker_b": ChatVertexAI(...), "master_a": ..., "slot_claude": ..., ...}
    """
    llms = {}
    project = os.getenv("PROJECT_ID")

    # 内部エージェント用LLM
    for agent_id, agent_def in agents_config.get("agents", {}).items():
        location = _resolve_location(agent_def)
        llms[agent_id] = ChatVertexAI(
            model_name=agent_def["model"],
            project=project,
            location=location,
            max_retries=3
        )

    # 外部知性スロット用LLM
    for slot_id, slot_def in agents_config.get("slots", {}).items():
        provider = slot_def.get("provider", "vertex_ai")

        if provider == "anthropic":
            llms[f"slot_{slot_id}"] = ChatAnthropic(
                model_name=slot_def["model"],
                anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
                max_retries=3
            )
        elif provider == "xai":
            llms[f"slot_{slot_id}"] = ChatOpenAI(
                model=slot_def["model"],
                api_key=os.getenv("GROK_API_KEY"),
                base_url="https://api.x.ai/v1",
                max_retries=3
            )
        elif provider == "vertex_ai":
            location = slot_def.get("location") or os.getenv("LOCATION")
            llms[f"slot_{slot_id}"] = ChatVertexAI(
                model_name=slot_def["model"],
                project=project,
                location=location,
                max_retries=3 
            )

    return llms
