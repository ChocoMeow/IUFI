"""Event and community-milestone modifiers that change live game economy.

Configured by `EVENT_SETTINGS` and `BATTLEPASS_MILESTONES` in settings.json.
Restart the bot after edits. Existing cooldowns already ticking are left unchanged.

Community Battle Pass milestones are unlocked from the sum of every player's
Battle Pass level. Each milestone lasts `duration_days` from first unlock.
For a given buff type, a higher milestone overwrites a lower one of that type
(e.g. 500 overwrites 100 for cooldown/shop; 750 overwrites 250 for XP /
quest potions; 1000 overwrites earlier cooldown and sets pity growth).
Unrelated tracks stay active until overwritten.
"""
from __future__ import annotations

import json
import os
import random
import time
from collections import Counter
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

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


def milestone_quest_potion_multiplier() -> float:
    """Multiplies potion amounts granted by daily/weekly quest rewards."""
    value, threshold, _ = _best_live_value("quest_potion_multiplier", 1)
    if threshold is None:
        return 1.0
    return max(0.0, _as_float(value, 1.0))


def milestone_pity_count_multiplier() -> float:
    """Multiplies pity counter increase on each normal roll."""
    value, threshold, _ = _best_live_value("pity_count_multiplier", 1)
    if threshold is None:
        return 1.0
    return max(0.0, _as_float(value, 1.0))


def battlepass_xp_multiplier() -> float:
    return 1.0 + (milestone_xp_percent() / 100.0)


def quest_potion_multiplier() -> float:
    return milestone_quest_potion_multiplier()


def pity_count_multiplier() -> float:
    return milestone_pity_count_multiplier()


# ---------------------------------------------------------------------------
# Xmas event (XMAS_EVENT in settings.json): daily countdown buffs and Holiday Stockings.
# Dates use the timezone from settings (KST). `force_day` overrides the day for testing,
# and also keeps stockings open.
# ---------------------------------------------------------------------------

def get_xmas_settings() -> dict[str, Any]:
    return func.settings.XMAS_EVENT or {}


def _xmas_countdown_settings() -> dict[str, Any]:
    return get_xmas_settings().get("countdown") or {}


def _xmas_stocking_settings() -> dict[str, Any]:
    return get_xmas_settings().get("stocking") or {}


def _xmas_today() -> date:
    tz = ZoneInfo(str(get_xmas_settings().get("timezone") or "Asia/Seoul"))
    return datetime.now(tz).date()


def _xmas_days() -> int:
    return max(1, int(_as_float(_xmas_countdown_settings().get("days", 25), 25)))


def xmas_countdown_day() -> int | None:
    """Day 1..days for today, or None when the countdown is off or outside its window."""
    if not (get_xmas_settings().get("enabled") and _xmas_countdown_settings().get("enabled")):
        return None

    force_day = _xmas_countdown_settings().get("force_day")
    if force_day is not None:
        try:
            day = int(force_day)
        except (TypeError, ValueError):
            return None
    else:
        start_raw = _xmas_countdown_settings().get("start_date")
        if not start_raw:
            return None
        try:
            start = date.fromisoformat(str(start_raw))
        except ValueError:
            return None
        day = (_xmas_today() - start).days + 1

    return day if 1 <= day <= _xmas_days() else None


# Buff types a day entry in `countdown.schedule` can use. Each entry is
# {"type": <key>, <value field>, optional "label"}. A day may list several buffs.
_XMAS_BUFF_TYPES: dict[str, dict[str, Any]] = {
    "roll_cooldown": {
        "label": "Roll Cooldown Reduction",
        "detail": lambda b: f"{_as_float(b.get('percent'), 0):g}% off /roll cooldown",
        "short": lambda b: f"Roll CD -{_as_float(b.get('percent'), 0):g}%",
    },
    "convert_multiplier": {
        "label": "Starcandy Conversion",
        "detail": lambda b: f"{_as_float(b.get('multiplier'), 1):g}x Starcandies when converting cards",
        "short": lambda b: f"Convert {_as_float(b.get('multiplier'), 1):g}x",
    },
    "shop_sale": {
        "label": "Shop Sale",
        "detail": lambda b: f"{_as_float(b.get('percent'), 0):g}% off shop (Battle Pass included)",
        "short": lambda b: f"Shop -{_as_float(b.get('percent'), 0):g}%",
    },
    "drop_rate": {
        "label": "Random Drops",
        "detail": lambda b: f"{_as_float(b.get('multiplier'), 1):g}x random card and Battle Pass XP drops",
        "short": lambda b: f"Drops {_as_float(b.get('multiplier'), 1):g}x",
    },
    "santa_iu": {
        "label": "Santa IU Buff",
        "detail": lambda b: f"{_as_float(b.get('proc_percent'), 0):g}% chance to reset /roll cooldown",
        "short": lambda b: f"Santa {_as_float(b.get('proc_percent'), 0):g}%",
    },
}
_xmas_warned_types: set[str] = set()


