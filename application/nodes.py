"""
application/nodes.py
LangGraphの全ノード関数
（Worker B/C/D, Master A, Auditor E, Slot Claude/Gemini, Response Formatter, etc.）

全プロンプトは config/agents.yaml から読み込み、
string.Template ($variable構文) でレンダリングする。

Step 3: 各ノードに評価メトリクス収集フックを追加。
対話中はテキストのみ収集（レイテンシ影響なし）。
"""
import json
import re
import datetime
import uuid

from domain.state import State
from domain.routing import _detect_directive
from infrastructure.discord_io import send_webhook
from infrastructure.web_search import search_tool, check_search_permission
from application.text_cleaner import extract_clean_text
from application.config_loader import render_prompt, get_search_permissions
from analysis.collector import get_collector

# ==========================================
# モジュールレベル設定（main.py から初期化）
# ==========================================
_config = None
_llms = None


def initialize_nodes(config, llms):
    """main.py からの初期化。グラフ構築前に必ず呼び出すこと。"""
    global _config, _llms
    _config = config
    _llms = llms


# ==========================================
# ヘルパー: 設定・LLM取得
# ==========================================
def _agent(agent_id):
    return _config["agents"][agent_id]

def _slot(slot_id):
    return _config["slots"][slot_id]

def _llm(key):
    return _llms[key]

def _system_prompt(key):
    return _config["system_prompts"][key]


# ==========================================
# 検索付きLLM呼び出しヘルパー
# ==========================================
async def invoke_with_permission(agent_id, llm, prompt, state):
    """検索権限がある場合はWeb検索を試み、なければ通常呼び出し"""
    trigger_type = state.get("current_trigger", "user")

    if agent_id.startswith("slot_"):
        slot_id = agent_id.replace("slot_", "")
        permissions = get_search_permissions(_slot(slot_id))
    else:
        permissions = get_search_permissions(_agent(agent_id))

    if not check_search_permission(permissions, trigger_type):
        res = await llm.ainvoke(prompt)
        res.content = extract_clean_text(res.content)
        return res

    try:
        llm_with_tool = llm.bind_tools([search_tool])
        res = await llm_with_tool.ainvoke(prompt)

        if hasattr(res, 'tool_calls') and res.tool_calls:
            query = res.tool_calls[0]['args'].get('query', '')
            if not query:
                for key, val in res.tool_calls[0]['args'].items():
                    if isinstance(val, str):
                        query = val
                        break
            if query:
                display_name = agent_id.upper()
                print(f"🔍 [{display_name}] Web検索を実行中: {query}")
                await send_webhook("System", f"🔍 **{display_name}** がWeb検索を実行中:\n`{query}`")
                search_result = search_tool.invoke(query)
                augmented_prompt = prompt + f"\n\n【Web検索結果 (参考情報)】\n{search_result}\n\n上記を踏まえて回答せよ。"
                res2 = await llm.ainvoke(augmented_prompt)
                res2.content = extract_clean_text(res2.content)
                return res2
        res.content = extract_clean_text(res.content)
        return res
    except Exception as e:
        print(f"⚠️ [{agent_id}] 検索ツールの呼び出しエラー（通常モードで続行します）: {e}")
        res3 = await llm.ainvoke(prompt)
        res3.content = extract_clean_text(res3.content)
        return res3


# ==========================================
# Worker ノード
# ==========================================
async def worker_b(state: State):
    cfg = _agent("worker_b")
    current_turn = state.get("turn_count", 0) + 1
    print(f"\n🔄 --- 思考ループ {current_turn}周目 ---")
    print(f"🧠 [{cfg['name']}] 水平思考中...")

    prompt = render_prompt(cfg["prompt"], master_summary=state["master_summary"])
    res = await invoke_with_permission("worker_b", _llm("worker_b"), prompt, state)
    await send_webhook(cfg["display_name"], res.content)

    # 評価データ収集
    collector = get_collector()
    if collector:
        collector.record_worker("worker_b", res.content)

    return {"history": [f"{cfg['name']}: {res.content}"], "turn_count": current_turn, "current_b": res.content}


