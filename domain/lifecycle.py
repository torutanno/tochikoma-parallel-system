"""
domain/lifecycle.py
スリープ判定と自律起動メッセージの定義

Step 3: schedules.yaml から設定を読み込む方式に変更。
"""
import datetime


def should_sleep(last_activity_time, sleep_timeout_seconds=300):
    """最終アクティビティからの経過時間でスリープ判定"""
    now = datetime.datetime.now()
    return (now - last_activity_time).total_seconds() >= sleep_timeout_seconds


def get_autonomous_query(trigger_type, schedules_config=None):
    """自律起動トリガーに対応するクエリメッセージを返す。
    schedules_config が渡された場合はYAMLから読み込む。"""
    if schedules_config:
        triggers = schedules_config.get("triggers", {})
        trigger = triggers.get(trigger_type, {})
        query = trigger.get("query", "")
        if query:
            return query.strip()

    # フォールバック（YAML未定義時）
    queries = {
        "morning": "【JST 4:00 自律起動】Master A、本日の思考の起点となるブリーフィング（Web検索も活用可）を行え。",
        "noon": "【JST 13:00 自律起動】Worker B、現在のシステム状態に対し、Webのノイズを用いた水平思考による攪乱を投下せよ。",
        "night": "【JST 22:00 自律起動】Auditor E、本日のシステムの思考プロセスをWebの事実と照らし合わせて監査せよ。",
    }
    return queries.get(trigger_type, "自律起動テスト")
