"""Time-gated debut event: 2x BP XP drops and wandering merchant state.

Merchant stock and per-person purchase totals persist in debut_event.json
(not a new Mongo collection). Player rewards still go through users.
"""
from __future__ import annotations

import asyncio
import copy
import json
import os
import random
import time
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import functions as func

_STATE_FILE = os.path.join(func.ROOT_DIR, "debut_event.json")
_lock = asyncio.Lock()
_state: dict[str, Any] = {}
_active_view: Any = None
_visit_buyers: set[str] = set()


def get_settings() -> dict[str, Any]:
    return func.settings.DEBUT_EVENT_SETTINGS or {}


def _timezone() -> ZoneInfo:
    return ZoneInfo(str(get_settings().get("timezone") or "Asia/Seoul"))


def now_kst() -> datetime:
    return datetime.now(_timezone())


def _parse_event_dt(key: str) -> datetime | None:
    raw = get_settings().get(key)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_timezone())
    else:
        parsed = parsed.astimezone(_timezone())
    return parsed


def event_start() -> datetime | None:
    return _parse_event_dt("start")


def event_end() -> datetime | None:
    return _parse_event_dt("end")


def event_id() -> str:
    return str(get_settings().get("event_id") or "debut")


def is_active(when: datetime | None = None) -> bool:
    start = event_start()
    end = event_end()
    if start is None or end is None:
        return False
    now = when or now_kst()
    return start <= now < end


def xp_drop_denominator() -> int:
    settings = get_settings()
    if is_active():
        return max(1, int(settings.get("xp_drop_chance", 3) or 3))
    return max(1, int(settings.get("xp_drop_chance_default", 6) or 6))


def items() -> list[dict[str, Any]]:
    raw = get_settings().get("items", [])
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict) and item.get("id")]


def item_by_id(sku: str) -> dict[str, Any] | None:
    for item in items():
        if str(item.get("id")) == sku:
            return item
    return None


def merchant_settings() -> dict[str, Any]:
    raw = get_settings().get("merchant") or {}
    return raw if isinstance(raw, dict) else {}


def interval_minutes() -> int:
    return max(1, int(merchant_settings().get("interval_minutes", 20) or 20))


def appearance_chance() -> int:
    return max(1, int(merchant_settings().get("chance", 4) or 4))


def min_gap_seconds() -> float:
    hours = float(merchant_settings().get("min_gap_hours", 2) or 2)
    return max(0.0, hours * 3600)


def appearance_duration() -> int:
    low = max(1, int(merchant_settings().get("duration_min_seconds", 120) or 120))
    high = max(low, int(merchant_settings().get("duration_max_seconds", 300) or 300))
    return random.randint(low, high)


def _empty_state() -> dict[str, Any]:
    remaining: dict[str, int | None] = {}
    for item in items():
        sku = str(item["id"])
        stock = item.get("stock")
        if stock is None:
            remaining[sku] = None
        else:
            remaining[sku] = max(0, int(stock))
    return {
        "event_id": event_id(),
        "remaining": remaining,
        "purchases": {},
        "last_appearance_ts": 0,
        "last_check_ts": 0,
    }


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


def _normalize_state(doc: dict[str, Any]) -> dict[str, Any]:
    base = _empty_state()
    remaining = dict(base["remaining"])
    stored = doc.get("remaining") if isinstance(doc.get("remaining"), dict) else {}
    for sku, default in remaining.items():
        if sku not in stored:
            continue
        value = stored.get(sku)
        if default is None or value is None:
            remaining[sku] = None if default is None else default
        else:
            try:
                remaining[sku] = max(0, int(value))
            except (TypeError, ValueError):
                remaining[sku] = default

    purchases: dict[str, dict[str, int]] = {}
    raw_purchases = doc.get("purchases") if isinstance(doc.get("purchases"), dict) else {}
    for user_id, basket in raw_purchases.items():
        if not isinstance(basket, dict):
            continue
        cleaned: dict[str, int] = {}
        for sku, count in basket.items():
            try:
                cleaned[str(sku)] = max(0, int(count))
            except (TypeError, ValueError):
                continue
        if cleaned:
            purchases[str(user_id)] = cleaned

    try:
        last_appearance = float(doc.get("last_appearance_ts") or 0)
    except (TypeError, ValueError):
        last_appearance = 0.0
    try:
        last_check = float(doc.get("last_check_ts") or 0)
    except (TypeError, ValueError):
        last_check = 0.0

    return {
        "event_id": event_id(),
        "remaining": remaining,
        "purchases": purchases,
        "last_appearance_ts": last_appearance,
        "last_check_ts": last_check,
    }


