import random, os
import functinos as func

from PIL import Image, ImageOps, ImageDraw
from .exceptions import ImageLoadError

TIER_EMOJI = {
    "common": "🥬",
    "rare": "💮",
    "epic": "💎",
    "legendary": "👑"
}

class Card:
    def __init__(
        self,
        id: str,
        tier: str,
        owner_id: int = None,
        stars: int = None,
    ):  
        self.id: str = id
        self._tier: str = tier

        self.owner_id: int = owner_id
        self.stars: int = stars

        self._image: Image.Image = None
        self._emoji: str = TIER_EMOJI.get(self._tier)

    def _add_border(self, img: Image.Image, border: int = 15, color: int = 0) -> Image.Image:
        """Creates a new image with border"""
        if not color:
            color = img.getpixel((0,0))
        return ImageOps.expand(img, border=border, fill=color)
    
    def _round_corners(self, image: Image.Image, radius: int = 20) -> Image.Image:
        """Creates a rounded corner image"""
        circle = Image.new('L', (radius * 2, radius * 2), 0)
        draw = ImageDraw.Draw(circle)
        draw.ellipse((0, 0, radius * 2, radius * 2), fill=255)
        
        alpha = Image.new('L', image.size, 255)
        w, h = image.size
        alpha.paste(circle.crop((0, 0, radius, radius)), (0, 0))
        alpha.paste(circle.crop((0, radius, radius, radius * 2)), (0, h - radius))
        alpha.paste(circle.crop((radius, 0, radius * 2, radius)), (w - radius, 0))
        alpha.paste(circle.crop((radius, radius, radius * 2, radius * 2)), (w - radius, h - radius))
        image.putalpha(alpha)

        return image

    def _load_image(self):
        """Load and process the image"""
        if not self.stars:
            self.stars = random.randint(1, 5)
            func.update_card(self.id, {"stars": self.stars}, mode="set", insert=True)

        try:
            with Image.open(os.path.join(func.ROOT_DIR, "images", self._tier, f"{self.id}.jpg")) as img:
                img = self._add_border(img)
                img = self._round_corners(img)
                img = img.resize((300, 533))
                self._image = img
        except Exception as e:
            raise ImageLoadError(f"Unable to load the image. Reason: {e}")

    def change_owner(self, owner_id: int) -> None:
        self.owner_id = owner_id
        func.update_card(self.id, {"owner_id": owner_id}, mode="set")

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

   