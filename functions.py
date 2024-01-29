import os, time, copy, json
from enum import Enum

from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCollection,
)

from datetime import (
    date,
    timedelta
)

from dotenv import load_dotenv
from typing import Any

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

class TOKEN:
    def __init__(self) -> None:
        load_dotenv()

        self.token = os.getenv("TOKEN")
        self.mongodb_url = os.getenv("MONGODB_URL")
        self.mongodb_name = os.getenv("MONGODB_NAME")

tokens: TOKEN = TOKEN()

# DB Var
MONGO_DB: AsyncIOMotorClient = None
USERS_DB: AsyncIOMotorCollection = None
CARDS_DB: AsyncIOMotorCollection = None
DAILY_QUEST_DB: AsyncIOMotorCollection = None

USERS_BUFFER: dict[int, dict[str, Any]] = {}
DAILY_QUEST_BUFFER: dict[int, dict[str, Any]] = {}
MAX_CARDS: int = 100
DEAFAULT_EXP = 100

USER_BASE: dict[str, Any] = {
    "candies": 0,
    "exp": 0,
    "claimed": 0,
    "cards": [],
    "collections": {},
    "potions": {},
    "actived_potions": {},
    "roll": {
        "rare": 0,
        "epic": 0,
        "legendary": 0
    },
    "cooldown": {
        "roll": 0,
        "claim": 0,
        "daily": 0
    },
    "profile": {
        "bio": "",
        "main": ""
    }
}

DAILY_QUEST_BASE: dict[str, Any] = {
    "claimed": 0,
    "next_reset_at": 0,
    "quests": []
}

class DailyQuestIds(Enum):
    ROLL = 0
    COLLECT = 1
    MATCH = 2
    BUY = 3
    TRADE = 4
    USE = 5

#id, name, description, reward quantity, reward emoji, max_progress
DAILY_QUESTS = [
            [0, 'Roll 5 times', 'Do "qr" or any other rolls five times', 10, '🍬', 5],
            [1, 'Collect Epic+ card', 'Collect a photocard whose rarity is above or equal to Epic by rolling', 20, '🍬',
             1],
            [2, "Play 1 Matching Game", "Play a matching game of any level (qmg)", 10, '🍬', 1],
            [3, "Buy 1 Item", "Buy an item from the shop.", 10, '🍬', 1],
            [4, "Trade 1 photocard", "Buy or sell a photocard", 10, '🍬', 1],
            [5, "Use 1 potion", "Use a potion", 10, '🍬', 1],
        ]

COOLDOWN_BASE: dict[str, tuple[str, int]] = {
    "roll": ("🎲", 600),
    "claim": ("🎮", 180),
    "daily": ("📅", 82800),
    "match_game": ("🃏", 0),
    "quiz_game": ("💯", 600)
}

def open_json(path: str) -> dict:
    try:
        with open(os.path.join(ROOT_DIR, path), encoding="utf8") as json_file:
            return json.load(json_file)
    except:
        return {}


def update_json(path: str, new_data: dict) -> None:
    data = open_json(path)
    if not data:
        return

    data.update(new_data)

    with open(os.path.join(ROOT_DIR, path), "w") as json_file:
        json.dump(data, json_file, indent=4)

def cal_retry_time(end_time: float, default: str = None) -> str | None:
    if end_time <= (current_time := time.time()):
        return default

    retry: float = int(end_time - current_time)

    minutes, seconds = divmod(retry, 60)
    hours, minutes = divmod(minutes, 60)

    return (f"{hours}h " if hours > 0 else "") + f"{minutes}m {seconds}s"

def calculate_level(exp: int) -> tuple[int, int]:
    level = 0

    while exp >= DEAFAULT_EXP:
        exp -= DEAFAULT_EXP
        level += 1

    return level, exp

