from random import Random

from .card import Card
from .exceptions import DuplicatedCardError

DROP_RATES = {
    'common': 0.9,
    'rare': 0.08,
    'epic': 0.007,
    'legendary': 0.003
}

class CardPool:
    _cards: dict[str, Card] = {}
    _available_cards: dict[str, list[Card]] = {
        category: [] for category in DROP_RATES
    }
    _rand = Random()

    @classmethod
    def add_available_card(cls, card: Card):
        cls._available_cards[card.tier[1]].append(card)

    @classmethod
    def remove_available_card(cls, card: Card):
        cls._available_cards[card.tier[1]].remove(card)

    @classmethod
    def add_card(cls, _id: str, tier: str, **kwargs) -> Card:
        card = Card(_id, tier, **kwargs)
        if card.id in cls._cards:
            raise DuplicatedCardError(f"Card {card.id} already added into the pool.")
        
        cls._cards[card.id] = card
        if not card.owner_id:
            cls.add_available_card(card)

        return card
    
    @classmethod
    def get_card(cls, id: str) -> Card | None:
        return cls._cards.get(id)
    
    @classmethod
    def roll(cls, amount: int = 3) -> list[Card]:
        categories = list(DROP_RATES.keys())
        results = cls._rand.choices(categories, weights=DROP_RATES.values(), k=amount)

        return [cls._rand.choice(cls._available_cards[result]) for result in results]