async def load_state() -> None:
    global _state
    async with _lock:
        doc = _read_state_file()
        if doc.get("event_id") != event_id():
            _state = _empty_state()
            _write_state_file(_state)
            func.logger.info(f"Debut merchant state reset/seeded for event {event_id()}.")
            return
        _state = _normalize_state(doc)


def _save_locked() -> None:
    _write_state_file(copy.deepcopy(_state))


def global_remaining(sku: str) -> int | None:
    remaining = _state.get("remaining") or {}
    if sku not in remaining:
        catalog = item_by_id(sku)
        if not catalog:
            return 0
        stock = catalog.get("stock")
        if stock is None:
            return None
        try:
            return max(0, int(stock))
        except (TypeError, ValueError):
            return 0

    value = remaining.get(sku)
    if value is None:
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def person_purchased(user_id: int | str, sku: str) -> int:
    basket = (_state.get("purchases") or {}).get(str(user_id)) or {}
    try:
        return max(0, int(basket.get(sku, 0) or 0))
    except (TypeError, ValueError):
        return 0


def bought_this_visit(user_id: int | str) -> bool:
    return str(user_id) in _visit_buyers


def reset_visit_buyers() -> None:
    _visit_buyers.clear()


def last_appearance_ts() -> float:
    try:
        return float(_state.get("last_appearance_ts") or 0)
    except (TypeError, ValueError):
        return 0.0


def is_shop_open() -> bool:
    view = _active_view
    return bool(view and not getattr(view, "closed", True))


def set_active_view(view: Any | None) -> None:
    global _active_view
    _active_view = view


def get_active_view() -> Any | None:
    return _active_view


def is_overdue(when: datetime | None = None) -> bool:
    now = when or now_kst()
    now_ts = now.timestamp()
    gap = min_gap_seconds()
    last = last_appearance_ts()
    if last > 0:
        return now_ts - last >= gap
    start = event_start()
    if start is None:
        return False
    return now_ts - start.timestamp() >= gap


def should_appear(when: datetime | None = None) -> bool:
    if is_shop_open():
        return False
    if is_overdue(when):
        return True
    return random.randint(1, appearance_chance()) == 1


