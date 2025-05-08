import asyncio
import os
import random
from .objects import Card
from .events import is_birthday_event_active, get_current_birthday_card_day, is_event_shop_active

class BirthdayCard(Card):
    def __init__(self, day_number):
        self.day_number = day_number
        self.id = f"birthday_{day_number}"
        self._tier = "birthday"
        self.owner_id = None
        self.is_gif: bool = False
        self._frame: str = None
        self.tag: str = None
        self.owner_id: int = None

        self._emoji: str = "🎂"
        self._lock: (
            asyncio.Lock) = asyncio.Lock()
        
    def change_owner(self, user_id):
        self.owner_id = user_id
    
    @property
    def image_path(self):
        return os.path.join("birthday", f"{self.day_number}.png")

def should_add_birthday_card():
    """Returns True if a birthday card should be added (5% chance during event)"""
    return is_birthday_event_active() and random.random() < 0.08

def can_give_card_32():
    return is_event_shop_active() and random.random() < 0.05

def get_birthday_card():
    """Returns a birthday card for the current day if event is active"""
    if is_birthday_event_active():
        day = get_current_birthday_card_day()
        if day:
            if can_give_card_32(): # 5% chance to give card 32 (5% out of 10% chance = 0.5% overall)
                return BirthdayCard(32)
            return BirthdayCard(day)
    return None

def replace_with_birthday_card(cards):
    """Replace a random card with birthday card if conditions are met"""
    if not should_add_birthday_card():
        return cards
        
    birthday_card = get_birthday_card()
    if birthday_card and cards:
        # Replace a random card with the birthday card
        random_index = random.randint(0, len(cards) - 1)
        cards[random_index] = birthday_card
    
    return cards
