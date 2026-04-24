import os
from typing import Optional

_stripe_available = False
try:
    import stripe  # type: ignore
    _api_key = os.environ.get("STRIPE_SECRET_KEY", "")
    if _api_key:
        stripe.api_key = _api_key
        _stripe_available = True
except ImportError:
    pass

_PRICE_IDS = {
    "trial":   os.environ.get("STRIPE_PRICE_TRIAL", ""),
    "basic":   os.environ.get("STRIPE_PRICE_BASIC", ""),
    "premium": os.environ.get("STRIPE_PRICE_PREMIUM", ""),
}

_PLAN_MODES = {
    "trial":   "payment",       # one-time ¥500
    "basic":   "subscription",  # ¥980/month
    "premium": "subscription",  # ¥1,980/month
}

_BASE_URL = os.environ.get("APP_BASE_URL", "")


def create_checkout_url(plan: str, line_user_id: str) -> Optional[str]:
    if not _stripe_available:
        return None
    price_id = _PRICE_IDS.get(plan)
    if not price_id or not _BASE_URL:
        return None
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode=_PLAN_MODES[plan],
            client_reference_id=line_user_id,
            success_url=f"{_BASE_URL}/payment-success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{_BASE_URL}/payment-cancel",
            metadata={"plan": plan, "line_user_id": line_user_id},
        )
        return session.url
    except Exception:
        return None


def parse_stripe_event(payload: bytes, sig_header: str):
    if not _stripe_available:
        return None
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    if not webhook_secret:
        return None
    try:
        return stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except Exception:
        return None