def xmas_buffs(day: int | None = None) -> list[dict[str, Any]]:
    """Buff entries configured for `day` (defaults to today). Unknown types are skipped with a warning."""
    if day is None:
        day = xmas_countdown_day()
    if day is None:
        return []

    schedule = _xmas_countdown_settings().get("schedule") or {}
    entries = schedule.get(str(day)) if isinstance(schedule, dict) else None
    if isinstance(entries, dict):
        entries = [entries]

    buffs = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        buff_type = str(entry.get("type"))
        if buff_type not in _XMAS_BUFF_TYPES:
            if buff_type not in _xmas_warned_types:
                _xmas_warned_types.add(buff_type)
                func.logger.warning(
                    f"XMAS_EVENT day {day}: unknown buff type [{buff_type}]. Valid types: {', '.join(_XMAS_BUFF_TYPES)}"
                )
            continue
        buffs.append(entry)
    return buffs


def _xmas_entries(buff_type: str) -> list[dict[str, Any]]:
    return [buff for buff in xmas_buffs() if buff.get("type") == buff_type]


def xmas_roll_cooldown_factor() -> float:
    """Remaining fraction of the roll cooldown. Same-type buffs on one day multiply."""
    factor = 1.0
    for buff in _xmas_entries("roll_cooldown"):
        factor *= 1.0 - _percent_fraction(buff.get("percent"), 0)
    return factor


def xmas_convert_multiplier() -> float:
    """Biggest convert multiplier among today's buffs. Buffs don't stack."""
    return max(
        (max(0.0, _as_float(buff.get("multiplier"), 1.0)) for buff in _xmas_entries("convert_multiplier")),
        default=1.0,
    )


def xmas_shop_sale_fraction() -> float:
    """Biggest shop sale among today's buffs. Buffs don't stack."""
    return max(
        (_percent_fraction(buff.get("percent"), 0) for buff in _xmas_entries("shop_sale")),
        default=0.0,
    )


def xmas_drop_rate_multiplier() -> float:
    multiplier = 1.0
    for buff in _xmas_entries("drop_rate"):
        multiplier *= max(0.0, _as_float(buff.get("multiplier"), 1.0))
    return multiplier


def xmas_santa_proc() -> bool:
    """Rolled once per normal /roll on Santa IU days. True means reset the roll cooldown."""
    miss = 1.0
    for buff in _xmas_entries("santa_iu"):
        miss *= 1.0 - _percent_fraction(buff.get("proc_percent"), 0)
    chance = 1.0 - miss
    return chance > 0 and random.random() < chance


def drop_spawn_roll() -> bool:
    """Spawn check for random card and Battle Pass XP drops (1 in 6 normally)."""
    return random.random() < min(1.0, (1 / 6) * xmas_drop_rate_multiplier())


def xmas_buff_text(buff: dict[str, Any]) -> str:
    spec = _XMAS_BUFF_TYPES[buff["type"]]
    return f"{buff.get('label') or spec['label']}: {spec['detail'](buff)}"


def xmas_day_text(day: int | None = None, *, short: bool = False, sep: str = " + ") -> str:
    """Describes every buff active on `day` (defaults to today)."""
    buffs = xmas_buffs(day)
    if not buffs:
        return "No buff"
    if short:
        return sep.join(_XMAS_BUFF_TYPES[buff["type"]]["short"](buff) for buff in buffs)
    return sep.join(xmas_buff_text(buff) for buff in buffs)


