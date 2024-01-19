from random import (
    choices,
    sample,
    shuffle
)
from collections import Counter

from .objects import Card, Question, QUIZ_LEVEL_BASE, RANK_BASE
from .exceptions import DuplicatedCardError, DuplicatedTagError
# from .deepsearch import (
#     Load_Data,
#     Search_Setup
# )

DROP_RATES = {
    'common': .9,
    'rare': .08,
    'epic': .007,
    'legendary': .003,
    'mystic': .001,
    "celestial": .0005
}

class CardPool:
    _cards: dict[str, Card] = {}
    _tag_cards: dict[str, Card] = {}
    _available_cards: dict[str, list[Card]] = {
        category: [] for category in DROP_RATES
    }

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
            raise DuplicatedCardError(f"Card {card.id} in {tier} already added into the pool.")
        
        cls._cards[card.id] = card
        if not card.owner_id:
            cls.add_available_card(card)
        
        if card.tag:
            cls.add_tag(card, card.tag)

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
        sorted_ranks = sorted(RANK_BASE.items(), key=lambda item: item[1][1], reverse=True)
        for rank, (emoji_id, rank_value, _) in sorted_ranks:
            if points >= rank_value:
                return (rank, emoji_id)
        return None
    
    @classmethod
    def get_question_distribution_by_rank(cls, rank: str) -> list[tuple[str, int]]:
        rank_details = RANK_BASE.get(rank)
        if not rank_details:
            raise Exception(f"Rank '{rank}' not found!")
        
        return rank_details[2]

    @classmethod
    def get_question(cls, rank: str, number: int) -> list[Question]:
        if rank not in QUIZ_LEVEL_BASE.keys():
            raise Exception(f"{rank} is not found in the quiz!")
        
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
                raise Exception(f"{rank_name} is not found in the quiz!")
            
            for question in cls.get_question(rank_name, return_num):
                questions.append(question)
        
        return questions