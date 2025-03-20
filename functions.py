import os, time, copy, json, random, logging, discord

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
        self.DAILY_QUESTS: Dict[str, Union[str, int]] = {}
        self.WEEKLY_QUESTS: Dict[str, Union[str, int]] = {}
        self.TIERS_BASE: Dict[str, List[str, int]] = {}
        self.FRAMES_BASE: Dict[str, List[str, str]] = {}
        self.POTIONS_BASE: Dict[str, Union[str, Dict[str, float]]] = {}
        self.RANK_BASE: Dict[Dict, Dict[str, Any]] = {}
        self.MATCH_GAME_SETTINGS: Dict[str, Dict[str, Any]] = {}
        self.MUSIC_GAME_SETTINGS: Dict[str, Any] = {}
        self.ADMIN_IDS: List[int] = []
        self.OPUS_PATH: str = ""
        self.LOGGING: Dict[Union[str, Dict[str, Union[str, bool]]]] = {}

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
        self.DAILY_QUESTS = {k: v for k, v in settings.get("DAILY_QUESTS").items()}
        self.WEEKLY_QUESTS = {k: v for k, v in settings.get("WEEKLY_QUESTS").items()}
        self.TIERS_BASE = settings.get("TIERS_BASE")
        self.FRAMES_BASE = settings.get("FRAMES_BASE")
        self.POTIONS_BASE = settings.get("POTIONS_BASE")
        self.RANK_BASE = settings.get("RANK_BASE")
        self.MATCH_GAME_SETTINGS = settings.get("MATCH_GAME_SETTINGS")
        self.MUSIC_GAME_SETTINGS = settings.get("MUSIC_GAME_SETTINGS")
        self.ADMIN_IDS = settings.get("ADMIN_IDS")
        self.OPUS_PATH = settings.get("OPUS_PATH")
        self.LOGGING = settings.get("LOGGING", {})

tokens: TOKEN = TOKEN()
settings: Settings = Settings()
logger: logging.Logger = logging.getLogger("iufi")

# DB Var
MONGO_DB: AsyncIOMotorClient = None
USERS_DB: AsyncIOMotorCollection = None
CARDS_DB: AsyncIOMotorCollection = None
QUESTIONS_DB: AsyncIOMotorCollection = None
MUSIC_DB: AsyncIOMotorCollection = None

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
    except:
        return {}

def cal_retry_time(end_time: float, default: str = None) -> str | None:
    if end_time <= (current_time := time.time()):
        return default

    retry: float = int(end_time - current_time)

    minutes, seconds = divmod(retry, 60)
    hours, minutes = divmod(minutes, 60)

    return (f"{hours}h " if hours > 0 else "") + f"{minutes}m {seconds}s"

def cal_last_online_time(start_time: float, default: str = "") -> str | None:
    if start_time > (current_time := time.time()):
        return default

    duration_since_start: float = int(current_time - start_time)

    minutes, seconds = divmod(duration_since_start, 60)
    hours, minutes = divmod(minutes, 60)

    return (f"{hours}h " if hours > 0 else "") + f"{minutes}m {seconds}s"

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

def truncate_string(text: str, length: int = 18) -> str:
    return text[:length - 3] + "..." if len(text) > length else text

async def get_user(user_id: int, *, insert: bool = True) -> Dict[str, Any]:
    user = USERS_BUFFER.get(user_id)
    if not user:
        user = await USERS_DB.find_one({"_id": user_id})
        if not user and insert:
            await USERS_DB.insert_one({"_id": user_id, **settings.USER_BASE})

        user = USERS_BUFFER[user_id] = user if user else copy.deepcopy(settings.USER_BASE) | {"_id": user_id}
    return user

