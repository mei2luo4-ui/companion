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

# lore 事件触发时间段（下午或晚上，避免打扰）
LORE_HOURS = list(range(14, 22))


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

    if hour in LORE_HOURS and not await db.has_event_today(user_id, "lore"):
        if random.random() < 0.3:
            await _create_lore_event(user_id, profile)

    # 动态：每次轮询有30%概率生成一条
    if random.random() < 0.3:
        random_profile = random.choice(companion.ALL_CHARACTER_PROFILES)
        await _create_moment_post(user_id, random_profile, recent_emotions)


def _get_related_characters(author_name: str) -> list[str]:
    return [
        name for name, text in companion.CHARACTER_RELATIONS.items()
        if name != author_name and author_name in text
    ]


async def _trigger_comments(moment_id: int, author_name: str, post_content: str):
    async def _one(char_name: str):
        try:
            comment = await companion.generate_moment_comment(char_name, author_name, post_content)
            await db.add_moment_comment(moment_id, char_name, comment)
        except Exception:
            pass

    tasks = [
        asyncio.create_task(_one(char_name))
        for char_name in _get_related_characters(author_name)
        if random.random() < 0.4
    ]
    if tasks:
        await asyncio.gather(*tasks)


async def _create_moment_post(user_id: int, profile: dict, recent_emotions: list[dict]):
    """生成一条纯动态（不写入 events 表，不受每日限制）"""
    try:
        content = await companion.generate_moment_post(profile)
        moment_id = await db.add_moment(user_id, content, character_name=profile["name"])
    except Exception:
        return
    await _trigger_comments(moment_id, profile["name"], content)


async def _create_event(user_id: int, event_type: str, profile: dict, recent_emotions: list[dict]):
    try:
        data = await companion.generate_event_content(event_type, profile, recent_emotions)
        scheduled_at = datetime.now().isoformat()
        await db.add_event(user_id, event_type, data["title"], data["content"], scheduled_at)
        moment_id = await db.add_moment(user_id, data["content"], character_name=profile["name"])
    except Exception:
        return
    await _trigger_comments(moment_id, profile["name"], data["content"])


async def _create_lore_event(user_id: int, profile: dict):
    try:
        import json
        seen = await db.get_seen_lore_chapters(user_id, profile["name"])
        chapter = companion.get_next_lore_chapter(profile["name"], seen)
        if chapter is None:
            return
        scheduled_at = datetime.now().isoformat()
        content_json = json.dumps({"chapter": chapter["chapter"], "text": chapter["content"]}, ensure_ascii=False)
        await db.add_event(user_id, "lore", chapter["title"], content_json, scheduled_at)
        moment_id = await db.add_moment(user_id, chapter["content"], character_name=profile["name"])
    except Exception:
        return
    await _trigger_comments(moment_id, profile["name"], chapter["content"])


async def event_scheduler_loop():
    """后台无限循环，每隔随机时间检查是否需要生成事件"""
    await asyncio.sleep(10)  # 启动后延迟10秒
    while True:
        try:
            await check_and_generate_events()
        except Exception:
            pass
        # 每 3~8 分钟检查一次
        await asyncio.sleep(random.randint(180, 480))
