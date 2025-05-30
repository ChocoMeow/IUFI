import datetime
import random
from datetime import timezone, timedelta

# Define KST timezone (UTC+9)
KST = timezone(timedelta(hours=9))

# Birthday event dates in KST
birthday_event_start = datetime.datetime(2025, 5, 1, 0, 0, tzinfo=KST)
birthday_event_end = datetime.datetime(2025, 5, 31, 23, 59, tzinfo=KST)
actual_birthday = datetime.datetime(2025, 5, 16, 0, 0, tzinfo=KST)
birthday_shop_end = datetime.datetime(2025, 6, 1, 23, 59, tzinfo=KST)

# Predefined daily buffs for each day of the month (0-indexed for easier access)
daily_buffs = [
    None,  # Placeholder for index 0 (no day 0)
    "2x_quiz_points",       # Day 1
    "2x_candy",             # Day 2
    "2x_music_points",      # Day 3
    "extra_moves_match_game", # Day 4
    "frame_discount",       # Day 5
    "shop_discount",        # Day 6
    "inventory_increase",   # Day 7
    "frame_discount",             # Day 8
    "frame_discount",       # Day 9
    "extra_moves_match_game", # Day 10
    "inventory_increase",      # Day 11
    "2x_candy",        # Day 12
    "extra_moves_match_game",   # Day 13
    "frame_discount",       # Day 14
    "2x_candy",             # Day 15
    "2x_quiz_points",       # Day 16 (Birthday)
    "frame_discount",       # Day 17
    "2x_music_points",      # Day 18
    "inventory_increase",   # Day 19
    "shop_discount",        # Day 20
    "extra_moves_match_game", # Day 21
    "2x_candy",             # Day 22
    "2x_quiz_points",       # Day 23
    "inventory_increase",   # Day 24
    "shop_discount",        # Day 25
    "2x_music_points",      # Day 26
    "extra_moves_match_game", # Day 27
    "frame_discount",       # Day 28
    "2x_candy",             # Day 29
    "shop_discount",        # Day 30
    "inventory_increase",   # Day 31
]

def get_birthday_event_end():
    return birthday_event_end

def is_birthday_buff_active(buff_name=None):
    # For testing, uncomment this line
    # return True
    
    now = datetime.datetime.now(KST)
    
    # On actual birthday, all buffs are active
    if is_birthday():
        return True
        
    # During birthday event, one specific buff is active each day
    if birthday_event_start <= now <= birthday_event_end:
        # For backward compatibility: if no specific buff is requested, 
        # return True to indicate some buff is active
        if buff_name is None:
            return True
            
        # Define existing birthday buffs
        available_buffs = ["2x_quiz_points", "2x_candy", "2x_music_points", "extra_moves_match_game", 
                           "frame_discount", "shop_discount", "inventory_increase"]
        
        # Get today's active buff from the predefined list
        daily_buff = daily_buffs[now.day]
        
        # Return True if the requested buff is active today
        return buff_name == daily_buff
    
    return False

def is_birthday_event_active():
    now = datetime.datetime.now(KST)
    return birthday_event_start <= now <= birthday_event_end

def get_current_birthday_card_day():
    now = datetime.datetime.now(KST)
    if birthday_event_start <= now <= birthday_event_end:
        # Calculate days since event started (add 1 to make the first day be day 1)
        day_number = (now.date() - birthday_event_start.date()).days + 1
        return day_number
    return None

def is_birthday():
    now = datetime.datetime.now(KST)
    return now.date() == actual_birthday.date()

def is_event_shop_active():
    now = datetime.datetime.now(KST)
    return now.date() >= actual_birthday.date() and now.date() <= birthday_shop_end.date()
