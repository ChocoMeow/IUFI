import random, os
import functinos as func

from PIL import Image, ImageDraw
from .exceptions import ImageLoadError

TIER_EMOJI = {
    "common": "🥬",
    "rare": "🌸",
    "epic": "💎",
    "legendary": "👑",
    "mystic": "🦄"
}

PRICE_BASE = {
    'common': 1,
    'rare': 10,
    'epic': 40,
    'legendary': 100,
    'mystic': 500
}

class Card:
    def __init__(
        self,
        pool,
        id: str,
        tier: str,
        owner_id: int = None,
        stars: int = None,
        tag: str = None
    ):  
        self.id: str = id
        self._tier: str = tier
        self._pool = pool

        self.owner_id: int = owner_id
        self.stars: int = stars
        self.tag: str = tag

        self._image: Image.Image = None
        self._emoji: str = TIER_EMOJI.get(self._tier)

    def _round_corners(self, image: Image.Image, radius: int = 30) -> Image.Image:
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

    def _load_image(self):
        """Load and process the image"""
        if not self.stars:
            self.stars = random.randint(1, 5)
            func.update_card(self.id, {"stars": self.stars}, mode="set", insert=True)

        try:
            with Image.open(os.path.join(func.ROOT_DIR, "images", self._tier, f"{self.id}.jpg")).convert('RGBA') as img:
                image = self._round_corners(img)
                self._image = image.resize((300, 533), Image.LANCZOS)

        except Exception as e:
            raise ImageLoadError(f"Unable to load the image. Reason: {e}")

    def change_owner(self, owner_id: int | None = None, *, remove_tag: bool = True) -> None:
        if self.owner_id != owner_id:
            self.owner_id = owner_id
            payload = {"owner_id": owner_id}
            if remove_tag:
                payload["tag"] = None
                if self.tag and self.tag.lower() in self._pool._tag_cards:
                    self._pool._tag_cards.pop(self.tag.lower())
                self.tag = None

            func.update_card(self.id, payload, mode="set")

    def change_tag(self, tag: str | None) -> None:
        if self.tag != tag:
            self.tag = tag
            func.update_card(self.id, {"tag": tag}, mode="set")

    @property
    def cost(self) -> int:
        return PRICE_BASE.get(self._tier)
    
    @property
    def tier(self) -> tuple[str, str]:
        """Return a tuple (emoji, name)"""
        return self._emoji, self._tier

    @property
    def image(self) -> Image.Image:
        """Return the image"""
        if self._image is None:
            self._load_image()
        return self._image