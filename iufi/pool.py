from __future__ import annotations

import os
import functions as func

from collections import Counter
from random import randint

from typing import (
    Optional,
    TYPE_CHECKING,
    Dict,
    Any,
    List
)

from random import (
    choice,
    choices,
    sample,
    shuffle
)

from .objects import (
    Card,
    Question,
    QUIZ_LEVEL_BASE,
    Track
)

from .exceptions import IUFIException, DuplicatedCardError, DuplicatedTagError
# from .deepsearch import (
#     Load_Data,
#     Search_Setup
# )

if TYPE_CHECKING:
    from .music import Player

DROP_RATES = {
    'common': .93,
    'rare': .05,
    'epic': .003,
    'legendary': .0008,
    'mystic': .0001,
    "celestial": .00005
}

class CardPool:
    _cards: dict[str, Card] = {}
    _tag_cards: dict[str, Card] = {}
    _available_cards: dict[str, List[Card]] = {
        category: [] for category in DROP_RATES
    }
    _match_game_cards: List[Card] = []

    #DeepSearch
    # search_image: Search_Setup | None = None

    # @classmethod
    # def load_search_metadata(cls) -> None:
    #     image_list = Load_Data().from_folder(["/metadata-files"])
    #     cls.search_image = Search_Setup(image_list=image_list)
    #     cls.search_image.run_index()

    @classmethod
    async def fetch_data(cls) -> None:
        # Fetch all card data from the database
        all_card_data: Dict[str, Any] = {doc["_id"]: doc async for doc in func.CARDS_DB.find()}

        # Process existing cards in the cards folder
        for category in os.listdir(func.CARDS_FOLDER):
            if category.startswith("."):
                continue

            for image in os.listdir(os.path.join(func.CARDS_FOLDER, category)):
                if image.startswith("."):
                    continue

                card_id = os.path.splitext(image)[0]
                card_data = all_card_data.get(card_id, {"_id": card_id})

                # Initialize stars if not present
                if "stars" not in card_data:
                    card_data["stars"] = (stars := randint(1, 5))
                    await func.update_card(card_id, {"$set": {"stars": stars}})
                cls.add_card(tier=category, **card_data)

    @classmethod
    async def process_new_cards(cls) -> None:
        # Process new images in the new cards folder
        new_images_dir = os.listdir(func.NEW_CARDS_FOLDER)
        if not new_images_dir:
            return
        
        available_ids = [str(index) for index in range(1, len(cls._cards) + len(new_images_dir) + 1000) if str(index) not in cls._cards]
        for new_image in new_images_dir:
            for category in os.listdir(func.CARDS_FOLDER):
                if not new_image.startswith(category):
                    continue

                # Get the next available ID
                card_id = available_ids.pop(0)

                # Move the new image to the cards folder with a new ID
                new_image_path = os.path.join(func.NEW_CARDS_FOLDER, new_image)
                target_image_path = os.path.join(func.CARDS_FOLDER, category, f"{card_id}.webp")
                os.rename(new_image_path, target_image_path)

                # Set initial stars for the new card
                await func.update_card(card_id, {"$set": {"stars": (stars := randint(1, 5))}}, insert=True)
                cls.add_card(_id=card_id, tier=category, stars=stars)

                func.logger.info(f"Added New Image {new_image}({category}) -> ID: {card_id}")

    @classmethod
    async def refresh(cls, process_new_cards: bool = False) -> None:
        cls._cards.clear()
        cls._tag_cards.clear()
        cls._available_cards.clear()
        cls._match_game_cards.clear()
        await cls.fetch_data()

        if process_new_cards:
            await cls.process_new_cards()

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

        if card.tier[1] != "celestial":
            cls._match_game_cards.append(card)

        return card
    
    @classmethod
    def get_card(cls, card_id: str) -> Card | None:
        if not card_id:
            return
        print(card_id)
        card_id = card_id.lstrip("0")
        card = cls._cards.get(card_id)
        if not card:
            card = cls._tag_cards.get(card_id.lower())
        return card
    
    @classmethod
    def roll(cls, amount: int = 3, *, included: List[str] = None, avoid: List[str] = None, luck_rates: float = None) -> List[Card]:
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
    def get_random_cards_for_match_game(cls, amount: int = 3) -> List[Card]:
        cards = sample(cls._match_game_cards,amount)
        return cards

