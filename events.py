"""Event and community-milestone modifiers that change live game economy.

Configured by `EVENT_SETTINGS` and `BATTLEPASS_MILESTONES` in settings.json.
Restart the bot after edits. Existing cooldowns already ticking are left unchanged.

Community Battle Pass milestones are unlocked from the sum of every player's
Battle Pass level. Each milestone lasts `duration_days` from first unlock.
For a given buff type, a higher milestone overwrites a lower one of that type
(e.g. 500 overwrites 100 for cooldown/shop; 750 overwrites 250 for XP; 1000
overwrites earlier cooldown). Unrelated tracks stay active until overwritten.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

from pymongo import ReturnDocument
from pymongo.errors import PyMongoError

import functions as func

_STATE_ID = "battlepass_milestones"
_STATE_FILE = os.path.join(func.ROOT_DIR, "bot_state.json")
_community_state: dict[str, Any] = {
    "total_levels": 0,
    "season_id": "",
    "unlocked": {},
}


def get_event_settings() -> dict[str, Any]:
    return func.settings.EVENT_SETTINGS or {}


def get_milestone_settings() -> dict[str, Any]:
    return func.settings.BATTLEPASS_MILESTONES or {}


def is_active() -> bool:
    return bool(get_event_settings().get("enabled", False))


def name() -> str:
    return str(get_event_settings().get("name") or "Event")


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _percent_fraction(value: Any, default: float = 0.0) -> float:
    return max(0.0, min(1.0, _as_float(value, default) / 100.0))


def _milestones_enabled() -> bool:
    return bool(get_milestone_settings().get("enabled", False))


def _milestone_list() -> list[dict[str, Any]]:
    raw = get_milestone_settings().get("milestones", [])
    if not isinstance(raw, list):
        return []
    parsed = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            total_levels = int(item.get("total_levels", 0))
        except (TypeError, ValueError):
            continue
        if total_levels <= 0:
            continue
        parsed.append({**item, "total_levels": total_levels})
    parsed.sort(key=lambda item: item["total_levels"])
    return parsed


def _duration_seconds() -> float:
    days = max(0.0, _as_float(get_milestone_settings().get("duration_days", 14), 14.0))
    return days * 86_400


def _unlocked_at(threshold: int) -> float | None:
    unlocked = _community_state.get("unlocked") or {}
    value = unlocked.get(str(threshold), unlocked.get(threshold))
    try:
        ts = float(value)
    except (TypeError, ValueError):
        return None
    return ts if ts > 0 else None


def _is_milestone_live(threshold: int, now: float | None = None) -> bool:
    unlocked_at = _unlocked_at(threshold)
    if not unlocked_at:
        return False
    now = time.time() if now is None else now
    return now < unlocked_at + _duration_seconds()


def _best_live_value(field: str, default: float = 0.0) -> tuple[float, int | None, float | None]:
    """Highest live milestone that defines `field`. Returns (value, threshold, expires_at)."""
    if not _milestones_enabled():
        return default, None, None

    now = time.time()
    best_threshold = None
    best_value = default
    best_expires = None
    for item in _milestone_list():
        if field not in item:
            continue
        threshold = item["total_levels"]
        if not _is_milestone_live(threshold, now):
            continue
        best_threshold = threshold
        best_value = item.get(field, default)
        unlocked_at = _unlocked_at(threshold) or now
        best_expires = unlocked_at + _duration_seconds()
    return best_value, best_threshold, best_expires


def community_total_levels() -> int:
    try:
        return max(0, int(_community_state.get("total_levels", 0)))
    except (TypeError, ValueError):
        return 0


def milestone_cooldown_fraction() -> float:
    value, _, _ = _best_live_value("cooldown_reduction_percent", 0)
    return _percent_fraction(value, 0)


def milestone_shop_sale_fraction() -> float:
    value, _, _ = _best_live_value("shop_sale_percent", 0)
    return _percent_fraction(value, 0)


def milestone_convert_multiplier() -> float:
    value, threshold, _ = _best_live_value("convert_candy_multiplier", 1)
    if threshold is None:
        return 1.0
    return max(0.0, _as_float(value, 1.0))


def milestone_xp_percent() -> float:
    value, threshold, _ = _best_live_value("battlepass_xp_percent", 0)
    if threshold is None:
        return 0.0
    return max(0.0, _as_float(value, 0.0))


def battlepass_xp_multiplier() -> float:
    return 1.0 + (milestone_xp_percent() / 100.0)


def cooldown_factor() -> float:
    event_factor = 1.0
    if is_active():
        event_factor = 1.0 - _percent_fraction(get_event_settings().get("cooldown_reduction_percent", 0))
    return event_factor * (1.0 - milestone_cooldown_fraction())


def cooldown_expiry(base_seconds: float, *, potion_speed: float = 0.0, apply_reduction: bool = True) -> float:
    """Unix timestamp for a newly started cooldown after potions, events, and milestones.

    Daily (`qd`) always uses `apply_reduction=False` so event/milestone CD cuts do not apply.
    """
    duration = max(0.0, float(base_seconds or 0))
    duration *= max(0.0, 1.0 - float(potion_speed or 0))
    if apply_reduction:
        duration *= cooldown_factor()
    return time.time() + duration


def convert_multiplier() -> float:
    event_mult = 1.0
    if is_active():
        event_mult = max(0.0, _as_float(get_event_settings().get("convert_candy_multiplier", 1), 1.0))
    return event_mult * milestone_convert_multiplier()


def convert_candies(base_amount: int | float) -> int:
    return int(max(0.0, float(base_amount or 0) * convert_multiplier()))


def shop_sale_fraction(item_key: str | None = None) -> float:
    event_sale = 0.0
    if is_active():
        event_sale = _percent_fraction(get_event_settings().get("shop_sale_percent", 0))

    milestone_sale = 0.0
    if item_key != "battlepass.pass":
        milestone_sale = milestone_shop_sale_fraction()

    return 1.0 - (1.0 - event_sale) * (1.0 - milestone_sale)


def shop_price(base_price: int | float, item_key: str | None = None) -> int:
    return max(0, int(round(float(base_price or 0) * (1.0 - shop_sale_fraction(item_key)))))


def community_progress_text() -> str:
    if not _milestones_enabled():
        return ""

    total = community_total_levels()
    lines = [f"Community BP levels: `{total}`"]
    now = time.time()
    next_goal = None
    for item in _milestone_list():
        threshold = item["total_levels"]
        unlocked_at = _unlocked_at(threshold)
        live = _is_milestone_live(threshold, now)
        if unlocked_at and live:
            remaining = int((unlocked_at + _duration_seconds()) - now)
            hours = max(0, remaining // 3600)
            lines.append(f"✅ {threshold}: active (`{hours}h` left)")
        elif unlocked_at:
            lines.append(f"⌛ {threshold}: expired")
        elif next_goal is None:
            next_goal = threshold

    if next_goal is not None:
        lines.append(f"Next unlock: `{next_goal}` ({max(0, next_goal - total)} to go)")
    elif _milestone_list():
        lines.append("All community milestones unlocked.")

    buffs = []
    cd = milestone_cooldown_fraction()
    if cd:
        buffs.append(f"cooldown -{int(round(cd * 100))}%")
    shop = milestone_shop_sale_fraction()
    if shop:
        buffs.append(f"shop {int(round(shop * 100))}% off (excluding battlepass)")
    xp = milestone_xp_percent()
    if xp:
        buffs.append(f"BP XP +{int(round(xp))}%")
    convert = milestone_convert_multiplier()
    if convert != 1.0:
        buffs.append(f"convert x{convert:g}")
    if buffs:
        lines.append("Active community buffs: " + ", ".join(buffs))

    return "\n".join(lines)


def _disable_state_db(error: Exception) -> None:
    """Stop using MongoDB for milestone state and persist to a local file instead."""
    func.STATE_DB = None
    func.logger.warning(
        f"Cannot use the MongoDB [bot_state] collection ({error}). "
        f"Community Battle Pass milestones will be stored in {_STATE_FILE} instead."
    )


def _read_state_file() -> dict[str, Any]:
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as file:
            doc = json.load(file)
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as error:
        func.logger.warning(f"Unable to read {_STATE_FILE}: {error}")
        return {}
    return doc if isinstance(doc, dict) else {}


def _write_state_file(doc: dict[str, Any]) -> None:
    try:
        with open(_STATE_FILE, "w", encoding="utf-8") as file:
            json.dump(doc, file, indent=4)
    except OSError as error:
        func.logger.warning(f"Unable to write {_STATE_FILE}: {error}")


async def _read_state() -> dict[str, Any]:
    if func.STATE_DB is not None:
        try:
            doc = await func.STATE_DB.find_one({"_id": _STATE_ID})
            return doc if isinstance(doc, dict) else {}
        except PyMongoError as error:
            _disable_state_db(error)
    return _read_state_file()


async def _write_state(fields: dict[str, Any]) -> None:
    if func.STATE_DB is not None:
        try:
            await func.STATE_DB.update_one({"_id": _STATE_ID}, {"$set": fields}, upsert=True)
            return
        except PyMongoError as error:
            _disable_state_db(error)
    _write_state_file({**_read_state_file(), **fields, "_id": _STATE_ID})


async def load_community_state() -> None:
    """Load or seed the global milestone document. Call once after Mongo connects."""
    global _community_state

    season_id = str(func.get_battlepass_settings().get("season_id", "default"))
    doc = await _read_state()
    total = await _sum_user_battlepass_levels(season_id)

    if doc.get("season_id") != season_id:
        doc = {"season_id": season_id, "total_levels": total, "unlocked": {}}
        await _write_state(doc)
        func.logger.info(f"Community Battle Pass milestones reset/seeded for season {season_id} at {total} total levels.")
    elif total != int(doc.get("total_levels", 0) or 0):
        doc["total_levels"] = total
        await _write_state({"total_levels": total})

    _community_state = {
        "total_levels": int(doc.get("total_levels", 0) or 0),
        "season_id": season_id,
        "unlocked": dict(doc.get("unlocked") or {}),
    }
    await _unlock_reached_milestones()


async def add_community_levels(delta: int) -> None:
    if delta <= 0 or not _milestones_enabled():
        return

    if func.STATE_DB is not None:
        try:
            doc = await func.STATE_DB.find_one_and_update(
                {"_id": _STATE_ID},
                {
                    "$inc": {"total_levels": int(delta)},
                    "$setOnInsert": {
                        "season_id": str(func.get_battlepass_settings().get("season_id", "default")),
                        "unlocked": {},
                    },
                },
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
        except PyMongoError as error:
            _disable_state_db(error)
        else:
            if isinstance(doc, dict):
                _community_state["total_levels"] = int(doc.get("total_levels", 0) or 0)
                if doc.get("unlocked") is not None:
                    _community_state["unlocked"] = dict(doc.get("unlocked") or {})
            await _unlock_reached_milestones()
            return

    _community_state["total_levels"] = community_total_levels() + int(delta)
    await _write_state({
        "season_id": _community_state.get("season_id") or str(func.get_battlepass_settings().get("season_id", "default")),
        "total_levels": _community_state["total_levels"],
    })
    await _unlock_reached_milestones()


async def _unlock_reached_milestones() -> None:
    if not _milestones_enabled():
        return

    total = community_total_levels()
    unlocked = dict(_community_state.get("unlocked") or {})
    now = time.time()
    newly = []
    for item in _milestone_list():
        key = str(item["total_levels"])
        if total < item["total_levels"]:
            continue
        if _unlocked_at(item["total_levels"]):
            continue
        unlocked[key] = now
        newly.append(item["total_levels"])

    if not newly:
        return

    _community_state["unlocked"] = unlocked
    await _write_state({"unlocked": unlocked, "season_id": _community_state.get("season_id")})
    func.logger.info(
        f"Community Battle Pass milestone(s) unlocked at {total} total levels: {newly}"
    )


async def _sum_user_battlepass_levels(season_id: str) -> int:
    if func.USERS_DB is None:
        return 0

    bp = func.get_battlepass_settings()
    xp_per_level = max(1, int(bp.get("xp_per_level", 150)))
    max_level = max(1, int(bp.get("max_level", 100)))
    pipeline = [
        {"$match": {"battlepass.season_id": season_id}},
        {"$project": {
            "level": {
                "$min": [
                    max_level,
                    {"$floor": {"$divide": [{"$ifNull": ["$battlepass.xp", 0]}, xp_per_level]}},
                ]
            }
        }},
        {"$group": {"_id": None, "total": {"$sum": "$level"}}},
    ]
    try:
        rows = await func.USERS_DB.aggregate(pipeline).to_list(1)
    except Exception:
        func.logger.exception("Failed to sum community Battle Pass levels")
        return 0
    if not rows:
        return 0
    try:
        return max(0, int(rows[0].get("total", 0) or 0))
    except (TypeError, ValueError):
        return 0
