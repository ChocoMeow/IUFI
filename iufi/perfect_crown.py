from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta
from io import BytesIO
from zoneinfo import ZoneInfo

import functions as func
from PIL import Image

from .objects import TempCard

KST = ZoneInfo("Asia/Seoul")

PERFECT_CROWN_INJECT_PROBABILITY = 0.1
PERFECT_CROWN_MISSING_WEIGHT = 6

ROYAL_TREASURY_DATE = datetime(2026, 5, 16, tzinfo=KST).date()

ROYAL_TREASURY_TIERS: dict[str, dict[str, str]] = {
    "mystic": {"label": "Mystic", "emoji": "🦄"},
    "legendary": {"label": "Legendary", "emoji": "👑"},
    "epic": {"label": "Epic", "emoji": "💎"},
}

ROYAL_TREASURY_TOKEN_COSTS: dict[str, int] = {
    "mystic": 12,
    "legendary": 5,
    "epic": 3,
}

PERFECT_CROWN_RELEASES: list[dict[str, str | datetime]] = [
    {"id": "pc_ep01", "label": "Episode 01", "release_at": datetime(2026, 4, 10, tzinfo=KST)},
    {"id": "pc_ep02", "label": "Episode 02", "release_at": datetime(2026, 4, 11, tzinfo=KST)},
    {"id": "pc_ep03", "label": "Episode 03", "release_at": datetime(2026, 4, 17, tzinfo=KST)},
    {"id": "pc_ep04", "label": "Episode 04", "release_at": datetime(2026, 4, 18, tzinfo=KST)},
    {"id": "pc_ep05", "label": "Episode 05", "release_at": datetime(2026, 4, 24, tzinfo=KST)},
    {"id": "pc_ep06", "label": "Episode 06", "release_at": datetime(2026, 4, 25, tzinfo=KST)},
    {"id": "pc_ep07", "label": "Episode 07", "release_at": datetime(2026, 5, 1, tzinfo=KST)},
    {"id": "pc_ep08", "label": "Episode 08", "release_at": datetime(2026, 5, 2, tzinfo=KST)},
    {"id": "pc_ep09", "label": "Episode 09", "release_at": datetime(2026, 5, 8, tzinfo=KST)},
    {"id": "pc_ep10", "label": "Episode 10", "release_at": datetime(2026, 5, 9, tzinfo=KST)},
    {"id": "pc_ep11", "label": "Episode 11", "release_at": datetime(2026, 5, 15, tzinfo=KST)},
    {"id": "pc_ep12", "label": "Episode 12", "release_at": datetime(2026, 5, 16, tzinfo=KST)},
]

PERFECT_CROWN_INDEX: dict[str, dict[str, str | datetime]] = {
    token["id"]: token for token in PERFECT_CROWN_RELEASES
}


def now_kst() -> datetime:
    return datetime.now(KST)


def is_royal_treasury_open(now: datetime | None = None) -> bool:
    now = now or now_kst()
    return now.date() == ROYAL_TREASURY_DATE


def get_user_perfect_crown_tokens(user: dict) -> set[str]:
    event_tokens = user.get("event_tokens", {}).get("perfect_crown", {})
    if isinstance(event_tokens, dict):
        return {token_id for token_id, owned in event_tokens.items() if owned}
    return set()


def get_active_token_pool(now: datetime | None = None) -> list[dict[str, str | datetime]]:
    now = now or now_kst()
    if is_royal_treasury_open(now):
        return PERFECT_CROWN_RELEASES.copy()

    active_tokens: list[dict[str, str | datetime]] = []
    for token in PERFECT_CROWN_RELEASES:
        release_at = token["release_at"]
        if not isinstance(release_at, datetime):
            continue
        if release_at <= now <= (release_at + timedelta(days=7)):
            active_tokens.append(token)
    return active_tokens


def get_weighted_pool_for_user(user: dict, now: datetime | None = None) -> tuple[list[dict[str, str | datetime]], list[int]]:
    pool = get_active_token_pool(now)
    if not pool:
        return [], []

    owned = get_user_perfect_crown_tokens(user)
    is_finale = is_royal_treasury_open(now)

    weighted: list[int] = []
    for token in pool:
        token_id = token["id"]
        if not isinstance(token_id, str):
            weighted.append(1)
            continue

        if is_finale and token_id not in owned:
            weighted.append(PERFECT_CROWN_MISSING_WEIGHT)
        else:
            weighted.append(1)

    return pool, weighted


