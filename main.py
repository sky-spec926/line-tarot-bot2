import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    AsyncApiClient,
    AsyncMessagingApi,
    Configuration,
    PushMessageRequest,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhook import WebhookParser
from linebot.v3.webhooks import FollowEvent, MessageEvent, TextMessageContent
from dotenv import load_dotenv

from database import (
    get_history,
    get_or_create_user,
    get_today_reading_count,
    get_user_by_stripe_customer,
    increment_daily_usage,
    init_db,
    save_reading,
    update_user_plan,
)
from payment import create_checkout_url, parse_stripe_event
from subscription import PLANS, PlanType, get_plan_comparison_text, get_upgrade_prompt
from tarot_reader import TarotReader

load_dotenv()

# ── Static messages ────────────────────────────────────────────────────────────

_WELCOME = """🔮 タロット占いへようこそ！

AIが本格的なタロット占いをお届けします✨

【基本コマンド】
・メッセージを送信 → 1枚引き（総合運）
・「3枚」を含む → 過去・現在・未来
・「履歴」→ 過去の占い一覧
・「プラン」→ 料金プランを確認

無料プランは1日3回まで占えます。
さっそく試してみてください！"""

_HELP = """🔮 タロット占いの使い方

【占いコマンド】
・何でも送信 → 1枚引き（総合運）
・「3枚」を含む → 過去・現在・未来
・「5枚」を含む → 5枚スプレッド ※ベーシック以上
・「ケルト」を含む → ケルト十字 ※プレミアムのみ

【テーマ別占い】（ベーシック以上）
・「恋愛占い」「仕事占い」「金運占い」など

【プレミアム専用】
・「今日の運勢」→ デイリー占い
・「相性占い ○○」→ 相性を占う

【その他】
・「履歴」→ 占い履歴
・「マイプラン」→ 現在のプラン確認
・「プラン」→ 料金プランを確認
・「ヘルプ」→ この使い方を表示"""

# ── Command sets ───────────────────────────────────────────────────────────────

_HISTORY_CMDS       = {"履歴", "記録", "ログ", "history"}
_HELP_CMDS          = {"ヘルプ", "使い方", "help", "？", "?"}
_PLAN_CMDS          = {"プラン", "料金", "価格", "plan", "plans", "プラン一覧"}
_MY_PLAN_CMDS       = {"マイプラン", "現在のプラン", "プラン確認", "myplan"}
_TRIAL_CMDS         = {"お試し申し込み", "お試し購入", "トライアル申し込み", "trial申し込み"}
_BASIC_CMDS         = {"ベーシック申し込み", "ベーシック購入", "basic申し込み"}
_PREMIUM_CMDS       = {"プレミアム申し込み", "プレミアム購入", "premium申し込み"}
_DAILY_FORTUNE_CMDS = {"今日の運勢", "今日の運気", "デイリー占い", "daily占い"}
_CANCEL_CMDS        = {"解約", "キャンセル", "プラン解約", "サブスク解約"}

_THEME_KEYWORDS: dict = {
    "恋愛":   ["恋愛", "恋", "love", "恋人", "片思い", "告白", "結婚", "デート", "別れ", "復縁"],
    "仕事":   ["仕事", "job", "work", "転職", "career", "職場", "ビジネス", "就活", "昇進"],
    "金運":   ["金運", "お金", "money", "収入", "貯金", "財運", "投資", "稼ぎ", "節約"],
    "健康":   ["健康", "体", "health", "病気", "体調", "ダイエット", "疲れ", "睡眠"],
    "人間関係": ["人間関係", "友達", "family", "家族", "友人", "relationships", "ハラスメント", "対人"],
}

# ── App setup ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app           = FastAPI(lifespan=lifespan)
parser        = WebhookParser(os.environ["LINE_CHANNEL_SECRET"])
configuration = Configuration(access_token=os.environ["LINE_CHANNEL_ACCESS_TOKEN"])
reader        = TarotReader()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _detect_num_cards(text: str) -> int:
    if any(kw in text for kw in ["10枚", "ケルト", "celtic", "十字"]):
        return 10
    if any(kw in text for kw in ["5枚", "five", "ファイブ"]):
        return 5
    if any(kw in text for kw in ["3枚", "three", "スリー", "過去現在未来", "過去・現在・未来"]):
        return 3
    return 1


def _detect_theme(text: str) -> Optional[str]:
    for theme, keywords in _THEME_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return theme
    return None


async def _reply(reply_token: str, text: str) -> None:
    async with AsyncApiClient(configuration) as api_client:
        await AsyncMessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text)],
            )
        )


