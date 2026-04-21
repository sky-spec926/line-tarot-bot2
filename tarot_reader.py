import os
import random
from anthropic import AsyncAnthropic
from tarot_cards import MAJOR_ARCANA

_SYSTEM_PROMPT = """あなたは経験豊富なタロット占い師です。温かみがあり、洞察力に優れた占い師として、引かれたカードを丁寧に解釈します。

占いの際のガイドライン:
- 日本語で回答する
- 200〜350文字程度でまとめる
- 温かみのある、前向きなトーンを心がける
- 正位置・逆位置を正確に踏まえて解釈する
- 具体的なアドバイスを含める
- 神秘的だが理解しやすい表現を使う
- LINEメッセージとして読みやすい改行を使う"""

_SPREAD_POSITIONS = {3: ["過去", "現在", "未来"]}
_SPREAD_NAMES = {1: "一枚引き", 3: "過去・現在・未来"}


class TarotReader:
    def __init__(self):
        self.client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    def draw_cards(self, n: int) -> list[dict]:
        selected = random.sample(MAJOR_ARCANA, min(n, len(MAJOR_ARCANA)))
        return [{**card, "reversed": random.choice([True, False])} for card in selected]

    def _format_header(self, cards: list[dict], num_cards: int) -> str:
        positions = _SPREAD_POSITIONS.get(num_cards, [])
        lines = ["🔮 タロット占いの結果\n"]
        for i, card in enumerate(cards):
            pos = f"【{positions[i]}】" if positions else ""
            direction = "逆位置🔄" if card["reversed"] else "正位置✨"
            lines.append(f"{pos}{card['emoji']} {card['ja_name']}（{direction}）")
        return "\n".join(lines)

    def _build_prompt(self, cards: list[dict], question: str, num_cards: int) -> str:
        positions = _SPREAD_POSITIONS.get(num_cards, [])
        cards_desc = []
        for i, card in enumerate(cards):
            pos = f"（{positions[i]}ポジション）" if positions else ""
            direction = "逆位置" if card["reversed"] else "正位置"
            cards_desc.append(f"・{card['ja_name']}（{card['en_name']}） {direction}{pos}")

        has_question = question and len(question) > 2
        question_line = f"質問・相談: {question}" if has_question else "（特定の質問なし：総合運）"

        return (
            f"スプレッド: {_SPREAD_NAMES.get(num_cards, '一枚引き')}\n"
            f"引いたカード:\n{chr(10).join(cards_desc)}\n\n"
            f"{question_line}\n\n"
            "上記のカードで占いの結果をお伝えください。"
        )

    async def get_reading_async(self, question: str, num_cards: int = 1) -> str:
        cards = self.draw_cards(num_cards)
        header = self._format_header(cards, num_cards)
        prompt = self._build_prompt(cards, question, num_cards)

        response = await self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": prompt}],
        )

        return f"{header}\n\n{response.content[0].text}"
