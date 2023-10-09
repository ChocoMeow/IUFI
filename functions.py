import os, time, copy

from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCollection,
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

USERS_BUFFER: dict[int, dict[str, Any]] = {}
COOLDOWN: dict[int, dict[str, float]] = {}
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

COOLDOWN_BASE: dict[str, int] = {
    "roll": 600,
    "claim": 180,
    "daily": 82800,
}

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