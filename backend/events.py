import asyncio
import random
from datetime import datetime, timezone
from . import database as db
from . import companion


EVENT_TYPES = {
    "morning": {"hours": range(8, 11), "label": "晨间问候"},
    "afternoon": {"hours": range(12, 15), "label": "午后闲聊"},
    "activity": {"hours": list(range(9, 12)) + list(range(14, 18)), "label": "活动邀请"},
    "evening": {"hours": range(20, 24), "label": "睡前陪伴"},
    "emotion_care": {"hours": range(0, 24), "label": "情绪关怀"},
}


async def check_and_generate_events():
    user_ids = await db.get_all_user_ids()
    for user_id in user_ids:
        await _check_for_user(user_id)


async def _check_for_user(user_id: int):
    now = datetime.now()
    hour = now.hour
    profile = await db.get_profile(user_id)
    recent_emotions = await db.get_recent_user_emotions(user_id, 5)

    if len(recent_emotions) >= 3:
        negative = {"焦虑", "悲伤", "愤怒", "疲惫"}
        neg_count = sum(1 for e in recent_emotions[:3] if e["emotion_label"] in negative)
        if neg_count >= 3 and not await db.has_event_today(user_id, "emotion_care"):
            await _create_event(user_id, "emotion_care", profile, recent_emotions)

    for event_type, config in EVENT_TYPES.items():
        if event_type == "emotion_care":
            continue
        if hour in config["hours"] and not await db.has_event_today(user_id, event_type):
            if random.random() < 0.4:
                await _create_event(user_id, event_type, profile, recent_emotions)


async def _create_event(user_id: int, event_type: str, profile: dict, recent_emotions: list[dict]):
    try:
        data = await companion.generate_event_content(event_type, profile, recent_emotions)
        scheduled_at = datetime.now().isoformat()
        await db.add_event(user_id, event_type, data["title"], data["content"], scheduled_at)
    except Exception:
        pass  # 事件生成失败静默处理，不影响主流程


async def event_scheduler_loop():
    """后台无限循环，每隔随机时间检查是否需要生成事件"""
    await asyncio.sleep(10)  # 启动后延迟10秒
    while True:
        try:
            await check_and_generate_events()
        except Exception:
            pass
        # 每 5~15 分钟检查一次
        await asyncio.sleep(random.randint(300, 900))
