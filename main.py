import discord, os, iufi, logging, ctypes, ctypes.util
import functions as func

from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient
from logging.handlers import TimedRotatingFileHandler

class IUFI(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def on_message(self, message: discord.Message, /) -> None:
        # Ignore messages from bots or outside of guilds
        if message.author.bot or not message.guild:
            return False

        # Handle messages in the music text channel
        if message.channel.id == func.settings.MUSIC_TEXT_CHANNEL:
            cmd = message.content.split(" ")[0].lower()
            if any(cmd.startswith(prefix + 'l') for prefix in bot.command_prefix):
                return await self.process_commands(message)

            player: iufi.Player = iufi.MusicPool.get_player(message.guild.id)
            if player and message.author in player.channel.members:
                await player.check_answer(message)

            return False
        
        # Check if the channel is allowed for the game
        if message.channel.category_id not in func.settings.ALLOWED_CATEGORY_IDS:
            return False
        
        # Ignore messages in certain channels
        if message.channel.id in func.settings.IGNORE_CHANNEL_IDS:
            return False
        
        # Validate commands for a market channel
        elif message.channel.id == func.settings.MARKET_CHANNEL:
            cmd = message.content.split(" ")[0].lower()
            valid_commands = {"i", "t", "cardinfo"}
            if not any(cmd.startswith(prefix + command) for prefix in bot.command_prefix for command in valid_commands):
                return False
        
        # Process commands normally
        await self.process_commands(message)

    async def connect_db(self) -> None:
        if not ((db_name := func.tokens.mongodb_name) and (db_url := func.tokens.mongodb_url)):
            raise Exception("MONGODB_NAME and MONGODB_URL can't not be empty in .env")

        try:
            # Establish a connection to the MongoDB server
            func.MONGO_DB = AsyncIOMotorClient(host=db_url, serverSelectionTimeoutMS=5000)
            await func.MONGO_DB.server_info()

            # Check if the specified database exists
            if db_name not in await func.MONGO_DB.list_database_names():
                raise Exception(f"{db_name} does not exist in your mongoDB!")
            
            func.logger.info(f"Successfully connected to [{db_name}] MongoDB!")

        except Exception as e:
            raise Exception("Not able to connect MongoDB! Reason:", e)
        
        # Initialize database collections
        func.CARDS_DB = func.MONGO_DB[db_name]["cards"]
        func.USERS_DB = func.MONGO_DB[db_name]["users"]
        func.QUESTIONS_DB = func.MONGO_DB[db_name]["questions"]
        func.MUSIC_DB = func.MONGO_DB[db_name]["musics"]

    async def setup_hook(self) -> None:
        # Connecting to MongoDB
        await self.connect_db()

        await iufi.CardPool.fetch_data()
        await iufi.CardPool.process_new_cards()
        await iufi.QuestionPool.fetch_data()
        await iufi.MusicPool.fetch_data()

        try:
            if not discord.opus.is_loaded():
                opus_library = ctypes.util.find_library('opus')
                discord.opus.load_opus(func.settings.OPUS_PATH or opus_library)
        except Exception as e:
            func.logger.error("Not able to load opus!", exc_info=e)

        # Load cog modules
        for module in os.listdir(os.path.join(func.ROOT_DIR, 'cogs')):
            if module.endswith(".py"):
                await self.load_extension(f"cogs.{module[:-3]}")
                func.logger.info(f"Loaded {module[:-3]}")

    async def on_ready(self):
        func.logger.info("------------------")
        func.logger.info(f"Logging As {self.user}")
        func.logger.info(f"Bot ID: {self.user.id}")
        func.logger.info("------------------")
        func.logger.info(f"Discord Version: {discord.__version__}")
        func.logger.info(f"Loaded {len(iufi.CardPool._cards)} images")
        func.logger.info(f"Loaded {len(iufi.QuestionPool._questions)} questions")
        func.logger.info(f"Loaded {len(iufi.MusicPool._questions)} questions")

    async def on_command_error(self, ctx: commands.Context, exception, /) -> None:
        error = getattr(exception, 'original', exception)
        if ctx.interaction:
            error = getattr(error, 'original', error)

        if isinstance(error, commands.CommandNotFound):
            return

        elif isinstance(error, (commands.CommandOnCooldown, commands.MissingPermissions, commands.RangeError, commands.BadArgument)):
            pass

        elif isinstance(error, (commands.MissingRequiredArgument, commands.MissingRequiredAttachment)):
            return await ctx.reply(embed=func.create_help_embed(ctx))

        elif not issubclass(error.__class__, iufi.IUFIException):
            error = "An unexpected error occurred. Please try again later!"
            func.logger.error(
                f"An unexpected error occurred in the `{ctx.command.name}` command on the {ctx.guild.name}({ctx.guild.id}) executed by {ctx.author.name}({ctx.author.id}).",
                exc_info=exception
            )
           
        try:
            return await ctx.reply(error)
        except:
            pass

# Load IUFI Settings
func.settings.load()

# Initialize logging settings for the bot to ensure proper monitoring and debugging
LOG_SETTINGS = func.settings.LOGGING
if (LOG_FILE := LOG_SETTINGS.get("file", {})).get("enable", True):
    log_path = os.path.abspath(LOG_FILE.get("path", "./logs"))
    if not os.path.exists(log_path):
        os.makedirs(log_path)

    file_handler = TimedRotatingFileHandler(filename=f'{log_path}/iufi.log', encoding="utf-8", backupCount=LOG_SETTINGS.get("max-history", 30), when="d")
    file_handler.namer = lambda name: name.replace(".log", "") + ".log"
    file_handler.setFormatter(logging.Formatter('{asctime} [{levelname:<8}] {name}: {message}', '%Y-%m-%d %H:%M:%S', style='{'))

    for log_name, log_level in LOG_SETTINGS.get("level", {}).items():
        _logger = logging.getLogger(log_name)
        _logger.setLevel(log_level)
        
    logging.getLogger().addHandler(file_handler)

# Configure the Discord intents for the bot
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# Initialize the bot with specified parameters
bot = IUFI(
    command_prefix=func.settings.BOT_PREFIX,
    help_command=None,
    chunk_guilds_at_startup=True,
    activity=discord.Activity(type=discord.ActivityType.listening, name=f"{func.settings.BOT_PREFIX[0]}help"),
    case_insensitive=True,
    intents=intents
)

# Run the bot if this script is executed directly
if __name__ == "__main__":
    bot.run(token=func.tokens.token, root_logger=True)