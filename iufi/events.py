import datetime
import random
from datetime import timezone, timedelta

# Define KST timezone (UTC+9)
KST = timezone(timedelta(hours=9))

# Birthday event dates in KST
birthday_event_start = datetime.datetime(2025, 4, 25, 0, 0, tzinfo=KST)
birthday_event_end = datetime.datetime(2025, 5, 31, 23, 59, tzinfo=KST)
actual_birthday = datetime.datetime(2025, 5, 16, 0, 0, tzinfo=KST)

def get_birthday_event_end():
    return birthday_event_end

def is_birthday_buff_active(buff_name=None):
    # For testing, uncomment this line
    # return True
    
    now = datetime.datetime.now(KST)
    
    # On actual birthday, all buffs are active
    if is_birthday():
        return True
        
    # During birthday event, one random buff is active each day
    if birthday_event_start <= now <= birthday_event_end:
        # For backward compatibility: if no specific buff is requested, 
        # return True to indicate some buff is active
        if buff_name is None:
            return True
            
        # Use a deterministic seed based on the date to get consistent results all day
        seed = now.year * 10000 + now.month * 100 + now.day
        random.seed(seed)
        
        # Define existing birthday buffs
        available_buffs = ["2x_quiz_points", "2x_candy", "2x_music_points", "extra_moves_match_game", 
                           "frame_discount", "shop_discount", "inventory_increase"]
        
        # Determine today's active buff
        daily_buff = random.choice(available_buffs)
        
        # Reset the random seed to not affect other random operations
        random.seed()
        
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
