import os, time, copy, json, random, logging, discord, Levenshtein

from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCollection,
)

from datetime import (
    date,
    timedelta
)

from typing import (
    List,
    Dict,
    Any,
    Union
)

from discord.ext import commands

from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

CARDS_FOLDER = os.path.join(ROOT_DIR, 'images')
if not os.path.exists(CARDS_FOLDER):
    os.makedirs(CARDS_FOLDER)

NEW_CARDS_FOLDER = os.path.join(ROOT_DIR, 'newImages')
if not os.path.exists(NEW_CARDS_FOLDER):
    os.makedirs(NEW_CARDS_FOLDER)

MUSIC_TRACKS_FOLDER = os.path.join(ROOT_DIR, 'musicTracks')
if not os.path.exists(MUSIC_TRACKS_FOLDER):
    os.makedirs(MUSIC_TRACKS_FOLDER)

class TOKEN:
    def __init__(self) -> None:
        load_dotenv()

        self.token = os.getenv("TOKEN")
        self.mongodb_url = os.getenv("MONGODB_URL")
        self.mongodb_name = os.getenv("MONGODB_NAME")

class Settings:
    def __init__(self):
        self.BOT_PREFIX: List[str] = []
        self.MAX_CARDS: int = 0
        self.DEFAULT_EXP: int = 0
        self.LAST_TRADE_TIMER: int = 0
        self.RESET_CARD_DAY: int = 0
        self.MAIN_GUILD: int = 0
        self.MAIN_CHAT_CHANNEL: int = 0
        self.MUSIC_TEXT_CHANNEL: int = 0
        self.MUSIC_VOICE_CHANNEL: int = 0
        self.GALLERY_CHANNEL: int = 0
        self.MARKET_CHANNEL: int = 0
        self.ALLOWED_CATEGORY_IDS: List[int] = []
        self.IGNORE_CHANNEL_IDS: List[int] = []
        self.GAME_CHANNEL_IDS: List[int] = []
        self.MUSIC_NODE: Dict[str, Union[str, int]] = {}
        self.USER_BASE: Dict[str, Any] = {}
        self.COOLDOWN_BASE: Dict[str, tuple[str, int]] = {}
        self.PITY_SETTINGS: Dict[str, Dict[str, Any]] = {}
        self.DAILY_QUESTS: Dict[str, Union[str, int]] = {}
        self.WEEKLY_QUESTS: Dict[str, Union[str, int]] = {}
        self.TIERS_BASE: Dict[str, List[str, int]] = {}
        self.FRAMES_BASE: Dict[str, List[str, str]] = {}
        self.POTIONS_BASE: Dict[str, Union[str, Dict[str, float]]] = {}
        self.RANK_BASE: Dict[Dict, Dict[str, Any]] = {}
        self.MATCH_GAME_SETTINGS: Dict[str, Dict[str, Any]] = {}
        self.MUSIC_GAME_SETTINGS: Dict[str, Any] = {}
        self.ADMIN_IDS: List[int] = []
        self.TESTER_IDS: List[int] = []
        self.BUG_REPORT_CHANNEL_ID: int = 0
        self.OPUS_PATH: str = ""
        self.LOGGING: Dict[Union[str, Dict[str, Union[str, bool]]]] = {}
        self.PVP_REWARDS_ENABLED: bool = False
        self.GIVE_REWARD_CARD: bool = False
        self.MONTHLY_LEADERBOARD_ROLE: int = 0
        self.BATTLEPASS_SETTINGS: Dict[str, Any] = {}
        self.EVENT_SETTINGS: Dict[str, Any] = {}
        self.TEASER_SETTINGS: Dict[str, Any] = {}
        self.BATTLEPASS_MILESTONES: Dict[str, Any] = {}
        # Newly added defaults so callers can reference them directly without getattr
        self.PVP_SETTINGS: Dict[str, Any] = {}
        self.REWARD_CARD_PROBABILITIES: Dict[str, Any] = {}
        self.PERFECT_CROWN_TREASURY_CARDS: Dict[str, List[str]] = {}

    def load(self):
        settings = open_json("settings.json")
        self.BOT_PREFIX = settings.get("BOT_PREFIX", [])
        self.MAX_CARDS = settings.get("MAX_CARDS")
        self.DEFAULT_EXP = settings.get("DEFAULT_EXP")
        self.LAST_TRADE_TIMER = settings.get("LAST_TRADE_TIMER")
        self.RESET_CARD_DAY = settings.get("RESET_CARD_DAY")
        self.MAIN_GUILD = settings.get("MAIN_GUILD")
        self.MAIN_CHAT_CHANNEL = settings.get("MAIN_CHAT_CHANNEL")
        self.MUSIC_TEXT_CHANNEL = settings.get("MUSIC_TEXT_CHANNEL")
        self.MUSIC_VOICE_CHANNEL = settings.get("MUSIC_VOICE_CHANNEL")
        self.GALLERY_CHANNEL = settings.get("GALLERY_CHANNEL")
        self.MARKET_CHANNEL = settings.get("MARKET_CHANNEL")
        self.ALLOWED_CATEGORY_IDS = settings.get("ALLOWED_CATEGORY_IDS")
        self.IGNORE_CHANNEL_IDS = settings.get("IGNORE_CHANNEL_IDS")
        self.GAME_CHANNEL_IDS = settings.get("GAME_CHANNEL_IDS")
        self.MUSIC_NODE = settings.get("MUSIC_NODE")
        self.USER_BASE = settings.get("USER_BASE")
        self.COOLDOWN_BASE = settings.get("COOLDOWN_BASE")
        self.PITY_SETTINGS = settings.get("PITY_SETTINGS", {})
        self.DAILY_QUESTS = {k: v for k, v in settings.get("DAILY_QUESTS").items()}
        self.WEEKLY_QUESTS = {k: v for k, v in settings.get("WEEKLY_QUESTS").items()}
        self.TIERS_BASE = settings.get("TIERS_BASE")
        self.FRAMES_BASE = settings.get("FRAMES_BASE")
        self.POTIONS_BASE = settings.get("POTIONS_BASE")
        self.RANK_BASE = settings.get("RANK_BASE")
        self.MATCH_GAME_SETTINGS = settings.get("MATCH_GAME_SETTINGS")
        self.MUSIC_GAME_SETTINGS = settings.get("MUSIC_GAME_SETTINGS")
        self.ADMIN_IDS = settings.get("ADMIN_IDS")
        self.TESTER_IDS = settings.get("TESTER_IDS") or []
        self.BUG_REPORT_CHANNEL_ID = settings.get("BUG_REPORT_CHANNEL_ID")
        self.OPUS_PATH = settings.get("OPUS_PATH")
        self.LOGGING = settings.get("LOGGING", {})
        self.PVP_REWARDS_ENABLED = settings.get("PVP_REWARDS_ENABLED", True)
        self.GIVE_REWARD_CARD = settings.get("GIVE_REWARD_CARD", True)
        self.MONTHLY_LEADERBOARD_ROLE = settings.get("MONTHLY_LEADERBOARD_ROLE", 0)
        self.BATTLEPASS_SETTINGS = settings.get("BATTLEPASS_SETTINGS", {})
        self.EVENT_SETTINGS = settings.get("EVENT_SETTINGS", {})
        self.TEASER_SETTINGS = settings.get("TEASER_SETTINGS", {})
        self.BATTLEPASS_MILESTONES = settings.get("BATTLEPASS_MILESTONES", {})
        self.PVP_SETTINGS = settings.get("PVP_SETTINGS", {})
        self.REWARD_CARD_PROBABILITIES = settings.get("REWARD_CARD_PROBABILITIES", {})
        self.PERFECT_CROWN_TREASURY_CARDS = settings.get("PERFECT_CROWN_TREASURY_CARDS", {})


