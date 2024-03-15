from enum import Enum, auto

class DailyQuestIds(Enum):
    ROLL = auto()
    DAILY = auto()

    PLAY_MATCH_GAME = auto()
    PLAY_MATCH_GAME_LVL_1 = auto()
    PLAY_MATCH_GAME_LVL_2 = auto()
    PLAY_MATCH_GAME_LVL_3 = auto()

    PLAY_QUIZ_GAME = auto()
    PLAY_MUSIC_GAME = auto()
    FRAME_CONFIG = auto()

    USE_ANY_POTION = auto()
    USE_SPEED_POTION = auto()
    USE_LUCK_POTION = auto()

    COLLECT_COMMON_CARD = auto()
    COLLECT_RARE_CARD = auto()
    COLLECT_EPIC_CARD = auto()
    COLLECT_LEGENDARY_CARD = auto()

    def __int__(self) -> int:
        return self.value

    def __str__(self) -> str:
        return str(self.value)