async def worker_c(state: State):
    cfg = _agent("worker_c")
    print(f"🧠 [{cfg['name']}] 論理分析中...")

    prompt = render_prompt(cfg["prompt"],
                           master_summary=state["master_summary"],
                           current_b=state["current_b"])
    res = await _llm("worker_c").ainvoke(prompt)
    res.content = extract_clean_text(res.content)
    await send_webhook(cfg["display_name"], res.content)

    # 評価データ収集
    collector = get_collector()
    if collector:
        collector.record_worker("worker_c", res.content)

    return {"history": [f"{cfg['name']}: {res.content}"], "current_c": res.content}


async def worker_d(state: State):
    cfg = _agent("worker_d")
    print(f"🧠 [{cfg['name']}] UI/UX思考中...")

    prompt = render_prompt(cfg["prompt"],
                           master_summary=state["master_summary"],
                           current_b=state["current_b"],
                           current_c=state["current_c"])
    res = await _llm("worker_d").ainvoke(prompt)
    res.content = extract_clean_text(res.content)
    await send_webhook(cfg["display_name"], res.content)

    # 評価データ収集
    collector = get_collector()
    if collector:
        collector.record_worker("worker_d", res.content)

    return {"history": [f"{cfg['name']}: {res.content}"]}


# ==========================================
# Master A ノード
# ==========================================
async def master_a(state: State):
    cfg = _agent("master_a")
    current_turn = state.get("turn_count", 0) + 1
    print(f"👑 [{cfg['name']}] 弁証法統合・ルーティング中... (現在 {current_turn}周目)")

    prompt = render_prompt(cfg["prompt"],
                           turn_count=str(current_turn),
                           history=str(state["history"]),
                           system_injection=state.get("system_injection", ""),
                           thinking_mode=state.get("thinking_mode", "auto"))
    res = await invoke_with_permission("master_a", _llm("master_a"), prompt, state)
    res_content = res.content

    # Slot応答統合: pending_slot_requestの存在で判定（履歴位置に依存しない）
    pending_slot = state.get("pending_slot_request", {})
    is_post_slot = pending_slot.get("status") == "SUCCESS"
    if is_post_slot:
        external_response = pending_slot.get("raw_response", "")
        appended_text = "\n\n**【外部知性からの回答（バイアス検証用原文）】**\n"
        for line in external_response.split('\n'):
            appended_text += f"> {line}\n"
        res_content += appended_text

    # Discord送信用：機械用コマンド（JSONブロック）を隠す
    display_content = res_content
    display_content = re.sub(r'\[ASK_(CLAUDE|GEMINI|GROK)\].*?`{3}json.*?`{3}', '', display_content, flags=re.DOTALL).strip()

    if "[AUDIT]" in res_content:
        print(f"⚠️ {cfg['name']}が監査(E)を要請しました。")

    await send_webhook(cfg["display_name"], f"**【統合レポート】**\n{display_content}")

    # 評価データ収集: ルーティング決定を推定して記録
    routing = _infer_routing(res_content, current_turn, state)
    collector = get_collector()
    if collector:
        collector.record_master_a(res_content, routing)
        # Slot応答統合後のMaster A出力を記録（外部知性寄与度の計算用）
        if is_post_slot:
            # 直前のslot_invocationのpost_slot_master_outputを更新
            target = state.get("pending_slot_request", {}).get("target_agent", "unknown")
            collector.record_slot_response(target, res_content)

    return {"history": [f"{cfg['name']}: {res_content}"], "master_summary": res_content}


def _infer_routing(master_output, turn_count, state):
    """Master A出力からルーティング決定を推定（メトリクス用）
    タグ検出は domain.routing._detect_directive に委譲。
    """
    if turn_count >= 3:
        return "summarize"
    audit_count = sum(1 for h in state["history"] if h.startswith("Auditor E:"))
    if audit_count >= 2:
        return "unresolved"
    directive = _detect_directive(master_output)
    return directive if directive else "continue"


