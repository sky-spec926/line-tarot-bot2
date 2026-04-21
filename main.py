import os
from fastapi import FastAPI, Request, HTTPException, Header
from linebot.v3.webhook import WebhookParser
from linebot.v3.messaging import (
    AsyncApiClient,
    AsyncMessagingApi,
    Configuration,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import FollowEvent, MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError
from dotenv import load_dotenv
from tarot_reader import TarotReader

load_dotenv()

app = FastAPI()
parser = WebhookParser(os.environ["LINE_CHANNEL_SECRET"])
configuration = Configuration(access_token=os.environ["LINE_CHANNEL_ACCESS_TOKEN"])
reader = TarotReader()

_WELCOME = """🔮 タロット占いへようこそ！

メッセージを送るとカードを自動で引いて、AIが占い結果をお伝えします。

使い方:
・何でも送信 → 1枚引き（総合運）
・「3枚」を含むメッセージ → 過去・現在・未来
・悩みや質問を書くと内容に合わせた占いに✨

さっそく試してみてください！"""


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
            text = event.message.text.strip()
            num_cards = _detect_num_cards(text)
            result = await reader.get_reading_async(text, num_cards)
            await _reply(event.reply_token, result)

    return "OK"


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
