import random, time, socket

from timeit import default_timer as timer
from itertools import zip_longest
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

class ExponentialBackoff:
    """
    The MIT License (MIT)
    Copyright (c) 2015-present Rapptz
    Permission is hereby granted, free of charge, to any person obtaining a
    copy of this software and associated documentation files (the "Software"),
    to deal in the Software without restriction, including without limitation
    the rights to use, copy, modify, merge, publish, distribute, sublicense,
    and/or sell copies of the Software, and to permit persons to whom the
    Software is furnished to do so, subject to the following conditions:
    The above copyright notice and this permission notice shall be included in
    all copies or substantial portions of the Software.
    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
    OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
    DEALINGS IN THE SOFTWARE.
    """

    def __init__(self, base: int = 1, *, integral: bool = False) -> None:

        self._base = base

        self._exp = 0
        self._max = 10
        self._reset_time = base * 2 ** 11
        self._last_invocation = time.monotonic()

        rand = random.Random()
        rand.seed()

        self._randfunc = rand.randrange if integral else rand.uniform

    def delay(self) -> float:

        invocation = time.monotonic()
        interval = invocation - self._last_invocation
        self._last_invocation = invocation

        if interval > self._reset_time:
            self._exp = 0

        self._exp = min(self._exp + 1, self._max)
        return self._randfunc(0, self._base * 2 ** self._exp)


class NodeStats:
    """The base class for the node stats object.
       Gives critical information on the node, which is updated every minute.
    """

    def __init__(self, data: dict) -> None:

        memory: dict = data.get("memory")
        self.used = memory.get("used")
        self.free = memory.get("free")
        self.reservable = memory.get("reservable")
        self.allocated = memory.get("allocated")

        cpu: dict = data.get("cpu")
        self.cpu_cores = cpu.get("cores")
        self.cpu_system_load = cpu.get("systemLoad")
        self.cpu_process_load = cpu.get("lavalinkLoad")

        self.players_active = data.get("playingPlayers")
        self.players_total = data.get("players")
        self.uptime = data.get("uptime")

    def __repr__(self) -> str:
        return f"<IUFI.NodeStats total_players={self.players_total!r} playing_active={self.players_active!r}>"