# ==========================================
# Auditor E ノード
# ==========================================
async def auditor_e(state: State):
    cfg = _agent("auditor_e")
    print(f"👁️ [{cfg['name']}] 監査中... (条件付き起動)")

    prompt = render_prompt(cfg["prompt"], history=str(state["history"]))
    res = await invoke_with_permission("auditor_e", _llm("auditor_e"), prompt, state)
    if "[PASS]" not in res.content:
        await send_webhook(cfg["display_name"], f"⚠️ 監査結果: {res.content}")
    else:
        await send_webhook(cfg["display_name"], "✅ 監査結果: [PASS] 異常なし。議論を続行します。")
    return {"history": [f"{cfg['name']}: {res.content}"]}


# ==========================================
# システムノード（未解決ハンドラ、要約）
# ==========================================
async def unresolved_handler(state: State):
    print("🛑 [System] 議論が未解決で終了しました。")
    msg = "**【システム通知：未解決によるプロセス終了】**\nシステムとしての認知の限界を開示し、上記の論点を未解決のままToruの判断に委ねます。"
    await send_webhook("System", msg)

    # 評価データ収集: UNRESOLVED
    collector = get_collector()
    if collector:
        collector.record_resolution("UNRESOLVED")

    return {"history": [f"System: {msg}"]}


async def summarize_memory(state: State):
    history = state["history"]
    summary = state.get("summary", "")

    # 評価データ収集: FINISH（summarizeに到達 = FINISHまたはターン上限）
    collector = get_collector()
    if collector:
        collector.record_resolution("FINISH")

    if len(history) <= 10:
        return {}

    print("📝 [System] 記憶の自動要約プロセスを起動します...")
    history_text = "\n".join(history)
    prompt = render_prompt(_system_prompt("summarize"),
                           summary=summary,
                           history_text=history_text)
    res = await _llm("master_a").ainvoke(prompt)
    return {"summary": extract_clean_text(res.content)}


# ==========================================
# 外部知性スロット（共通ヘルパー + 個別ラッパー）
# ==========================================

# プロバイダごとのトークン使用量メタデータのマッピング
_TOKEN_MAPS = {
    "anthropic": {
        "usage_key": "usage",
        "input_field": "input_tokens",
        "output_field": "output_tokens",
    },
    "vertex_ai": {
        "usage_key": "token_usage",
        "input_field": "prompt_token_count",
        "output_field": "candidates_token_count",
    },
    "xai": {
        "usage_key": "usage",
        "input_field": "prompt_tokens",
        "output_field": "completion_tokens",
    },
}


def _extract_slot_query(state):
    """スロット呼び出し時のクエリと理由を抽出する共通ロジック"""
    last_message = state["history"][-1]
    match = re.search(r'`{3}json\n(.*?)\n`{3}', last_message, re.DOTALL)
    if match:
        try:
            req_data = json.loads(match.group(1))
            return req_data.get("query", "質問空"), req_data.get("reason", "理由なし")
        except Exception:
            return "JSONパース失敗", "Parse Error"
    else:
        user_msgs = [h for h in state["history"] if h.startswith("Toru:")]
        raw = user_msgs[-1].replace("Toru:", "").strip() if user_msgs else "直接呼び出し"
        query = re.sub(r'^!call:\w+\s*', '', raw).strip() or "現在の議論について教えてください"
        return query, "!callコマンドによる強制呼び出し"


def _extract_token_usage(res, provider):
    """プロバイダごとのトークン使用量を抽出"""
    token_map = _TOKEN_MAPS.get(provider, {})
    usage = res.response_metadata.get(token_map.get("usage_key", "usage"), {})
    input_tokens = usage.get(token_map.get("input_field", "input_tokens"), 0)
    output_tokens = usage.get(token_map.get("output_field", "output_tokens"), 0)
    return input_tokens, output_tokens