async def _push(user_id: str, text: str) -> None:
    async with AsyncApiClient(configuration) as api_client:
        await AsyncMessagingApi(api_client).push_message(
            PushMessageRequest(to=user_id, messages=[TextMessage(text=text)])
        )


async def _resolve_plan(user_id: str) -> PlanType:
    user = await get_or_create_user(user_id)
    plan_str = user.get("plan", "free")

    expires_at = user.get("plan_expires_at")
    if expires_at and plan_str == "trial":
        try:
            exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if datetime.now(tz=timezone.utc) > exp:
                await update_user_plan(user_id, "free")
                return PlanType.FREE
        except Exception:
            pass

    try:
        return PlanType(plan_str)
    except ValueError:
        return PlanType.FREE


async def _format_my_plan(user_id: str) -> str:
    user = await get_or_create_user(user_id)
    plan_type = await _resolve_plan(user_id)
    cfg = PLANS[plan_type]

    lines = ["👤 あなたの現在のプラン\n"]
    lines.append(f"🎴 {cfg.name}（{cfg.price_display}）")
    lines.append("")
    lines.append("【利用可能な機能】")
    for feat in cfg.features_display:
        lines.append(feat)

    expires_at = user.get("plan_expires_at")
    if expires_at and plan_type == PlanType.TRIAL:
        try:
            exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            lines.append(f"\n📅 有効期限: {exp.strftime('%Y/%m/%d')}")
        except Exception:
            pass

    if plan_type != PlanType.PREMIUM:
        lines.append("\n「プラン」でアップグレードを確認できます✨")

    return "\n".join(lines)


async def _format_history(user_id: str, limit: int) -> str:
    rows = await get_history(user_id, limit=limit)
    if not rows:
        return "📚 まだ占い履歴がありません。\nメッセージを送って最初の占いをしてみましょう！"

    display = rows[:10]
    nums = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩"]
    lines = [f"📚 占い履歴（最新{len(display)}件）\n"]
    for i, row in enumerate(display):
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


async def _handle_purchase(
    reply_token: str, plan: str, user_id: str, plan_name: str
) -> None:
    url = create_checkout_url(plan, user_id)
    if url:
        msg = (
            f"💳 {plan_name}のお申し込み\n\n"
            "以下のリンクからお支払い手続きへお進みください。\n\n"
            f"{url}\n\n"
            "お支払い完了後、自動的にプランが切り替わります✨"
        )
    else:
        msg = (
            f"💳 {plan_name}のお申し込み\n\n"
            "現在お支払いシステムの準備中です。\n"
            "しばらくお待ちください🙇\n\n"
            "（管理者: STRIPE_* 環境変数を設定してください）"
        )
    await _reply(reply_token, msg)


