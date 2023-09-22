from .objects import Card, TempCard
from io import BytesIO
from PIL import Image

def extend_lists(lists: list[list[Image.Image]]) -> list[list[Image.Image]]:
    # Find the length of the largest list
    max_length = max(len(lst) for lst in lists)

    # Extend each list by cycling through their own elements
    for i, lst in enumerate(lists):
        lst.extend(lst * ((max_length // len(lst)) + 1))
        lists[i] = lst[:max_length]

    return lists

def gen_cards_view(cards: list[Card | TempCard | None], cards_per_row: int = 3) -> tuple[BytesIO, str]:
    # Create a new image for output
    padding = 10
    card_width = 200
    card_height = 355
    num_rows = (len(cards) + cards_per_row - 1) // cards_per_row  # calculate number of rows

    output_image = Image.new('RGBA', 
                             ((card_width * cards_per_row) + (padding * (cards_per_row - 1)), 
                              (card_height * num_rows) + (padding * (num_rows - 1))), 
                             (0, 0, 0, 0))

    resized_image_bytes = BytesIO()

    # Paste images into the output image with 10 pixels padding
    if is_gif := any([card.is_gif if card else False for card in cards]):
        gif_lists = [
            card.image if card and card.is_gif else [card.image] if card else [None] 
            for card in cards
        ]
        extended_gifs = extend_lists(gif_lists)

        modified_frames: list[Image.Image] = []
        for gif_frames in zip(*extended_gifs):
            output_image = output_image.copy()

            for i, frame in enumerate(gif_frames):
                if frame:
                    x = (card_width + padding) * (i % cards_per_row)
                    y = (card_height + padding) * (i // cards_per_row)

                    output_image.paste(frame, (x, y))

            modified_frames.append(output_image)
        modified_frames[0].save(resized_image_bytes, format="GIF", save_all=True, append_images=modified_frames[1:], loop=0)
    
    else:
        for i, card in enumerate(cards):
            if card:  # if card is not None
                x = (card_width + padding) * (i % cards_per_row)
                y = (card_height + padding) * (i // cards_per_row)
                output_image.paste(card.image, (x, y))

        output_image.save(resized_image_bytes, format='PNG')

    resized_image_bytes.seek(0)
    return resized_image_bytes, "gif" if is_gif else "png"