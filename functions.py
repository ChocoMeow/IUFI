import os, time, copy, json, iufi
from enum import Enum, auto

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
COUPLE_DB: AsyncIOMotorCollection = None

USERS_BUFFER: dict[int, dict[str, Any]] = {}
DAILY_QUEST_BUFFER: dict[int, dict[str, Any]] = {}
COUPLE_BUFFER: dict[int, dict[str, Any]] = {}
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
        "daily": 0,
        "quiz_game": 0,
    },
    "profile": {
        "bio": "",
        "main": ""
    },
    "event_item": {
      "rose": 0,
    },
    "couple_id": None
}

DAILY_QUEST_BASE: dict[str, Any] = {
    "claimed": 0,
    "next_reset_at": 0,
    "quests": []
}

COUPLE_BASE: dict[str, Any] = {
    "next_reset_at": 0,
    "date_partnered": 0,
    "quests": [],
    "partner_1": None,
    "partner_2": None,
    "score": 0,
}

class DailyQuestIds(Enum):
    ROLL = 0
    COLLECT_EPIC_CARD = auto()
    MATCH_GAME = auto()
    BUY_ITEM = auto()
    TRADE = auto()
    USE_POTION = auto()
    PLAY_QUIZ = auto()
    COLLECT_LEGENDARY_CARD = auto()

#id, name, description, reward quantity, reward emoji, max_progress,reward_type
DAILY_QUESTS = [
    [DailyQuestIds.ROLL, 'Roll 5 times', 'Do "qr" or any other rolls five times', 10, f'{iufi.get_main_currency_emoji()}', 5, 'candies'],
    [DailyQuestIds.COLLECT_EPIC_CARD, 'Collect Epic+ card', 'Collect a photocard whose rarity is above or equal to Epic by rolling', 20, f'{iufi.get_main_currency_emoji()}', 1, 'candies'],
    [DailyQuestIds.MATCH_GAME, "Play 1 Matching Game", "Play a matching game of any level (qmg)", 10, f'{iufi.get_main_currency_emoji()}', 1, 'candies'],
    [DailyQuestIds.BUY_ITEM, "Buy 1 Item", "Buy an item from the shop.", 10, f'{iufi.get_main_currency_emoji()}', 1, 'candies'],
    [DailyQuestIds.TRADE, "Trade 1 photocard", "Buy or sell a photocard", 10, f'{iufi.get_main_currency_emoji()}', 1, 'candies'],
    [DailyQuestIds.USE_POTION, "Use 1 potion", "Use a potion", 10, f'{iufi.get_main_currency_emoji()}', 1, 'candies'],
    [DailyQuestIds.PLAY_QUIZ, "Play 1 Quiz", "Play a quiz", 10, f'{iufi.get_main_currency_emoji()}', 1, 'candies'],
]

