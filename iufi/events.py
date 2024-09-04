import datetime

# Debut Anniversary
EVENT_CONFIG: dict[str, dict[str, str | datetime.datetime]] = {
    "debut_anniversary": {
        "name": "Debut Anniversary",
        "description": "Celebrate IU's debut anniversary with IUFI!",
        "start_date": datetime.datetime(datetime.datetime.now().year, 9, 3),
        "end_date": datetime.datetime(datetime.datetime.now().year, 9, 22),
        "folder": "debut"
    }
}

debut_anniversary_day = EVENT_CONFIG["debut_anniversary"]


def is_debut_anniversary_day() -> bool:
    return debut_anniversary_day["start_date"] <= datetime.datetime.now() <= debut_anniversary_day["end_date"]


def get_match_game_cover(level: str) -> str:
    return "cover/" + (
        f"{debut_anniversary_day['folder']}/level{level}.png" if is_debut_anniversary_day() else f"level{level}.jpg")


DAILY_REWARDS: dict[int, tuple[str, str, int]] = {
    1: ("🎤", "candies", 10),
    2: ("🎤", "candies", 20),
    3: ("🎤", "candies", 30),
    4: ("🎤", "candies", 40),
    5: ("🎤", "candies", 50),
    6: ("🎤", "candies", 60),
    7: ("🎤", "candies", 70),
    8: ("🎤", "candies", 80),
    9: ("🎤", "candies", 90),
    10: ("🎤", "candies", 100),
    11: ("🎤", "candies", 110),
    12: ("🎤", "candies", 120),
    13: ("🎤", "candies", 130),
    14: ("🎤", "candies", 140),
    15: ("🎤", "candies", 150),
    16: ("🎤", "candies", 160),
    17: ("🎤", "candies", 170),
}

CARDS_TO_SELL: dict[int, [tuple[str, int]]] = {
    1: (("1", 10), ("2", 20)),
    2: (("3", 30), ("4", 40)),
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

MARKET_ID = 1143358510697021532


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
