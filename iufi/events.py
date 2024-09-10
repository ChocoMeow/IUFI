import datetime

# Debut Anniversary
EVENT_CONFIG: dict[str, dict[str, str | datetime.datetime]] = {
    "debut_anniversary": {
        "name": "Debut Anniversary",
        "description": "Celebrate IU's debut anniversary with IUFI!",
        "start_date": datetime.datetime(datetime.datetime.now().year, 9, 5),
        "end_date": datetime.datetime(datetime.datetime.now().year, 9, 26),
        "folder": "debut"
    }
}

debut_anniversary_day = EVENT_CONFIG["debut_anniversary"]


def is_debut_anniversary_day() -> bool:
    return debut_anniversary_day["start_date"] <= datetime.datetime.now() <= debut_anniversary_day["end_date"]


def get_end_time() -> datetime.datetime:
    return debut_anniversary_day["end_date"]


def get_match_game_cover(level: str) -> str:
    return "cover/" + f"level{level}.jpg"


DAILY_REWARDS: dict[int, tuple[str, str, int]] = {
    1: ("🎵", "candies", 5),
    2: ("🎵", "candies", 5),
    3: ("🎵", "candies", 5),
    4: ("🎵", "candies", 10),
    5: ("🌸", "roll.rare", 1),
    6: ("🎵", "candies", 15),
    7: ("🎵", "candies", 25),
    8: ("💎", "roll.epic", 1),
    9: ("🎵", "candies", 25),
    10: ("🎵", "candies", 15),
    11: ("🎵", "candies", 10),
    12: ("🎵", "candies", 10),
    13: ("🌸", "roll.rare", 1),
    14: ("🎵", "candies", 10),
    15: ("🎵", "candies", 5),
    16: ("🎵", "candies", 5),
    17: ("🎵", "candies", 5)
}

CARDS_TO_SELL: dict[int, [tuple[str, int]]] = {
    1: (("1", 10), ("2", 20)),
    2: (("194", 3), ("327", 999)),
    3: (("5", 50), ("6", 60)),
    4: (("7", 70), ("8", 80)),
    5: (("9", 90), ("10", 100)),
    6: (("11", 110), ("12", 120)),
    7: (("13", 130), ("14", 140)),
    8: (("15", 150), ("16", 160)),
    9: (("17", 170), ("18", 180)),
    10: (("19", 190), ("20", 200)),
    11: (("21", 210), ("22", 220)),
    12: (("23", 230), ("24", 240)),
    13: (("25", 250), ("26", 260)),
    14: (("27", 270), ("28", 280)),
    15: (("29", 290), ("30", 300)),
    16: (("31", 310), ("32", 320)),
    17: (("33", 330), ("34", 340)),
}