# Runtime globals used across the bot
# Keep these in place so the project still loads with the old slash/message command design.
tokens: TOKEN = TOKEN()
settings: Settings = Settings()
logger: logging.Logger = logging.getLogger("iufi")

# DB Var
MONGO_DB: AsyncIOMotorClient = None
USERS_DB: AsyncIOMotorCollection = None
CARDS_DB: AsyncIOMotorCollection = None
QUESTIONS_DB: AsyncIOMotorCollection = None
MUSIC_DB: AsyncIOMotorCollection = None
STATE_DB: AsyncIOMotorCollection = None

USERS_BUFFER: Dict[int, Dict[str, Any]] = {}

QUESTS_SETTINGS: Dict[str, Dict[str, int]] = {
    "daily": {
        "update_time": 86_400,
        "items": 3
    },
    "weekly": {
        "update_time": 86_400 * 7,
        "items": 2
    }
}

def open_json(path: str) -> dict:
    try:
        with open(os.path.join(ROOT_DIR, path), encoding="utf8") as json_file:
            return json.load(json_file)
    except Exception:
        return {}

def cal_retry_time(end_time: float, default: str = None) -> str | None:
    if end_time <= (current_time := time.time()):
        return default

    retry: float = int(end_time - current_time)
    minutes, seconds = divmod(retry, 60)
    hours, minutes = divmod(minutes, 60)

    return (f"{hours}h " if hours > 0 else "") + f"{minutes}m {seconds}s"

def cal_last_online_time(start_time: float, default: str = "") -> str | None:
    if not start_time or start_time > (current_time := time.time()):
        return default

    total_seconds = int(current_time - start_time)

    days = total_seconds // 86_400
    if days >= 1:
        hours = (total_seconds % 86_400) // 3600
        return f"{days}d {hours}h"

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{hours}h {minutes}m"

def calculate_level(exp: int) -> tuple[int, int]:
    level = 0

    while exp >= settings.DEFAULT_EXP:
        exp -= settings.DEFAULT_EXP
        level += 1

    return level, exp

def convert_seconds(seconds: float) -> str:
    if seconds >= 60:
        minutes = int(seconds // 60)
        seconds = seconds % 60
        return f"{minutes:1d}m {seconds:.1f}s"
    else:
        return f"{seconds:.1f}s"

def get_potions(potions: Dict[str, float], base: Dict[str, str | Dict[str, float]], details: bool = False) -> Dict[str, float]:
    result: Dict[str, float] = {}
    for potion, expiration in potions.items():
        if expiration <= time.time():
            continue
        potion = potion.split("_")
        potion_data = base.get(potion[0], {})
        result[potion[0]] = potion_data.copy() | {"level": potion[1], "expiration": expiration} if details else potion_data.get("levels", {}).get(potion[1], 0)
    return result

def clean_text(input_text: str, allow_spaces: bool = True, convert_to_lower: bool = False) -> str:
    if not input_text:
        return ""
    
    cleaned_text = "".join(char for char in input_text if char.isalnum() or char.isspace())
    
    if not allow_spaces:
        cleaned_text = "".join(char for char in cleaned_text if char != " ")
    
    if convert_to_lower:
        cleaned_text = cleaned_text.lower()
    
    return cleaned_text

def jac_similarity(str1: str, str2: str) -> float:
    """
    Calculate Jaccard similarity between two strings based on character sets.
    Returns a float between 0 and 1, where 1 means identical character sets.
    """
    if not str1 or not str2:
        return 0.0

    set1 = set(str1.lower())
    set2 = set(str2.lower())

    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))

    return intersection / union if union > 0 else 0.0

def lev_similarity(str1: str, str2: str) -> float:
    """
    Calculate normalized Levenshtein similarity between two strings.
    Returns a float between 0 and 1, where 1 means identical strings.
    """
    if not str1 or not str2:
        return 0.0

    distance = Levenshtein.distance(str1.lower(), str2.lower())
    max_len = max(len(str1), len(str2))

    return 1 - (distance / max_len) if max_len > 0 else 0.0

