import discord, os, iufi, logging, ctypes, ctypes.util
import functions as func

from discord import app_commands
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient
from logging.handlers import TimedRotatingFileHandler

class IUFI(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tree.on_error = self.on_app_command_error

    async def on_message(self, message: discord.Message, /) -> None:
        # All commands are slash commands now; on_message only forwards music quiz answers.
        if message.author.bot or not message.guild:
            return

        if message.channel.id == func.settings.MUSIC_TEXT_CHANNEL:
            player: iufi.Player = iufi.MusicPool.get_player(message.guild.id)
            if player and message.author in player.channel.members:
                await player.check_answer(message)

    async def on_app_command_error(self, interaction: discord.Interaction, exception: app_commands.AppCommandError, /) -> None:
        error = getattr(exception, 'original', exception)

        if isinstance(error, app_commands.CommandOnCooldown):
            message = str(error)

        elif isinstance(error, (app_commands.MissingPermissions, app_commands.CheckFailure)):
            message = "You do not have permission to use this command."

        elif issubclass(error.__class__, iufi.IUFIException):
            message = str(error)

        else:
            message = "An unexpected error occurred. Please try again later!"
            cmd_name = interaction.command.qualified_name if interaction.command else "unknown"
            func.logger.error(
                f"An unexpected error occurred in the `{cmd_name}` command on the {interaction.guild.name}({interaction.guild.id}) executed by {interaction.user.name}({interaction.user.id}).",
                exc_info=exception
            )

        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.HTTPException:
            pass

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
        func.logger.info("Startup: connecting to database...")
        # Connecting to MongoDB
        await self.connect_db()

        func.logger.info("Startup: loading card pool...")
        await iufi.CardPool.fetch_data()
        func.logger.info("Startup: processing new cards folder...")
        await iufi.CardPool.process_new_cards()
        func.logger.info("Startup: loading quiz question pool...")
        await iufi.QuestionPool.fetch_data()
        func.logger.info("Startup: loading music question pool...")
        await iufi.MusicPool.fetch_data()

        try:
            if not discord.opus.is_loaded():
                opus_library = ctypes.util.find_library('opus')
                discord.opus.load_opus(func.settings.OPUS_PATH or opus_library)
        except Exception as e:
            func.logger.error("Not able to load opus!", exc_info=e)

        # Load cog modules
        func.logger.info("Startup: loading cogs...")
        for module in os.listdir(os.path.join(func.ROOT_DIR, 'cogs')):
            if module.endswith(".py"):
                await self.load_extension(f"cogs.{module[:-3]}")
                func.logger.info(f"Loaded {module[:-3]}")

        func.logger.info("Startup: syncing slash commands...")
        synced = await self.tree.sync()
        func.logger.info(f"Synced {len(synced)} slash commands globally.")

        func.logger.info("Startup: setup_hook complete, waiting for Discord READY event...")

    async def on_ready(self):
        func.logger.info("------------------")
        func.logger.info(f"Logging As {self.user}")
        func.logger.info(f"Bot ID: {self.user.id}")
        func.logger.info("------------------")
        func.logger.info(f"Discord Version: {discord.__version__}")
        func.logger.info(f"Loaded {len(iufi.CardPool._cards)} images")
        func.logger.info(f"Loaded {len(iufi.QuestionPool._questions)} questions")
        func.logger.info(f"Loaded {len(iufi.MusicPool._questions)} questions")

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
    command_prefix=func.settings.BOT_PREFIX,  # required by commands.Bot ctor but unused; all commands are slash commands
    help_command=None,
    chunk_guilds_at_startup=False,
    activity=discord.Activity(type=discord.ActivityType.listening, name="/help"),
    case_insensitive=True,
    intents=intents
)

# Run the bot if this script is executed directly
if __name__ == "__main__":
    bot.run(token=func.tokens.token, root_logger=True)