"""
domain/state.py
LangGraphのState定義（システムの状態スキーマ）
"""
from typing import TypedDict, Annotated
import operator


class State(TypedDict):
    history: Annotated[list, operator.add]
    summary: str
    turn_count: int
    master_summary: str
    current_b: str
    current_c: str
    slot_metadata: Annotated[list, operator.add]
    pending_slot_request: dict
    system_injection: str
    current_trigger: str
    thinking_mode: str