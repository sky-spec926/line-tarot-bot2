import json
import os
from datetime import date, datetime
from typing import Optional

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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id                TEXT PRIMARY KEY,
                plan                   TEXT NOT NULL DEFAULT 'free',
                plan_expires_at        TEXT,
                stripe_customer_id     TEXT,
                stripe_subscription_id TEXT,
                created_at             TEXT NOT NULL,
                updated_at             TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS daily_usage (
                user_id  TEXT NOT NULL,
                date     TEXT NOT NULL,
                count    INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, date)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS contact_messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                email      TEXT NOT NULL,
                message    TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        await db.commit()


async def get_or_create_user(user_id: str) -> dict:
    async with aiosqlite.connect(_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row:
            return dict(row)
        now = datetime.now().isoformat()
        await db.execute(
            "INSERT INTO users (user_id, plan, created_at, updated_at) VALUES (?, 'free', ?, ?)",
            (user_id, now, now),
        )
        await db.commit()
    return {
        "user_id": user_id, "plan": "free", "plan_expires_at": None,
        "stripe_customer_id": None, "stripe_subscription_id": None,
        "created_at": now, "updated_at": now,
    }


async def update_user_plan(
    user_id: str,
    plan: str,
    expires_at: Optional[str] = None,
    stripe_customer_id: Optional[str] = None,
    stripe_subscription_id: Optional[str] = None,
) -> None:
    now = datetime.now().isoformat()
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute(
            """INSERT INTO users
               (user_id, plan, plan_expires_at, stripe_customer_id,
                stripe_subscription_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                   plan                   = excluded.plan,
                   plan_expires_at        = excluded.plan_expires_at,
                   stripe_customer_id     = COALESCE(excluded.stripe_customer_id, stripe_customer_id),
                   stripe_subscription_id = COALESCE(excluded.stripe_subscription_id, stripe_subscription_id),
                   updated_at             = excluded.updated_at""",
            (user_id, plan, expires_at, stripe_customer_id, stripe_subscription_id, now, now),
        )
        await db.commit()


async def get_user_by_stripe_customer(customer_id: str) -> Optional[dict]:
    async with aiosqlite.connect(_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE stripe_customer_id = ?", (customer_id,)
        ) as cursor:
            row = await cursor.fetchone()
    return dict(row) if row else None


async def get_today_reading_count(user_id: str) -> int:
    today = date.today().isoformat()
    async with aiosqlite.connect(_DB_PATH) as db:
        async with db.execute(
            "SELECT count FROM daily_usage WHERE user_id = ? AND date = ?",
            (user_id, today),
        ) as cursor:
            row = await cursor.fetchone()
    return row[0] if row else 0


async def increment_daily_usage(user_id: str) -> None:
    today = date.today().isoformat()
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute(
            """INSERT INTO daily_usage (user_id, date, count) VALUES (?, ?, 1)
               ON CONFLICT(user_id, date) DO UPDATE SET count = count + 1""",
            (user_id, today),
        )
        await db.commit()


async def save_reading(
    user_id: str,
    question: str,
    cards: list,
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


async def save_contact(name: str, email: str, message: str) -> None:
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute(
            "INSERT INTO contact_messages (name, email, message, created_at) VALUES (?, ?, ?, ?)",
            (name, email, message, datetime.now().strftime("%Y/%m/%d %H:%M")),
        )
        await db.commit()


async def get_history(user_id: str, limit: int = 5) -> list:
    if limit < 0:
        async with aiosqlite.connect(_DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT created_at, question, cards_json FROM readings"
                " WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ) as cursor:
                rows = await cursor.fetchall()
    else:
        async with aiosqlite.connect(_DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT created_at, question, cards_json FROM readings"
                " WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
    return [dict(r) for r in rows]