def get_week_unix_timestamps() -> tuple[float, float]:
    today = date.today()

    # Get the first day of this week (Monday)
    start_of_this_week = today - timedelta(days=today.weekday())

    # Get the first day of next week (next Monday)
    start_of_next_week = start_of_this_week + timedelta(days=7)

    return time.mktime(start_of_this_week.timetuple()), time.mktime(start_of_next_week.timetuple())

def get_month_unix_timestamps() -> tuple[float, float]:
    today = date.today()

    # Get the first day of this month
    start_of_this_month = date(today.year, today.month, 1)
    
    # Get the first day of next month
    if today.month == 12:
        start_of_next_month = date(today.year + 1, 1, 1)
    else:
        start_of_next_month = date(today.year, today.month + 1, 1)

    return time.mktime(start_of_this_month.timetuple()), time.mktime(start_of_next_month.timetuple())

def match_string(input_string: str, word_list: List[str]) -> str:
    for word in word_list:
        if word.startswith(input_string):
            return word
    return None

def get_battlepass_settings() -> Dict[str, Any]:
    return settings.BATTLEPASS_SETTINGS or {}

def battlepass_enabled() -> bool:
    return bool(get_battlepass_settings().get("enabled", False))

def get_battlepass_default_state() -> Dict[str, Any]:
    bp_settings = get_battlepass_settings()
    return {
        "season_id": bp_settings.get("season_id", "default"),
        "is_active": False,
        "is_purchased": False,
        "xp": 0,
        "claimed_rewards": [],
        "claimed_one_time": {
            "mg2_click_plus_2": False,
            "mg3_click_plus_2": False
        }
    }

def get_battlepass_state(user: Dict[str, Any]) -> Dict[str, Any]:
    state = user.get("battlepass")
    default_state = get_battlepass_default_state()

    if not isinstance(state, dict):
        return copy.deepcopy(default_state)

    merged_state = copy.deepcopy(default_state)
    merged_state.update(state)

    claimed_one_time = merged_state.get("claimed_one_time", {})
    if not isinstance(claimed_one_time, dict):
        claimed_one_time = {}
    base_one_time = default_state["claimed_one_time"]
    merged_state["claimed_one_time"] = {
        "mg2_click_plus_2": bool(claimed_one_time.get("mg2_click_plus_2", base_one_time["mg2_click_plus_2"])),
        "mg3_click_plus_2": bool(claimed_one_time.get("mg3_click_plus_2", base_one_time["mg3_click_plus_2"]))
    }

    claimed_rewards = merged_state.get("claimed_rewards", [])
    if not isinstance(claimed_rewards, list):
        claimed_rewards = []
    merged_state["claimed_rewards"] = claimed_rewards

    if merged_state.get("season_id") != default_state["season_id"]:
        return copy.deepcopy(default_state)

    return merged_state

def with_battlepass_state_synced(user: Dict[str, Any], query: Dict[str, Any] = None) -> tuple[Dict[str, Any], Dict[str, Any]]:
    if query is None:
        query = {}

    synced_state = get_battlepass_state(user)
    if user.get("battlepass") != synced_state:
        query.setdefault("$set", {})["battlepass"] = synced_state

    return synced_state, query

def get_battlepass_xp_for_action(action: str) -> int:
    xp_map = get_battlepass_settings().get("xp_per_action", {})
    try:
        return int(xp_map.get(action, 0))
    except Exception:
        return 0

def scale_battlepass_action_xp(action: str, scored: int, maximum: int) -> int:
    """Grant a share of an action's configured XP. A full score always hits the max."""
    try:
        scored = int(scored)
        maximum = int(maximum)
    except (TypeError, ValueError):
        return 0
    if scored <= 0 or maximum <= 0:
        return 0
    max_xp = get_battlepass_xp_for_action(action)
    if max_xp <= 0:
        return 0
    scored = min(scored, maximum)
    return max(1, round(max_xp * scored / maximum))

def has_purchased_battlepass(state: Dict[str, Any] | None) -> bool:
    if not isinstance(state, dict):
        return False
    return bool(state.get("is_purchased") or state.get("is_active"))