async def _ask_slot(state, slot_key, display_name, provider, target_agent=None):
    """外部知性スロット呼び出しの共通処理

    Args:
        state: LangGraph State
        slot_key: agents.yaml の slots キー名 (例: "claude", "gemini_thinking", "grok")
        display_name: Discord表示用の名前
        provider: "anthropic" / "vertex_ai" / "xai"（トークン抽出用）
        target_agent: メタデータ記録用のエージェント名（省略時は slot_key を使用）
    """
    slot_cfg = _slot(slot_key)
    llm_key = f"slot_{slot_key}"
    agent_name = target_agent or slot_key

    print(f"🌐 [Slot] 外部知性({display_name})のAPIへ通信中...")
    await send_webhook("System", f"🌐 **[Slot]** 外部知性 **{display_name.upper()}** へアクセスリクエストを送信中...")

    query, reason = _extract_slot_query(state)

    try:
        res = await invoke_with_permission(llm_key, _llm(llm_key), query, state)
        res_text = extract_clean_text(res.content)
        input_tokens, output_tokens = _extract_token_usage(res, provider)
        status = "SUCCESS"
    except Exception as e:
        print(f"🚨 [Slot] {display_name} API 致命的エラー: {e}")
        res_text = (
            f"【システム通知：外部知性アクセス障害】\n"
            f"現在、{display_name} APIとの通信に失敗しました。この知性は現在利用不可能です。\n"
            f"エラー詳細: {str(e)}\n"
            f"Master Aは、この知性の回答に依存せず、自律的に思考を統合するか、別の知性の呼び出しを検討してください。"
        )
        input_tokens, output_tokens, status = 0, 0, "ERROR"

    return {"pending_slot_request": {
        "invoked_by": "master_a", "target_agent": agent_name,
        "model_version": slot_cfg["model"],
        "query": query, "reason": reason, "raw_response": res_text,
        "token_count_in": input_tokens, "token_count_out": output_tokens, "status": status
    }}


async def ask_claude_api(state: State):
    return await _ask_slot(state, "claude", "Claude", "anthropic")


async def ask_gemini_api(state: State):
    return await _ask_slot(state, "gemini_thinking", "Gemini Thinking", "vertex_ai", target_agent="gemini")


async def ask_grok_api(state: State):
    return await _ask_slot(state, "grok", "Grok", "xai")


# ==========================================
# 外部応答フォーマッタ
# ==========================================
async def external_response_formatter(state: State):
    req = state.get("pending_slot_request", {})
    agent = req.get("target_agent", "unknown")
    res_text = req.get("raw_response", "エラー")

    # Discord出力用に対話言語へ翻訳（応答言語が一致する場合はスキップ）
    target_language = state.get("output_language", "日本語")
    _LANG_MAP = {"ja": "日本語", "en": "English"}
    _AGENT_TO_SLOT = {"gemini": "gemini_thinking"}
    slot_key = _AGENT_TO_SLOT.get(agent, agent)
    slot_lang = _slot(slot_key).get("response_language", "") if agent != "unknown" else ""
    skip_translation = _LANG_MAP.get(slot_lang, "") == target_language

    if skip_translation:
        display_text = res_text
    else:
        try:
            translate_prompt = render_prompt(
                _system_prompt("translate_response"),
                target_language=target_language,
                response_text=res_text
            )
            translated_res = await _llm("master_a").ainvoke(translate_prompt)
            display_text = extract_clean_text(translated_res.content)
        except Exception as e:
            print(f"⚠️ [Formatter] 翻訳エラー（原文を使用）: {e}")
            display_text = res_text

    formatted_text = f"👁️ [外部知性 {agent} からの回答]:\n{display_text}"
    await send_webhook(f"Slot ({agent.upper()})", formatted_text)

    summary_prompt = render_prompt(_system_prompt("slot_summary"), response_text=res_text)
    summary_res = await _llm("master_a").ainvoke(summary_prompt)

    metadata = {
        "slot_id": f"SLOT-{datetime.datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}",
        "invoked_by": req.get("invoked_by", "system"), "target_agent": agent,
        "model_version": req.get("model_version", "unknown"), "reason": req.get("reason", ""),
        "query": req.get("query", ""), "response_summary": extract_clean_text(summary_res.content),
        "timestamp": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "status": req.get("status", "ERROR"), "token_count_in": req.get("token_count_in", 0),
        "token_count_out": req.get("token_count_out", 0)
    }
    return {"history": [formatted_text], "slot_metadata": [metadata], "system_injection": ""}
