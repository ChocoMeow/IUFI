import discord, os, iufi, logging, ctypes, ctypes.util, shlex, inspect
import functions as func

from discord import app_commands
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient
from logging.handlers import TimedRotatingFileHandler

class _MessageResponse:
    def __init__(self, interaction):
        self.interaction = interaction
        self._message = None

    def is_done(self):
        return self._message is not None

    async def send_message(self, *args, **kwargs):
        kwargs.pop("ephemeral", None)
        self._message = await self.interaction.channel.send(*args, **kwargs)
        return self._message

    async def send(self, *args, **kwargs):
        return await self.send_message(*args, **kwargs)

    async def defer(self, *args, **kwargs):
        return None

    async def send_modal(self, modal):
        card_ids = getattr(self.interaction, "legacy_args", [])
        callback = getattr(modal, "_callback", None)
        if callback is None:
            return await self.send_message("This command cannot be used through a message command.")
        if not card_ids:
            return await self.send_message("Please provide at least one card ID.")
        await callback(self.interaction, card_ids)

class _MessageInteraction:
    def __init__(self, message):
        self.user = message.author
        self.guild = message.guild
        self.channel = message.channel
        self.message = message
        self.response = _MessageResponse(self)
        self.followup = self.response

    async def original_response(self):
        return self.response._message

class IUFI(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tree.on_error = self.on_app_command_error

    async def on_message(self, message: discord.Message, /) -> None:
        if message.author.bot or not message.guild:
            return

        if message.channel.id == func.settings.MUSIC_TEXT_CHANNEL:
            player: iufi.Player = iufi.MusicPool.get_player(message.guild.id)
            if player and message.author in player.channel.members:
                await player.check_answer(message)

        content = message.content.strip()
        prefixes = [p for p in (func.settings.BOT_PREFIX or ["q", "Q"]) if p]
        if not content or not prefixes:
            return

        matched_prefix = None
        for prefix in prefixes:
            if not content.lower().startswith(prefix.lower()):
                continue

            # Legacy q-commands are compact (e.g. qroll), not spaced (e.g. q roll).
            next_index = len(prefix)
            if len(content) > next_index and content[next_index].isspace():
                continue

            matched_prefix = prefix
            break
        if matched_prefix is None:
            return

        cmd_text = content[len(matched_prefix):].strip()
        if not cmd_text or cmd_text.startswith("/") or cmd_text.startswith("!"):
            return

        try:
            parts = shlex.split(cmd_text)
        except ValueError:
            return

        if not parts:
            return

        lookup = {}
        for command in self.tree.walk_commands():
            if isinstance(command, app_commands.Group):
                continue
            qualified = command.qualified_name.lower()
            lookup[qualified] = command
            lookup[command.name.lower()] = command

        legacy_aliases = {
            "r": "roll",
            "mg": "game",
            "q": "quiz",
            "cd": "cooldown",
            "s": "shop",
            "eq": "emojiquiz",
            "bp": "battlepass",
            "bpass": "battlepass",
            "pvptest": "pvp_test",
            "pvp_auto": "pvp_test",
            "mypity": "pity",
            "i": "cardinfo",
            "il": "cardinfolast",
            "c": "convert",
            "cl": "convertlast",
            "ca": "convertall",
            "cm": "convertmass",
            "st": "settag",
            "stl": "settaglast",
            "rt": "removetag",
            "t": "trade",
            "te": "tradeeveryone",
            "tl": "tradelast",
            "tel": "tradeeveryonelast",
            "tp": "tradepotion",
            "tpe": "tradepotioneveryone",
            "u": "upgrade",
            "sf": "setframe",
            "sfl": "setframelast",
            "rf": "removeframe",
            "up": "usepotion",
            "p": "profile",
            "sb": "setbio",
            "m": "main",
            "ml": "mainlast",
            "cc": "createcollection",
            "sc": "setcollection",
            "scl": "setcollectionlast",
            "rc": "removecollection",
            "f": "showcollection",
            "d": "daily",
            "v": "view",
            "in": "inventory",
            "qu": "quests",
            "wl": "wishlist",
            "tr": "togglereminder",
            "h": "help",
        }
        for alias, command_name in legacy_aliases.items():
            if command_name in lookup:
                lookup[alias] = lookup[command_name]

        matched_command = None
        matched_args = []
        normalized_parts = [part.lower() for part in parts]

        for key, command in sorted(lookup.items(), key=lambda kv: len(kv[0].split()), reverse=True):
            key_parts = key.split()
            if normalized_parts[:len(key_parts)] == key_parts:
                matched_command = command
                matched_args = parts[len(key_parts):]
                break

        if matched_command is None:
            base_name = parts[0].lower()
            if base_name.startswith("q") and len(base_name) > 1:
                base_name = base_name[1:]
            matched_command = lookup.get(base_name)
            matched_args = parts[1:]

        if matched_command is None:
            return

        callback = matched_command.callback
        signature = inspect.signature(callback)
        kwargs = {}
        positional = list(matched_args)

        for param_name, param in signature.parameters.items():
            if param_name in {"self", "interaction", "ctx"}:
                continue
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue

            if not positional:
                continue

            value = positional.pop(0)

            if param_name == "member" or param_name == "opponent":
                resolved = None
                if value.startswith("<@") and value.endswith(">"):
                    user_id = value[2:-1].replace("!", "")
                    resolved = message.guild.get_member(int(user_id))
                else:
                    name = value.lower()
                    resolved = discord.utils.find(
                        lambda member: member.name.lower() == name or member.display_name.lower() == name,
                        message.guild.members,
                    )
                kwargs[param_name] = resolved or message.author
                continue

            if param.annotation is int:
                try:
                    value = int(value)
                except ValueError:
                    pass
            elif param.annotation is float:
                try:
                    value = float(value)
                except ValueError:
                    pass
            elif param_name in {"tier", "level", "category", "card_id", "tag", "name", "bio", "command", "potion_name", "cooldown", "day_number", "count", "slot", "limit", "candies", "amount", "quantity", "member", "opponent"}:
                pass

            kwargs[param_name] = value

        interaction = _MessageInteraction(message)
        interaction.legacy_args = positional
        missing = [
            param_name
            for param_name, param in signature.parameters.items()
            if param_name not in {"self", "interaction", "ctx"}
            and param.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
            and param.default is inspect.Parameter.empty
            and param_name not in kwargs
        ]
        if missing:
            command_name = matched_command.qualified_name
            missing_names = ", ".join(missing)
            return await interaction.response.send_message(
                f"Missing required argument(s): `{missing_names}`. Usage: `q{command_name} ...`"
            )

        binding = getattr(matched_command, "binding", None)
        if binding is None:
            await callback(interaction, **kwargs)
        else:
            await callback(binding, interaction, **kwargs)

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