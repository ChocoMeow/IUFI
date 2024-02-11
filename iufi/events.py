import datetime

# valentines day
EVENT_CONFIG: dict[str, dict[str, str | datetime.datetime]] = {
    "valentines_day": {
        "name": "Valentine's Day",
        "description": "A day to celebrate love and affection",
        "start_date": datetime.datetime(datetime.datetime.now().year, 2, 5),
        "end_date": datetime.datetime(datetime.datetime.now().year, 2, 20),
        "folder": "valentines_day"
    }
}

valentines_day = EVENT_CONFIG["valentines_day"]

def is_valentines_day() -> bool:
    return valentines_day["start_date"] <= datetime.datetime.now() <= valentines_day["end_date"]

def get_match_game_cover(level: str) -> str:
    return "cover/" + (f"{valentines_day['folder']}/level{level}.png" if is_valentines_day() else f"level{level}.jpg")

def get_main_currency_emoji() -> str:
    return "🍫" if is_valentines_day() else "🍬"

def get_main_currency_name() -> str:
    return "Choco" if is_valentines_day() else "Candies"

def is_feb_14() -> bool:
    return datetime.datetime.now().month == 2 and datetime.datetime.now().day == 14