"""
main.py
Tochikoma Parallel System v4.5 (DDD + Config + Eval + Thinking Strategy Edition)
エントリーポイント

Step 3: 評価フレームワーク統合
- セッションごとのメトリクス自動収集（リアルタイム）
- embedding距離計算（Gemini Embedding 2、セッション終了時バッチ）
- !eval コマンドによるバッチ分析レポート生成
"""
import os
import json
import asyncio
import datetime
import uuid
import logging
import warnings

import discord
from dotenv import load_dotenv
from langchain_core.documents import Document

from domain.lifecycle import should_sleep, get_autonomous_query
from infrastructure.discord_io import send_webhook
from infrastructure.vector_store import vector_store, embeddings
from infrastructure.llm_providers import create_llms
from infrastructure.scheduler import create_scheduler
from application.text_cleaner import extract_clean_text
from application.config_loader import load_agents_config, load_schedules_config, render_prompt
from application.command_parser import parse_ban_unban, parse_thinking_mode, build_system_injection
from application.nodes import initialize_nodes
from application.graph_builder import build_graph
from analysis.collector import start_session, finalize_session
from analysis.report_generator import load_all_sessions, compute_statistics, generate_markdown_report

warnings.filterwarnings("ignore")
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

print("=" * 50)
print("Tochikoma Parallel System v4.5")
print("DDD + Config + Eval + Thinking Strategy Edition")
print("=" * 50)

agents_config = load_agents_config()
schedules_config = load_schedules_config()
llms = create_llms(agents_config)
initialize_nodes(agents_config, llms)
app = build_graph()

print(f"✅ {len(agents_config.get('agents', {}))} エージェント、"
      f"{len(agents_config.get('slots', {}))} スロットを初期化しました。")
print(f"📊 評価フレームワーク: 有効（Gemini Embedding 2）")

MEMORY_FILE = "global_memory.json"

def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return {"summary": "", "history": data[-6:]}
                return data
        except Exception:
            pass
    return {"summary": "", "history": []}

def save_memory(memory_dict):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory_dict, f, ensure_ascii=False, indent=2)

global_memory = load_memory()
banned_slots = set()
current_thinking_mode = "auto"
is_awake = False
last_activity_time = datetime.datetime.now()
sleep_timeout = schedules_config.get("sleep_timeout_seconds", 300)

def embed_documents_sync(texts):
    return embeddings.embed_documents(texts)

async def sleep_checker():
    global is_awake, last_activity_time
    while True:
        await asyncio.sleep(60)
        if is_awake and should_sleep(last_activity_time, sleep_timeout):
            is_awake = False
            print("💤 5分間無操作のためスリープモードへ移行。")
            await send_webhook("System", "💤 5分間の無入力を検知。システムはスリープモード（API通信遮断状態）に移行しました。")

async def autonomous_trigger(trigger_type):
    global is_awake, last_activity_time, global_memory
    is_awake = True
    last_activity_time = datetime.datetime.now()
    query = get_autonomous_query(trigger_type, schedules_config)
    print(f"⏰ 自律起動トリガー発火: {trigger_type}")
    await send_webhook("System", f"⏰ 定期実行トリガーが発火しました ({trigger_type})。システムが覚醒し、自律思考を開始します。")
    start_session(trigger_type=trigger_type, input_query=query)
    summary_text = f"【これまでの文脈】: {global_memory['summary']}\n\n" if global_memory['summary'] else ""
    final_state = await app.ainvoke({
        "history": global_memory["history"], "summary": global_memory["summary"],
        "master_summary": f"{summary_text}{query}", "turn_count": 0,
        "current_b": "", "current_c": "", "system_injection": "",
        "current_trigger": trigger_type, "thinking_mode": "auto",
    })
    new_summary = final_state.get("summary", "")
    new_history = final_state["history"][-4:] if len(final_state["history"]) > 10 else final_state["history"]
    global_memory = {"summary": new_summary, "history": new_history}
    save_memory(global_memory)
    await finalize_session(embed_documents_sync)

async def memory_consolidation_batch():
    global global_memory
    print("🌙 [System] 深夜0時の記憶並列化（レム睡眠）バッチを開始...")
    await send_webhook("System", "🌙 **深夜0時の記憶並列化（レム睡眠）バッチ**を開始します。本日の短期記憶を上位概念に圧縮します。")
    history = global_memory.get("history", [])
    if not history:
        print("💤 統合すべき記憶がありません。")
        return
    history_text = "\n".join(history)
    prompt = render_prompt(agents_config["system_prompts"]["rem_sleep"], history_text=history_text)
    res = await llms["master_a"].ainvoke(prompt)
    insight = extract_clean_text(res.content)
    log_id = f"REM-{datetime.datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    structured_log = f"【ID】: {log_id}\n【日時】: {timestamp}\n【レム睡眠 記憶統合】: {insight}"
    new_doc = Document(page_content=structured_log, metadata={"log_id": log_id, "type": "rem_sleep"})
    vector_store.add_documents([new_doc])
    print(f"📚 深夜の記憶統合が完了しました。[ID: {log_id}]")
    await send_webhook("System", f"📚 記憶の並列化が完了しました。新たな上位概念を長期記憶（無意識）に保存しました。\n> {insight}")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"\n✅ ログイン完了: {client.user} (v4.5 DDD + Config + Eval Edition)")
    scheduler = create_scheduler(schedules_config, autonomous_trigger, memory_consolidation_batch)
    scheduler.start()
    client.loop.create_task(sleep_checker())

