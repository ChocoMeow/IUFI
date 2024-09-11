import datetime

# Debut Anniversary
EVENT_CONFIG: dict[str, dict[str, str | datetime.datetime]] = {
    "debut_anniversary": {
        "name": "Debut Anniversary",
        "description": "Celebrate IU's debut anniversary with IUFI!",
        "start_date": datetime.datetime(datetime.datetime.now().year, 9, 11),
        "end_date": datetime.datetime(datetime.datetime.now().year, 9, 26),
        "folder": "debut"
    }
}

debut_anniversary_day = EVENT_CONFIG["debut_anniversary"]


def is_debut_anniversary_day() -> bool:
    return debut_anniversary_day["start_date"] <= datetime.datetime.now() <= debut_anniversary_day["end_date"]


def get_end_time() -> datetime.datetime:
    return debut_anniversary_day["end_date"]


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
    1: (('10243', 9), ('10650', 15), ('06507', 31), ('07294', 40), ('08971', 66), ('00916', 414)),
    2: (('01944', 25), ('4895', 19), ('00788', 98), ('02518', 86), ('10614', 500)),
    3: (('07073', 18), ('03056', 25), ('10607', 110), ('00558', 80), ('10365', 396)),
    4: (('01128', 11), ('05393', 23), ('02916', 84), ('05992', 72), ('02463', 307)),
    5: (('02722', 29), ('09024', 23), ('07748', 119), ('08243', 87), ('00270', 394)),
    6: (('04341', 7), ('02169', 35), ('09925', 77), ('01184', 73)),
    7: (('06356', 17), ('8075', 24), ('03130', 75), ('00876', 80), ('07206', 408)),
    8: (('05259', 23), ('5778', 39), ('06567', 75), ('07302', 2000), ('03689', 90), ('02839', 87), ('10697', 470)),
    9: (('02246', 25), ('02944', 87), ('10584', 33), ('10718', 30)),
    10: (('03112', 17), ('5126', 20), ('08573', 72), ('00543', 99)),
    11: (('04250', 11), ('00113', 20), ('01473', 94), ('09451', 100), ('02223', 411)),
    12: (('03577', 23), ('03146', 28), ('03658', 445), ('10734', 69)),
    13: (('02055', 27), ('9285', 36), ('08764', 97), ('00093', 102)),
    14: (('03211', 25), ('08572', 80), ('02669', 89), ('10738', 27)),
    15: (('02250', 18), ('8506', 23), ('03055', 84), ('10233', 82)),
    16: (('05059', 29), ('04538', 23), ('00702', 68), ('07230', 87), ('06352', 250))
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

BUY_MESSAGE: list[str] = [
    "🎉 {0} just bought the secret prize! Time to see what’s inside!",
    "🚀 Blast off! {0} grabbed the hidden gem. What’s the big reveal!",
    "🎁 Surprise alert! {0} just unlocked the exclusive card. What’s the scoop!",
    "🎲 {0} rolled the dice and bought the surprise card! Get ready for the reveal!",
    "🌟 {0} just made the ultimate find! What’s their new treasure?",
    "💥 {0} hit the jackpot! Their new card is about to make some waves!",
    "🎊 Boom! {0} just got their hands on the surprise card. What’s in store!",
    "🧩 Puzzle solved! {0} just acquired the special card. What’s the secret?",
    "🔮 Crystal ball says {0} just grabbed the exclusive item! Time to unveil!",
    "🎈 Confetti time! {0} picked up the surprise card. What’s the excitement?",
    "🕵️‍♂️ Detective {0} cracked the code and found the hidden treasure! What’s the prize?",
    "🧙‍♂️ Magic unlocked! {0} just snagged the enchanted card. Let’s see the wonder!",
    "🚨 Heads up! {0} went for the special card. Get ready for a fantastic reveal!",
    "🕶️ Cool move, {0}! You just grabbed the limited edition card. Time for the reveal!",
    "🌈 Rainbow alert! {0} just landed the surprise card. What’s the colorful prize?",
    "🎁 {0} went all-in! The mystery card is now theirs—what's inside?",
    "🕵️‍♂️ Aha! {0} found the secret stash! What’s the mystery card going to be?",
    "🌟 Boom! {0} pulled the trigger on the mystery card! Get ready for the surprise!",
    "🎊 Congrats, {0}! The mystery card is now yours—unbox the excitement!",
    "💥 Surprise alert! {0} just snagged the mystery card. What will they uncover?",
    "🧩 Puzzle complete! {0} just bought the mystery card. What’s their lucky find?",
    "🔮 Mystery unlocked! {0} claimed the card. The big reveal is just moments away!",
    "🎉 Hold up! {0} went for the mystery card! What’s the big surprise?",
    "🧙‍♂️ Wizard-level move, {0}! You’ve got the mystery card—prepare for magic!",
    "🎈 Confetti time! {0} just picked the mystery card. What’s the treasure inside?",
    "🕶️ Cool move, {0}! You’ve got the mystery card. Get ready for the epic reveal!",
    "🚨 Alert! {0} bought the mystery card! Time to unveil the surprise!"
]

MILESTONES = [500, 2000, 5844, 10000]
MILESTONE_ONE_REWARD = [["🎵", "candies", 50]]
MILESTONE_TWO_REWARD = [["🌸", "roll.rare", 2]]
MILESTONE_THREE_REWARD = [["🌸", "roll.rare", 1], ["💎", "roll.epic", 1]]
MILESTONE_FOUR_REWARD = [["🎵", "candies", 50], ["💎", "roll.epic", 2], ["👑", "roll.legendary", 1]]
ANNIVERSARY_QUEST_REWARDS = [MILESTONE_ONE_REWARD, MILESTONE_TWO_REWARD, MILESTONE_THREE_REWARD, MILESTONE_FOUR_REWARD]

MARKET_ID = 987354574304190476  # iufi server
ANNOUNCEMENT_ID = 987353737548935198  # iufi server


def GetTodayReward() -> tuple[str, str, int]:
    current_day = (datetime.datetime.now() - debut_anniversary_day["start_date"]).days + 1
    return DAILY_REWARDS.get(current_day, None)


def GetTodayCardSell() -> list[tuple[str, int]]:
    current_day = (datetime.datetime.now() - debut_anniversary_day["start_date"]).days + 1
    return CARDS_TO_SELL.get(current_day, None)


def GetAllCards() -> list[tuple[str, int]]:
    return [card for cards in CARDS_TO_SELL.values() for card in cards]
