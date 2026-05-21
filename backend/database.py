import aiosqlite
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "companion.db")

CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profile (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL DEFAULT '晓柔',
    personality TEXT NOT NULL DEFAULT '温柔体贴',
    speaking_style TEXT NOT NULL DEFAULT '温柔低语',
    avatar_emoji TEXT NOT NULL DEFAULT '/avatars/1f42a266ff2e5e663cc3a41dbe2d827b.png',
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    character_name TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    emotion_label TEXT,
    emotion_score REAL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS diary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    mood_score REAL,
    tags TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    is_seen INTEGER NOT NULL DEFAULT 0,
    scheduled_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    summary TEXT NOT NULL,
    importance INTEGER NOT NULL DEFAULT 5,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS moments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    character_name TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    likes INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS moment_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    moment_id INTEGER NOT NULL,
    character_name TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (moment_id) REFERENCES moments(id)
);
"""


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_TABLES)
        for migration in [
            "ALTER TABLE messages ADD COLUMN character_name TEXT NOT NULL DEFAULT ''",
        ]:
            try:
                await db.execute(migration)
                await db.commit()
            except Exception:
                pass


async def create_user(username: str, password_hash: str) -> int:
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?,?,?)",
            (username, password_hash, now),
        )
        user_id = cursor.lastrowid
        await db.execute(
            "INSERT INTO profile (user_id, name, personality, speaking_style, avatar_emoji, updated_at) VALUES (?,?,?,?,?,?)",
            (user_id, "晓柔", "温柔体贴", "温柔低语", "/avatars/1f42a266ff2e5e663cc3a41dbe2d827b.png", now),
        )
        await db.commit()
        return user_id


async def get_user_by_username(username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE username=?", (username,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_profile(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM profile WHERE user_id=?", (user_id,))
        row = await cursor.fetchone()
        return dict(row)


async def update_profile(user_id: int, name: str, personality: str, speaking_style: str, avatar_emoji: str):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE profile SET name=?, personality=?, speaking_style=?, avatar_emoji=?, updated_at=? WHERE user_id=?",
            (name, personality, speaking_style, avatar_emoji, now, user_id),
        )
        await db.commit()


async def add_message(user_id: int, role: str, content: str, emotion_label: str = None, emotion_score: float = None, character_name: str = '') -> int:
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO messages (user_id, character_name, role, content, emotion_label, emotion_score, created_at) VALUES (?,?,?,?,?,?,?)",
            (user_id, character_name, role, content, emotion_label, emotion_score, now),
        )
        await db.commit()
        return cursor.lastrowid


async def clear_messages(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM messages WHERE user_id=?", (user_id,))
        await db.commit()


async def get_recent_messages(user_id: int, limit: int = 30, character_name: str = '') -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM messages WHERE user_id=? AND character_name=? ORDER BY created_at DESC LIMIT ?",
            (user_id, character_name, limit)
        )
        rows = await cursor.fetchall()
        return list(reversed([dict(r) for r in rows]))


async def count_messages(user_id: int, character_name: str = '') -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM messages WHERE user_id=? AND character_name=? AND role='user'",
            (user_id, character_name)
        )
        return (await cursor.fetchone())[0]


async def get_memories(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM memories WHERE user_id=? ORDER BY importance DESC, created_at DESC LIMIT 20", (user_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def add_memory(user_id: int, summary: str, importance: int = 5):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO memories (user_id, summary, importance, created_at) VALUES (?,?,?,?)",
            (user_id, summary, importance, now),
        )
        await db.execute(
            "DELETE FROM memories WHERE user_id=? AND id NOT IN (SELECT id FROM memories WHERE user_id=? ORDER BY importance DESC, created_at DESC LIMIT 20)",
            (user_id, user_id),
        )
        await db.commit()


async def add_diary(user_id: int, content: str, mood_score: float = None, tags: str = None) -> int:
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO diary (user_id, content, mood_score, tags, created_at) VALUES (?,?,?,?,?)",
            (user_id, content, mood_score, tags, now),
        )
        await db.commit()
        return cursor.lastrowid


async def get_diary_list(user_id: int, limit: int = 30) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM diary WHERE user_id=? ORDER BY created_at DESC LIMIT ?", (user_id, limit)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_mood_history(user_id: int, days: int = 14) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT DATE(created_at) as date, AVG(emotion_score) as avg_score, COUNT(*) as count
            FROM messages
            WHERE user_id=? AND role='user' AND emotion_score IS NOT NULL
              AND created_at >= datetime('now', ?)
            GROUP BY DATE(created_at)
            ORDER BY date ASC
            """,
            (user_id, f"-{days} days"),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_recent_user_emotions(user_id: int, limit: int = 5) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT emotion_label, emotion_score FROM messages WHERE user_id=? AND role='user' AND emotion_score IS NOT NULL ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_last_user_message_time(user_id: int) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT created_at FROM messages WHERE user_id=? AND role='user' ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def add_event(user_id: int, type_: str, title: str, content: str, scheduled_at: str) -> int:
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO events (user_id, type, title, content, scheduled_at, created_at) VALUES (?,?,?,?,?,?)",
            (user_id, type_, title, content, scheduled_at, now),
        )
        await db.commit()
        return cursor.lastrowid


async def get_pending_events(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM events WHERE user_id=? AND is_seen=0 ORDER BY scheduled_at ASC LIMIT 5", (user_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def dismiss_event(user_id: int, event_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE events SET is_seen=1 WHERE id=? AND user_id=?", (event_id, user_id))
        await db.commit()


async def has_event_today(user_id: int, type_: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM events WHERE user_id=? AND type=? AND DATE(created_at)=DATE('now')",
            (user_id, type_),
        )
        return (await cursor.fetchone())[0] > 0


async def get_seen_lore_chapters(user_id: int, character_name: str) -> set:
    """返回该用户已推送过的某角色故事章节号集合"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT content FROM events WHERE user_id=? AND type='lore' AND title LIKE ?",
            (user_id, f"%{character_name}%"),
        )
        rows = await cursor.fetchall()
    chapters = set()
    import json as _json
    for (content,) in rows:
        try:
            data = _json.loads(content)
            if "chapter" in data:
                chapters.add(data["chapter"])
        except Exception:
            pass
    return chapters


async def get_all_user_ids() -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id FROM users")
        rows = await cursor.fetchall()
        return [r[0] for r in rows]


async def add_moment(user_id: int, content: str, character_name: str = '') -> int:
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO moments (user_id, character_name, content, created_at) VALUES (?,?,?,?)",
            (user_id, character_name, content, now),
        )
        await db.commit()
        return cursor.lastrowid


async def get_moments(user_id: int, limit: int = 30) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM moments WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def like_moment(moment_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE moments SET likes = likes + 1 WHERE id=?", (moment_id,))
        await db.commit()
        cursor = await db.execute("SELECT likes FROM moments WHERE id=?", (moment_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0


async def add_moment_comment(moment_id: int, character_name: str, content: str) -> int:
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO moment_comments (moment_id, character_name, content, created_at) VALUES (?,?,?,?)",
            (moment_id, character_name, content, now),
        )
        await db.commit()
        return cursor.lastrowid


async def get_moment_comments(moment_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM moment_comments WHERE moment_id=? ORDER BY created_at ASC",
            (moment_id,),
        )
        return [dict(r) for r in await cursor.fetchall()]
