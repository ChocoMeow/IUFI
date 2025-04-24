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

def get_birthday_buffs():
    """
    Returns the buff multipliers for IU's birthday (May 16th).
    
    Returns:
        dict: A dictionary containing buff multipliers for different activities
    """
    if not is_birthday_buff_active():
        return {
            'starcandies': 1.0,
            'quiz_points': 1.0,
            'music_points': 1.0,
            'exp': 1.0,
            'luck': 0.0,
            'match_extra_moves': 0
        }
    
    return {
        'starcandies': 2.0,     # 2x Starcandies from all sources
        'quiz_points': 2.0,     # 2x Points for quiz games
        'music_points': 2.0,    # 2x Points for music quiz
        'exp': 2.0,             # 2x EXP gain
        'luck': 1.0,            # 2x Luck for normal rolls (100% boost)
        'match_extra_moves': 2  # 2 extra moves for match game
    }