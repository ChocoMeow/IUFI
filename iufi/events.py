import datetime

# Debut Anniversary
EVENT_CONFIG: dict[str, dict[str, str | datetime.datetime]] = {
    "debut_anniversary": {
        "name": "Debut Anniversary",
        "description": "Celebrate IU's debut anniversary with IUFI!",
        "start_date": datetime.datetime(datetime.datetime.now().year, 9, 9),
        "end_date": datetime.datetime(datetime.datetime.now().year, 9, 26),
        "folder": "debut"
    }
}

debut_anniversary_day = EVENT_CONFIG["debut_anniversary"]


def is_debut_anniversary_day() -> bool:
    return debut_anniversary_day["start_date"] <= datetime.datetime.now() <= debut_anniversary_day["end_date"]


def get_end_time() -> datetime.datetime:
    return debut_anniversary_day["end_date"]

def get_match_game_cover(level: str) -> str:
    return "cover/" + f"level{level}.jpg"


DAILY_REWARDS: dict[int, tuple[str, str, int]] = {
    1: ("🎵", "candies", 5),
    2: ("🎵", "candies", 5),
    3: ("🎵", "candies", 5),
    4: ("🎵", "candies", 10),
    5: ("🌸", "roll.rare", 1),
    6: ("🎵", "candies", 10),
    7: ("🎵", "candies", 15),
    8: ("🎵", "candies", 25),
    9: ("💎", "roll.epic", 1),
    10: ("🎵", "candies", 25),
    11: ("🎵", "candies", 15),
    12: ("🎵", "candies", 10),
    13: ("🌸", "roll.rare", 1),
    14: ("🎵", "candies", 10),
    15: ("🎵", "candies", 5),
    16: ("🎵", "candies", 5),
    17: ("🎵", "candies", 5)
}

CARDS_TO_SELL: dict[int, [tuple[str, int]]] = {
    1: (("1", 10), ("2", 20)),
    2: (("194", 3), ("327", 999)),
    3: (("5", 50), ("6", 60)),
    4: (("7", 70), ("8", 80)),
    5: (("9", 90), ("10", 100)),
    6: (("11", 110), ("12", 120)),
    7: (("13", 130), ("14", 140)),
    8: (("15", 150), ("16", 160)),
    9: (("17", 170), ("18", 180)),
    10: (("19", 190), ("20", 200)),
    11: (("21", 210), ("22", 220)),
    12: (("23", 230), ("24", 240)),
    13: (("25", 250), ("26", 260)),
    14: (("27", 270), ("28", 280)),
    15: (("29", 290), ("30", 300)),
    16: (("31", 310), ("32", 320)),
    17: (("33", 330), ("34", 340)),
}

MILESTONES = [5, 10, 13, 14]
MILESTONE_ONE_REWARD = [["🎵", "candies", 50]]
MILESTONE_TWO_REWARD = [["🌸", "roll.rare", 2]]
MILESTONE_THREE_REWARD = [["🌸", "roll.rare", 1],["💎", "roll.epic", 1]]
MILESTONE_FOUR_REWARD = [["🎵", "candies", 50],["💎", "roll.epic", 2],["👑", "roll.legendary", 1]]
ANNIVERSARY_QUEST_REWARDS = [MILESTONE_ONE_REWARD, MILESTONE_TWO_REWARD, MILESTONE_THREE_REWARD, MILESTONE_FOUR_REWARD]

#MARKET_ID = 1159846609924927558 # dev server
#ANNOUNCEMENT_ID = 1159846609924927558 # dev server
MARKET_ID = 1143358510697021532 #my server
ANNOUNCEMENT_ID = 1143358510697021532 #my server

def GetTodayReward() -> tuple[str, str, int]:
    # current day - event start day
    current_day = (datetime.datetime.now() - debut_anniversary_day["start_date"]).days + 1
    print("current_day: ", current_day)
    return DAILY_REWARDS.get(current_day, None)


def GetTodayCardSell() -> list[tuple[str, int]]:
    # current day - event start day
    current_day = (datetime.datetime.now() - debut_anniversary_day["start_date"]).days + 1
    print("current_day: ", current_day)
    return CARDS_TO_SELL.get(current_day, None)


def GetAllCards() -> list[tuple[str, int]]:
    return [card for cards in CARDS_TO_SELL.values() for card in cards]