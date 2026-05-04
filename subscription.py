from dataclasses import dataclass
from enum import Enum


class PlanType(str, Enum):
    FREE = "free"
    TRIAL = "trial"
    BASIC = "basic"
    PREMIUM = "premium"


@dataclass
class PlanConfig:
    name: str
    price_display: str
    daily_limit: int        # -1 = unlimited
    max_cards: int
    history_limit: int      # 0 = none, -1 = unlimited
    detail_level: str
    max_tokens: int
    themes_allowed: list
    has_daily_fortune: bool
    has_compatibility: bool
    has_numerology: bool
    has_personal_reading: bool
    features_display: list


PLANS: dict = {
    PlanType.FREE: PlanConfig(
        name="無料プラン",
        price_display="無料",
        daily_limit=3,
        max_cards=1,
        history_limit=0,
        detail_level="basic",
        max_tokens=400,
        themes_allowed=[],
        has_daily_fortune=False,
        has_compatibility=False,
        has_numerology=False,
        has_personal_reading=False,
        features_display=[
            "・1枚引き",
            "・1日3回まで",
            "・基本的な解釈",
        ],
    ),
    PlanType.TRIAL: PlanConfig(
        name="お試しプラン",
        price_display="¥500（30日間・買い切り）",
        daily_limit=5,
        max_cards=3,
        history_limit=5,
        detail_level="standard",
        max_tokens=500,
        themes_allowed=[],
        has_daily_fortune=False,
        has_compatibility=False,
        has_numerology=False,
        has_personal_reading=False,
        features_display=[
            "・1枚引き・3枚引き（過去・現在・未来）",
            "・1日5回まで",
            "・標準的な解釈",
            "・占い履歴5件",
        ],
    ),
    PlanType.BASIC: PlanConfig(
        name="ベーシックプラン",
        price_display="¥980/月",
        daily_limit=-1,
        max_cards=5,
        history_limit=20,
        detail_level="detailed",
        max_tokens=700,
        themes_allowed=["恋愛", "仕事", "金運"],
        has_daily_fortune=False,
        has_compatibility=False,
        has_numerology=True,
        has_personal_reading=False,
        features_display=[
            "・1枚〜5枚引き",
            "・無制限",
            "・詳しい解釈",
            "・占い履歴20件",
            "・テーマ別占い（恋愛・仕事・金運）",
            "・数秘術（運命数鑑定）",
        ],
    ),
    PlanType.PREMIUM: PlanConfig(
        name="プレミアムプラン",
        price_display="¥1,980/月",
        daily_limit=-1,
        max_cards=10,
        history_limit=-1,
        detail_level="premium",
        max_tokens=1000,
        themes_allowed=["恋愛", "仕事", "金運", "健康", "人間関係"],
        has_daily_fortune=True,
        has_compatibility=True,
        has_numerology=True,
        has_personal_reading=True,
        features_display=[
            "・全スプレッド（〜10枚ケルト十字）",
            "・無制限",
            "・最高レベルの詳細解釈",
            "・占い履歴無制限",
            "・テーマ別占い（5テーマ）",
            "・毎日の運勢",
            "・相性占い",
            "・数秘術（運命数鑑定）",
            "・個人鑑定（お名前＋生年月日）",
        ],
    ),
}

_PLAN_ORDER = [PlanType.FREE, PlanType.TRIAL, PlanType.BASIC, PlanType.PREMIUM]


def get_plan_comparison_text() -> str:
    lines = ["💎 タロット占い 料金プラン\n"]
    for plan_type in _PLAN_ORDER:
        cfg = PLANS[plan_type]
        lines.append(f"【{cfg.name}】{cfg.price_display}")
        for feat in cfg.features_display:
            lines.append(feat)
        lines.append("")
    lines.append("━━━━━━━━━━━━")
    lines.append("▶ プランを申し込む")
    lines.append("「お試し申し込み」　¥500（30日）")
    lines.append("「ベーシック申し込み」　¥980/月")
    lines.append("「プレミアム申し込み」　¥1,980/月")
    return "\n".join(lines)


def get_upgrade_prompt(current_plan: PlanType, needed_feature: str) -> str:
    upgrade_map = {
        PlanType.FREE: ("お試し申し込み", PLANS[PlanType.TRIAL]),
        PlanType.TRIAL: ("ベーシック申し込み", PLANS[PlanType.BASIC]),
        PlanType.BASIC: ("プレミアム申し込み", PLANS[PlanType.PREMIUM]),
    }
    if current_plan not in upgrade_map:
        return "「プラン」と送信して料金プランを確認してください。"

    cmd, next_cfg = upgrade_map[current_plan]
    return (
        f"✨ {needed_feature}は「{next_cfg.name}」以上でご利用いただけます。\n\n"
        f"「{cmd}」で{next_cfg.price_display}でお申し込みいただけます！\n"
        "または「プラン」で全プランを比較できます。"
    )
