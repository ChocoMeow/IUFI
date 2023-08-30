from .card import Card
from io import BytesIO
from PIL import Image

def gen_cards_view(cards: list[Card | None], cards_per_row: int = 3) -> BytesIO:
    # Create a new image for output
    padding = 10
    card_width = 200
    card_height = 355
    num_rows = (len(cards) + cards_per_row - 1) // cards_per_row  # calculate number of rows

    output_image = Image.new('RGBA', 
                             ((card_width * cards_per_row) + (padding * (cards_per_row - 1)), 
                              (card_height * num_rows) + (padding * (num_rows - 1))), 
                             (0, 0, 0, 0))

    # Paste images into the output image with 10 pixels padding
    for i, card in enumerate(cards):
        row = i // cards_per_row
        col = i % cards_per_row

        if card:  # if card is not None
            x = (card_width + padding) * col
            y = (card_height + padding) * row
            output_image.paste(card.image, (x, y))

    resized_image_bytes = BytesIO()
    output_image.save(resized_image_bytes, format='PNG')
    resized_image_bytes.seek(0)

    return resized_image_bytes