def update_quest_progress(user: Dict[str, Any], completed_quests: Union[str, List[str]], progress: int = 1, *, query: Dict[str, Any] = None) -> Dict[str, Any]:
    global settings

    completed_quests = completed_quests if isinstance(completed_quests, list) else [completed_quests]
    if not query:
        query: Dict[str, Any] = {}

    for quest_type in settings.USER_BASE["quests"].keys():
        user_quest = user.copy().get("quests", {}).get(quest_type, copy.deepcopy(settings.USER_BASE["quests"][quest_type]))

        QUESTS_BASE: Dict[str, Any] = getattr(settings, f"{quest_type.upper()}_QUESTS", None)
        if not QUESTS_BASE:
            continue
        
        #  Check if the quests need to be updated
        if (quest_updated := user_quest["next_update"] < (now := time.time())):
            _settings = QUESTS_SETTINGS.get(quest_type, {})
            quests_by_type = {}

            # Group quests by their type
            for quest_name, quest_details in QUESTS_BASE.items():
                type = quest_details['type']
                if type not in quests_by_type:
                    quests_by_type[type] = []
                quests_by_type[type].append(quest_name)

            # Now pick one quest from each type
            new_quests = [random.choice(quests) for quests in quests_by_type.values()]

            new_quests = random.sample(new_quests, k=_settings.get("items", len(new_quests)))

            user_quest["progresses"] = query.setdefault("$set", {})[f"quests.{quest_type}.progresses"] = {str(quest): 0 for quest in new_quests}
            query["$set"][f"quests.{quest_type}.next_update"] = now + _settings.get("update_time", 0)

        # Update the progress for each quest
        for quest_name in completed_quests:
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

    return query

def create_help_embed(ctx: commands.Context, cmd: commands.Command = None) -> discord.Embed:
    if (correction_required := not cmd):
        cmd = ctx.command

    # Prepare command usage string
    command_usage = f"{ctx.prefix}{cmd.parent.qualified_name + ' ' if cmd.parent else ''}{cmd.name} {cmd.signature}"
    
    # Build usage description
    if correction_required:
        param_position = command_usage.find(f"<{ctx.current_parameter.name}>") + 1
        usage_description = f"**Correct Usage:**\n```{command_usage}\n" + " " * param_position + "^" * len(ctx.current_parameter.name) + "```\n"
    else:
        usage_description = f"**Usage:**\n```{command_usage}```\n"

    # Add aliases if available
    if cmd.aliases:
        aliases = ', '.join([f'{ctx.prefix}{alias}' for alias in cmd.aliases])
        usage_description += f"**Aliases:**\n`{aliases}`\n\n"

    # Replace placeholders in command help
    help_text = cmd.help.replace("@prefix@", settings.BOT_PREFIX[0])

    # Complete the description
    usage_description += f"**Description:**\n{help_text}\n\u200b"

    # Create and return the embed
    embed = discord.Embed(description=usage_description, color=discord.Color.random())
    embed.set_footer(icon_url=ctx.me.display_avatar.url, text="More Help: Ask the staff!")
    return embed

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

async def update_user(user_id: int, data: dict) -> None:
    user = await get_user(user_id)
    data.setdefault('$set', {})['last_active_time'] = time.time()

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
                # Check if the value contains $each
                if isinstance(value, dict) and "$each" in value:
                    nested_user.setdefault(cursors[-1], []).extend(value["$each"])
                else:
                    nested_user.setdefault(cursors[-1], []).append(value)

            elif mode == "$pull":
                if cursors[-1] in nested_user:
                    value = value.get("$in", []) if isinstance(value, dict) else [value]
                    nested_user[cursors[-1]] = [item for item in nested_user[cursors[-1]] if item not in value]

            else:
                raise ValueError(f"Invalid mode: {mode}")

    await USERS_DB.update_one({"_id": user_id}, data)

async def update_card(card_id: List[str] | str, data: dict, insert: bool = False) -> None:
    if insert:
        await CARDS_DB.insert_one({"_id": card_id})

    if isinstance(card_id, list):
        return await CARDS_DB.update_many({"_id": {"$in": card_id}}, data)

    await CARDS_DB.update_one({"_id": card_id}, data)