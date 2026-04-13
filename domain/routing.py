"""
domain/routing.py
Master Aの出力に基づくルーティング判断ロジック

タグ検出ロジックを _detect_directive に集約し、
routing_function（グラフ用）と nodes.py の _infer_routing（メトリクス用）で共用する。
"""


def _detect_directive(text):
    """Master Aの出力テキストからディレクティブタグを検出する。

    Returns:
        str or None: 検出されたディレクティブ名。未検出なら None。
    """
    if "[FINISH]" in text:
        return "finish"
    elif "[ASK_CLAUDE]" in text:
        return "ask_claude"
    elif "[ASK_GEMINI]" in text:
        return "ask_gemini"
    elif "[ASK_GROK]" in text:
        return "ask_grok"
    elif "[AUDIT]" in text:
        return "audit"
    elif "[UNRESOLVED]" in text:
        return "unresolved"
    return None


def routing_function(state):
    """Master Aの出力からグラフの次の遷移先を決定する"""
    if state.get("turn_count", 0) >= 3:
        return "summarize"

    audit_count = sum(1 for h in state["history"] if h.startswith("Auditor E:"))
    if audit_count >= 2:
        return "unresolved"

    last_msg = state["history"][-1]
    directive = _detect_directive(last_msg)

    if directive == "finish":
        return "summarize"
    elif directive:
        return directive
    return "continue"


def pre_routing_function(state):
    """エントリーポイントでのルーティング：!callコマンドを検出して直接スロットへ"""
    injection = state.get("system_injection", "")
    if "CLAUDE" in injection and "強制呼び出し" in injection:
        return "ask_claude"
    elif "GROK" in injection and "強制呼び出し" in injection:
        return "ask_grok"
    elif "GEMINI" in injection and "強制呼び出し" in injection:
        return "ask_gemini"
    return "worker_b"