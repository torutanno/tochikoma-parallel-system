"""
application/graph_builder.py
LangGraph StateGraphの構築とEdge定義
"""
from langgraph.graph import StateGraph, END
from domain.state import State
from domain.routing import routing_function, pre_routing_function
from application.nodes import (
    worker_b, worker_c, worker_d, master_a, auditor_e,
    unresolved_handler, summarize_memory,
    ask_claude_api, ask_gemini_api, ask_grok_api, external_response_formatter
)

def build_graph():
    """Tochikoma のメイングラフを構築してコンパイルする"""
    workflow = StateGraph(State)

    # ノード登録
    workflow.add_node("node_b", worker_b)
    workflow.add_node("node_c", worker_c)
    workflow.add_node("node_d", worker_d)
    workflow.add_node("node_e", auditor_e)
    workflow.add_node("node_a", master_a)
    workflow.add_node("node_unresolved", unresolved_handler)
    workflow.add_node("node_summarize", summarize_memory)
    workflow.add_node("node_ask_claude", ask_claude_api)
    workflow.add_node("node_ask_gemini", ask_gemini_api)
    workflow.add_node("node_ask_grok", ask_grok_api)
    workflow.add_node("node_response_formatter", external_response_formatter)

    # エントリーポイント
    workflow.add_node("node_pre_router", lambda state: state)
    workflow.set_entry_point("node_pre_router")

    # 固定Edge
    workflow.add_edge("node_b", "node_c")
    workflow.add_edge("node_c", "node_d")
    workflow.add_edge("node_d", "node_a")
    workflow.add_edge("node_e", "node_a")
    workflow.add_edge("node_unresolved", "node_summarize")
    workflow.add_edge("node_summarize", END)
    workflow.add_edge("node_ask_claude", "node_response_formatter")
    workflow.add_edge("node_ask_gemini", "node_response_formatter")
    workflow.add_edge("node_ask_grok", "node_response_formatter")
    workflow.add_edge("node_response_formatter", "node_b")

    # 条件分岐Edge
    workflow.add_conditional_edges(
        "node_pre_router", pre_routing_function,
        {
            "worker_b": "node_b",
            "ask_claude": "node_ask_claude",
            "ask_grok": "node_ask_grok",
            "ask_gemini": "node_ask_gemini"
        }
    )
    workflow.add_conditional_edges(
        "node_a", routing_function,
        {
            "continue": "node_b",
            "audit": "node_e",
            "unresolved": "node_unresolved",
            "summarize": "node_summarize",
            "ask_claude": "node_ask_claude",
            "ask_gemini": "node_ask_gemini",
            "ask_grok": "node_ask_grok"
        }
    )

    return workflow.compile()
