import os
import random
from typing import Optional

from anthropic import AsyncAnthropic

from tarot_cards import FULL_DECK

_SYSTEM_PROMPTS = {
    "basic": """あなたは経験豊富なタロット占い師です。引かれたカードを丁寧に解釈します。
- 日本語で回答する
- 180〜230文字程度でまとめる
- 温かみのある、前向きなトーンを心がける
- 正位置・逆位置を踏まえて解釈する
- 具体的なアドバイスを1つ含める
- LINEメッセージとして読みやすい改行を使う""",

    "standard": """あなたは経験豊富なタロット占い師です。引かれたカードを丁寧に解釈します。
- 日本語で回答する
- 260〜320文字程度でまとめる
- 温かみのある、前向きなトーンを心がける
- 正位置・逆位置を正確に踏まえて解釈する
- 各カードの意味に簡潔に触れる
- 具体的なアドバイスを2つ含める
- LINEメッセージとして読みやすい改行を使う""",

    "detailed": """あなたは経験豊富なタロット占い師です。引かれたカードを詳しく解釈します。
- 日本語で回答する
- 380〜460文字程度でまとめる
- 温かみのある、前向きなトーンを心がける
- 正位置・逆位置を正確に踏まえて解釈する
- テーマに焦点を当てた解釈をする
- 各カードの意味と相互関係を説明する
- 具体的なアドバイスを3つ以上含める
- LINEメッセージとして読みやすい改行を使う""",

    "premium": """あなたは最高峰のタロット占い師です。引かれたカードを非常に詳しく、多面的に解釈します。
- 日本語で回答する
- 550〜700文字程度でまとめる
- 深い洞察と温かみのあるトーンを心がける
- 正位置・逆位置を正確かつ詳細に踏まえて解釈する
- テーマに沿った深い解釈をする
- 各カードの意味と相互関係を詳しく説明する
- 過去・現在・未来の流れを含む総合的な分析をする
- 具体的で実践的なアドバイスを5つ以上含める
- LINEメッセージとして読みやすい改行を使う""",
}

_SPREAD_POSITIONS = {
    3:  ["過去", "現在", "未来"],
    5:  ["現状", "課題", "アドバイス", "近い将来", "結果"],
    10: ["現状", "課題", "意識", "潜在意識", "過去", "近い将来", "あなた", "周囲", "期待と恐れ", "結果"],
}

_SPREAD_NAMES = {
    1:  "一枚引き",
    3:  "過去・現在・未来",
    5:  "5枚スプレッド",
    10: "ケルト十字スプレッド",
}

_MAX_TOKENS = {
    "basic":    400,
    "standard": 500,
    "detailed": 700,
    "premium":  1000,
}


class TarotReader:
    def __init__(self):
        self.client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    def draw_cards(self, n: int) -> list:
        selected = random.sample(FULL_DECK, min(n, len(FULL_DECK)))
        return [{**card, "reversed": random.choice([True, False])} for card in selected]

    def _format_header(self, cards: list, num_cards: int) -> str:
        positions = _SPREAD_POSITIONS.get(num_cards, [])
        spread_name = _SPREAD_NAMES.get(num_cards, "一枚引き")
        lines = [f"🔮 タロット占いの結果（{spread_name}）\n"]
        for i, card in enumerate(cards):
            pos = f"【{positions[i]}】" if positions else ""
            direction = "逆位置🔄" if card["reversed"] else "正位置✨"
            lines.append(f"{pos}{card['emoji']} {card['ja_name']}（{direction}）")
        return "\n".join(lines)

    def _build_prompt(
        self,
        cards: list,
        question: str,
        num_cards: int,
        theme: Optional[str] = None,
    ) -> str:
        positions = _SPREAD_POSITIONS.get(num_cards, [])
        cards_desc = []
        for i, card in enumerate(cards):
            pos = f"（{positions[i]}ポジション）" if positions else ""
            direction = "逆位置" if card["reversed"] else "正位置"
            cards_desc.append(f"・{card['ja_name']}（{card['en_name']}） {direction}{pos}")

        has_question = bool(question and len(question) > 2)
        question_line = f"質問・相談: {question}" if has_question else "（特定の質問なし：総合運）"
        theme_line = f"テーマ: {theme}に焦点を当てて解釈してください。" if theme else ""

        return (
            f"スプレッド: {_SPREAD_NAMES.get(num_cards, '一枚引き')}\n"
            f"引いたカード:\n{chr(10).join(cards_desc)}\n\n"
            f"{question_line}\n"
            f"{theme_line}\n"
            "上記のカードで占いの結果をお伝えください。"
        )

    async def get_reading_async(
        self,
        question: str,
        num_cards: int = 1,
        detail_level: str = "basic",
        theme: Optional[str] = None,
    ) -> tuple:
        cards = self.draw_cards(num_cards)
        header = self._format_header(cards, num_cards)
        prompt = self._build_prompt(cards, question, num_cards, theme)
        system_prompt = _SYSTEM_PROMPTS.get(detail_level, _SYSTEM_PROMPTS["basic"])
        max_tokens = _MAX_TOKENS.get(detail_level, 400)

        response = await self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": prompt}],
        )

        reply = f"{header}\n\n{response.content[0].text}"
        return reply, cards

    async def get_daily_fortune(self) -> tuple:
        return await self.get_reading_async(
            "今日の総合的な運勢と過ごし方のアドバイス",
            num_cards=3,
            detail_level="premium",
        )

    async def get_compatibility_reading(self, target: str) -> tuple:
        return await self.get_reading_async(
            f"相性占い: {target}との相性と関係のアドバイス",
            num_cards=5,
            detail_level="premium",
            theme="恋愛",
        )
