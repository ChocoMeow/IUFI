import discord, os, iufi, logging, ctypes, ctypes.util, shlex, inspect
import functions as func

from discord import app_commands
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient
from logging.handlers import TimedRotatingFileHandler

# Seconds a rejected prefix command's notice stays before it deletes itself.
LEGACY_NOTICE_LIFETIME = 8

class _MessageResponse:
    def __init__(self, interaction):
        self.interaction = interaction
        self._message = None

    def is_done(self):
        return self._message is not None

    async def send_message(self, *args, **kwargs):
        kwargs.pop("ephemeral", None)
        kwargs.pop("wait", None)
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
    def __init__(self, message, client=None):
        self.user = message.author
        self.guild = message.guild
        self.channel = message.channel
        self.channel_id = message.channel.id
        self.guild_id = message.guild.id if message.guild else None
        self.message = message
        # App command checks such as `app_commands.checks.cooldown` read these.
        self.created_at = message.created_at
        self.id = message.id
        self.client = client
        self.command = None
        self.extras = {}
        self.response = _MessageResponse(self)
        self.followup = self.response

    async def original_response(self):
        return self.response._message

class IUFI(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tree.on_error = self.on_app_command_error
        self.tree.interaction_check = self.tree_interaction_check

    async def tree_interaction_check(self, interaction: discord.Interaction) -> bool:
        func.ensure_command_channel(interaction)
        return True

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

        lookup = self.build_legacy_lookup()

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

        await self.invoke_legacy_command(message, matched_command, matched_args)

    def build_legacy_lookup(self) -> dict[str, app_commands.Command]:
        """Maps legacy message command text (e.g. `roll`, `r`, `leaderboard quiz`, `l q`) to slash commands."""
        lookup: dict[str, app_commands.Command] = {}
        subcommands: dict[str, app_commands.Command] = {}

        for command in self.tree.walk_commands():
            if isinstance(command, app_commands.Group):
                continue
            lookup[command.qualified_name.lower()] = command
            if command.parent is None:
                lookup[command.name.lower()] = command
            else:
                subcommands.setdefault(command.name.lower(), command)

        # Top level commands own the short form, so `qquiz` stays the quiz game
        # instead of whichever cog happened to load last.
        for name, command in subcommands.items():
            lookup.setdefault(name, command)

        # Short forms for grouped commands, e.g. `ql q` -> `/leaderboard quiz`.
        group_aliases = {
            "leaderboard": ["l", "lb"],
        }
        group_default_subcommands = {
            "leaderboard": "exp",
        }
        subcommand_aliases = {
            "leaderboard": {
                "e": "exp",
                "c": "candies",
                "mg": "matchgame",
                "q": "quiz",
                "m": "music",
                "bp": "battlepass",
            },
        }
        for group_name, aliases in group_aliases.items():
            group_keys = [group_name, *aliases]
            sub_aliases = subcommand_aliases.get(group_name, {})

            for key, command in list(lookup.items()):
                key_parts = key.split()
                if len(key_parts) != 2 or key_parts[0] != group_name:
                    continue

                sub_name = key_parts[1]
                sub_keys = [sub_name, *(alias for alias, target in sub_aliases.items() if target == sub_name)]
                for group_key in group_keys:
                    for sub_key in sub_keys:
                        lookup[f"{group_key} {sub_key}"] = command

            default_sub = group_default_subcommands.get(group_name)
            if default_sub and (default_command := lookup.get(f"{group_name} {default_sub}")):
                for group_key in group_keys:
                    lookup.setdefault(group_key, default_command)

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

        return lookup

    async def legacy_command_allowed(self, interaction: _MessageInteraction, command: app_commands.Command) -> tuple[bool, str | None]:
        """Run a message invocation through the command's own checks.

        Returns whether it may run and the reply to post. Message replies cannot be
        ephemeral, so callers auto-delete these instead.
        """
        groups = []
        parent = command.parent
        while parent is not None:
            groups.append(parent)
            parent = parent.parent

        denied = "You do not have permission to use this command."
        try:
            for group in reversed(groups):
                if not await discord.utils.maybe_coroutine(group.interaction_check, interaction):
                    return False, denied

            for check in getattr(command, "checks", []):
                if not await discord.utils.maybe_coroutine(check, interaction):
                    return False, denied

        except app_commands.CommandOnCooldown as error:
            seconds = max(1, round(error.retry_after))
            return False, f"{interaction.user.mention} you're on cooldown. Try again in {seconds}s."

        except app_commands.AppCommandError as error:
            return False, str(error) or denied

        except Exception as error:
            func.logger.warning(
                f"Denied legacy invocation of `{command.qualified_name}` because its permission check failed to run: {error}"
            )
            return False, denied

        return True, None

    def resolve_legacy_member(self, message: discord.Message, value: str) -> discord.Member | None:
        """Resolves a message argument (mention, raw id, username or nickname) to a member."""
        raw = value.strip()
        if not raw or not message.guild:
            return None

        # Role and channel mentions are never a member.
        if raw.startswith("<@&") or raw.startswith("<#"):
            return None

        identifier = raw[2:-1].lstrip("!") if raw.startswith("<@") and raw.endswith(">") else raw
        if identifier.isdigit():
            member_id = int(identifier)
            mentioned = discord.utils.get(message.mentions, id=member_id)
            return message.guild.get_member(member_id) or (mentioned if isinstance(mentioned, discord.Member) else None)

        # Plain text such as `@Someone` is not a real mention, so match it by name.
        name = raw.lstrip("@").lower()
        if not name:
            return None

        def matches(member: discord.Member) -> bool:
            candidates = {member.name.lower(), member.display_name.lower()}
            if member.global_name:
                candidates.add(member.global_name.lower())
            if member.nick:
                candidates.add(member.nick.lower())
            return name in candidates

        return discord.utils.find(matches, message.guild.members)

    async def invoke_legacy_command(self, message: discord.Message, matched_command: app_commands.Command, matched_args: list[str]) -> None:
        callback = matched_command.callback
        signature = inspect.signature(callback)
        kwargs = {}
        positional = list(matched_args)
        unresolved_member: tuple[str, str] | None = None

        for param_name, param in signature.parameters.items():
            if param_name in {"self", "interaction", "ctx"}:
                continue
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue
            if not positional:
                continue

            value = positional.pop(0)

            if param_name == "member" or param_name == "opponent":
                # Never fall back to the author: that silently retargets the command
                # at the player who ran it (e.g. "You are not able to trade with yourself").
                resolved = self.resolve_legacy_member(message, value)
                if resolved is None:
                    unresolved_member = (param_name, value)
                    break
                kwargs[param_name] = resolved
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

        interaction = _MessageInteraction(message, client=self)
        interaction.legacy_args = positional
        interaction.command = matched_command

        try:
            func.ensure_command_channel(interaction)
        except app_commands.CheckFailure:
            # Prefix replies are public; stay silent instead of cluttering the channel.
            return

        allowed, denial = await self.legacy_command_allowed(interaction, matched_command)
        if not allowed:
            if denial is None:
                return
            return await interaction.response.send_message(denial, delete_after=LEGACY_NOTICE_LIFETIME)

        if unresolved_member:
            param_name, value = unresolved_member
            return await interaction.response.send_message(
                f"Could not find the {param_name} `{value}`. Mention them (pick the name from Discord's autocomplete) "
                f"or use their exact username.",
                allowed_mentions=discord.AllowedMentions.none(),
                delete_after=LEGACY_NOTICE_LIFETIME,
            )

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

        elif isinstance(error, app_commands.MissingPermissions):
            message = "You do not have permission to use this command."

        elif isinstance(error, app_commands.CheckFailure):
            message = str(error) or "You do not have permission to use this command."

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
        func.STATE_DB = func.MONGO_DB[db_name]["bot_state"]

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

        func.logger.info("Startup: loading community Battle Pass milestones...")
        import events
        await events.load_community_state()

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