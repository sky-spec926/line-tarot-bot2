import json
import os
from datetime import datetime

import aiosqlite

_DB_PATH = os.environ.get("DB_PATH", "tarot_history.db")


async def init_db() -> None:
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT    NOT NULL,
                created_at  TEXT    NOT NULL,
                question    TEXT,
                cards_json  TEXT    NOT NULL,
                reply       TEXT    NOT NULL
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_user ON readings(user_id)"
        )
        await db.commit()


async def save_reading(
    user_id: str,
    question: str,
    cards: list[dict],
    reply: str,
) -> None:
    slim = [{"ja_name": c["ja_name"], "reversed": c["reversed"]} for c in cards]
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute(
            "INSERT INTO readings (user_id, created_at, question, cards_json, reply)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                user_id,
                datetime.now().strftime("%Y/%m/%d %H:%M"),
                question,
                json.dumps(slim, ensure_ascii=False),
                reply,
            ),
        )
        await db.commit()


async def get_history(user_id: str, limit: int = 5) -> list[dict]:
    async with aiosqlite.connect(_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT created_at, question, cards_json FROM readings"
            " WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]
