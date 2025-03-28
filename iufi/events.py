import asyncio
import datetime

GLOBAL_MILESTONES = [500, 2000, 7000, 160593]
MILESTONE_ONE_REWARD = [["🍊", "candies", 50]]
MILESTONE_TWO_REWARD = [["🌸", "roll.rare", 2]]
MILESTONE_THREE_REWARD = [["🌸", "roll.rare", 1], ["💎", "roll.epic", 1]]
MILESTONE_FOUR_REWARD = [["🍊", "candies", 50], ["💎", "roll.epic", 2], ["👑", "roll.legendary", 1]]
GLOBAL_QUEST_REWARDS = [MILESTONE_ONE_REWARD, MILESTONE_TWO_REWARD, MILESTONE_THREE_REWARD, MILESTONE_FOUR_REWARD]

NAUGHTY_LIST = [120409761182253056,135827436544851969,160849769848242176,213896841845014528,236400388847173632,391569501201891334,415078118596935680,625226356057440276,675092715838636053,717033456663658627,1099205010438500393,1223531350972174337,1235715617412091945]

def get_global_end_time():
    return datetime.datetime(datetime.datetime.now().year, 4, 6)

def is_april_fools():
    now_kst = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    return now_kst.month == 4 and now_kst.day == 1

def is_user_naughty(user_id):
    return user_id in NAUGHTY_LIST
