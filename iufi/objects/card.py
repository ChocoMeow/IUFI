from __future__ import annotations

import io
import os
import random
import asyncio

from PIL import Image, ImageDraw, ImageSequence
from typing import Union, List, Dict, TYPE_CHECKING

from ..exceptions import ImageLoadError, IUFIException

CARD_SIZE = (1080, 1920)
SIZE_RATE = 0.2
FRAME_SIZE_INCREMENT = (0.005, 0.003)

if TYPE_CHECKING:
    from ..pool import CardPool

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

    def preview_frame(self, frame: str = None) -> io.BytesIO:
        try:
            image_path = os.path.join(func.ROOT_DIR, "images", self._tier)

            image_bytes = io.BytesIO()
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

    async def image_bytes(self, hide_image_if_no_owner: bool = False) -> io.BytesIO:
        image = await self.image(hide_image_if_no_owner=hide_image_if_no_owner)
        image_bytes = io.BytesIO()

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

    async def image_bytes(self) -> io.BytesIO:
        """Return the image as bytes."""
        images = await self.image()
        image_bytes = io.BytesIO()

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