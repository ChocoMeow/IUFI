from .objects import CARD_SIZE, SIZE_RATE, Card, TempCard
from io import BytesIO
from PIL import Image

PADDING = 10

def extend_lists(lists: list[list[Image.Image]]) -> list[list[Image.Image]]:
    # Find the length of the largest list
    max_length = max(len(lst) for lst in lists)

    # Extend each list by cycling through their own elements
    for i, lst in enumerate(lists):
        lst.extend(lst * ((max_length // len(lst)) + 1))
        lists[i] = lst[:max_length]

    return lists

def gen_cards_view(cards: list[Card | TempCard | None], cards_per_row: int = 3, *, size_rate: float = SIZE_RATE, hide_image_if_no_owner: bool = False) -> tuple[BytesIO, str]:
    # Create a new image for output
    card_width, card_height = int(CARD_SIZE[0] * size_rate), int(CARD_SIZE[1] * size_rate)
    num_rows = (len(cards) + cards_per_row - 1) // cards_per_row  # calculate number of rows

    output_image = Image.new(
        'RGBA',
        ((card_width * cards_per_row) + (PADDING * (cards_per_row - 1)), 
        (card_height * num_rows) + (PADDING * (num_rows - 1))), 
        (0, 0, 0, 0)
    )

    temp_cards: dict[str, list[Image.Image] | Image.Image] = {
        i: card.image(size_rate=size_rate, hide_image_if_no_owner=hide_image_if_no_owner) if card else None 
        for i, card in enumerate(cards)
    }
    
    resized_image_bytes = BytesIO()
    # Paste images into the output image with 10 pixels padding
    if is_gif := any([card.is_gif for card in cards if card]):
        gif_lists = [
            (card) if card and isinstance(card, list) else [card] if card else [None]
            for card in temp_cards.values()
        ]
        
        extended_gifs = extend_lists(gif_lists)
        modified_frames: list[Image.Image] = []
        
        for gif_frames in zip(*extended_gifs):
            output_image = output_image.copy()

            for i, frame in enumerate(gif_frames):
                if frame:
                    x = (card_width + PADDING) * (i % cards_per_row)
                    y = (card_height + PADDING) * (i // cards_per_row)

                    output_image.paste(frame, (x, y))

            modified_frames.append(output_image)
        modified_frames[0].save(resized_image_bytes, format="GIF", save_all=True, append_images=modified_frames, loop=0, duration=100, optimize=False)
    
    else:
        for i, card in enumerate(temp_cards.values()):
            if card:  # if card is not None
                x = (card_width + PADDING) * (i % cards_per_row)
                y = (card_height + PADDING) * (i // cards_per_row)

                output_image.paste(card, (x, y))

        output_image.save(resized_image_bytes, format='WEBP')

    resized_image_bytes.seek(0)
    return resized_image_bytes, "gif" if is_gif else "webp"