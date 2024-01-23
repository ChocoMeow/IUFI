from __future__ import annotations

import random, os, asyncio, Levenshtein
import functions as func

from PIL import Image, ImageDraw, ImageSequence
from io import BytesIO
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

from .exceptions import ImageLoadError, IUFIException

if TYPE_CHECKING:
    from .pool import CardPool

TIERS_BASE: dict[str, tuple[str, int]] = {
    "common": ("🥬", 1),
    "rare": ("🌸", 10),
    "epic": ("💎", 40),
    "legendary": ("👑", 100),
    "mystic": ("🦄", 500),
    "celestial": ("💫", 1000)
}

FRAMES_BASE: dict[str, tuple[str, str]] = {
    "hearts": ("💕", 20),
    "celebrity": ("🌟", 20),
    "uaena": ("💌", 40),
    "dandelions": ("🌷", 40),
    "shine": ("✨", 60),
    "lovepoem": ("💠", 60),
    "cheer": ("🎤", 60),
    "smoon": ("🍓", 60),
    "signed": ("✍️", 60),
    "lilac": ("💐", 60),
    "palette": ("🎨", 60),
    "starfish": ("🍥", 60),
    "cactus": ("🌵", 60)
}

POTIONS_BASE: dict[str, str | dict[str, float]] = {
    "speed": {
        "emoji": "⚡",
        "expiration": 1800,
        "levels": {
            "i": .3,
            "ii": .5,
            "iii": .7
        }
    },
    "luck": {
        "emoji": "🍀",
        "expiration": 900,
        "levels": {
            "i": 3,
            "ii": 4,
            "iii": 6
        }
    }
}

QUIZ_LEVEL_BASE: dict[str, tuple[int, tuple[int, int, hex]]] = {
    "easy": (10, (1, 1, 0x7CD74B)),
    "medium": (20, (3, 2, 0xF9E853)),
    "hard": (30, (5, 3, 0xD75C4B))
}

RANK_BASE: dict[str, tuple[str, int, list[tuple[str, int]]]] = {
    "Milk": ("1173065442009555096", 0, [('easy', 5)]),
    "Bronze": ("1173063915098345472", 10, [('easy', 4), ('medium', 1)]),
    "Silver": ("1173063924116095087", 25, [('easy', 3), ('medium', 2)]),
    "Gold": ("1173063917614927975", 60, [('easy', 2), ('medium', 3)]),
    "Platinum": ("1173063922564218961", 100, [('easy', 1), ('medium', 4)]),
    "Diamond": ("1173064418075099167", 200, [('medium', 5)]),
    "Master": ("1173063919846293535", 350, [('medium', 3), ('hard', 2)]),
    "Challenger": ("1173064415453663242", 500, [('medium', 2), ('hard', 3)]),
}

class CardObject:
    __slots__ = ("_image")

    def __init__(self) -> None:
        self._image: list[Image.Image] | Image.Image = None

    def _round_corners(self, image: Image.Image, radius: int = 10) -> Image.Image:
        """Creates a rounded corner image"""
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
    
    def _load_image(self, path: str) -> None:
        """Load and process the image"""
        try:
            with Image.open(path) as img:
                size = (200, 355)
                process_frame = self._round_corners

                if img.format == "GIF":
                    self._image = [process_frame(frame.resize(size)) for frame in ImageSequence.Iterator(img)]
                else:
                    self._image = process_frame(img.resize(size, Image.LANCZOS))

        except Exception as e:
            raise ImageLoadError(f"Unable to load the image. Reason: {e}")