def xmas_days_left() -> int:
    """Days until Dec 25 counted from the active day, or from today when the countdown is not running."""
    day = xmas_countdown_day()
    if day is not None:
        return _xmas_days() - day
    try:
        start = date.fromisoformat(str(_xmas_countdown_settings().get("start_date")))
    except (TypeError, ValueError):
        return 0
    return max(0, (date(start.year, 12, 25) - _xmas_today()).days)


def xmas_status_text() -> str:
    """One-line banner for shop and daily embeds. Empty when no countdown day is active."""
    day = xmas_countdown_day()
    if day is None:
        return ""
    return (
        f"🎄 Day `{day}/{_xmas_days()}` · {xmas_day_text(day)} "
        f"· `{xmas_days_left()}` days until Christmas"
    )


def xmas_schedule_lines() -> list[str]:
    return [
        f"Day {day:>2}: {xmas_day_text(day, short=True)}"
        for day in range(1, _xmas_days() + 1)
    ]


def xmas_stocking_active() -> bool:
    if not (get_xmas_settings().get("enabled") and _xmas_stocking_settings().get("enabled")):
        return False
    if _xmas_countdown_settings().get("force_day") is not None:
        return True
    try:
        start = date.fromisoformat(str(_xmas_stocking_settings()["start_date"]))
        end = date.fromisoformat(str(_xmas_stocking_settings()["end_date"]))
    except (KeyError, ValueError):
        return False
    return start <= _xmas_today() <= end


def xmas_stocking_odds_text() -> str:
    weights = {str(k): _as_float(v, 0) for k, v in (_xmas_stocking_settings().get("level_weights") or {}).items()}
    total = sum(weights.values())
    if total <= 0:
        return "No stocking odds configured."
    return " / ".join(f"Lv.{k} {w / total * 100:g}%" for k, w in weights.items())


def _roll_range(bounds: Any) -> int:
    if not isinstance(bounds, (list, tuple)) or not bounds:
        return 0
    return random.randint(int(bounds[0]), int(bounds[-1]))


def open_xmas_stocking() -> tuple[int, Counter, Counter] | None:
    """Rolls one Holiday Stocking. Returns (level, rewards, lucky) or None outside the window.

    `rewards` is the full $inc payload. `lucky` counts the chance-roll hits inside it.
    """
    if not xmas_stocking_active():
        return None

    stocking = _xmas_stocking_settings()
    levels = stocking.get("levels") or {}
    weights = {str(k): _as_float(v, 0) for k, v in (stocking.get("level_weights") or {}).items()}
    level_keys = [k for k in weights if k in levels and weights[k] > 0]
    if not level_keys:
        return None

    level = random.choices(level_keys, weights=[weights[k] for k in level_keys])[0]
    cfg = levels[level]

    rewards: Counter = Counter()
    lucky: Counter = Counter()

    rewards["candies"] += _roll_range(cfg.get("candies"))
    for tier, bounds in (cfg.get("rolls") or {}).items():
        rewards[f"roll.{tier}"] += _roll_range(bounds)

    potion = cfg.get("potion") or {}
    if potion:
        count = _roll_range(potion.get("count"))
        rewards[f"potions.speed_{potion['level']}"] += count
        rewards[f"potions.luck_{potion['level']}"] += count

    for chance in cfg.get("chance_rolls") or []:
        if random.random() < _percent_fraction(chance.get("chance_percent", 0)):
            key = f"roll.{chance['tier']}"
            amount = _roll_range(chance.get("amount"))
            rewards[key] += amount
            lucky[key] += amount

    return int(level), rewards, lucky


def _xmas_reward_label(key: str) -> str:
    if key == "candies":
        return f"{func.currency_emoji()} {func.currency_name('Starcandies').title()}"
    if key.startswith("roll."):
        tier = key.split(".", 1)[1]
        emoji = (func.settings.TIERS_BASE.get(tier) or ["🎲"])[0]
        return f"{emoji} {tier.title()} Roll"
    if key.startswith("potions."):
        potion, level = key.split(".", 1)[1].split("_", 1)
        emoji = (func.settings.POTIONS_BASE.get(potion) or {}).get("emoji", "🧪")
        return f"{emoji} {potion.title()} {level.upper()} Potion"
    return key


