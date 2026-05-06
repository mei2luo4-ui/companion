import aiosqlite
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "companion.db")

CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS profile (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '小暖',
    personality TEXT NOT NULL DEFAULT '温柔体贴',
    speaking_style TEXT NOT NULL DEFAULT '亲密随意',
    avatar_emoji TEXT NOT NULL DEFAULT '🌸',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    emotion_label TEXT,
    emotion_score REAL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS diary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    mood_score REAL,
    tags TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    is_seen INTEGER NOT NULL DEFAULT 0,
    scheduled_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    summary TEXT NOT NULL,
    importance INTEGER NOT NULL DEFAULT 5,
    created_at TEXT NOT NULL
);
"""


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_TABLES)
        # 确保 profile 表有默认行
        cursor = await db.execute("SELECT COUNT(*) FROM profile")
        count = (await cursor.fetchone())[0]
        if count == 0:
            now = datetime.utcnow().isoformat()
            await db.execute(
                "INSERT INTO profile (name, personality, speaking_style, avatar_emoji, updated_at) VALUES (?,?,?,?,?)",
                ("小暖", "温柔体贴", "亲密随意", "🌸", now),
            )
        await db.commit()


async def get_profile() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM profile LIMIT 1")
        row = await cursor.fetchone()
        return dict(row)


async def update_profile(name: str, personality: str, speaking_style: str, avatar_emoji: str):
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE profile SET name=?, personality=?, speaking_style=?, avatar_emoji=?, updated_at=? WHERE id=1",
            (name, personality, speaking_style, avatar_emoji, now),
        )
        await db.commit()


async def add_message(role: str, content: str, emotion_label: str = None, emotion_score: float = None) -> int:
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO messages (role, content, emotion_label, emotion_score, created_at) VALUES (?,?,?,?,?)",
            (role, content, emotion_label, emotion_score, now),
        )
        await db.commit()
        return cursor.lastrowid


async def get_recent_messages(limit: int = 30) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM messages ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return list(reversed([dict(r) for r in rows]))


async def count_messages() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM messages WHERE role='user'")
        return (await cursor.fetchone())[0]


async def get_memories() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM memories ORDER BY importance DESC, created_at DESC LIMIT 10"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def add_memory(summary: str, importance: int = 5):
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO memories (summary, importance, created_at) VALUES (?,?,?)",
            (summary, importance, now),
        )
        # 只保留最新 20 条记忆
        await db.execute(
            "DELETE FROM memories WHERE id NOT IN (SELECT id FROM memories ORDER BY importance DESC, created_at DESC LIMIT 20)"
        )
        await db.commit()


async def add_diary(content: str, mood_score: float = None, tags: str = None) -> int:
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO diary (content, mood_score, tags, created_at) VALUES (?,?,?,?)",
            (content, mood_score, tags, now),
        )
        await db.commit()
        return cursor.lastrowid


async def get_diary_list(limit: int = 30) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM diary ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_mood_history(days: int = 14) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT DATE(created_at) as date, AVG(emotion_score) as avg_score, COUNT(*) as count
            FROM messages
            WHERE role='user' AND emotion_score IS NOT NULL
              AND created_at >= datetime('now', ?)
            GROUP BY DATE(created_at)
            ORDER BY date ASC
            """,
            (f"-{days} days",),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_recent_user_emotions(limit: int = 5) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT emotion_label, emotion_score FROM messages WHERE role='user' AND emotion_score IS NOT NULL ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def add_event(type_: str, title: str, content: str, scheduled_at: str) -> int:
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO events (type, title, content, scheduled_at, created_at) VALUES (?,?,?,?,?)",
            (type_, title, content, scheduled_at, now),
        )
        await db.commit()
        return cursor.lastrowid


async def get_pending_events() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM events WHERE is_seen=0 ORDER BY scheduled_at ASC LIMIT 5"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def dismiss_event(event_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE events SET is_seen=1 WHERE id=?", (event_id,))
        await db.commit()


async def has_event_today(type_: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM events WHERE type=? AND DATE(created_at)=DATE('now')",
            (type_,),
        )
        return (await cursor.fetchone())[0] > 0
