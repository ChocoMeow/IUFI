import asyncio
import datetime

GLOBAL_MILESTONES = [500, 2000, 5844, 10000]
MILESTONE_ONE_REWARD = [["🎵", "candies", 50]]
MILESTONE_TWO_REWARD = [["🌸", "roll.rare", 2]]
MILESTONE_THREE_REWARD = [["🌸", "roll.rare", 1], ["💎", "roll.epic", 1]]
MILESTONE_FOUR_REWARD = [["🎵", "candies", 50], ["💎", "roll.epic", 2], ["👑", "roll.legendary", 1]]
GLOBAL_QUEST_REWARDS = [MILESTONE_ONE_REWARD, MILESTONE_TWO_REWARD, MILESTONE_THREE_REWARD, MILESTONE_FOUR_REWARD]

NAUGHTY_LIST = []

def get_global_end_time():
    datetime.datetime(datetime.datetime.now().year, 4, 6)