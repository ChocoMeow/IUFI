from __future__ import annotations

import random, os, asyncio, Levenshtein, re, yt_dlp
import functions as func

from PIL import Image, ImageDraw, ImageSequence
from io import BytesIO
from difflib import SequenceMatcher

from discord import (
    FFmpegPCMAudio,
    Member
)

from typing import (
    Optional,
    Union,
    List,
    TYPE_CHECKING,
    Dict,
    Any
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

YTDL_FORMAT_OPTIONS: Dict[str, str] = {
    'format': 'bestaudio/best',
    'outtmpl': os.path.join(func.MUSIC_TRACKS_FOLDER, '%(id)s.%(ext)s'),
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

YTDL = yt_dlp.YoutubeDL(YTDL_FORMAT_OPTIONS)

class CardObject:
    __slots__ = ("is_gif")

    def __init__(self) -> None:
        self.is_gif: bool = False;
    
    def _round_corners(self, image: Image.Image, radius: int = 8) -> Image.Image:
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
    
    def _load_image(self, path: str, *, size_rate: float = SIZE_RATE) -> Union[List[Image.Image], Image.Image]:
        """Load and process the image"""
        try:
            with Image.open(path) as img:
                img_size = (int(CARD_SIZE[0] * size_rate), int(CARD_SIZE[1] * size_rate))
                images = [self._round_corners(frame.resize(img_size)) for frame in ImageSequence.Iterator(img)]
                self.is_gif = len(images) > 1
                return images if len(images) > 1 else images[0]
            
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
        "_emoji",
        "is_gif",
        "last_trade_time",
        "_lock"
    )

    _frame_cache: Dict[str, Dict[str, Union[List[Image.Image], Image.Image]]] = {}  # Path to Frame

    def __init__(
        self,
        pool: CardPool,
        id: str,
        tier: str,
        owner_id: int = None,
        stars: int = None,
        tag: str = None,
        frame: str = None,
        last_trade_time: float = None
    ):  
        self.id: str = id
        self._tier: str = tier
        self._frame: str = frame
        self._pool: CardPool = pool

        self.owner_id: int = owner_id
        self.stars: int = stars if stars else 0
        self.tag: str = tag
        self.is_gif: bool = False
        self.last_trade_time = last_trade_time or 0

        self._emoji: str = func.settings.TIERS_BASE.get(self._tier)[0]
        self._lock: asyncio.Lock = asyncio.Lock()

    def _load_frame(self, image: Image.Image, frame: str = None, *, size_rate: float = SIZE_RATE) -> Image.Image:
        try:
            frame = frame or self._frame or self._tier
            new_size_rate = size_rate - (FRAME_SIZE_INCREMENT[0] if frame else FRAME_SIZE_INCREMENT[1])
            img_size = (int(CARD_SIZE[0] * new_size_rate), int(CARD_SIZE[1] * new_size_rate))
            frame_size = (int(CARD_SIZE[0] * size_rate), int(CARD_SIZE[1] * size_rate))

            # Check if the frame is in cache
            frame_cache = Card._frame_cache.setdefault(str(size_rate), {})

            if frame not in frame_cache:
                with Image.open(os.path.join(func.ROOT_DIR, "frames", f"{frame}.webp")) as frame_img:

                    # Resize and cache the frame image
                    frame_cache[frame] = frame_img.resize(frame_size, Image.LANCZOS)

            # Get the cached frame image
            frame_img = frame_cache[frame]

            # Create the final image with rounded corners and frame
            result = Image.new('RGBA', frame_size)
            image = self._round_corners(image.resize(img_size, Image.LANCZOS))
            result.paste(image, ((frame_size[0] - img_size[0]) // 2, (frame_size[1] - img_size[1]) // 2))
            result.paste(frame_img, (0, 0), frame_img)
            return result
        
        except FileNotFoundError:
            return self._round_corners(image.resize(img_size, Image.LANCZOS))

    def _load_image(self, *, size_rate: float = SIZE_RATE) -> Union[list[Image.Image], Image.Image]:
        """Load and process the image"""
        try:
            image_path = os.path.join(func.ROOT_DIR, "images", self._tier)

            with Image.open(os.path.join(image_path, f"{self.id}.webp")) as img:
                images = [self._load_frame(frame.convert('RGBA'), size_rate=size_rate) for frame in ImageSequence.Iterator(img)]
                self.is_gif = len(images) > 1
                return images if len(images) > 1 else images[0]
                    
        except Exception as e:
            raise ImageLoadError(f"Unable to load the image. Reason: {e}")

    def preview_frame(self, frame: str = None) -> BytesIO:
        try:
            image_path = os.path.join(func.ROOT_DIR, "images", self._tier)

            image_bytes = BytesIO()
            with Image.open(os.path.join(image_path, f"{self.id}.webp")) as img:
                if frame:
                    image = self._load_frame(img.resize(CARD_SIZE, Image.LANCZOS), frame)
                else:
                    image = self._round_corners(img.resize(CARD_SIZE, Image.LANCZOS))
                    
                image.save(image_bytes, format='WEBP')
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
                
                self.tag, self._frame, self.last_trade_time = None, None, 0

    def change_tag(self, tag: str | None = None) -> None:
        if self.tag == tag:
            return
        
        self.tag = tag
        asyncio.create_task(func.update_card(self.id, {"$set": {"tag": tag}}))
    
    def change_frame(self, frame: str | None = None) -> None:
        if self._frame == frame:
            raise IUFIException("This frame is already assigned to this card.")
        
        self._frame = frame.lower() if frame else None

    def change_stars(self, stars: int) -> None:
        if self.stars != stars:
            self.stars = stars

            asyncio.create_task(func.update_card(self.id, {"$set": {"stars": stars}}))

    async def image_bytes(self, hide_image_if_no_owner: bool = False) -> BytesIO:
        image = await self.image(hide_image_if_no_owner=hide_image_if_no_owner)
        image_bytes = BytesIO()

        if self.is_gif:
            image[0].save(image_bytes, format="WEBP", save_all=True, append_images=image[1:], loop=0, duration=100, optimize=False)
        else:
            image.save(image_bytes, format='WEBP')
        
        image_bytes.seek(0)
        return image_bytes
    
    async def image(self, *, size_rate: float = SIZE_RATE, hide_image_if_no_owner: bool = False) -> Image.Image | list[Image.Image]:
        """Return the image or a list of images based on ownership status."""
        async with self._lock:
            # Check if the image should be hidden due to no owner
            if hide_image_if_no_owner and not self.owner_id:
                return await TempCard(f"cover/level{random.randint(1, 3)}.webp").image(size_rate=size_rate)
            
            return await asyncio.to_thread(self._load_image, size_rate=size_rate)

    @property
    def cost(self) -> int:
        price = func.settings.TIERS_BASE.get(self._tier)[1]
        if self.stars > 5:
            price *= 1 + ((self.stars - 5) * .25)

        return round(price)
    
    @property
    def tier(self) -> tuple[str, str]:
        """Return a tuple (emoji, name)"""
        return self._emoji, self._tier

    @property
    def frame(self) -> tuple[str, str]:
        frame_emoji = func.settings.FRAMES_BASE.get(self._frame)
        if frame_emoji:
            return frame_emoji, self._frame
        
        return "None", "None"

    @property
    def format(self) -> str:
        return "webp"
    
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
        return f"{self._emoji} {self.id.zfill(5)} " + (f"({self.tag})" if self.tag else "")

class TempCard(CardObject):
    _image_cache: Dict[str, Dict[str, Union[List[Image.Image], Image.Image]]] = {}  # Path to Image

    def __init__(self, path: str) -> None:
        super().__init__()
        self._path: str = path
        self._lock: asyncio.Lock = asyncio.Lock()

    async def image_bytes(self) -> BytesIO:
        """Return the image as bytes."""
        images = await self.image()
        image_bytes = BytesIO()

        if self.is_gif:
            images[0].save(image_bytes, format="WEBP", save_all=True, append_images=images, loop=0, duration=100, optimize=False)
        else:
            images.save(image_bytes, format='WEBP')

        image_bytes.seek(0)
        return image_bytes
    
    async def image(self, *, size_rate: float = SIZE_RATE, hide_image_if_no_owner: bool = False) -> Union[List[Image.Image], Image.Image]:
        """Load and return the image, caching it by size rate and path."""
        async with self._lock:
            if self._path not in TempCard._image_cache:
                TempCard._image_cache[self._path] = {}

            if size_rate not in TempCard._image_cache[self._path]:
                TempCard._image_cache[self._path][size_rate] = await asyncio.to_thread(self._load_image, self._path, size_rate=size_rate)
                
            return TempCard._image_cache[self._path][size_rate]
    
    @property
    def format(self) -> str:
        return "webp"
        
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

        self._average_time = ((self._average_time * self.total) + time) / (self.total + 1) if self.total > 0 else time

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

class Track():
    def __init__(
        self,
        data: Dict[str, Any]
    ):  
        self.data: Dict[str, Any] = data
        self.is_updated: bool = False

    async def load_data(self, *, stream=False) -> Dict[str, Any]:
        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: YTDL.extract_info(self.url, download=not stream))
            
            self.data["yt_data"] = {
                "title": data.get("title", "--"),
                "duration": data.get("duration", 0),
                "album": data.get("album", "--"),
                "artists": data.get("artists", []),
                "release_year": data.get("release_year", "----")
            }
            self.is_updated = True
        
        except Exception as e:
            func.logger.info("An exception occurred while loading track info from YouTube.", exc_info=e)
    
    async def get_audio_file_path(self) -> Optional[str]:
        for item in os.listdir(func.MUSIC_TRACKS_FOLDER):
            if os.path.splitext(item)[0] == self.id:
                return os.path.join(func.MUSIC_TRACKS_FOLDER, item)
        
        await self.load_data()
        return self.get_audio_file_path(self)

    def check_answer(self, answer: str, threshold: float = .9) -> bool:
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

    def update_state(self, member: Member, time_used: float, result: bool) -> None:
        self.is_updated = True

        self.data["average_time"] = ((self.data["average_time"] * self.total) + time_used) / (self.total + 1) if self.total > 0 else time_used

        current_best_time = self.data["best_record"]["time"]
        if result and (not current_best_time or current_best_time > time_used):
            self.data["best_record"]["member"] = member.id
            self.data["best_record"]["time"] = time_used

        key = "correct" if result else "wrong"
        self.data[key] = self.data.get(key, 0) + 1

    async def source(self, start: float = 0) -> FFmpegPCMAudio:
        return FFmpegPCMAudio(await Track.get_audio_file_path(self), options=f'-vn -ss {start}')
    
    @property
    def is_loaded(self) -> bool:
        return "yt_data" in self.data
    
    @property
    def id(self) -> str:
        return self.data.get("_id")

    @property
    def url(self) -> str:
        return self.data.get("url")
    
    @property
    def thumbnail(self) -> str:
        return f"https://i.ytimg.com/vi/{self.id}/maxresdefault.jpg"
    
    @property
    def title(self) -> str:
        return self.data["yt_data"]["title"]

    @property
    def duration(self) -> int:
        return self.data["yt_data"]["duration"]
    
    @property
    def album(self) -> str:
        return self.data["yt_data"]["album"]
    
    @property
    def artists(self) -> List[str]:
        return self.data["yt_data"]["artists"]
    
    @property
    def release_year(self) -> str:
        return self.data["yt_data"]["release_year"]
    
    @property
    def total(self) -> int:
        return self.data["correct"] + self.data["wrong"]
    
    @property
    def average_time(self) -> float:
        return self.data["average_time"]
    
    @property
    def correct_rate(self) -> float:
        total = self.total
        if not total:
            return 0
        return round(self.data["correct"] / total, 2) * 100
    
    @property
    def wrong_rate(self) -> float:
        return 100 - self.correct_rate

    @property
    def best_record(self) -> tuple[int, float]:
        br = self.data["best_record"]
        return br["member"], br["time"]

    @property
    def answers(self) -> List[str]:
        return self.data["answers"]

    @property
    def likes(self) -> int:
        return self.data["likes"]