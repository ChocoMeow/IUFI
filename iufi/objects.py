from __future__ import annotations

import random, os, asyncio
import functions as func

from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageSequence
from io import BytesIO
from typing import TYPE_CHECKING

from .exceptions import ImageLoadError
if TYPE_CHECKING:
    from .pool import CardPool

TIERS_BASE: dict[str, tuple[str, int]] = {
    "common": ("🥬", 1),
    "rare": ("🌸", 10),
    "epic": ("💎", 40),
    "legendary": ("👑", 100),
    "mystic": ("🦄", 500),
    "celestial": ("💫", 1500)
}

FRAMES_BASE: dict[str, str] = {
    "hearts": "💕",
    "celebrity": "🌟",
    "uaena": "💌",
    "dandelions": "🌷",
    "shine": "✨",
    "lovepoem": "💠",
    "cheer": "🎤",
    "smoon": "🍓",
    "signed": "✍️",
}

POTIONS_BASE: dict[str, str] = {
    "speed": "🏃",
    "luck": "🌠",
}

class Card:
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

    def _load_frame(self, image: Image.Image) -> Image.Image:
        with Image.open(os.path.join(func.ROOT_DIR, "frames", f"{self._frame}.png")).convert("RGBA").resize((200, 355)) as frame:
            image = self._round_corners(image)
            output = Image.new("RGBA", frame.size)
            output.paste(image, (6, 8))
            output.paste(frame, (0, 0), mask=frame)

            return output
        
    def _load_image(self):
        """Load and process the image"""
        def blocking_io(loop):
            if not self.stars:
                self.stars = random.randint(1, 5)
                loop.create_task(func.update_card(self.id, {"$set": {"stars": self.stars}}, insert=True))

            try:
                if self._tier != "celestial":
                    with Image.open(os.path.join(func.ROOT_DIR, "images", self._tier, f"{self.id}.jpg")) as img:
                        image = img.resize(((190, 338) if self._frame else (200, 355)), Image.LANCZOS)
                        if self._frame:
                            self._image = self._load_frame(image)
                        else:
                            self._image = self._round_corners(image)
                else:
                    with Image.open(os.path.join(func.ROOT_DIR, "images", self._tier, f"{self.id}.gif")) as img:
                        modified_frames = []
                        for img_frame in ImageSequence.Iterator(img):
                            frame = img_frame.resize((190, 338) if self._frame else (200, 355))
                            if self._frame:
                                frame = self._load_frame(frame)
                            else:    
                                frame = self._round_corners(frame)
                            modified_frames.append(frame)

                        self._image = modified_frames

            except Exception as e:
                raise ImageLoadError(f"Unable to load the image. Reason: {e}")

        with ThreadPoolExecutor() as executor:
            loop = asyncio.get_event_loop()
            loop.run_in_executor(executor, blocking_io, loop)

    def change_owner(self, owner_id: int | None = None, *, remove_tag: bool = True, remove_frame: bool = True) -> None:
        if self.owner_id != owner_id:
            self.owner_id = owner_id
            if remove_tag:
                if self.tag and self.tag.lower() in self._pool._tag_cards:
                    self._pool._tag_cards.pop(self.tag.lower())
                self.tag = None
            if remove_frame:
                self._frame = None
                self._image = None

    def change_tag(self, tag: str | None = None) -> None:
        if self.tag != tag:
            self.tag = tag
            asyncio.create_task(func.update_card(self.id, {"$set": {"tag": tag}}))
    
    def change_frame(self, frame: str | None = None) -> None:
        if self._frame != frame:
            self._frame = frame.lower() if frame else None

            if self.image:
                self._load_image()

    @property
    def cost(self) -> int:
        return TIERS_BASE.get(self._tier)[1]
    
    @property
    def tier(self) -> tuple[str, str]:
        """Return a tuple (emoji, name)"""
        return self._emoji, self._tier

    @property
    def frame(self) -> tuple[str, str]:
        return FRAMES_BASE.get(self._frame), self._frame
    @property
    def image(self) -> list[Image.Image] | Image.Image:
        """Return the image"""
        if self._image is None:
            self._load_image()
        return self._image

    @property
    def image_bytes(self) -> BytesIO:
        image_bytes = BytesIO()

        if self.is_gif:
            self.image[0].save(image_bytes, format="GIF", save_all=True, append_images=self.image[1:], loop=0)
        else:
            self.image.save(image_bytes, format='PNG')
        image_bytes.seek(0)

        return image_bytes

    @property
    def is_gif(self) -> bool:
        return isinstance(self.image, list)

    @property
    def format(self) -> str:
        return "gif" if self.is_gif else "png"