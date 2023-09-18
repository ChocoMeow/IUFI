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

#DB Var
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
    "frame": {
        "hearts": 0,
        "celebrity": 0,
        "uaena": 0,
        "dandelions": 0,
        "shine": 0,
        "cheer": 0,
        "smoon": 0,
        "signed": 0,
    },
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
    "roll": 300,
    "claim": 120,
    "daily": 82800
}

def cal_retry_time(end_time: float, default: str=None) -> str | None:
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

async def get_user(user_id: int) -> dict[str, Any]:
    user = USERS_BUFFER.get(user_id)
    if not user:
        user = await USERS_DB.find_one({"_id": user_id})
        if not user:
            await USERS_DB.insert_one({"_id": user_id, **USER_BASE})

        user = USERS_BUFFER[user_id] = user if user else copy.deepcopy(USER_BASE)
    return user

async def update_user(user_id: int, data: dict) -> None:
    user = await get_user(user_id)

    for mode, action in data.items():
        for key, value in action.items():
            cursors = key.split(".")

            nested_user = user
            for c in cursors[:-1]:
                nested_user = nested_user[c]

            if mode == "$set":
                try:
                    nested_user[cursors[-1]] = value
                except TypeError:
                    nested_user[int(cursors[-1])] = value
            elif mode == "$unset":
                del nested_user[cursors[-1]]
            elif mode == "$inc":
                nested_user[cursors[-1]] += value
            elif mode == "$push":
                if isinstance(value, dict):
                    for items in value.values():
                        for item in items:
                            nested_user[cursors[-1]].append(item)
                else:
                    nested_user[cursors[-1]].append(value)
            elif mode == "$pull":
                if isinstance(value, dict):
                    for items in value.values():
                        for item in items:
                            nested_user[cursors[-1]].remove(item)
                else:
                    nested_user[cursors[-1]].remove(value)
            else:
                raise ValueError(f"Invalid mode: {mode}")
                
    await USERS_DB.update_one({"_id": user_id}, data)

async def update_card(card_id: list[str] | str, data: dict, insert: bool = False) -> None:
    if insert:
        await CARDS_DB.insert_one({"_id": card_id})
    
    if isinstance(card_id, list):
        return await CARDS_DB.update_many({"_id": {"$in": card_id}}, data)
    
    await CARDS_DB.update_one({"_id": card_id}, data)