@client.event
async def on_message(message):
    global global_memory, banned_slots, is_awake, last_activity_time, current_thinking_mode
    if message.author.bot:
        return
    last_activity_time = datetime.datetime.now()
    if not is_awake:
        is_awake = True
        await send_webhook("System", "☀️ ユーザートリガーを検知。システムが覚醒しました。")
    msg_lower = message.content.lower()
    if "!reset" in msg_lower or "リセット" in msg_lower:
        global_memory = {"summary": "", "history": []}
        save_memory(global_memory)
        banned_slots.clear()
        await send_webhook("System", "🧹 短期記憶（文脈）と封印状態をリセットしました。")
        return
    if "!eval" in msg_lower:
        await send_webhook("System", "📊 評価フレームワーク: バッチ分析を開始します...")
        try:
            sessions = load_all_sessions()
            if not sessions:
                await send_webhook("System", "⚠️ 評価データがありません。対話を行ってからお試しください。")
                return
            stats = compute_statistics(sessions)
            report = generate_markdown_report(stats)
            preview = report[:1800] + "\n\n... (詳細はサーバー上のレポートを参照)" if len(report) > 1800 else report
            await send_webhook("System", f"📊 **評価レポート** ({len(sessions)}セッション)\n```\n{preview}\n```")
            os.makedirs("reports", exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            md_path = f"reports/eval_report_{ts}.md"
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(report)
            json_path = f"reports/eval_stats_{ts}.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
            await send_webhook("System", f"📁 保存完了:\n`{md_path}`\n`{json_path}`")
        except Exception as e:
            await send_webhook("System", f"🚨 評価レポート生成エラー: {str(e)}")
        return
    if "!test:morning" in msg_lower:
        await send_webhook("System", "🛠️ テスト: 朝の自律起動を強制発動します。")
        await autonomous_trigger("morning")
        return
    if "!test:rem" in msg_lower:
        await memory_consolidation_batch()
        return
    try:
        ban_messages = parse_ban_unban(msg_lower, banned_slots)
        for msg in ban_messages:
            await send_webhook("System", msg)
        mode, mode_msg = parse_thinking_mode(msg_lower)
        if mode:
            current_thinking_mode = mode
            await send_webhook("System", mode_msg)
        system_injection = build_system_injection(msg_lower, banned_slots)
    
        start_session(trigger_type="user", input_query=message.content)
        global_memory["history"].append(f"Toru: {message.content}")
        docs = vector_store.similarity_search(message.content, k=1)
        past_context = f"\n\n【過去の関連記憶】\n{docs[0].page_content}\n" if docs else ""
        summary_text = f"【これまでの文脈】: {global_memory['summary']}\n\n" if global_memory['summary'] else ""
        final_state = await app.ainvoke({
            "history": global_memory["history"], "summary": global_memory["summary"],
            "master_summary": f"{summary_text}Toruからの指示: {message.content}{past_context}",
            "turn_count": 0, "current_b": "", "current_c": "", "system_injection": system_injection,
            "current_trigger": "user", "thinking_mode": current_thinking_mode,
        })
        new_summary = final_state.get("summary", "")
        new_history = final_state["history"][-4:] if len(final_state["history"]) > 10 else final_state["history"]
        global_memory = {"summary": new_summary, "history": new_history}
        save_memory(global_memory)
        master_cfg = agents_config["agents"]["master_a"]
        master_name = master_cfg["name"]
        master_a_messages = [msg for msg in final_state["history"] if msg.startswith(f"{master_name}:")]
        if master_a_messages:
            log_id = f"LOG-{datetime.datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            structured_log = f"【ID】: {log_id}\n【日時】: {timestamp}\n【過去の問い】: {message.content}\n【結論】: {master_a_messages[-1]}"
            meta = {"log_id": log_id, "timestamp": timestamp, "target_layer": "解釈の層", "responsibility": master_name}
            if final_state.get("slot_metadata"):
                meta.update({f"slot_{k}": v for k, v in final_state["slot_metadata"][-1].items() if isinstance(v, (str, int, float, bool))})
            vector_store.add_documents([Document(page_content=structured_log, metadata=meta)])
        await finalize_session(embed_documents_sync)
    except Exception as e:
        print(f"🚨 [System] メッセージ処理中にエラーが発生: {e}")
        await send_webhook("System", f"🚨 処理中にエラーが発生しました。\n```\n{str(e)[:500]}\n```")
        try:
            await finalize_session(embed_documents_sync)
        except Exception:
            pass

if __name__ == "__main__":
    discord.utils.setup_logging(level=logging.WARNING)
    client.run(DISCORD_TOKEN)