def next_tick_at(when: datetime | None = None) -> datetime:
    now = when or now_kst()
    start = event_start()
    interval = interval_minutes()
    if start and now < start:
        return start

    minute = (now.minute // interval) * interval
    candidate = now.replace(minute=minute, second=0, microsecond=0)
    if candidate < now:
        candidate += timedelta(minutes=interval)
    return candidate


def seconds_until_next_tick(when: datetime | None = None) -> float:
    now = when or now_kst()
    target = next_tick_at(now)
    return max(0.0, (target - now).total_seconds())


def _roll_price(item: dict[str, Any]) -> int:
    low = int(item.get("price_min", 0) or 0)
    high = int(item.get("price_max", low) or low)
    if high < low:
        low, high = high, low
    return random.randint(low, high)


def format_event_stock() -> str:
    """Remaining truck inventory for the whole event (not this visit)."""
    lines = ["```"]
    for item in items():
        sku = str(item["id"])
        remaining = global_remaining(sku)
        stock_text = "∞" if remaining is None else str(remaining)
        name = f"{item.get('emoji', '')} {item.get('name') or sku}"
        lines.append(f"{name:<28} {stock_text:>6}")
    lines.append("```")
    return "\n".join(lines)


def build_appearance_stock() -> list[dict[str, Any]]:
    listings: list[dict[str, Any]] = []
    for item in items():
        sku = str(item["id"])
        per_appearance = max(0, int(item.get("per_appearance", 1) or 0))
        remaining = global_remaining(sku)
        if remaining is None:
            available = per_appearance
        else:
            available = min(per_appearance, remaining)
        if available <= 0:
            continue
        listings.append({
            "id": sku,
            "name": str(item.get("name") or sku),
            "emoji": str(item.get("emoji") or "🛒"),
            "type": str(item.get("type") or "roll"),
            "key": item.get("key"),
            "pack_qty": max(1, int(item.get("pack_qty", 1) or 1)),
            "per_appearance": per_appearance,
            "per_person": item.get("per_person"),
            "price": _roll_price(item),
            "left": available,
            "stock": remaining,
        })
    return listings


async def mark_appearance() -> None:
    async with _lock:
        _state["last_appearance_ts"] = time.time()
        _state["last_check_ts"] = time.time()
        _save_locked()


async def mark_check() -> None:
    async with _lock:
        _state["last_check_ts"] = time.time()
        _save_locked()


def _grant_query(user: dict[str, Any], listing: dict[str, Any], quantity: int, price: int) -> dict[str, Any] | str:
    reward_type = listing.get("type")
    pack_qty = max(1, int(listing.get("pack_qty", 1) or 1))
    total_grant = pack_qty * quantity
    query: dict[str, Any] = {"$inc": {"candies": -price}}

    if reward_type == "roll":
        query["$inc"][f"roll.{listing.get('key') or 'rare'}"] = total_grant
    elif reward_type == "slots":
        query["$inc"]["extra_props.extra_card_slots"] = total_grant
    elif reward_type == "potion":
        query["$inc"][str(listing.get("key") or "potions.luck_iii")] = total_grant
    elif reward_type == "battlepass_xp":
        if not func.battlepass_enabled():
            return "Battle Pass is currently disabled."
        state = func.get_battlepass_state(user)
        bp_settings = func.get_battlepass_settings()
        xp_per_level = max(1, int(bp_settings.get("xp_per_level", 150)))
        max_level = max(1, int(bp_settings.get("max_level", 100)))
        room = (xp_per_level * max_level) - max(0, int(state.get("xp", 0) or 0))
        if room <= 0:
            return "You are already at the Battle Pass XP cap."
        query = func.add_battlepass_xp(user, total_grant, query=query, apply_modifiers=False)
        granted = int((query.get("$inc") or {}).get("battlepass.xp", 0) or 0)
        full_set = query.get("$set", {}).get("battlepass")
        if isinstance(full_set, dict):
            granted = max(0, int(full_set.get("xp", 0)) - int(state.get("xp", 0)))
        if granted <= 0:
            return "You are already at the Battle Pass XP cap."
    else:
        return "This item cannot be sold right now."

    return func.update_quest_progress(user, "BUY_ITEM", progress=quantity, query=query)


async def purchase(user_id: int, listing: dict[str, Any], quantity: int) -> tuple[bool, str]:
    sku = str(listing["id"])
    catalog = item_by_id(sku)
    if not catalog:
        return False, "That item is not in the truck."

    quantity = max(1, int(quantity))
    price_each = int(listing.get("price", 0) or 0)
    per_person = catalog.get("per_person")

    async with _lock:
        appearance_left = int(listing.get("left", 0) or 0)
        if appearance_left < quantity:
            return False, "The truck does not have that many of this item right now."

        remaining = global_remaining(sku)
        if remaining is not None and remaining < quantity:
            return False, "The truck is out of stock for this item."

        if str(user_id) in _visit_buyers:
            return False, "You already bought something this visit. Wait for the truck to come back."

        bought = person_purchased(user_id, sku)
        if per_person is not None:
            try:
                cap = int(per_person)
            except (TypeError, ValueError):
                cap = 0
            if cap >= 0 and bought + quantity > cap:
                left = max(0, cap - bought)
                if left <= 0:
                    return False, "You have already bought the maximum of this item."
                return False, f"You can only buy `{left}` more of this item."

        user = await func.get_user(user_id)
        total_price = price_each * quantity
        if int(user.get("candies", 0) or 0) < total_price:
            need = total_price - int(user.get("candies", 0) or 0)
            return False, f"You need `{need}` more candies."

        query = _grant_query(user, listing, quantity, total_price)
        if isinstance(query, str):
            return False, query

        snapshot = copy.deepcopy(_state)
        listing["left"] = appearance_left - quantity
        if remaining is not None:
            _state.setdefault("remaining", {})[sku] = remaining - quantity
            listing["stock"] = remaining - quantity
        purchases = _state.setdefault("purchases", {})
        basket = purchases.setdefault(str(user_id), {})
        basket[sku] = bought + quantity
        _visit_buyers.add(str(user_id))
        _save_locked()

        try:
            await func.update_user(user_id, query)
        except Exception:
            _state.clear()
            _state.update(snapshot)
            listing["left"] = appearance_left
            listing["stock"] = remaining
            _visit_buyers.discard(str(user_id))
            _save_locked()
            func.logger.exception("Debut merchant purchase failed; stock restored.")
            return False, "The merchant could not complete that sale. Try again."

    pack_qty = max(1, int(listing.get("pack_qty", 1) or 1))
    label = listing.get("name") or sku
    xp_note = ""
    if listing.get("type") == "battlepass_xp":
        old_xp, new_xp = func.get_battlepass_xp_change(user, query)
        xp_note = f"\n{func.format_battlepass_xp_change(old_xp, new_xp)}"
    return True, f"Bought **{quantity}× {listing.get('emoji', '')} {label}** for `{total_price}` 🍬.{xp_note}"


async def close_active_shop() -> None:
    view = get_active_view()
    if view is None:
        return
    closer = getattr(view, "close_shop", None)
    if closer:
        await closer()
    set_active_view(None)
