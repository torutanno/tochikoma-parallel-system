"""
application/command_parser.py
Discordからの強制介入コマンド（!reset, !ban, !call, !mode等）の解析
"""


def parse_ban_unban(msg_lower, banned_slots):
    """!ban:xxx / !unban:xxx コマンドを解析し、banned_slotsを更新する。
    返り値: 送信すべきメッセージのリスト"""
    messages = []
    for target in ["claude", "grok", "gemini"]:
        if f"!ban:{target}" in msg_lower:
            banned_slots.add(target)
            messages.append(f"🚫 {target.upper()} の自律的な呼び出しを封印しました。")
        elif f"!unban:{target}" in msg_lower:
            banned_slots.discard(target)
            messages.append(f"🔓 {target.upper()} の封印を解除しました。")
    return messages


def parse_thinking_mode(msg_lower):
    """!mode:inductive / !mode:deductive / !mode:auto コマンドを解析する。
    Returns:
        tuple: (thinking_mode, message) or (None, None) if no mode command found
    """
    valid_modes = {
        "inductive": ("inductive", "🧠 思考モードを **帰納法（inductive）** に切り替えました。具体→一般化の推論を優先します。"),
        "deductive": ("deductive", "🧠 思考モードを **演繹法（deductive）** に切り替えました。原理→具体の推論を優先します。"),
        "auto": ("auto", "🧠 思考モードを **自動選択（auto）** に戻しました。Master Aがクエリに応じて判断します。"),
    }
    for mode_key, (mode_val, mode_msg) in valid_modes.items():
        if f"!mode:{mode_key}" in msg_lower:
            return mode_val, mode_msg
    return None, None


def build_system_injection(msg_lower, banned_slots):
    """!call:xxx コマンドとban状態からsystem_injection文字列を構築する"""
    system_injection = ""

    for target in ["claude", "grok", "gemini"]:
        if f"!call:{target}" in msg_lower:
            system_injection = (
                f"\n\n【SYSTEM COMMAND】Toruから {target.upper()} の強制呼び出し指示が出ています。"
                f"今回の出力は必ず `[ASK_{target.upper()}]` のJSONフォーマットを用いて終了してください。"
                f"自律的な統合は行わず、外部知性に問いを投げることに専念してください。"
            )
            banned_slots.discard(target)

    if banned_slots:
        banned_str = ", ".join([f"[ASK_{t.upper()}]" for t in banned_slots])
        system_injection += (
            f"\n\n【SYSTEM COMMAND】現在、Toruの指示により以下の呼び出しコマンドは封印されています。"
            f"絶対に使用しないでください: {banned_str}"
        )

    return system_injection