class Card(CardObject):
    __slots__ = (
        "id",
        "_tier",
        "_pool",
        "owner_id",
        "stars",
        "tag",
        "_frame",
        "_image",
        "_emoji"
    )

    def __init__(
        self,
        pool: CardPool,
        id: str,
        tier: str,
        owner_id: int = None,
        stars: int = None,
        tag: str = None,
        frame: str = None,
    ):  
        self.id: str = id
        self._tier: str = tier
        self._pool: CardPool = pool

        self.owner_id: int = owner_id
        self.stars: int = stars if stars else 0
        self.tag: str = tag
        self._frame: str = frame

        self._image: list[Image.Image] | Image.Image = None
        self._emoji: str = TIERS_BASE.get(self._tier)[0]
    
    def _load_frame(self, image: Image.Image, frame: str = None) -> Image.Image:
        with Image.open(os.path.join(func.ROOT_DIR, "frames", f"{frame if frame else self._frame}.png")).convert("RGBA").resize((200, 355)) as img:
            image = self._round_corners(image)
            output = Image.new("RGBA", img.size)
            output.paste(image, (6, 8))
            output.paste(img, (0, 0), mask=img)

            return output

    def _load_image(self) -> None:
        """Load and process the image"""
        try:
            image_path = os.path.join(func.ROOT_DIR, "images", self._tier)
            image_file = f"{self.id}.gif" if self._tier == "celestial" else f"{self.id}.jpg"
            size = (190, 338) if self._frame else (200, 355)

            with Image.open(os.path.join(image_path, image_file)) as img:
                process_frame = self._load_frame if self._frame else self._round_corners

                if img.format != "GIF":
                    self._image = process_frame(img.resize(size, Image.LANCZOS))
                else:
                    self._image = [process_frame(frame.resize(size)).convert('RGB') for frame in ImageSequence.Iterator(img)]

        except Exception as e:
            raise ImageLoadError(f"Unable to load the image. Reason: {e}")

    def preview_frame(self, frame: str = None) -> BytesIO:
        try:
            image_path = os.path.join(func.ROOT_DIR, "images", self._tier)
            image_file = f"{self.id}.gif" if self._tier == "celestial" else f"{self.id}.jpg"
            size = (190, 338) if frame else (200, 355)

            image_bytes = BytesIO()

            with Image.open(os.path.join(image_path, image_file)) as img:
                if frame:
                    image = self._load_frame(img.resize(size, Image.LANCZOS), frame)
                else:
                    image = self._round_corners(img.resize(size, Image.LANCZOS))
                    
                image.save(image_bytes, format='PNG')
                image_bytes.seek(0)
                return image_bytes
        
        except Exception as e:
            raise ImageLoadError(f"Unable to load the image. Reason: {e}")
        
    def change_owner(self, owner_id: int | None = None) -> None:
        if self.owner_id != owner_id:
            self.owner_id = owner_id

            if owner_id is None:
                if self.stars > 5:
                    self.change_stars(random.randint(1, 5))

                if self.tag and self.tag.lower() in self._pool._tag_cards:
                    self._pool._tag_cards.pop(self.tag.lower())
                self.tag = None

                self._frame, self._image = None, None

    def change_tag(self, tag: str | None = None) -> None:
        if self.tag == tag:
            return
        
        self.tag = tag
        asyncio.create_task(func.update_card(self.id, {"$set": {"tag": tag}}))
    
    def change_frame(self, frame: str | None = None) -> None:
        if self._frame == frame:
            raise IUFIException("This frame is already assigned to this card.")
        
        self._frame = frame.lower() if frame else None

        if self.image:
            self._load_image()

    def change_stars(self, stars: int) -> None:
        if self.stars != stars:
            self.stars = stars

            asyncio.create_task(func.update_card(self.id, {"$set": {"stars": stars}}))

    def image_bytes(self) -> BytesIO:
        image_bytes = BytesIO()

        if self.is_gif:
            self.image[0].save(image_bytes, format="GIF", save_all=True, append_images=self.image[1:], loop=0)
        else:
            self.image.save(image_bytes, format='PNG')
        image_bytes.seek(0)

        return image_bytes
    
    @property
    def cost(self) -> int:
        price = TIERS_BASE.get(self._tier)[1]
        if self.stars > 5:
            price *= 1 + ((self.stars - 5) * .25)

        return round(price)
    
    @property
    def tier(self) -> tuple[str, str]:
        """Return a tuple (emoji, name)"""
        return self._emoji, self._tier

    @property
    def frame(self) -> tuple[str, str]:
        return FRAMES_BASE.get(self._frame)[0], self._frame
    
    @property
    def image(self) -> list[Image.Image] | Image.Image:
        """Return the image"""
        if self._image is None:
            self._load_image()
        return self._image

    @property
    def is_gif(self) -> bool:
        return isinstance(self.image, list)

    @property
    def format(self) -> str:
        return "gif" if self.is_gif else "png"
    
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
        return f"🖼️ {FRAMES_BASE.get(self._frame)[0] if self._frame else '- '}"

    def __str__(self) -> str:
        return f"{self._emoji} {self.id.zfill(5)}"

class TempCard(CardObject):
    def __init__(self, path: str) -> None:
        super().__init__()

        self._path = path

    @property
    def image(self) -> list[Image.Image] | Image.Image:
        """Return the image"""
        if self._image is None:
            self._load_image(self._path)
        return self._image

    @property
    def is_gif(self) -> bool:
        return isinstance(self.image, list)

class Question:
    def __init__(
        self,
        question: str,
        answers: list[str],
        num_correct: int = 0,
        num_wrong: int = 0,
        average_time: float = 0.0,
        attachment: str = None,
        default_level: str = None
    ):
        self.question: str = question
        self.answers: list[str] = answers
        self.attachment: str | None = attachment

        self._correct: int = num_correct
        self._wrong: int = num_wrong
        self._average_time: float = average_time
        self._default_level: str = default_level

        self.is_updated: bool = False

    def check_answer(self, answer: str, threshold: float = .75) -> bool:
        answer = answer.lower()
        for model_answer in self.answers:

            model_answer = model_answer.lower()

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

    def update_average_time(self, time: float) -> None:
        if not self.is_updated:
            self.is_updated = True

        if self.total >= 0:
            self._average_time += time
        else:
            self._average_time = ((self._average_time * self.total) + time) / (self.total + 1)

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