"""
infrastructure/scheduler.py
APScheduler設定（schedules.yaml ベース）
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz


def create_scheduler(schedules_config, autonomous_trigger_func, rem_func):
    """schedules.yaml の定義に基づきスケジューラーを作成する。

    Args:
        schedules_config: schedules.yaml の内容
        autonomous_trigger_func: 自律起動コールバック（trigger_typeを引数に取る）
        rem_func: レム睡眠バッチコールバック
    """
    tz = pytz.timezone(schedules_config.get("timezone", "Asia/Tokyo"))
    scheduler = AsyncIOScheduler(timezone=tz)

    # 自律起動トリガー
    for trigger_type, trigger_def in schedules_config.get("triggers", {}).items():
        hour = trigger_def.get("hour", 0)
        minute = trigger_def.get("minute", 0)
        scheduler.add_job(
            autonomous_trigger_func,
            CronTrigger(hour=hour, minute=minute, timezone=tz),
            args=[trigger_type]
        )

    # レム睡眠バッチ
    rem_config = schedules_config.get("rem_sleep", {})
    scheduler.add_job(
        rem_func,
        CronTrigger(
            hour=rem_config.get("hour", 0),
            minute=rem_config.get("minute", 0),
            timezone=tz
        )
    )

    return scheduler