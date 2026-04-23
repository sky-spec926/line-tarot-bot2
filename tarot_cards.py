MAJOR_ARCANA = [
    {"id": 0,  "en_name": "The Fool",           "ja_name": "愚者",       "emoji": "🃏"},
    {"id": 1,  "en_name": "The Magician",        "ja_name": "魔術師",     "emoji": "🔮"},
    {"id": 2,  "en_name": "The High Priestess",  "ja_name": "女教皇",     "emoji": "📿"},
    {"id": 3,  "en_name": "The Empress",         "ja_name": "女帝",       "emoji": "👑"},
    {"id": 4,  "en_name": "The Emperor",         "ja_name": "皇帝",       "emoji": "⚔️"},
    {"id": 5,  "en_name": "The Hierophant",      "ja_name": "教皇",       "emoji": "✝️"},
    {"id": 6,  "en_name": "The Lovers",          "ja_name": "恋人",       "emoji": "💑"},
    {"id": 7,  "en_name": "The Chariot",         "ja_name": "戦車",       "emoji": "🏆"},
    {"id": 8,  "en_name": "Strength",            "ja_name": "力",         "emoji": "💪"},
    {"id": 9,  "en_name": "The Hermit",          "ja_name": "隠者",       "emoji": "🕯️"},
    {"id": 10, "en_name": "Wheel of Fortune",    "ja_name": "運命の輪",   "emoji": "☸️"},
    {"id": 11, "en_name": "Justice",             "ja_name": "正義",       "emoji": "⚖️"},
    {"id": 12, "en_name": "The Hanged Man",      "ja_name": "吊られた男", "emoji": "🙃"},
    {"id": 13, "en_name": "Death",               "ja_name": "死神",       "emoji": "💀"},
    {"id": 14, "en_name": "Temperance",          "ja_name": "節制",       "emoji": "🌊"},
    {"id": 15, "en_name": "The Devil",           "ja_name": "悪魔",       "emoji": "😈"},
    {"id": 16, "en_name": "The Tower",           "ja_name": "塔",         "emoji": "⚡"},
    {"id": 17, "en_name": "The Star",            "ja_name": "星",         "emoji": "⭐"},
    {"id": 18, "en_name": "The Moon",            "ja_name": "月",         "emoji": "🌙"},
    {"id": 19, "en_name": "The Sun",             "ja_name": "太陽",       "emoji": "☀️"},
    {"id": 20, "en_name": "Judgement",           "ja_name": "審判",       "emoji": "📯"},
    {"id": 21, "en_name": "The World",           "ja_name": "世界",       "emoji": "🌍"},
]

_SUITS = [
    {"en": "Wands",     "ja": "ワンド",     "emoji": "🔥"},
    {"en": "Cups",      "ja": "カップ",     "emoji": "🍷"},
    {"en": "Swords",    "ja": "ソード",     "emoji": "🗡️"},
    {"en": "Pentacles", "ja": "ペンタクル", "emoji": "💰"},
]
_NUM_JA   = ["", "エース", "二", "三", "四", "五", "六", "七", "八", "九", "十"]
_COURT_JA = [("Page", "ペイジ"), ("Knight", "ナイト"), ("Queen", "クイーン"), ("King", "キング")]


def _build_minor() -> list[dict]:
    cards = []
    for suit in _SUITS:
        for n in range(1, 11):
            cards.append({
                "en_name": f"{'Ace' if n == 1 else n} of {suit['en']}",
                "ja_name": f"{suit['ja']}の{_NUM_JA[n]}",
                "emoji":   suit["emoji"],
            })
        for en_c, ja_c in _COURT_JA:
            cards.append({
                "en_name": f"{en_c} of {suit['en']}",
                "ja_name": f"{suit['ja']}の{ja_c}",
                "emoji":   suit["emoji"],
            })
    return cards


MINOR_ARCANA = _build_minor()
FULL_DECK = MAJOR_ARCANA + MINOR_ARCANA  # 78枚
