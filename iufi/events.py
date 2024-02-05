import datetime

# valentines day
EVENT_CONFIG: dict[str, dict[str, str | datetime.datetime]] = {
    "valentines_day": {
        "name": "Valentine's Day",
        "description": "A day to celebrate love and affection",
        "start_date": datetime.datetime(datetime.datetime.now().year, 1, 7),
        "end_date": datetime.datetime(datetime.datetime.now().year, 2, 15),
        "folder": "valentines_day"
    }
}

valentines_day = EVENT_CONFIG["valentines_day"]


def is_valentines_day() -> bool:
    return valentines_day["start_date"] <= datetime.datetime.now() <= valentines_day["end_date"]


def get_match_game_cover(level: str) -> str:
    if is_valentines_day():
        return f"cover/{valentines_day['folder']}/level{level}.png"
    else:
        return f"cover/level{level}.jpg"


def get_main_currency_emoji() -> str:
    if is_valentines_day():
        return "🍫"
    else:
        return "🍬"


def get_main_currency_name() -> str:
    if is_valentines_day():
        return "Choco"
    else:
        return "Candies"