def describe_xmas_stocking(rewards: Counter, lucky: Counter) -> str:
    lines = []
    for key, total in rewards.items():
        if not total:
            continue
        bonus = lucky.get(key, 0)
        base = total - bonus
        label = _xmas_reward_label(key)
        if base:
            lines.append(f"{label} x{base}")
        if bonus:
            lines.append(f"✨ {label} x{bonus} (lucky)")
    return "\n".join(lines)


def cooldown_factor() -> float:
    event_factor = 1.0
    if is_active():
        event_factor = 1.0 - _percent_fraction(get_event_settings().get("cooldown_reduction_percent", 0))
    return event_factor * (1.0 - milestone_cooldown_fraction())


def cooldown_expiry(base_seconds: float, *, potion_speed: float = 0.0, apply_reduction: bool = True, roll_buff: bool = False) -> float:
    """Unix timestamp for a newly started cooldown after potions, events, and milestones.

    Daily (`qd`) always uses `apply_reduction=False` so event/milestone CD cuts do not apply.
    """
    duration = max(0.0, float(base_seconds or 0))
    duration *= max(0.0, 1.0 - float(potion_speed or 0))
    if apply_reduction:
        duration *= cooldown_factor()
    if roll_buff:
        duration *= xmas_roll_cooldown_factor()
    return time.time() + duration


def convert_multiplier(*, apply_holiday: bool = True) -> float:
    """Biggest convert multiplier from the event, milestones, and Xmas buffs. Sources don't stack."""
    candidates = [milestone_convert_multiplier()]
    if is_active():
        candidates.append(max(0.0, _as_float(get_event_settings().get("convert_candy_multiplier", 1), 1.0)))
    if apply_holiday:
        candidates.append(xmas_convert_multiplier())
    return max(candidates, default=1.0)


def convert_candies(base_amount: int | float, *, apply_holiday: bool = True) -> int:
    return int(max(0.0, float(base_amount or 0) * convert_multiplier(apply_holiday=apply_holiday)))


def convert_cap_for_tier(tier: str) -> int | None:
    """Max candies one card of `tier` can convert for, as a share of its current shop roll price.

    Returns None when the tier has no shop roll or the cap is disabled.
    """
    cfg = func.settings.CONVERT_CAP or {}
    if not cfg.get("enabled"):
        return None
    base_price = (func.settings.SHOP_ROLL_PRICES or {}).get(tier)
    if base_price is None:
        return None
    price = shop_price(base_price, f"roll.{tier}")
    return int(price * _percent_fraction(cfg.get("percent_of_shop_price", 100), 1.0))


def card_convert_candies(cards: list, *, apply_holiday: bool = True) -> int:
    """Candies for converting `cards`. Multiplier applies first, then each card is capped.

    The cap only applies to cards at or below `max_star`, and only for tiers that have a shop roll.
    Cards are capped one by one, so `convertall` and `convertmass` can't add up past the cap.
    """
    multiplier = convert_multiplier(apply_holiday=apply_holiday)
    max_star = int((func.settings.CONVERT_CAP or {}).get("max_star", 5))
    total = 0.0
    for card in cards:
        value = float(card.cost) * multiplier
        if (card.stars or 0) <= max_star:
            cap = convert_cap_for_tier(card.tier[1])
            if cap is not None:
                value = min(value, cap)
        total += value
    return int(max(0.0, total))


def shop_sale_fraction(item_key: str | None = None) -> float:
    """Biggest shop sale from the event, milestones, and Xmas buffs. Sales don't stack."""
    sales = []
    if is_active():
        sales.append(_percent_fraction(get_event_settings().get("shop_sale_percent", 0)))

    # Xmas sale applies to every shop item, Battle Pass included.
    sales.append(xmas_shop_sale_fraction())

    if item_key != "battlepass.pass":
        sales.append(milestone_shop_sale_fraction())

    return max(sales, default=0.0)


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
    quest_potion = milestone_quest_potion_multiplier()
    if quest_potion != 1.0:
        buffs.append(f"quest potions x{quest_potion:g}")
    pity = milestone_pity_count_multiplier()
    if pity != 1.0:
        buffs.append(f"pity growth x{pity:g}")
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