class QuestionPool:
    _questions: List[Question] = []

    @classmethod
    async def fetch_data(cls) -> None:
        async for question_doc in func.QUESTIONS_DB.find():
            cls.add_question(Question(**question_doc))

    @classmethod
    async def refresh(cls) -> None:
        cls._questions.clear()
        await cls.fetch_data()
        
    @classmethod
    def add_question(cls, question: Question) -> None:
        if not question.attachment:
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
    def get_question_distribution_by_rank(cls, rank: str) -> List[tuple[str, int]]:
        rank_details = func.settings.RANK_BASE.get(rank)
        if not rank_details:
            raise IUFIException(f"Rank '{rank}' not found!")
        
        return rank_details["questions"]

    @classmethod
    def get_question(cls, rank: str, number: int) -> List[Question]:
        if rank not in QUIZ_LEVEL_BASE.keys():
            raise IUFIException(f"{rank} is not found in the quiz!")
        
        questions: dict[str, List[Question]] = {
            level: [q for q in cls._questions if q.level == level]
            for level in QUIZ_LEVEL_BASE.keys()
        }

        num_available = len(questions[rank])
        num_to_return = min(number, num_available)

        return sample(questions[rank], k=num_to_return)
    
    @classmethod
    def get_question_by_rank(cls, ranks: List[tuple[str, int]]) -> List[Question]:
        questions: List[Question] = []
        
        for (rank_name, return_num) in ranks:
            if rank_name not in QUIZ_LEVEL_BASE.keys():
                raise IUFIException(f"{rank_name} is not found in the quiz!")
            
            for question in cls.get_question(rank_name, return_num):
                questions.append(question)
        
        return questions

class MusicPool:
    _voice_clients: Dict[int, Player] = {}
    _questions: Dict[str, Track] = {}

    @classmethod
    def get_player(cls, guild_id: int) -> Optional[Player]:
        player = cls._voice_clients.get(guild_id)
        if player and not player.voice_client:
            del cls._voice_clients[guild_id]
        
        return cls._voice_clients.get(guild_id)
    
    @classmethod
    async def add_player(cls, guild_id: int, player: Player) -> None:
        existing_player = cls.get_player(guild_id=guild_id)
        if existing_player:
            await existing_player.disconnect()
        
        if player is not None:
            cls._voice_clients[guild_id] = player
        
    @classmethod
    async def add_question(cls, data: Dict[str, Any]) -> None:
        # Create track instance and update questions dictionary
        cls._questions[data["_id"]] = Track(data=data)

    @classmethod
    async def get_question(cls, id: str) -> Track:
        if not cls._questions:
            await cls.fetch_data()

        return cls._questions.get(id)

    @classmethod
    async def get_all_questions(cls) -> List[Track]:
        if not cls._questions:
            await cls.fetch_data()

        return list(cls._questions.values())
    
    @classmethod
    async def get_random_question(cls, history: List[str]) -> Optional[Track]:
        if not cls._questions:
            await cls.fetch_data()

        # Filter the questions to exclude those in the history
        available_questions = [track for id, track in cls._questions.items() if id not in history]

        if not available_questions:
            return None

        return choice(available_questions)

    @classmethod
    async def fetch_data(cls) -> None:
        async for music_quiz in func.MUSIC_DB.find():
            await cls.add_question(music_quiz)
    
    @classmethod
    async def save(cls) -> None:
        if not cls._questions:
            return
        
        for track in cls._questions.values():
            if track.is_updated:
                await func.MUSIC_DB.update_one({"_id": track.id}, {"$set": track.data})
                track.is_updated = False

    @classmethod
    async def reset(cls) -> None:
        await func.MUSIC_DB.update_many({}, {"$set": {
            "correct": 0,
            "wrong": 0,
            "average_time": 0,
            "likes": 0,
            "best_record": {
                "member": None,
                "time": 0
            }
        }})
        cls._questions.clear()

    @classmethod
    async def refresh(cls) -> None:
        await cls.save()
        cls._questions.clear()