def should_inject_token(probability: float = PERFECT_CROWN_INJECT_PROBABILITY) -> bool:
    return random.random() < probability


class PerfectCrownToken:
    def __init__(self, token_id: str, label: str, release_at: datetime):
        self.id = token_id
        self.label = label
        self.release_at = release_at
        self.owner_id: int | None = None
        self.is_gif: bool = False
        self.is_perfect_crown_token = True
        self._lock: asyncio.Lock = asyncio.Lock()

    @property
    def tier(self) -> tuple[str, str]:
        return "👑", "perfect_crown"

    @property
    def format(self) -> str:
        return "webp"

    @property
    def display_id(self) -> str:
        return f"🆔 {self.id.upper()}"

    @property
    def display_stars(self) -> str:
        return "🎁 TOKEN"

    @property
    def display_tag(self) -> str:
        return f"🏷️ {self.label}"

    @property
    def display_frame(self) -> str:
        return "🖼️ EVENT"

    def change_owner(self, owner_id: int | None = None) -> None:
        self.owner_id = owner_id

    async def image(self, *, size_rate: float = 0.2, hide_image_if_no_owner: bool = False) -> Image.Image | list[Image.Image]:
        async with self._lock:
            token_image = TempCard(f"perfect_crown/{self.id}.webp")
            try:
                return await token_image.image(size_rate=size_rate)
            except Exception:
                fallback = TempCard("cover/level1.webp")
                return await fallback.image(size_rate=size_rate)

    async def image_bytes(self) -> BytesIO:
        image = await self.image()
        image_bytes = BytesIO()
        if isinstance(image, list):
            image[0].save(image_bytes, format="WEBP", save_all=True, append_images=image[1:], loop=0, duration=100, optimize=False)
        else:
            image.save(image_bytes, format="WEBP")
        image_bytes.seek(0)
        return image_bytes

    def __str__(self) -> str:
        return f"👑 {self.label}"


def create_token(token_data: dict[str, str | datetime]) -> PerfectCrownToken:
    token_id = str(token_data["id"])
    label = str(token_data["label"])
    release_at = token_data["release_at"]
    if not isinstance(release_at, datetime):
        release_at = now_kst()
    return PerfectCrownToken(token_id=token_id, label=label, release_at=release_at)


def inject_perfect_crown_token(cards: list, user: dict, probability: float = PERFECT_CROWN_INJECT_PROBABILITY, now: datetime | None = None) -> list:
    if not cards or not should_inject_token(probability):
        return cards

    pool, weights = get_weighted_pool_for_user(user, now)
    if not pool:
        return cards

    selected = random.choices(pool, weights=weights, k=1)[0]
    token = create_token(selected)
    replace_index = random.randint(0, len(cards) - 1)
    cards[replace_index] = token
    return cards


def build_perfect_crown_claim_update(token_id: str) -> dict:
    return {
        "$set": {f"event_tokens.perfect_crown.{token_id}": True},
        "$inc": {"event_tokens.perfect_crown_count": 1},
    }


def get_treasury_card_ids_for_tier(tier: str) -> list[str]:
    cards_by_tier = func.settings.PERFECT_CROWN_TREASURY_CARDS or {}
    return [str(card_id) for card_id in cards_by_tier.get(tier, [])]


def get_treasury_cards_for_tier(tier: str) -> list:
    from .pool import CardPool

    cards: list = []
    for card_id in get_treasury_card_ids_for_tier(tier):
        cards.append(CardPool.get_card(card_id))
    return cards


async def ensure_royal_treasury_cards_claimed(bot_user_id: int) -> dict[str, int]:
    from .pool import CardPool

    synced = 0
    skipped = 0

    for tier in ROYAL_TREASURY_TIERS.keys():
        for card in get_treasury_cards_for_tier(tier):
            if not card:
                skipped += 1
                continue

            if card.owner_id is None:
                card.change_owner(bot_user_id)
                try:
                    CardPool.remove_available_card(card)
                except Exception:
                    pass
                await func.update_card(card.id, {"$set": {"owner_id": bot_user_id}})
                synced += 1
            elif card.owner_id == bot_user_id:
                continue
            else:
                skipped += 1

    return {"synced": synced, "skipped": skipped}

