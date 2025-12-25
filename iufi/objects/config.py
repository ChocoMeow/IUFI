from  pydantic import BaseModel
from pathlib import Path
from typing import List, Dict, Union, Optional, Any

class Pity(BaseModel):
    soft_pity: int = 0
    hard_pity: int = 0
    soft_pity_boost: float = 1.0

class Quest(BaseModel):
    title: str
    amount: int
    rewards: List[tuple[str, str, Union[int, List[int]]]]
    type: str

class Potion(BaseModel):
    emoji: str
    expiration: int
    levels: Dict[str, float]

class Rank(BaseModel):
    emoji_id: str
    points: int
    discord_role_id: Optional[str] = None
    questions: List[tuple[str, int]]
    rewards: Dict[str, Union[tuple[str, int], List[tuple[str, int]]]]

class MatchGame(BaseModel):
    cooldown: int
    timeout: int
    cards: int
    elem_per_row: int
    max_clicks: int
    rewards: Dict[str, Union[tuple[str, int], List[tuple[str, int]]]]

class MusicGame(BaseModel):
    next_song_interval: int
    rewards: Dict[str, List[Union[tuple[str, int], List[tuple[str, int]]]]]

class LoggingPath(BaseModel):
    path: str
    enabled: Optional[bool] = False
    max_history: Optional[int] = 30

class Logging(BaseModel):
    file: LoggingPath
    level: Dict[str, str]
    enabled: bool = True

class PvPGame(BaseModel):
    power_ranges: Dict[str, tuple[int, int]]
    challenge_timeout: int
    round_delay: int
    max_reroll_attempts: int
    reward_enabled: bool

class ConfigModel(BaseModel):
    BOT_PREFIX: List[str] = []
    MAX_CARDS: int = 0
    DEFAULT_EXP: int = 0
    LAST_TRADE_TIMER: int = 0
    RESET_CARD_DAY: int = 0
    MAIN_GUILD: int = 0
    MAIN_CHAT_CHANNEL: int = 0
    MUSIC_TEXT_CHANNEL: int = 0
    MUSIC_VOICE_CHANNEL: int = 0
    GALLERY_CHANNEL: int = 0
    MARKET_CHANNEL: int = 0
    ALLOWED_CATEGORY_IDS: List[int] = []
    IGNORE_CHANNEL_IDS: List[int] = []
    GAME_CHANNEL_IDS: List[int] = []
    USER_BASE: Dict[str, Any] = {}
    COOLDOWN_BASE: Dict[str, tuple[str, int]] = {}
    PITY_SETTINGS: Dict[str, Pity] = {}
    DAILY_QUESTS: Dict[str, Quest] = {}
    WEEKLY_QUESTS: Dict[str, Quest] = {}
    TIERS_BASE: Dict[str, tuple[str, int]] = {}
    FRAMES_BASE: Dict[str, tuple[str, int, bool]] = {}
    POTIONS_BASE: Dict[str, Potion] = {}
    RANK_BASE: Dict[str, Rank] = {}
    MATCH_GAME_SETTINGS: Dict[str, MatchGame] = {}
    MUSIC_GAME_SETTINGS: MusicGame = {}
    ADMIN_IDS: List[int] = []
    BUG_REPORT_CHANNEL_ID: int = 0
    OPUS_PATH: str = ""
    LOGGING: Logging = {}
    GIVE_REWARD_CARD: bool = False
    MONTHLY_LEADERBOARD_ROLE: int = 0
    PVP_SETTINGS: PvPGame = {}
    REWARD_CARD_PROBABILITIES: Dict[str, Any] = {}

    # Paths (Not from config file)
    CARDS_FOLDER_PATH: Path
    NEW_CARDS_FOLDER_PATH: Path
    MUSIC_TRACKS_FOLDER_PATH: Path

class Config:
    """
    Singleton wrapper/proxy around ConfigModel.

    Usage:
      - Initialize/replace: Config({...})
      - Raw model: cfg = Config.get()
    """

    _instance: Optional[ConfigModel] = None
    WORKING_DIR: Path = Path(__file__).resolve().parent.parent

    def __new__(cls, config_dict: Optional[Dict[str, Any]] = None) -> "Config":
        # If called with a dict, initialize/replace the singleton model
        if config_dict is not None:
            cls.init(config_dict)
        # Return class so attribute access works as Config.FOO
        return cls

    @classmethod
    def init(cls, config_dict: Dict[str, Any], *, replace: bool = True) -> ConfigModel:
        """
        Create/replace the singleton ConfigModel from a mapping. Returns the model.
        If replace is False and an instance exists, it is returned unchanged.
        """
        if cls._instance is not None and not replace:
            return cls._instance
        
        init_paths = cls().init_paths()
        cls._instance = ConfigModel(**{**config_dict, **init_paths})
        return cls._instance

    @classmethod
    def init_paths(cls, base: Optional[Path] = None) -> Dict[str, Path]:
        base_dir = Path(base) if base is not None else cls.WORKING_DIR
        folders = {
            "CARDS_FOLDER_PATH": base_dir / "images",
            "NEW_CARDS_FOLDER_PATH": base_dir / "newImages",
            "MUSIC_TRACKS_FOLDER_PATH": base_dir / "musicTracks",
        }
        for p in folders.values():
            p.mkdir(parents=True, exist_ok=True)

        return folders
    
    @classmethod
    def get(cls) -> ConfigModel:
        """Return the singleton model, creating a default instance if necessary."""
        if cls._instance is None:
            cls._instance = ConfigModel()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Clear the singleton (useful for tests)."""
        cls._instance = None

    # Dynamic attribute accessors that forward to ConfigModel.
    # This avoids writing per-field properties.
    def __getattr__(self, name: str) -> Any:
        model = self.get()
        if hasattr(model, name):
            return getattr(model, name)
        # This error mirrors normal attribute behavior
        raise AttributeError(f"{type(self).__name__!r} has no attribute {name!r}")

    def __setattr__(self, name: str, value: Any) -> None:
        # Allow setting of internal attributes on the class object
        if name in {"_instance", "WORKING_DIR"}:
            # set on the class object itself
            super().__setattr__(name, value)
            return
        # If the attribute exists on the pydantic model, set it there (runs validation)
        model = self.get()
        if hasattr(model, name):
            setattr(model, name, value)
            return
        # Otherwise set on the class (fallback)
        super().__setattr__(name, value)