# ── LINE webhook ───────────────────────────────────────────────────────────────

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
            continue

        if not (isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent)):
            continue

        text    = event.message.text.strip()
        user_id = event.source.user_id

        # ── Static commands (no plan check needed) ──
        if text in _HELP_CMDS:
            await _reply(event.reply_token, _HELP)
            continue

        if text in _PLAN_CMDS:
            await _reply(event.reply_token, get_plan_comparison_text())
            continue

        if text in _MY_PLAN_CMDS:
            await _reply(event.reply_token, await _format_my_plan(user_id))
            continue

        if text in _CANCEL_CMDS:
            await _reply(event.reply_token,
                "解約をご希望の場合は、Stripeのカスタマーポータルからお手続きください。\n"
                "次の更新日まで引き続きご利用いただけます。\n\n"
                "ご不明な点はサポートへお問い合わせください。")
            continue

        # ── Purchase commands ──
        if text in _TRIAL_CMDS:
            await _handle_purchase(event.reply_token, "trial", user_id, "お試しプラン（¥500・30日間）")
            continue

        if text in _BASIC_CMDS:
            await _handle_purchase(event.reply_token, "basic", user_id, "ベーシックプラン（¥980/月）")
            continue

        if text in _PREMIUM_CMDS:
            await _handle_purchase(event.reply_token, "premium", user_id, "プレミアムプラン（¥1,980/月）")
            continue

        # ── Resolve subscription plan ──
        plan_type = await _resolve_plan(user_id)
        plan_cfg  = PLANS[plan_type]

        # ── History command ──
        if text in _HISTORY_CMDS:
            if plan_cfg.history_limit == 0:
                await _reply(event.reply_token,
                    "📚 占い履歴は「お試しプラン」以上でご利用いただけます。\n\n"
                    "「プラン」で詳細を確認してください✨")
            else:
                await _reply(event.reply_token,
                    await _format_history(user_id, plan_cfg.history_limit))
            continue

        # ── Daily fortune (premium only) ──
        if text in _DAILY_FORTUNE_CMDS:
            if not plan_cfg.has_daily_fortune:
                await _reply(event.reply_token, get_upgrade_prompt(plan_type, "毎日の運勢"))
            else:
                reply, cards = await reader.get_daily_fortune()
                await _reply(event.reply_token, reply)
                await save_reading(user_id, "今日の運勢", cards, reply)
                await increment_daily_usage(user_id)
            continue

        # ── Compatibility reading (premium only) ──
        if text.startswith("相性占い"):
            if not plan_cfg.has_compatibility:
                await _reply(event.reply_token, get_upgrade_prompt(plan_type, "相性占い"))
            else:
                target = text[4:].strip() or "相手"
                reply, cards = await reader.get_compatibility_reading(target)
                await _reply(event.reply_token, reply)
                await save_reading(user_id, text, cards, reply)
                await increment_daily_usage(user_id)
            continue

        # ── Daily limit check ──
        if plan_cfg.daily_limit > 0:
            today_count = await get_today_reading_count(user_id)
            if today_count >= plan_cfg.daily_limit:
                await _reply(event.reply_token,
                    f"⏰ 本日の占い回数（{plan_cfg.daily_limit}回）に達しました。\n\n"
                    "「プラン」でアップグレードすると無制限に占えます✨")
                continue

        # ── Spread size check ──
        num_cards = _detect_num_cards(text)
        if num_cards > plan_cfg.max_cards:
            spread_names = {3: "3枚引き", 5: "5枚引き", 10: "ケルト十字（10枚）"}
            feature = spread_names.get(num_cards, f"{num_cards}枚引き")
            await _reply(event.reply_token, get_upgrade_prompt(plan_type, feature))
            continue

        # ── Theme detection (fall back if not allowed by plan) ──
        theme = _detect_theme(text)
        if theme and theme not in plan_cfg.themes_allowed:
            theme = None

        # ── Execute reading ──
        reply, cards = await reader.get_reading_async(
            text, num_cards, plan_cfg.detail_level, theme
        )
        await _reply(event.reply_token, reply)

        if plan_cfg.history_limit != 0:
            await save_reading(user_id, text, cards, reply)

        await increment_daily_usage(user_id)

    return "OK"


# ── Stripe webhook ─────────────────────────────────────────────────────────────

@app.post("/stripe-webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(alias="Stripe-Signature", default=""),
) -> dict:
    payload = await request.body()
    event = parse_stripe_event(payload, stripe_signature)
    if event is None:
        raise HTTPException(status_code=400, detail="Invalid Stripe event")

    event_type = event["type"]

    if event_type == "checkout.session.completed":
        session      = event["data"]["object"]
        line_user_id = (
            session.get("client_reference_id")
            or session.get("metadata", {}).get("line_user_id")
        )
        plan = session.get("metadata", {}).get("plan")

        if line_user_id and plan:
            expires_at = None
            if plan == "trial":
                exp = datetime.now(tz=timezone.utc) + timedelta(days=30)
                expires_at = exp.isoformat()

            await update_user_plan(
                line_user_id,
                plan,
                expires_at,
                stripe_customer_id=session.get("customer"),
                stripe_subscription_id=session.get("subscription"),
            )

            plan_labels = {
                "trial":   "お試しプラン（30日間）",
                "basic":   "ベーシックプラン",
                "premium": "プレミアムプラン",
            }
            try:
                await _push(line_user_id,
                    f"✨ {plan_labels.get(plan, plan)}のお申し込みが完了しました！\n\n"
                    "プレミアム機能をお楽しみください🔮\n"
                    "「ヘルプ」で使える機能を確認できます。")
            except Exception:
                pass

    elif event_type in ("customer.subscription.deleted", "customer.subscription.updated"):
        subscription = event["data"]["object"]
        if subscription.get("status") in ("canceled", "unpaid", "past_due"):
            customer_id = subscription.get("customer")
            if customer_id:
                user = await get_user_by_stripe_customer(customer_id)
                if user:
                    await update_user_plan(user["user_id"], "free")
                    try:
                        await _push(user["user_id"],
                            "📣 サブスクリプションが終了しました。\n"
                            "無料プランに戻りました。\n\n"
                            "「プラン申し込み」でいつでも再開できます🔮")
                    except Exception:
                        pass

    return {"status": "ok"}


# ── Payment landing pages ──────────────────────────────────────────────────────

@app.get("/payment-success")
async def payment_success() -> dict:
    return {"message": "お支払いが完了しました。LINEに通知が届きます。ありがとうございます！"}


@app.get("/payment-cancel")
async def payment_cancel() -> dict:
    return {"message": "お支払いがキャンセルされました。またのご利用をお待ちしております。"}


# ── Health check ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
