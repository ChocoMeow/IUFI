import os, time, copy

from pymongo import MongoClient
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

if not (tokens.mongodb_name and tokens.mongodb_url):
    raise Exception("MONGODB_NAME and MONGODB_URL can't not be empty in .env")

try:
    mongodb = MongoClient(host=tokens.mongodb_url, serverSelectionTimeoutMS=5000)
    mongodb.server_info()
    if tokens.mongodb_name not in mongodb.list_database_names():
        raise Exception(f"{tokens.mongodb_name} does not exist in your mongoDB!")
    print("Successfully connected to MongoDB!")

except Exception as e:
    raise Exception("Not able to connect MongoDB! Reason:", e)

USERS_DB = mongodb[tokens.mongodb_name]['users']
CARDS_DB = mongodb[tokens.mongodb_name]['cards'] 

USERS_LOCK = []
USERS_BUFFER: dict[int, dict[str, Any]] = {}
COOLDOWN: dict[int, dict[str, float]] = {}
MAX_CARDS: int = 100
DEAFAULT_EXP = 100

USER_BASE: dict[str, Any] = {
    "candies": 0,
    "exp": 0,
    "claimed": 0,
    "cards": [],
    "roll": {
        "rare": 0,
        "epic": 0,
        "legendary": 0
    },
    "cooldown": {
        "roll": (now := int(time.time())),
        "claim": now,
        "daily": now
    }
}

COOLDOWN_BASE = {
    "roll": 600,
    "claim": 180,
    "daily": 86400
}

def get_user(user_id: int) -> dict[str, Any]:
    user = USERS_BUFFER.get(user_id)
    if not user:
        user = USERS_DB.find_one({"_id": user_id})
        if not user:
            USERS_DB.insert_one({"_id": user_id, **USER_BASE})

        user = USERS_BUFFER[user_id] = user if user else copy.deepcopy(USER_BASE)
    return user

def update_user(user_id: int, data: dict) -> None:
    user = get_user(user_id)

    for mode, action in data.items():
        for key, value in action.items():
            cursors = key.split(".")

            nested_user = user
            for c in cursors[:-1]:
                nested_user = nested_user[c]

            if mode == "$set":
                nested_user[cursors[-1]] = value
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
                
    USERS_DB.update_one({"_id": user_id}, data)

def update_card(card_id: list[str] | str, data: dict, insert: bool = False) -> None:
    if insert:
        CARDS_DB.insert_one({"_id": card_id})
    
    if isinstance(card_id, list):
        return CARDS_DB.update_many({"_id": {"$in": card_id}}, data)
    
    CARDS_DB.update_one({"_id": card_id}, data)

def cal_retry_time(end_time: float, default: str=None) -> str | None:
    if end_time <= (current_time := time.time()):
        return default
    
    retry: float = int(end_time - current_time)

    minutes, seconds = divmod(retry, 60)
    hours, minutes = divmod(minutes, 60)

    return (f"{hours}h " if hours > 0 else "") + f"{minutes}m {seconds}s"

def check_user_cooldown(user_id: int, type: str = "roll") -> str | None:
    user = get_user(user_id)
    if user:
        end_time: float = user.get("cooldown", {}).get(type, None)

        if not end_time:
            return ValueError(f"Invalid type: {type}")
        
        return cal_retry_time(end_time)

def calculate_level(exp: int) -> tuple[int, int]:
    level = 0

    while exp >= DEAFAULT_EXP:
        exp -= DEAFAULT_EXP
        level += 1
    
    return level, exp