"""
78장 타로 덱 id 목록 및 셔플. assets/tarot/tarot_<id>.png / reverse/tarot_<id>_r.png 와 일치.
tarot_milk_tea, tarotcards.png, tarot_back.png 는 덱에 포함하지 않음.
"""

import random
from typing import List


def _major_ids() -> List[str]:
    return [
        "fool", "magician", "high_priestess", "empress", "emperor",
        "hierophant", "lovers", "chariot", "strength", "hermit",
        "wheel_of_fortune", "justice", "hanged_man", "death", "temperance",
        "devil", "tower", "star", "moon", "sun", "judgement", "world",
    ]


def _minor_ids(suit: str) -> List[str]:
    return (
        [f"{suit}_{i}" for i in range(1, 11)]
        + [f"{suit}_page", f"{suit}_knight", f"{suit}_queen", f"{suit}_king"]
    )


TAROT_CARD_IDS: List[str] = _major_ids() + _minor_ids("cups") + _minor_ids("pentacles") + _minor_ids("swords") + _minor_ids("wands")
assert len(TAROT_CARD_IDS) == 78, f"덱 78장 아님: {len(TAROT_CARD_IDS)}"


def build_deck(shuffle: bool = True) -> List[dict]:
    """
    78장 덱 구성. 각 항목은 {"id": str, "reversed": bool}.
    shuffle=True 이면 순서와 정/역을 랜덤.
    """
    deck = []
    for cid in TAROT_CARD_IDS:
        deck.append({"id": cid, "reversed": random.random() < 0.5})
    if shuffle:
        random.shuffle(deck)
    return deck