COUPLE_QUESTS = [
    [DailyQuestIds.ROLL, 'Roll 100 times', 'Do "qr" or any other rolls twenty times', 1, f'👑', 100, 'roll.legendary'],
    [DailyQuestIds.COLLECT_LEGENDARY_CARD, 'Collect Legendary card', 'Collect a photocard whose rarity is above or equal to Legendary by rolling', 20, f'{iufi.get_main_currency_emoji()}', 1, 'candies'],
    [DailyQuestIds.MATCH_GAME, "Play 10 Matching Game", "Play a matching game of any level (qmg)", 30, f'{iufi.get_main_currency_emoji()}', 10, 'candies'],
    [DailyQuestIds.BUY_ITEM, "Buy 5 Items", "Buy an item from the shop.", 30, f'{iufi.get_main_currency_emoji()}', 5, 'candies'],
    [DailyQuestIds.TRADE, "Trade 5 photocard", "Buy or sell a photocard", 15, f'{iufi.get_main_currency_emoji()}', 5, 'candies'],
    [DailyQuestIds.USE_POTION, "Use 5 potion", "Use a potion", 1, f'🌸', 5, 'roll.rare'],
    [DailyQuestIds.PLAY_QUIZ, "Play 10 Quiz", "Play a quiz", 1, f'💎', 10, 'roll.epic'],
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

async def update_db(db: AsyncIOMotorCollection, tempStore: dict, filter: dict, data: dict) -> None:
    for mode, action in data.items():
        for key, value in action.items():
            cursors = key.split(".")

            nested_data = tempStore
            for c in cursors[:-1]:
                nested_data = nested_data.setdefault(c, {})

            if mode == "$set":
                try:
                    nested_data[cursors[-1]] = value
                except TypeError:
                    nested_data[int(cursors[-1])] = value

            elif mode == "$unset":
                nested_data.pop(cursors[-1], None)

            elif mode == "$inc":
                nested_data[cursors[-1]] = nested_data.get(cursors[-1], 0) + value

            elif mode == "$push":
                nested_data.setdefault(cursors[-1], []).extend(value.get("$in", []) if isinstance(value, dict) else [value])

            elif mode == "$pull":
                if cursors[-1] in nested_data:
                    value = value.get("$in", []) if isinstance(value, dict) else [value]
                    nested_data[cursors[-1]] = [item for item in nested_data[cursors[-1]] if item not in value]

            else:
                raise ValueError(f"Invalid mode: {mode}")

    await db.update_one(filter, data)

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
    await update_db(USERS_DB, user, {"_id": user_id}, data)

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
    await update_db(DAILY_QUEST_DB, daily_quest, {"_id": user_id}, data)

async def add_daily_quest_progress(user_id: int, quest_id: int, progress: int) -> None:
    daily_quest = await get_daily_quest(user_id)
    if not daily_quest:
        user = await get_user(user_id)
        await add_couple_quest_progress(user["couple_id"], quest_id, progress)
        return
    can_update = False
    process_reward = False
    for quest in daily_quest["quests"]:
        if quest[0] == quest_id and quest[1] < DAILY_QUESTS[quest_id][5]:
            quest[1] += progress
            if quest[1] >= DAILY_QUESTS[quest_id][5]:
                quest[1] = DAILY_QUESTS[quest_id][5]
                process_reward = True
            can_update = True
            break
    if can_update:
        await update_daily_quest(user_id, {"$set": {"quests": daily_quest["quests"]}})
    if process_reward:
        await update_user(user_id, {"$inc": {DAILY_QUESTS[quest_id][6]: DAILY_QUESTS[quest_id][3]}})
    user = await get_user(user_id)
    await add_couple_quest_progress(user["couple_id"], quest_id, progress)

async def add_couple_quest_progress(couple_id: int, quest_id: int, progress: int) -> None:
    couple_data = await get_couple_data(couple_id)
    if not couple_data or couple_data.get("next_reset_at", 0) < time.time():
        return

    for quest in couple_data["quests"]:
        if quest[0] == quest_id and quest[1] < COUPLE_QUESTS[quest_id][5]:
            quest[1] = min(quest[1] + progress, COUPLE_QUESTS[quest_id][5])
            await update_couple(couple_id, {"$set": {"quests": couple_data["quests"]}})
            
            if quest[1] == COUPLE_QUESTS[quest_id][5]:
                for partner in ["partner_1", "partner_2"]:
                    await update_user(couple_data[partner], {"$inc": {COUPLE_QUESTS[quest_id][6]: COUPLE_QUESTS[quest_id][3]}})
                await update_couple(couple_id, {"$inc": {"score": 1}})
            break

def get_daily_quest_by_id(quest_id):
    for quest in DAILY_QUESTS:
        if quest[0] == quest_id:
            return quest
    return None

def get_couple_quest_by_id(quest_id):
    quest_id = DailyQuestIds(quest_id)
    for quest in COUPLE_QUESTS:
        if quest[0] == quest_id:
            return quest
    return None

async def reduce_partner_cooldown(user_id: int, couple_id: int, type: str) -> None:
    if not couple_id: return
    
    couple_data = await get_couple_data(couple_id)
    if not couple_data:
        return

    other_parnter = couple_data["partner_1"] if couple_data["partner_1"] == user_id else couple_data["partner_2"]
    partner_data = await get_user(other_parnter)
    if partner_data.get("cooldown", {}).get(type, 0) <= time.time():
        return
    
    await update_user(other_parnter, {"$set": {f"cooldown.{type}": partner_data["cooldown"][type] - (COOLDOWN_BASE[type][1] // 2)}})

async def get_couple_data(couple_id: int) -> dict[str, Any]:
    couple_data = COUPLE_BUFFER.get(couple_id)
    if not couple_data:
        couple_data = COUPLE_BUFFER[couple_id] = await COUPLE_DB.find_one({"_id": couple_id})
    return couple_data

async def make_couple(partner_1: int, partner_2: int) -> None:
    couple_data = {
        **COUPLE_BASE,
        "partner_1": partner_1,
        "partner_2": partner_2,
        "date_partnered": time.time()
    }
    couple_result = await COUPLE_DB.insert_one(couple_data)
    couple_id = couple_result.inserted_id
    COUPLE_BUFFER[couple_id] = couple_data

    await update_user(partner_1, {"$set": {"couple_id": couple_id}})
    await update_user(partner_2, {"$set": {"couple_id": couple_id}})

async def update_couple(couple_id: int, data: dict) -> None:
    couple = await get_couple_data(couple_id)
    await update_db(COUPLE_DB, couple, {"_id": couple_id}, data)