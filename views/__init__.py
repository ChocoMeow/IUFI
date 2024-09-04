from discord.ext import commands

class ButtonOnCooldown(commands.CommandError):
    def __init__(self, retry_after: float) -> None:
        self.retry_after = retry_after
        
from .roll import RollView
from .matchgame import MatchGame
from .quiz import QuizView, ResetAttemptView, QUIZ_SETTINGS
from .frame import FrameView
from .photocard import PhotoCardView
from .shop import ShopView
from .trade import TradeView
from .confirm import ConfirmView
from .collection import CollectionView
from .help import HelpView
from .debugs import DebugView
from .drop import DropView
from .anniversarysell import AnniversarySellView