SALE_MESSAGE: list[str] = [
    "🎭 Mystery Card: Buy first, be surprised later!",
    "🎁 Feeling lucky? Buy the mystery card to find out!",
    "🕵️‍♂️ Secret card in the shop! Dare to discover it?",
    "🧙‍♂️ Magic in the air! What’s behind the mystery card?",
    "🔮 Mystery Card: Click on buy to reveal your fate!",
    "🧩 A hidden card lies within. Only one way to see it!",
    "🃏 Wild card alert! Buy now to unveil the mystery.",
    "🎱 Mystery card! Take a chance—what will you get?",
    "🚀 Blast off into the unknown with a mystery card!",
    "🧀 Curiosity piqued? Buy the mystery card and see!",
    "🦉 The wise choose mystery. What will yours be?",
    "🌟 Mystery Card: It's a surprise every time!",
    "💥 Mystery drop incoming! Buy now to unlock the surprise!",
    "🎩 Abracadabra! Buy the mystery card and see the magic!",
    "🧭 Take the mystery route! Only the bold will see what's inside.",
    "🤔 What’s behind the curtain? Buy the mystery card to find out!",
    "🔥 Feeling adventurous? A mystery card awaits your courage!",
    "🕹️ Mystery mode activated! Hit ‘Buy’ to reveal.",
    "🦋 A surprise is fluttering in the shop… grab it to see!",
    "🧠 Brain teaser: What’s the mystery card? Find out by buying!",
    "🧙‍♀️ A sprinkle of magic dust… and your mystery card appears!",
    "🏴‍☠️ X marks the spot! Buy the mystery card for hidden treasure!",
    "🌌 Mystery card: A journey to the unknown begins now!",
    "🧸 What's in the surprise box? Buy it to see what's inside!",
    "🐉 A dragon guards the mystery card… brave enough to get it?",
    "🐾 Only the curious shall discover the mystery card’s secret.",
    "🔑 Unlock the unknown! The mystery card is a key away.",
    "🎀 A surprise wrapped in mystery! Ready to unwrap it?",
    "💌 Love surprises? This mystery card could be your new favorite!",
    "🎲 Feeling lucky? Take a chance and see what you get!",
    "🚪 Behind this cover... a surprise awaits. Buy it if you dare!",
    "🍀 Fortune favors the bold! Click to uncover your surprise!",
    "🧳 Unpack your surprise! What’s hidden inside?",
    "🌟 A surprise awaits the curious. Will you be the one?",
    "🦸‍♂️ Heroes make bold choices! What secret reward will you unveil?",
    "🛒 One click away from the unknown. Ready to shop?",
    "🎡 Step right up! The surprise spinner is live in the shop!",
    "🌠 Make a wish and see what the stars bring to your collection!",
    "🧭 Navigate to the unknown! What treasure will you find?",
    "🦜 A parrot squawks: 'Treasure ahead!' Will you find it?",
    "🍫 Like a mystery chocolate—buy it and savor the surprise!",
    "📦 Sealed and packed! What’s inside? Only one way to know.",
    "🧩 Puzzle time! Solve it by buying and revealing your reward.",
    "🌈 Every purchase is a rainbow—what’s at the end for you?",
    "🔦 Shine a light into the unknown! What's lurking in the shadows?",
    "🕶️ The coolest surprises hide in plain sight. Can you spot them?",
    "🔥 Feeling the heat? Grab this and find out what's burning hot!",
    "🎵 Hit the right note! What tune will this bring to your collection?",
    "🌴 Adventure calls! What surprise will your expedition uncover?",
    "🛍️ Shop all day, ayy-ayy! No breaks, just buys. What will you haul today?",
    "🛒 Greed is free, ayy-ayy! Fill up your cart like there’s no tomorrow!",
    "🛍️ Let’s go haul! Fill your collection until it’s bursting—don’t leave anything behind!",
    "🚀 No plan B here! Grab it all until it’s all yours! Ready for the haul?",
    "⏰ Time is short, so shop faster! The shop never closes, and neither should your ambition.",
    "🎨 What’s on your wish list? Make it full and make it happen—this shop's open forever!",
    "🎶 It's time to show, go, and make it sure, sure—grab what you want in the shop!",
    "💪 Victory smells like a full collection! Take what you want—no limits, no shame!",
    "🛍️ Look around! There’s no such thing as ‘enough’ here—only more, more, more!",
    "💎 Fill it up till it’s overflowing! This shop never closes, so neither does your chance!",
    "🦊 Be bold, take it all! For the one who shops without limits.",
    "🌠 Make your goal! Whether it’s rare, epic, or legendary, don’t stop until it’s yours!",
    "🏆 Even jealousy is welcome when your collection’s this good. What’s next on your wish list?",
    "🎉 Let’s go haul, till the shop is empty! More is more, go and make it your own"
]

MILESTONES = [2, 3, 4, 5]
MILESTONE_ONE_REWARD = [["🎵", "candies", 50]]
MILESTONE_TWO_REWARD = [["🌸", "roll.rare", 2]]
MILESTONE_THREE_REWARD = [["🌸", "roll.rare", 1], ["💎", "roll.epic", 1]]
MILESTONE_FOUR_REWARD = [["🎵", "candies", 50], ["💎", "roll.epic", 2], ["👑", "roll.legendary", 1]]
ANNIVERSARY_QUEST_REWARDS = [MILESTONE_ONE_REWARD, MILESTONE_TWO_REWARD, MILESTONE_THREE_REWARD, MILESTONE_FOUR_REWARD]

MARKET_ID = 1159846609924927558 # dev server
ANNOUNCEMENT_ID = 1159846609924927558 # dev server
#MARKET_ID = 1143358510697021532  # my server
#ANNOUNCEMENT_ID = 1143358510697021532  # my server


def GetTodayReward() -> tuple[str, str, int]:
    # current day - event start day
    current_day = (datetime.datetime.now() - debut_anniversary_day["start_date"]).days + 1
    print("current_day: ", current_day)
    return DAILY_REWARDS.get(current_day, None)


def GetTodayCardSell() -> list[tuple[str, int]]:
    # current day - event start day
    current_day = (datetime.datetime.now() - debut_anniversary_day["start_date"]).days + 1
    print("current_day: ", current_day)
    return CARDS_TO_SELL.get(current_day, None)


def GetAllCards() -> list[tuple[str, int]]:
    return [card for cards in CARDS_TO_SELL.values() for card in cards]
