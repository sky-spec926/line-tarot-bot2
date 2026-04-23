import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    AsyncApiClient,
    AsyncMessagingApi,
    Configuration,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhook import WebhookParser
from linebot.v3.webhooks import FollowEvent, MessageEvent, TextMessageContent
from dotenv import load_dotenv

from database import get_history, init_db, save_reading
from tarot_reader import TarotReader

load_dotenv()

_WELCOME = """🔮 タロット占いへようこそ！

メッセージを送るとカードを自動で引いて、AIが占い結果をお伝えします。

使い方:
・何でも送信 → 1枚引き（総合運）
・「3枚」を含む → 過去・現在・未来
・「履歴」と送信 → 過去の占い一覧
・悩みや質問を書くと内容に合わせた占いに✨

さっそく試してみてください！"""

_HELP = """🔮 タロット占いの使い方

【占いを始める】
・メッセージを何でも送信
　→ 1枚引き（総合運）
・「3枚」を含むメッセージ
　→ 過去・現在・未来の3枚

【履歴を見る】
・「履歴」と送信
　→ 直近5件の占い結果を表示

【例】
・「今日の運勢は？」
・「仕事のことで悩んでいます 3枚」
・「恋愛について教えて」"""

_HISTORY_CMDS = {"履歴", "記録", "ログ", "history"}
_HELP_CMDS    = {"ヘルプ", "使い方", "help", "？", "?"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(lifespan=lifespan)
parser       = WebhookParser(os.environ["LINE_CHANNEL_SECRET"])
configuration = Configuration(access_token=os.environ["LINE_CHANNEL_ACCESS_TOKEN"])
reader       = TarotReader()


def _detect_num_cards(text: str) -> int:
    if any(kw in text for kw in ["3枚", "three", "スリー", "過去現在未来", "過去・現在・未来"]):
        return 3
    return 1


async def _reply(reply_token: str, text: str) -> None:
    async with AsyncApiClient(configuration) as api_client:
        await AsyncMessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text)],
            )
        )


async def _format_history(user_id: str) -> str:
    rows = await get_history(user_id, limit=5)
    if not rows:
        return "📚 まだ占い履歴がありません。\nメッセージを送って最初の占いをしてみましょう！"

    nums = ["①", "②", "③", "④", "⑤"]
    lines = ["📚 占い履歴（最新5件）\n"]
    for i, row in enumerate(rows):
        cards = json.loads(row["cards_json"])
        cards_str = " / ".join(
            f"{c['ja_name']}({'逆' if c['reversed'] else '正'})" for c in cards
        )
        q = row["question"] or "（総合運）"
        if len(q) > 18:
            q = q[:18] + "…"
        lines.append(f"{nums[i]} {row['created_at']}")
        lines.append(f"「{q}」")
        lines.append(f"🃏 {cards_str}\n")

    return "\n".join(lines)


@app.post("/webhook")
async def webhook(
    request: Request,
    x_line_signature: str = Header(alias="X-Line-Signature"),
) -> str:
    body = await request.body()
    try:
        events = parser.parse(body.decode(), x_line_signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        if isinstance(event, FollowEvent):
            await _reply(event.reply_token, _WELCOME)

        elif isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
            text    = event.message.text.strip()
            user_id = event.source.user_id

            if text in _HISTORY_CMDS:
                await _reply(event.reply_token, await _format_history(user_id))

            elif text in _HELP_CMDS:
                await _reply(event.reply_token, _HELP)

            else:
                num_cards = _detect_num_cards(text)
                reply, cards = await reader.get_reading_async(text, num_cards)
                await _reply(event.reply_token, reply)
                await save_reading(user_id, text, cards, reply)

    return "OK"


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