def convert_seconds(seconds: float) -> str:
    if seconds >= 60:
        minutes = int(seconds // 60)
        seconds = seconds % 60
        return f"{minutes:1d}m {seconds:.1f}s"
    else:
        return f"{seconds:.1f}s"

def get_potions(potions: dict[str, float], base: dict[str, str | dict[str, float]], details: bool = False) -> dict[str, float]:
    result: dict[str, float] = {}
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

def match_string(input_string: str, word_list: list[str]) -> str:
    for word in word_list:
        if word.startswith(input_string):
            return word
    return None

async def get_user(user_id: int, *, insert: bool = True) -> dict[str, Any]:
    user = USERS_BUFFER.get(user_id)
    if not user:
        user = await USERS_DB.find_one({"_id": user_id})
        if not user and insert:
            await USERS_DB.insert_one({"_id": user_id, **USER_BASE})

        user = USERS_BUFFER[user_id] = user if user else copy.deepcopy(USER_BASE) | {"_id": user_id}
    return user

async def update_user(user_id: int, data: dict) -> None:
    user = await get_user(user_id)
    for mode, action in data.items():
        for key, value in action.items():
            cursors = key.split(".")

            nested_user = user
            for c in cursors[:-1]:
                nested_user = nested_user.setdefault(c, {})

            if mode == "$set":
                try:
                    nested_user[cursors[-1]] = value
                except TypeError:
                    nested_user[int(cursors[-1])] = value

            elif mode == "$unset":
                nested_user.pop(cursors[-1], None)

            elif mode == "$inc":
                nested_user[cursors[-1]] = nested_user.get(cursors[-1], 0) + value

            elif mode == "$push":
                nested_user.setdefault(cursors[-1], []).extend(value.get("$in", []) if isinstance(value, dict) else [value])

            elif mode == "$pull":
                if cursors[-1] in nested_user:
                    value = value.get("$in", []) if isinstance(value, dict) else [value]
                    nested_user[cursors[-1]] = [item for item in nested_user[cursors[-1]] if item not in value]

            else:
                raise ValueError(f"Invalid mode: {mode}")

    await USERS_DB.update_one({"_id": user_id}, data)

async def update_card(card_id: list[str] | str, data: dict, insert: bool = False) -> None:
    if insert:
        await CARDS_DB.insert_one({"_id": card_id})

    if isinstance(card_id, list):
        return await CARDS_DB.update_many({"_id": {"$in": card_id}}, data)

    await CARDS_DB.update_one({"_id": card_id}, data)

async def get_daily_quest(user_id: int, *, insert: bool = True) -> dict[str, Any]:
    daily_quest = DAILY_QUEST_BUFFER.get(user_id)
    if not daily_quest:
        daily_quest = await DAILY_QUEST_DB.find_one({"_id": user_id})
        if not daily_quest and insert:
            await DAILY_QUEST_DB.insert_one({"_id": user_id, **DAILY_QUEST_BASE})

        daily_quest = DAILY_QUEST_BUFFER[user_id] = daily_quest if daily_quest else copy.deepcopy(DAILY_QUEST_BASE) | {"_id": user_id}
    return daily_quest

async def update_daily_quest(user_id: int, data: dict) -> None:
    daily_quest = await get_daily_quest(user_id)
    for mode, action in data.items():
        for key, value in action.items():
            cursors = key.split(".")

            nested_daily_quest = daily_quest
            for c in cursors[:-1]:
                nested_daily_quest = nested_daily_quest.setdefault(c, {})

            if mode == "$set":
                try:
                    nested_daily_quest[cursors[-1]] = value
                except TypeError:
                    nested_daily_quest[int(cursors[-1])] = value

            elif mode == "$unset":
                nested_daily_quest.pop(cursors[-1], None)

            elif mode == "$inc":
                nested_daily_quest[cursors[-1]] = nested_daily_quest.get(cursors[-1], 0) + value

            elif mode == "$push":
                nested_daily_quest.setdefault(cursors[-1], []).extend(value.get("$in", []) if isinstance(value, dict) else [value])

            elif mode == "$pull":
                if cursors[-1] in nested_daily_quest:
                    value = value.get("$in", []) if isinstance(value, dict) else [value]
                    nested_daily_quest[cursors[-1]] = [item for item in nested_daily_quest[cursors[-1]] if item not in value]

            else:
                raise ValueError(f"Invalid mode: {mode}")

async def add_quest_progress(user_id: int, quest_id: int, progress: int) -> None:
    daily_quest = await get_daily_quest(user_id)
    can_update = False
    for quest in daily_quest["quests"]:
        if quest[0] == quest_id and quest[1] < DAILY_QUESTS[quest_id][5]:
            quest[1] += progress
            if quest[1] > DAILY_QUESTS[quest_id][5]:
                quest[1] = DAILY_QUESTS[quest_id][5]
            can_update = True
            break
    if can_update:
        await update_daily_quest(user_id, {"$set": {"quests": daily_quest["quests"]}})
