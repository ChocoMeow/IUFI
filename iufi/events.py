import datetime
from datetime import timezone, timedelta

# Define KST timezone (UTC+9)
KST = timezone(timedelta(hours=9))

# Birthday event dates in KST
birthday_event_start = datetime.datetime(2025, 5, 1, 0, 0, tzinfo=KST)
birthday_event_end = datetime.datetime(2025, 5, 31, 23, 59, tzinfo=KST)
actual_birthday = datetime.datetime(2025, 5, 16, 0, 0, tzinfo=KST)

def get_birthday_event_end():
    return birthday_event_end

def is_birthday_buff_active():
    now = datetime.datetime.now(KST)
    return now.date() == actual_birthday.date()

def is_birthday_event_active():
    now = datetime.datetime.now(KST)
    return birthday_event_start <= now <= birthday_event_end

def get_current_birthday_card_day():
    now = datetime.datetime.now(KST)
    if birthday_event_start.month == now.month and birthday_event_start.year == now.year:
        return now.day if 1 <= now.day <= 31 else None
    return None