def _apply_battlepass_xp_modifiers(amount: int, state: Dict[str, Any]) -> int:
    import events
    scaled = int(round(amount * events.battlepass_xp_multiplier()))
    if scaled < amount and events.battlepass_xp_multiplier() >= 1:
        scaled = amount
    amount = scaled

    if has_purchased_battlepass(state):
        return max(0, amount)

    try:
        free_percent = float(get_battlepass_settings().get("free_xp_percent", 50))
    except (TypeError, ValueError):
        free_percent = 50.0
    free_percent = max(0.0, min(100.0, free_percent))
    # Round half up so a 1 XP roll still grants 1 at 50%.
    return max(0, int((amount * free_percent + 50) // 100))

def add_battlepass_xp(user: Dict[str, Any], amount: int, *, query: Dict[str, Any] = None) -> Dict[str, Any]:
    if query is None:
        query = {}

    if not battlepass_enabled():
        return query

    try:
        amount = int(amount)
    except Exception:
        return query

    if amount <= 0:
        return query

    state, query = with_battlepass_state_synced(user, query)
    amount = _apply_battlepass_xp_modifiers(amount, state)

    if amount <= 0:
        return query

    bp_settings = get_battlepass_settings()
    xp_per_level = max(1, int(bp_settings.get("xp_per_level", 150)))
    max_level = max(1, int(bp_settings.get("max_level", 100)))
    max_total_xp = xp_per_level * max_level

    full_set = query.get("$set", {}).get("battlepass")
    if isinstance(full_set, dict):
        current_xp = max(0, int(full_set.get("xp", 0)))
    else:
        pending_inc = int(query.get("$inc", {}).get("battlepass.xp", 0))
        current_xp = max(0, int(state.get("xp", 0))) + pending_inc
    available_room = max_total_xp - current_xp
    if available_room <= 0:
        return query

    grant = min(amount, available_room)
    old_level, _, _ = calculate_battlepass_level(current_xp)
    new_xp = current_xp + grant
    new_level, _, _ = calculate_battlepass_level(new_xp)

    if isinstance(full_set, dict):
        full_set["xp"] = new_xp
    else:
        increments = query.setdefault("$inc", {})
        increments["battlepass.xp"] = increments.get("battlepass.xp", 0) + grant

    levels_gained = max(0, new_level - old_level)
    if levels_gained:
        query["_bp_levels_gained"] = int(query.get("_bp_levels_gained", 0) or 0) + levels_gained

    return _grant_reached_battlepass_levels(state, old_level, new_level, query)

def get_battlepass_xp_change(user: Dict[str, Any], query: Dict[str, Any] | None = None) -> tuple[int, int]:
    """XP before and after a query built with `add_battlepass_xp`. User doc is not mutated."""
    old_xp = max(0, int(get_battlepass_state(user).get("xp", 0) or 0))
    if not query:
        return old_xp, old_xp

    full_set = query.get("$set", {}).get("battlepass")
    if isinstance(full_set, dict) and full_set.get("xp") is not None:
        try:
            return old_xp, max(0, int(full_set["xp"]))
        except (TypeError, ValueError):
            return old_xp, old_xp

    try:
        gained = int((query.get("$inc") or {}).get("battlepass.xp", 0) or 0)
    except (TypeError, ValueError):
        gained = 0
    return old_xp, old_xp + max(0, gained)

def format_battlepass_xp_change(old_xp: int, new_xp: int) -> str:
    gained = new_xp - old_xp
    sign = "+" if gained >= 0 else ""
    return f"🎫 Battle Pass XP: `{old_xp}` → `{new_xp}` (`{sign}{gained}`)"

def calculate_battlepass_level(xp: int) -> tuple[int, int, int]:
    bp_settings = get_battlepass_settings()
    xp_per_level = max(1, int(bp_settings.get("xp_per_level", 150)))
    max_level = max(1, int(bp_settings.get("max_level", 100)))
    max_total_xp = xp_per_level * max_level

    xp = min(max(0, int(xp)), max_total_xp)
    level = min(max_level, xp // xp_per_level)

    if level >= max_level:
        return level, xp_per_level, 0

    in_level_xp = xp % xp_per_level
    return level, in_level_xp, xp_per_level - in_level_xp

def get_battlepass_rewards_for_level(level: int) -> List[Dict[str, Any]]:
    bp_settings = get_battlepass_settings()
    reward_table = bp_settings.get("reward_table", {})

    milestones = reward_table.get("milestones", {})
    if str(level) in milestones:
        return _normalize_battlepass_rewards(milestones.get(str(level), []))

    filler = reward_table.get("filler", {})
    if isinstance(filler.get("rewards"), list):
        return _normalize_battlepass_rewards(filler.get("rewards", []))

    base = int(filler.get("starcandies_base", filler.get("even_starcandies_base", 50)))
    step = int(filler.get("starcandies_step_per_10_levels", filler.get("even_starcandies_step_per_10_levels", 10)))
    cap = int(filler.get("starcandies_cap", filler.get("even_starcandies_cap", 120)))
    amount = min(cap, base + ((max(1, level) - 1) // 10) * step)
    return [{"type": "starcandies", "amount": amount}]

def format_battlepass_reward(reward: Dict[str, Any]) -> str:
    reward_type = reward.get("type", "unknown")
    amount = reward.get("amount", 1)

    if reward_type == "starcandies":
        return f"🍬 Starcandies x{amount}"
    if reward_type == "potion":
        potion_key = reward.get("key", "potions.speed_i")
        potion_name = potion_key.split(".", 1)[1].replace("_", " ").upper() if "." in potion_key else potion_key.upper()
        return f"🧪 {potion_name} x{amount}"
    if reward_type == "roll":
        tier = str(reward.get("key") or reward.get("tier") or "rare").lower()
        emoji = (settings.TIERS_BASE.get(tier) or ["🌸"])[0]
        label = {"rare": "Rare Roll", "epic": "Epic Roll", "legendary": "Legend Roll"}.get(tier, f"{tier.title()} Roll")
        return f"{emoji} {label} x{amount}"
    if reward_type == "free_rare":
        return "🌸 Rare Roll x1"
    if reward_type == "free_epic":
        return "💎 Epic Roll x1"
    if reward_type == "free_legend":
        return "👑 Legend Roll x1"
    if reward_type == "mg2_click_plus_2":
        return "🎯 MG2 +2 Click (one-time)"
    if reward_type == "mg3_click_plus_2":
        return "🎯 MG3 +2 Click (one-time)"

    return f"{reward_type} x{amount}"

def _normalize_battlepass_rewards(raw: Any) -> List[Dict[str, Any]]:
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        return [raw]
    return []

def _battlepass_full_set(query: Dict[str, Any]) -> Dict[str, Any] | None:
    full_set = query.get("$set", {}).get("battlepass")
    return full_set if isinstance(full_set, dict) else None

def apply_battlepass_reward(reward: Dict[str, Any], query: Dict[str, Any] = None) -> Dict[str, Any]:
    if query is None:
        query = {}

    reward_type = reward.get("type", "unknown")
    try:
        amount = int(reward.get("amount", 1) or 1)
    except Exception:
        amount = 1

    def _inc(path: str, value: int) -> None:
        increments = query.setdefault("$inc", {})
        increments[path] = increments.get(path, 0) + value

    if reward_type == "starcandies":
        _inc("candies", amount)
        return query

    if reward_type == "potion":
        _inc(str(reward.get("key") or "potions.speed_i"), amount)
        return query

    if reward_type == "roll":
        tier = str(reward.get("key") or reward.get("tier") or "rare").lower()
        _inc(f"roll.{tier}", amount)
        return query

    if reward_type == "free_rare":
        _inc("roll.rare", amount)
        return query
    if reward_type == "free_epic":
        _inc("roll.epic", amount)
        return query
    if reward_type == "free_legend":
        _inc("roll.legendary", amount)
        return query

    if reward_type in ("mg2_click_plus_2", "mg3_click_plus_2"):
        full_set = _battlepass_full_set(query)
        if full_set is not None:
            full_set.setdefault("claimed_one_time", {})[reward_type] = True
        else:
            query.setdefault("$set", {})[f"battlepass.claimed_one_time.{reward_type}"] = True

    return query

def _pending_claimed_reward_levels(state: Dict[str, Any], query: Dict[str, Any]) -> List[int]:
    full_set = _battlepass_full_set(query)
    if full_set is not None:
        claimed = full_set.get("claimed_rewards", [])
    else:
        claimed = list(state.get("claimed_rewards") or [])
        pending = query.get("$push", {}).get("battlepass.claimed_rewards")
        if isinstance(pending, dict) and "$each" in pending:
            claimed.extend(pending["$each"])
        elif pending is not None:
            claimed.append(pending)

    levels: List[int] = []
    for item in claimed:
        try:
            levels.append(int(item))
        except Exception:
            continue
    return levels

def _grant_reached_battlepass_levels(
    state: Dict[str, Any],
    old_level: int,
    new_level: int,
    query: Dict[str, Any]
) -> Dict[str, Any]:
    claimed = set(_pending_claimed_reward_levels(state, query))
    newly_claimed: List[int] = []

    for level in range(max(1, old_level + 1), new_level + 1):
        if level in claimed:
            continue
        for reward in get_battlepass_rewards_for_level(level):
            apply_battlepass_reward(reward, query)
        newly_claimed.append(level)
        claimed.add(level)

    if not newly_claimed:
        return query

    full_set = _battlepass_full_set(query)
    if full_set is not None:
        full_set.setdefault("claimed_rewards", []).extend(newly_claimed)
        return query

    push = query.setdefault("$push", {})
    existing = push.get("battlepass.claimed_rewards")
    if isinstance(existing, dict) and "$each" in existing:
        existing["$each"].extend(newly_claimed)
    elif existing is not None:
        push["battlepass.claimed_rewards"] = {"$each": [existing, *newly_claimed]}
    else:
        push["battlepass.claimed_rewards"] = {"$each": newly_claimed}

    return query

def pick_battlepass_drop_xp() -> int:
    amounts = get_battlepass_settings().get("drop", {}).get("xp_amounts", [10, 25, 50])
    choices = []
    for amount in amounts:
        try:
            value = int(amount)
        except Exception:
            continue
        if value > 0:
            choices.append(value)
    return random.choice(choices) if choices else random.choice([10, 25, 50])

def truncate_string(text: str, length: int = 18) -> str:
    return text[:length - 3] + "..." if len(text) > length else text

def _normalize_user_collections(user: Dict[str, Any]) -> None:
    collections = user.get("collections")
    if not isinstance(collections, dict):
        return

    for name, slots in list(collections.items()):
        if isinstance(slots, list):
            continue
        if not isinstance(slots, dict):
            collections[name] = [None] * 6
            continue

        # Heal legacy/corrupted in-memory shape where slots became a dict with numeric keys.
        fixed_slots = [None] * 6
        for key, card_id in slots.items():
            if str(key).isdigit():
                idx = int(key)
                if 0 <= idx < 6:
                    fixed_slots[idx] = card_id
        collections[name] = fixed_slots

def _quest_has_level_iii_potion_reward(quest: Dict[str, Any]) -> bool:
    for reward in quest.get("rewards", []):
        if len(reward) < 2:
            continue
        reward_key = reward[1]
        if isinstance(reward_key, str) and reward_key.startswith("potions.") and reward_key.endswith("_iii"):
            return True
    return False

def _pick_new_quests(quest_type: str, quests_base: Dict[str, Any], items: int) -> List[str]:
    quests_by_type: Dict[str, List[str]] = {}

    for quest_name, quest_details in quests_base.items():
        if quest_details.get("retired"):
            continue
        quest_group = quest_details["type"]
        quests_by_type.setdefault(quest_group, []).append(quest_name)

    candidates = [random.choice(grouped_quests) for grouped_quests in quests_by_type.values()]
    sample_size = min(items, len(candidates))
    if sample_size <= 0:
        return []

    if quest_type.lower() != "weekly":
        return random.sample(candidates, k=sample_size)

    level_iii_candidates = [
        quest_name for quest_name in candidates
        if _quest_has_level_iii_potion_reward(quests_base.get(quest_name, {}))
    ]

    if not level_iii_candidates:
        return random.sample(candidates, k=sample_size)

    guaranteed_quest = random.choice(level_iii_candidates)
    if sample_size == 1:
        return [guaranteed_quest]

    other_candidates = [quest_name for quest_name in candidates if quest_name != guaranteed_quest]
    return [guaranteed_quest] + random.sample(other_candidates, k=sample_size - 1)

TRADE_COMMAND_NAMES = {
    "trade",
    "tradeeveryone",
    "tradelast",
    "tradeeveryonelast",
    "tradepotion",
    "tradepotioneveryone",
}
CHANNEL_UNRESTRICTED_ROOT_COMMANDS = {"dev", "debug", "test"}

def is_admin_interaction(interaction: discord.Interaction) -> bool:
    return interaction.user.id in settings.ADMIN_IDS

def is_tester_interaction(interaction: discord.Interaction) -> bool:
    return interaction.user.id in (settings.TESTER_IDS or [])

def in_market_channel(interaction: discord.Interaction) -> bool:
    return interaction.channel_id == settings.MARKET_CHANNEL

def in_music_channel(interaction: discord.Interaction) -> bool:
    return interaction.channel_id == settings.MUSIC_TEXT_CHANNEL

def _is_channel_unrestricted_command(command: Any) -> bool:
    if command is None:
        return False

    current = command
    while current is not None:
        if getattr(current, "name", None) in CHANNEL_UNRESTRICTED_ROOT_COMMANDS:
            return True
        current = getattr(current, "parent", None)
    return False

def ensure_command_channel(interaction: discord.Interaction) -> None:
    """Raise if this player command is not allowed in the current channel."""
    command = getattr(interaction, "command", None)
    if _is_channel_unrestricted_command(command):
        return

    channel_id = interaction.channel_id
    ignore_ids = set(settings.IGNORE_CHANNEL_IDS or [])
    game_ids = set(settings.GAME_CHANNEL_IDS or [])
    is_trade = getattr(command, "name", None) in TRADE_COMMAND_NAMES

    if channel_id == settings.GALLERY_CHANNEL:
        raise discord.app_commands.CheckFailure(
            "The gallery is for sharing collections only. Use a game channel for commands."
        )

    if channel_id in ignore_ids:
        raise discord.app_commands.CheckFailure("Commands are not allowed in this channel.")

    if channel_id == settings.MARKET_CHANNEL:
        if is_trade:
            return
        raise discord.app_commands.CheckFailure(
            "Only trade commands can be used in the market. Use a game channel for other commands."
        )

    if channel_id in game_ids:
        return

    if is_trade:
        raise discord.app_commands.CheckFailure(
            "Trade commands can only be used in game channels or the market."
        )

    raise discord.app_commands.CheckFailure("This command can only be used in a game channel.")

async def get_user(user_id: int, *, insert: bool = True) -> Dict[str, Any]:
    user = USERS_BUFFER.get(user_id)
    if not user:
        user = await USERS_DB.find_one({"_id": user_id})
        if not user and insert:
            await USERS_DB.insert_one({"_id": user_id, **settings.USER_BASE})

        user = USERS_BUFFER[user_id] = user if user else copy.deepcopy(settings.USER_BASE) | {"_id": user_id}
    _normalize_user_collections(user)
    return user

def update_quest_progress(user: Dict[str, Any], completed_quests: Union[str, List[str]], progress: int = 1, *, query: Dict[str, Any] = None) -> Dict[str, Any]:
    global settings

    completed_quests = completed_quests if isinstance(completed_quests, list) else [completed_quests]
    if not query:
        query: Dict[str, Any] = {}

    for quest_type in settings.USER_BASE["quests"].keys():
        user_quest = user.copy().get("quests", {}).get(quest_type, copy.deepcopy(settings.USER_BASE["quests"][quest_type]))

        # Use direct attribute access for quest bases instead of getattr
        if quest_type.lower() == 'daily':
            QUESTS_BASE: Dict[str, Any] = settings.DAILY_QUESTS
        elif quest_type.lower() == 'weekly':
            QUESTS_BASE: Dict[str, Any] = settings.WEEKLY_QUESTS
        else:
            QUESTS_BASE: Dict[str, Any] = {}
        if not QUESTS_BASE:
            continue
        
        #  Check if the quests need to be updated
        if (quest_updated := user_quest["next_update"] < (now := time.time())):
            _settings = QUESTS_SETTINGS.get(quest_type, {})
            new_quests = _pick_new_quests(
                quest_type,
                QUESTS_BASE,
                _settings.get("items", len(QUESTS_BASE))
            )

            user_quest["progresses"] = query.setdefault("$set", {})[f"quests.{quest_type}.progresses"] = {str(quest): 0 for quest in new_quests}
            query["$set"][f"quests.{quest_type}.next_update"] = now + _settings.get("update_time", 0)

        # Update the progress for each quest
        for quest_name in completed_quests:
            if quest_name not in QUESTS_BASE:
                continue
            if quest_name in user_quest["progresses"]:
                if user_quest["progresses"][quest_name] < QUESTS_BASE[quest_name]["amount"]:
                    quest_progress = user_quest["progresses"][quest_name]
                    quest_amount = QUESTS_BASE[quest_name]["amount"]

                    if quest_progress + progress > quest_amount:
                        progress = min(progress, quest_amount - quest_progress)
    
                    # If the quests were just updated, set the progress to the specified 
                    if quest_updated:
                        query["$set"][f"quests.{quest_type}.progresses"][quest_name] = progress
                    else:
                        query.setdefault("$inc", {})[f"quests.{quest_type}.progresses.{quest_name}"] = progress

                    # If the quest is now complete, select a reward at random
                    if (user_quest["progresses"][quest_name] + progress) >= QUESTS_BASE[quest_name]["amount"]:
                        reward = random.choice(QUESTS_BASE[quest_name]["rewards"])
                        query.setdefault("$inc", {}).setdefault(reward[1], 0)
                        query["$inc"].setdefault("exp", 0)

                        query["$inc"][reward[1]] += random.randint(reward[2][0], reward[2][1]) if isinstance(reward[2], list) else reward[2]
                        query["$inc"]["exp"] += 10
                        query = add_battlepass_xp(
                            user,
                            get_battlepass_xp_for_action(f"{quest_type}_quest"),
                            query=query
                        )

    return query

def text_in_chunks(message: str, max_length: int = 2000) -> list:
    # Split the message into words and prepare to form chunks
    words = message.split(' ')
    current_chunk = []
    chunks = []

    for word in words:
        # Check if adding the next word exceeds the maximum length
        if len(' '.join(current_chunk + [word])) > max_length:
            # Save the current chunk to the list
            chunks.append(' '.join(current_chunk))
            # Start a new chunk with the current word
            current_chunk = [word]
        else:
            # Add the word to the current chunk
            current_chunk.append(word)

    # Add the remaining words as the last chunk if any
    if current_chunk:
        chunks.append(' '.join(current_chunk))

    return chunks

def get_user_card_limit(user: Dict[str, Any]) -> int:
    """Returns the maximum number of cards a user can have."""
    extra_card_slots = user.get("extra_props", {}).get("extra_card_slots", 0)
    return settings.MAX_CARDS + extra_card_slots or settings.MAX_CARDS

async def update_user(user_id: int, data: dict) -> None:
    user = await get_user(user_id)
    data = dict(data or {})
    levels_gained = int(data.pop("_bp_levels_gained", 0) or 0)
    data.setdefault('$set', {})['last_active_time'] = time.time()

    # Auto-augment monthly counters for common stats so callers don't need to update monthly fields everywhere.
    # We'll look at $inc entries and duplicate them into monthly fields where appropriate and set last-update timestamps.
    now_ts = time.time()
    incs = data.get('$inc', {})
    if incs:
        # Handle top-level exp increments -> monthly.exp and last update
        if 'exp' in incs:
            data.setdefault('$inc', {})['monthly.exp'] = data['$inc'].get('exp', 0)
            data.setdefault('$set', {})['monthly.exp_last_update'] = now_ts

        # Handle PVP increments (pvp.wins, pvp.losses, pvp.total_matches)
        for key in list(incs.keys()):
            if key.startswith('pvp.'):
                suffix = key.split('.', 1)[1]
                monthly_key = f"monthly.pvp.{suffix}"
                data.setdefault('$inc', {})[monthly_key] = data['$inc'].get(key, 0)
                data.setdefault('$set', {})['monthly.pvp_last_update'] = now_ts

        # Handle game_state.<game>.points increments (music, mv_guess, quiz, emoji etc.)
        for key in list(incs.keys()):
            if key.count('.') >= 2 and key.split('.')[0] == 'game_state' and key.split('.')[-1] == 'points':
                # e.g. game_state.music_game.points -> game_state.music_game.monthly_points
                # (parent path must exclude `points`; otherwise Mongo conflicts: points vs points.monthly_points)
                parts = key.split('.')
                game_path = '.'.join(parts[:-1])
                monthly_points_key = f"{game_path}.monthly_points"
                last_update_key = f"{game_path}.last_update"
                data.setdefault('$inc', {})[monthly_points_key] = data['$inc'].get(key, 0)
                data.setdefault('$set', {})[last_update_key] = now_ts

    def _is_index(part: str) -> bool:
        return part.isdigit()

    def _ensure_list_index(lst: list, idx: int, default_value=None) -> None:
        while len(lst) <= idx:
            lst.append(default_value)

    # Proceed with the original in-memory merging logic
    for mode, action in data.items():
        if not str(mode).startswith("$") or not isinstance(action, dict):
            continue
        for key, value in action.items():
            cursors = key.split('.')

            nested_user = user
            for idx, c in enumerate(cursors[:-1]):
                next_cursor = cursors[idx + 1]

                if isinstance(nested_user, list):
                    if not _is_index(c):
                        break

                    list_idx = int(c)
                    default_container = [] if _is_index(next_cursor) else {}
                    _ensure_list_index(nested_user, list_idx, None)
                    if not isinstance(nested_user[list_idx], (dict, list)):
                        nested_user[list_idx] = default_container
                    nested_user = nested_user[list_idx]
                    continue

                nxt = nested_user.get(c)
                if not isinstance(nxt, (dict, list)):
                    nxt = [] if _is_index(next_cursor) else {}
                    nested_user[c] = nxt
                nested_user = nxt

            last_cursor = cursors[-1]

            if mode == "$set":
                if isinstance(nested_user, list) and _is_index(last_cursor):
                    list_idx = int(last_cursor)
                    _ensure_list_index(nested_user, list_idx, None)
                    nested_user[list_idx] = value
                else:
                    nested_user[last_cursor] = value

            elif mode == "$unset":
                if isinstance(nested_user, list) and _is_index(last_cursor):
                    list_idx = int(last_cursor)
                    if 0 <= list_idx < len(nested_user):
                        nested_user[list_idx] = None
                else:
                    nested_user.pop(last_cursor, None)

            elif mode == "$inc":
                if isinstance(nested_user, list) and _is_index(last_cursor):
                    list_idx = int(last_cursor)
                    _ensure_list_index(nested_user, list_idx, 0)
                    nested_user[list_idx] = (nested_user[list_idx] or 0) + value
                else:
                    nested_user[last_cursor] = nested_user.get(last_cursor, 0) + value

            elif mode == "$push":
                # Check if the value contains $each
                if isinstance(value, dict) and "$each" in value:
                    nested_user.setdefault(last_cursor, []).extend(value["$each"])
                else:
                    nested_user.setdefault(last_cursor, []).append(value)

            elif mode == "$pull":
                if last_cursor in nested_user:
                    value = value.get("$in", []) if isinstance(value, dict) else [value]
                    nested_user[last_cursor] = [item for item in nested_user[last_cursor] if item not in value]

            else:
                raise ValueError(f"Invalid mode: {mode}")

    for op in ("$inc", "$push", "$pull", "$unset"):
        if op in data and not data[op]:
            data.pop(op)

    await USERS_DB.update_one({"_id": user_id}, data)
    if levels_gained:
        import events
        await events.add_community_levels(levels_gained)

async def update_card(card_id: List[str] | str, data: dict, insert: bool = False) -> None:
    if insert:
        await CARDS_DB.insert_one({"_id": card_id})

    if isinstance(card_id, list):
        return await CARDS_DB.update_many({"_id": {"$in": card_id}}, data)

    await CARDS_DB.update_one({"_id": card_id}, data)

async def check_wishlist(message: discord.Message, card_ids: List[str]) -> None:
    user_docs = await USERS_DB.find({"wishlist": {"$in": card_ids}}).to_list()
    if user_docs:
        await USERS_DB.update_many(
            {"wishlist": {"$in": card_ids}},
            {"$pull": {"wishlist": {"$in": card_ids}}}
        )
        for user_doc in user_docs:
            try:
                user = message.guild.get_member(user_doc["_id"])
                if user:
                    await user.send(f"Your wish card has been rolled or traded by another player. {message.jump_url}")
            except Exception as _:
                continue

def calculate_soft_pity_boost(user: Dict[str, Any]) -> Dict[str, float]:
    """
    Calculate the rate boost multipliers for each tier based on soft pity progress.
    The boost increases linearly from 1.0x at soft_pity to soft_pity_boost at hard_pity-1.

    Returns: Dict of {tier: boost_multiplier}
    """
    user_pity = user.get("pity", {})
    tier_hierarchy = ["rare", "epic", "legendary", "mystic", "celestial"]
    boosts = {}

    for tier in tier_hierarchy:
        pity_config = settings.PITY_SETTINGS.get(tier, {})
        soft_pity = pity_config.get('soft_pity', 0)
        hard_pity = pity_config.get('hard_pity', float('inf'))
        max_boost = pity_config.get('soft_pity_boost', 1.0)
        current_pity = user_pity.get(tier, 0)

        if current_pity >= soft_pity and current_pity < hard_pity:
            # Calculate linear increase from 1.0x to max_boost
            soft_pity_range = hard_pity - soft_pity
            progress_in_soft_pity = current_pity - soft_pity
            boost_progress = progress_in_soft_pity / soft_pity_range
            boost = 1.0 + (max_boost - 1.0) * boost_progress
            boosts[tier] = boost
        elif current_pity >= hard_pity:
            # At hard pity, apply max boost (though guarantee kicks in)
            boosts[tier] = max_boost
        else:
            # Not in soft pity range
            boosts[tier] = 1.0

    return boosts

def check_pity_guarantee(user: Dict[str, Any]) -> str | None:
    """
    Check if user has hit any hard pity threshold and return the guaranteed tier.
    Does NOT modify pity counters - just checks and returns the tier to guarantee.
    Returns: guaranteed_tier (highest tier that hit hard pity, or None)
    """
    # Get user's current pity counters
    user_pity = user.get("pity", {})

    # Define tier hierarchy (lowest to highest)
    tier_hierarchy = ["rare", "epic", "legendary", "mystic", "celestial"]

    # Check which hard pity thresholds have been hit, return the highest one
    guaranteed_tier = None

    for tier in tier_hierarchy:
        pity_config = settings.PITY_SETTINGS.get(tier, {})
        hard_pity_threshold = pity_config.get('hard_pity', float('inf'))
        current_pity = user_pity.get(tier, 0)

        # If this tier's hard pity has been reached
        if current_pity >= hard_pity_threshold:
            guaranteed_tier = tier  # Keep updating to get the highest tier

    return guaranteed_tier

def update_pity_from_cards(user: Dict[str, Any], cards: List[Any]) -> Dict[str, Any]:
    """
    After rolling, check the cards received and update pity accordingly.
    - If user got a high tier card:
      - Reset that tier's pity and all lower tiers to 0
      - Increment all higher tiers by 1
    - If user only got common cards, increment all pity counters by 1
    Returns: query with pity updates
    """
    # Define tier hierarchy (lowest to highest)
    tier_hierarchy = ["rare", "epic", "legendary", "mystic", "celestial"]

    # Get the highest tier from the rolled cards
    highest_tier_rolled = None
    for card in cards:
        card_tier = card.tier[1] if hasattr(card, 'tier') and isinstance(card.tier, tuple) else None
        if card_tier and card_tier in tier_hierarchy:
            if highest_tier_rolled is None:
                highest_tier_rolled = card_tier
            else:
                # Compare and keep the higher tier
                if tier_hierarchy.index(card_tier) > tier_hierarchy.index(highest_tier_rolled):
                    highest_tier_rolled = card_tier

    query = {}

    if highest_tier_rolled and highest_tier_rolled != "common":
        # User got a rare+ card
        tier_index = tier_hierarchy.index(highest_tier_rolled)

        # Reset that tier and all lower tiers to 0
        query["$set"] = {}
        for i in range(tier_index + 1):
            tier_to_reset = tier_hierarchy[i]
            query["$set"][f"pity.{tier_to_reset}"] = 0

        # Increment all higher tiers by 1
        query["$inc"] = {}
        for i in range(tier_index + 1, len(tier_hierarchy)):
            tier_to_increment = tier_hierarchy[i]
            query["$inc"][f"pity.{tier_to_increment}"] = 1
    else:
        # User only got common cards - increment all pity counters
        query["$inc"] = {}
        for tier in tier_hierarchy:
            query["$inc"][f"pity.{tier}"] = 1

    return query


def framed_title(title: str, total_length: int = 25) -> str:
    """
    Create a single-line framed title like:
    ╔═══ Your Title Here ═══╗

    :param title: The text to display inside the frame.
    :param total_length: The total desired length of the final string.
    :return: A formatted string with box-drawing characters.
    """
    if not isinstance(title, str):
        title = str(title) if title is not None else ""
    if total_length < 6:
        raise ValueError("total_length must be at least 6 to render a valid frame.")

    left_corner = "╔"
    right_corner = "╗"
    fill_char = "═"

    # Add single spaces around the title for readability
    inner = f" {title} "
    inner_len = len(inner)

    # The total space available for fill characters on both sides
    available = total_length - len(left_corner) - len(right_corner) - inner_len

    if available < 0:
        # If the title is too long, we truncate (you could also choose to expand instead)
        # Here we trim the title to fit exactly.
        trim_len = total_length - len(left_corner) - len(right_corner) - 2  # account for spaces
        if trim_len <= 0:
            raise ValueError("total_length is too small to fit any title content.")
        inner = f" {title[:trim_len]} "
        inner_len = len(inner)
        available = total_length - len(left_corner) - len(right_corner) - inner_len

    # Distribute fill characters on both sides
    left_fill = available // 2
    right_fill = available - left_fill

    return f"**{left_corner}{fill_char * left_fill}{inner}{fill_char * right_fill}{right_corner}**"