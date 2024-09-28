from __future__ import annotations

import re, copy
import functions as func

from collections import Counter

from typing import (
    TYPE_CHECKING,
    Dict
)

if TYPE_CHECKING:
    from .music import Track

from random import (
    choice,
    choices,
    sample,
    shuffle
)

from .objects import (
    Card,
    Question,
    QUIZ_LEVEL_BASE
)

from .exceptions import IUFIException, DuplicatedCardError, DuplicatedTagError
# from .deepsearch import (
#     Load_Data,
#     Search_Setup
# )

DROP_RATES = {
    'common': .93,
    'rare': .05,
    'epic': .003,
    'legendary': .0008,
    'mystic': .0001,
    "celestial": .00005
}

URL_REGEX = re.compile(
    r"https?://(?:www\.)?.+"
)

NODE_VERSION = "v4"
CALL_METHOD = ["PATCH", "DELETE"]


class CardPool:
    _cards: dict[str, Card] = {}
    _tag_cards: dict[str, Card] = {}
    _available_cards: dict[str, list[Card]] = {
        category: [] for category in DROP_RATES
    }
    _match_game_cards: list[Card] = []

    #DeepSearch
    # search_image: Search_Setup | None = None

    # @classmethod
    # def load_search_metadata(cls) -> None:
    #     image_list = Load_Data().from_folder(["/metadata-files"])
    #     cls.search_image = Search_Setup(image_list=image_list)
    #     cls.search_image.run_index()

    @classmethod
    def add_available_card(cls, card: Card) -> None:
        card.change_owner()
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
            return
            # raise DuplicatedCardError(f"Card {card.id} in {tier} already added into the pool.")
        
        cls._cards[card.id] = card
        if not card.owner_id:
            cls.add_available_card(card)
        
        if card.tag:
            cls.add_tag(card, card.tag)

        if card.tier[1] != "celestial":
            cls._match_game_cards.append(card)

        return card
    
    @classmethod
    def get_card(cls, card_id: str) -> Card | None:
        if not card_id:
            return
        card_id = card_id.lstrip("0")
        card = cls._cards.get(card_id)
        if not card:
            card = cls._tag_cards.get(card_id.lower())
        return card
    
    @classmethod
    def roll(cls, amount: int = 3, *, included: list[str] = None, avoid: list[str] = None, luck_rates: float = None) -> list[Card]:
        results = included if included else []

        drop_rates = DROP_RATES.copy()
        if luck_rates:
            drop_rates = {k: v if k == 'common' else v * (1 + luck_rates) for k, v in DROP_RATES.items()}
            total = sum(drop_rates.values())
            drop_rates['common'] = 1 - (total - drop_rates['common'])
        
        if avoid:
            drop_rates = {k: v for k, v in drop_rates.items() if k not in avoid}

        results.extend(choices(list(drop_rates.keys()), weights=drop_rates.values(), k=amount - len(results)))
        cards = [
            card
            for cat, amt in Counter(results).items()
            for card in sample(cls._available_cards[cat], k=amt)
        ]
        shuffle(cards)
        return cards

    @classmethod
    def get_random_cards_for_match_game(cls, amount: int = 3) -> list[Card]:
        cards = sample(cls._match_game_cards,amount)
        return cards

class QuestionPool:
    _questions: list[Question] = []

    @classmethod
    def add_question(cls, question: Question) -> None:
        cls._questions.append(question)

    @classmethod
    def remove_question(cls, question: Question) -> None:
        cls._questions.remove(question)
    
    @classmethod
    def get_rank(cls, points: int) -> tuple[str, int]:
        sorted_ranks = sorted(func.settings.RANK_BASE.items(), key=lambda item: item[1]["points"], reverse=True)
        for rank, details in sorted_ranks:
            if points >= details["points"]:
                return (rank, details["emoji_id"])
        return None

    @classmethod
    def get_question_distribution_by_rank(cls, rank: str) -> list[tuple[str, int]]:
        rank_details = func.settings.RANK_BASE.get(rank)
        if not rank_details:
            raise IUFIException(f"Rank '{rank}' not found!")
        
        return rank_details["questions"]

    @classmethod
    def get_question(cls, rank: str, number: int) -> list[Question]:
        if rank not in QUIZ_LEVEL_BASE.keys():
            raise IUFIException(f"{rank} is not found in the quiz!")
        
        questions: dict[str, list[Question]] = {
            level: [q for q in cls._questions if q.level == level]
            for level in QUIZ_LEVEL_BASE.keys()
        }

        num_available = len(questions[rank])
        num_to_return = min(number, num_available)

        return sample(questions[rank], k=num_to_return)
    
    @classmethod
    def get_question_by_rank(cls, ranks: list[tuple[str, int]]) -> list[Question]:
        questions: list[Question] = []
        
        for (rank_name, return_num) in ranks:
            if rank_name not in QUIZ_LEVEL_BASE.keys():
                raise IUFIException(f"{rank_name} is not found in the quiz!")
            
            for question in cls.get_question(rank_name, return_num):
                questions.append(question)
        
        return questions

class MusicPool:

    _questions: Dict[str, Track] = {}

    @classmethod
    def add_question(cls, data: Dict) -> None:
        cls._questions[data["id"]] = Track(data=data)

    @classmethod
    def get_question(cls, id: str) -> Track:
        return cls._questions.get(id)

    @classmethod
    async def get_random_question(cls) -> Track:
        if not cls._questions:
            await cls.fetch_data()
        
        track: Track = choice(cls._questions.values())
        if not track.db_data:
            track_data = await func.MUSIC_DB.find_one({"_id": track.identifier})
            if not track_data:
                await func.MUSIC_DB.insert_one({ "_id": track.identifier, **func.TRACK_BASE})

            track.db_data = track_data or copy.deepcopy(func.TRACK_BASE)
            
        return track

    @classmethod
    async def fetch_data(cls) -> None:
        ...