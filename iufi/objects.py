from __future__ import annotations

import random, os, asyncio, Levenshtein, re, discord
import functions as func

from PIL import Image, ImageDraw, ImageSequence
from io import BytesIO
from difflib import SequenceMatcher
from typing import (
    Optional,
    Union,
    List,
    TYPE_CHECKING
)

from .exceptions import ImageLoadError, IUFIException

if TYPE_CHECKING:
    from .pool import CardPool

YOUTUBE_REGEX = re.compile(r'(https?://)?(www\.)?youtube\.(com|nl)/watch\?v=([-\w]+)')
CARD_SIZE = (1080, 1920)
SIZE_RATE = 0.2
FRAME_SIZE_INCREMENT = (0.005, 0.003)

QUIZ_LEVEL_BASE: dict[str, tuple[int, tuple[int, int, hex]]] = {
    "easy": (10, (1, 1, 0x7CD74B)),
    "medium": (20, (3, 2, 0xF9E853)),
    "hard": (30, (5, 3, 0xD75C4B))
}

class CardObject:
    __slots__ = ("_image")

    def __init__(self) -> None:
        self._image: list[Image.Image] | Image.Image = None

    @classmethod
    def _round_corners(cls, image: Image.Image, radius: int = 8) -> Image.Image:
        """Creates a rounded corner image"""
        radius = min(image.size) * radius // 100
        mask = Image.new('L', image.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.pieslice([(0, 0), (radius * 2, radius * 2)], 180, 270, fill=255)
        draw.rectangle([(radius, 0), (image.size[0] - radius, image.size[1])], fill=255)
        draw.rectangle([(0, radius), (image.size[0], image.size[1] - radius)], fill=255)
        draw.pieslice([(image.size[0] - radius * 2, 0), (image.size[0], radius * 2)], 270, 360, fill=255)
        draw.pieslice([(0, image.size[1] - radius * 2), (radius * 2, image.size[1])], 90, 180, fill=255)
        draw.pieslice([(image.size[0] - radius * 2, image.size[1] - radius * 2), (image.size[0], image.size[1])], 0, 90, fill=255)

        # Apply the mask to the image
        output = Image.new('RGBA', image.size)
        output.putalpha(mask)
        output.paste(image, (0, 0), mask)

        return output
    
    @classmethod
    def _load_frame(cls, image: Image.Image, frame: str, *, size_rate: float = SIZE_RATE) -> Image.Image:
        try:
            new_size_rate = size_rate - (FRAME_SIZE_INCREMENT[0] if frame else FRAME_SIZE_INCREMENT[1])
            img_size = (int(CARD_SIZE[0] * new_size_rate), int(CARD_SIZE[1] * new_size_rate))
            
            with Image.open(os.path.join(func.ROOT_DIR, "frames", f"{frame}.webp")) as frame_img:
                size = (int(CARD_SIZE[0] * size_rate), int(CARD_SIZE[1] * size_rate))
                frame_img = frame_img.resize(size, Image.LANCZOS)
                
                result = Image.new('RGBA', size)
                image = cls._round_corners(image.resize(img_size, Image.LANCZOS))
                result.paste(image, ((size[0] - img_size[0]) // 2, (size[1] - img_size[1]) // 2))
                result.paste(frame_img, (0, 0), frame_img)
                return result
                
        except FileNotFoundError:
            return cls._round_corners(image.resize(img_size, Image.LANCZOS))
        
    @classmethod
    def _load_image(cls, image_path: str, *, card_frame: str = None, size_rate: float = SIZE_RATE) -> Union[list[Image.Image], Image.Image]:
        """Load and process the image"""
        try:
            with Image.open(image_path) as img:
                if card_frame:
                    images = [cls._load_frame(frame.convert('RGBA'), card_frame, size_rate=size_rate) for frame in ImageSequence.Iterator(img)]
                
                else:
                    img_size = (int(CARD_SIZE[0] * size_rate), int(CARD_SIZE[1] * size_rate))
                    images = [cls._round_corners(frame.resize(img_size)) for frame in ImageSequence.Iterator(img)]

                if len(images) > 1:
                    return images
                return images[0]
                    
        except Exception as e:
            raise ImageLoadError(f"Unable to load the image. Reason: {e}")
        
class Card(CardObject):
    __slots__ = (
        "id",
        "tier",
        "category"
    )

    def __init__(
        self,
        id: str,
        tier: str,
        category: str,
    ):  
        self.id: str = id
        self._tier: str = tier
        self._category: str = category

        self._image: list[Image.Image] | Image.Image = None
        self._emoji: str = func.settings.TIERS_BASE.get(self._tier)[0]

    def image_bytes(self) -> BytesIO:
        image_bytes = BytesIO()

        if self.is_gif:
            self.image[0].save(image_bytes, format="GIF", save_all=True, append_images=self.image[1:], loop=0)
        else:
            self.image.save(image_bytes, format='WEBP')
        image_bytes.seek(0)

        return image_bytes
    
    @property
    def is_gif(self) -> bool:
        return isinstance(self.image, list)
    
    @property
    def image_path(self) -> str:
        return os.path.join(func.ROOT_DIR, "images", self._tier, self.id)
    
    @property
    def image(self) -> list[Image.Image] | Image.Image:
        if not self._image:
            self._image = self._load_image(self.image_path, card_frame=self._tier)
        return self._image
    
    @property
    def tier(self) -> Optional[tuple[str, str]]:
        """Return a tuple (emoji, name)"""
        return self._emoji, self._tier
    
    @property
    def category(self) -> str:
        return self._category
    
    @property
    def format(self) -> str:
        return "gif" if self.is_gif else "webp"
    
class DuplicateCard(CardObject):
    __slots__ = (
        "id",
        "_origin",
        "owner_id",
        "stars",
        "tag"
    )

    def __init__(
        self,
        pool: CardPool,
        id: str,
        origin_card_id: str,
        owner_id: int,
        stars: int,
        tag: int,
        frame: str
    ):  
        self.id: str = id
        self._pool: CardPool = pool
        self._origin_card: Card = None
        self.owner_id: int = owner_id
        self.stars: int = stars
        self.tag: str = tag
        self._frame: str = frame

    def preview_frame(self, frame: str = None) -> BytesIO:
        try:
            image_bytes = BytesIO()
            image = CardObject._load_image(self._origin_card.image_path, card_frame=frame)
            image.save(image_bytes, format='WEBP')
            image_bytes.seek(0)
            return image_bytes
        
        except Exception as e:
            raise ImageLoadError(f"Unable to load the image. Reason: {e}")
        
    def change_owner(self, owner_id: int | None = None) -> None:
        if owner_id is None:
            self._pool._duplicated_cards.pop(self.id, None)
            return

        if self.owner_id != owner_id:
            self.owner_id = owner_id

    def change_tag(self, tag: str | None = None) -> None:
        if self.tag in self._pool._tagged_duplicated_cards:
            self._pool._tagged_duplicated_cards.pop(self.tag, None)

        if tag is None:
            return

        self._pool._tagged_duplicated_cards[tag.lower()] = self
        
    def change_frame(self, frame: str | None = None) -> None:
        if self._frame == frame:
            raise IUFIException("This frame is already assigned to this card.")
        
        self._frame = frame.lower() if frame else None
        self._image = None

    def change_stars(self, stars: int) -> None:
        if self.stars != stars:
            self.stars = stars

    @property
    def cost(self) -> int:
        price = func.settings.TIERS_BASE.get(self._tier)[1]
        if self.stars > 5:
            price *= 1 + ((self.stars - 5) * .25)

        return round(price)

    @property
    def frame(self) -> tuple[str, str]:
        return func.settings.FRAMES_BASE.get(self._frame)[0], self._frame
    
    @property
    def display_id(self) -> str:
        return f"🆔 {self.id.zfill(5)}"
    
    @property
    def display_stars(self) -> str:
        return ("⭐ " if self.stars < 5 else "🌟 ") + str(self.stars)

    @property
    def display_tag(self) -> str:
        return f"🏷️ {self.tag if self.tag else '-':<11}"

    @property
    def display_frame(self) -> str:
        return f"🖼️ {func.settings.FRAMES_BASE.get(self._frame)[0] if self._frame else '- '}"

    def __str__(self) -> str:
        return f"{self._origin_card._emoji} {self.id.zfill(5)} " + (f"({self.tag})" if self.tag else "")

class Question:
    def __init__(
        self,
        _id: int,
        question: str,
        answers: list[str],
        num_correct: int = 0,
        num_wrong: int = 0,
        average_time: float = 0.0,
        attachment: str = None,
        records: dict | None = None,
        tips: str = "",
        default_level: str = None
    ):
        self.id = _id
        self.question: str = question
        self.answers: list[str] = answers
        self.attachment: str | None = attachment
        self.tips: str = tips

        self._correct: int = num_correct
        self._wrong: int = num_wrong
        self._average_time: float = average_time
        self._default_level: str = default_level
        self._records: dict | None = records if records else {}

        self.is_updated: bool = False

    def check_answer(self, answer: str, threshold: float = .75) -> bool:
        answer = answer.lower()
        is_number_or_date = self.is_number_or_date(answer)
        for model_answer in self.answers:

            model_answer = model_answer.lower()

            if is_number_or_date:
                if model_answer == answer:
                    return True
                continue

            string1 = set(model_answer.split())
            string2 = set(answer.split())
            jac_similarity = len(string1 & string2) / len(string1 | string2)

            string1 = model_answer.replace(" ", "")
            string2 = answer.replace(" ", "")
            lev_similarity = Levenshtein.ratio(string1, string2)
            seq_similarity = SequenceMatcher(None, string1, string2).ratio()

            if lev_similarity >= threshold or jac_similarity >= threshold or seq_similarity >= threshold:
                return True
        return False

    def is_number_or_date(self, answer: str) -> bool:
        return answer.replace(" ", "").replace("/", "").replace(".", "").replace("-", "").isdigit()

    def update_average_time(self, time: float) -> None:
        if not self.is_updated:
            self.is_updated = True

        if self.total >= 0:
            self._average_time += time
        else:
            self._average_time = ((self._average_time * self.total) + time) / (self.total + 1)

    def update_user(self, user_id: int, answer: str, response_time: float, is_correct: bool = None) -> None:
        if not self.is_updated:
            self.is_updated = True

        user_id = str(user_id)
        if user_id not in self._records:
            self._records[user_id] = {
                "answers": []
            }

        user_record = self._records[user_id]
        if answer not in user_record["answers"]:
            user_record["answers"].append(answer)

        if is_correct:
            user_record["fastest_response_time"] = min(user_record.get("fastest_response_time", float("inf")), round(response_time, 1))

    def best_record(self) -> tuple[str, float] | None:
        sorted_records = sorted((item for item in self._records.items() if item[1].get("fastest_response_time")), key=lambda item: item[1]["fastest_response_time"])

        # Return the user ID and fastest_response_time of the first record
        return (sorted_records[0][0], sorted_records[0][1]["fastest_response_time"]) if sorted_records else None
    
    def toDict(self) -> dict:
        if self.is_updated:
            self.is_updated = False

        return {
            "question": self.question,
            "answers": self.answers,
            "num_correct": self._correct,
            "num_wrong": self._wrong,
            "average_time": self.average_time,
            "attachment": self.attachment,
            "records": self._records,
            "default_level": self._default_level
        }
    
    @property
    def level(self) -> str:
        if self._default_level:
            return self._default_level
        
        if self.correct_rate >= 85 or self._wrong == 0:
            return "easy"
        elif self.correct_rate >= 40:
            return "medium"
        else:
            return "hard"

    @property
    def average_time(self) -> float:
        base_time = QUIZ_LEVEL_BASE.get(self.level)[0]

        if not self._average_time:
            return base_time
        
        return round((self._average_time + base_time) / 2, 1)

    @property
    def total(self) -> int:
        return self._correct + self._wrong
    
    @property
    def correct_rate(self) -> float:
        total = self.total
        if not total:
            return 0
        return round(self._correct / total, 2) * 100
    
    @property
    def wrong_rate(self) -> float:
        if self._wrong == 0:
            return 0
        
        return 100 - self.correct_rate

class Track:
    """The base track object. Returns critical track information needed for parsing by Lavalink.
       You can also pass in commands.Context to get a discord.py Context object in your track.
    """

    def __init__(
        self,
        *,
        track_id: str = None,
        info: dict,
        search_type: str = "ytsearch",
    ):
        self.track_id: str = track_id
        self.info: dict = info

        self.identifier: str = info.get("identifier")
        self.title: str = info.get("title", "Unknown")
        self.author: str = info.get("author", "Unknown")
        self.uri: str = info.get("uri", "https://discord.com/application-directory/605618911471468554")
        self.source: str = info.get("sourceName", "youtube")

        self.original: Optional[Track] = self
        self._search_type: str = search_type

        self.thumbnail: str = info.get("artworkUrl")
        if not self.thumbnail and YOUTUBE_REGEX.match(self.uri):
            self.thumbnail = f"https://img.youtube.com/vi/{self.identifier}/maxresdefault.jpg"
        
        self.length: float = 3000 if self.source == "soundcloud" and "/preview/" in self.identifier else info.get("length")
        self.is_stream: bool = info.get("isStream", False)
        self.is_seekable: bool = info.get("isSeekable", True)
        self.position: int = info.get("position", 0)

        self.db_data: Optional[dict] = None
        self.is_updated: bool = False

    def check_answer(self, answer: str, threshold: float = .75) -> bool:
        answer = answer.lower()
        title = re.sub(r"\(.*?\)|\[.*?\]", "", self.title.lower())

        string1 = set(title.split())
        string2 = set(answer.split())
        jac_similarity = len(string1 & string2) / len(string1 | string2)

        string1 = title.replace(" ", "")
        string2 = answer.replace(" ", "")
        lev_similarity = Levenshtein.ratio(string1, string2)
        seq_similarity = SequenceMatcher(None, string1, string2).ratio()

        if lev_similarity >= threshold or jac_similarity >= threshold or seq_similarity >= threshold:
            return True
        return False 
    
    def update_state(self, member: discord.Member, time_used: float, result: bool) -> None:
        self.is_updated = True

        if self.total >= 0:
            self.db_data["average_time"] += time_used
        else:
            self.db_data["average_time"] = ((self.db_data["average_time"] * self.total) + time_used) / (self.total + 1)

        current_best_time = self.db_data["best_record"]["time"]
        if result and (current_best_time is None or current_best_time > time_used):
            self.db_data["best_record"]["member"] = member.id
            self.db_data["best_record"]["time"] = time_used

        key = "correct" if result else "wrong"
        self.db_data[key] = self.db_data.get(key, 0) + 1
    
    @property
    def total(self) -> int:
        return self.db_data["correct"] + self.db_data["wrong"]
    
    @property
    def average_time(self) -> float:
        return self.db_data["average_time"]
    
    @property
    def correct_rate(self) -> float:
        total = self.total
        if not total:
            return 0
        return round(self.db_data["correct"] / total, 2) * 100
    
    @property
    def wrong_rate(self) -> float:
        return 100 - self.correct_rate

    @property
    def best_record(self) -> tuple[int, float]:
        br = self.db_data["best_record"]
        return br["member"], br["time"]
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, Track):
            return False

        return other.track_id == self.track_id

    def __str__(self) -> str:
        return self.title

    def __repr__(self) -> str:
        return f"<IUFI.track title={self.title!r} uri=<{self.uri!r}> length={self.length}>"

class Playlist:
    """The base playlist object.
       Returns critical playlist information needed for parsing by Lavalink.
       You can also pass in commands.Context to get a discord.py Context object in your tracks.
    """

    def __init__(
        self,
        *,
        playlist_info: dict,
        tracks: list,
    ):
        self.playlist_info = playlist_info
        self.name = playlist_info.get("name")        
        self.tracks = [
            Track(track_id=track["encoded"], info=track["info"])
            for track in tracks
        ]

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<Voicelink.playlist name={self.name!r} track_count={len(self.tracks)}>"