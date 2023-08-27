from random import Random

from .card import Card
from .exceptions import DuplicatedCardError, DuplicatedTagError

DROP_RATES = {
    'common': 0.9,
    'rare': 0.08,
    'epic': 0.007,
    'legendary': 0.003,
    'mystic':.001
}

class CardPool:
    _cards: dict[str, Card] = {}
    _tag_cards: dict[str, Card] = {}
    _available_cards: dict[str, list[Card]] = {
        category: [] for category in DROP_RATES
    }

    _rand = Random()

    @classmethod
    def add_available_card(cls, card: Card) -> None:
        cls._available_cards[card.tier[1]].append(card)

    @classmethod
    def remove_available_card(cls, card: Card) -> None:
        cls._available_cards[card.tier[1]].remove(card)

    @classmethod
    def add_tag(cls, card: Card, tag: str) -> None:
        if tag.lower() in cls._tag_cards:
            raise DuplicatedTagError(f"Tag {tag} already added into the pool.")
        
        card.change_tag(tag)
        cls._tag_cards[tag.lower()] = card
    
    @classmethod
    def change_tag(cls, card: Card, tag: str) -> None:
        if tag.lower() in cls._tag_cards:
            raise DuplicatedTagError(f"Tag {tag} already added into the pool.")
        
        if card.tag and card.tag.lower() in cls._tag_cards:
            card = cls._tag_cards.pop(card.tag.lower())
            card.change_tag(tag)
            cls._tag_cards[tag.lower()] = card

    @classmethod
    def remove_tag(cls, card: Card) -> None:
        try:
            card = cls._tag_cards.pop(card.tag.lower())
            card.change_tag(None)
        except KeyError as _:
            return
        
    @classmethod
    def add_card(cls, _id: str, tier: str, **kwargs) -> Card:
        card = Card(cls, _id, tier, **kwargs)
        if card.id in cls._cards:
            raise DuplicatedCardError(f"Card {card.id} in {tier} already added into the pool.")
        
        cls._cards[card.id] = card
        if not card.owner_id:
            cls.add_available_card(card)
        
        if card.tag:
            cls.add_tag(card, card.tag)

        return card
    
    @classmethod
    def get_card(cls, id: str) -> Card | None:
        return cls._cards.get(id)
    
    @classmethod
    def roll(cls, amount: int = 3) -> list[Card]:
        categories = list(DROP_RATES.keys())
        results = cls._rand.choices(categories, weights=DROP_RATES.values(), k=amount)

        return [cls._rand.sample(cls._available_cards[result], k=1)[0] for result in results]

