import asyncio

from .objects import CARD_SIZE, SIZE_RATE, Card, TempCard
from io import BytesIO
from PIL import Image

PADDING = 10
LOCK = asyncio.Lock()

def extend_lists(lists: list[list[Image.Image]]) -> list[list[Image.Image]]:
    # Find the length of the largest list
    max_length = max(len(lst) for lst in lists)

    # Extend each list by cycling through their own elements
    for i, lst in enumerate(lists):
        lst.extend(lst * ((max_length // len(lst)) + 1))
        lists[i] = lst[:max_length]

    return lists

async def create_image(card_width: float, card_height: float, cards_per_row: int, num_rows: int, padding: int):
    return await asyncio.to_thread(
        Image.new,
        'RGBA',
        (
            (card_width * cards_per_row) + (padding * (cards_per_row - 1)),
            (card_height * num_rows) + (padding * (num_rows - 1))
        ),
        (0, 0, 0, 0)
    )

async def paste_image(output_image: Image.Image, frame: Image.Image, x: float, y: float):
    await asyncio.to_thread(output_image.paste, frame, (x, y))

async def save_image_to_bytes(image: Image.Image, format: str, bytes_io: BytesIO, append_images=None):
    if not append_images:
        await asyncio.to_thread(image.save, bytes_io, format=format)

    else:
        await asyncio.to_thread(
            image.save,
            bytes_io,
            format=format,
            save_all=True,
            append_images=append_images,
            loop=0,
            duration=100,
            optimize=False
        )

async def gen_cards_view(cards: list[Card | TempCard | None], cards_per_row: int = 3, *, size_rate: float = SIZE_RATE, hide_image_if_no_owner: bool = False) -> tuple[BytesIO, str]:
    async with LOCK:
        card_width, card_height = int(CARD_SIZE[0] * size_rate), int(CARD_SIZE[1] * size_rate)
        num_rows = (len(cards) + cards_per_row - 1) // cards_per_row

        output_image = await create_image(card_width, card_height, cards_per_row, num_rows, PADDING)

        temp_cards = {
            i: await card.image(size_rate=size_rate, hide_image_if_no_owner=hide_image_if_no_owner) if card else None 
            for i, card in enumerate(cards)
        }
        
        resized_image_bytes = BytesIO()
        
        if any(card.is_gif for card in cards if card):
            gif_lists = [
                (card) if card and isinstance(card, list) else [card] if card else [None]
                for card in temp_cards.values()
            ]
            
            extended_gifs = extend_lists(gif_lists)
            modified_frames: list[Image.Image] = []
            
            for gif_frames in zip(*extended_gifs):
                for i, frame in enumerate(gif_frames):
                    if frame:
                        x = (card_width + PADDING) * (i % cards_per_row)
                        y = (card_height + PADDING) * (i // cards_per_row)

                        await paste_image(output_image, frame, x, y)

                modified_frames.append(output_image.copy())  # only copy when necessary
            await save_image_to_bytes(modified_frames[0], "WEBP", resized_image_bytes, append_images=modified_frames[1:])

            # Clear large images from memory
            for frame in modified_frames:
                del frame

        else:
            for i, card in enumerate(temp_cards.values()):
                if card:
                    x = (card_width + PADDING) * (i % cards_per_row)
                    y = (card_height + PADDING) * (i // cards_per_row)

                    await paste_image(output_image, card, x, y)

            await save_image_to_bytes(output_image, 'WEBP', resized_image_bytes)

        resized_image_bytes.seek(0)
        return resized_image_bytes, "webp"