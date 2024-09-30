import discord, os, iufi
import discord, os, iufi, logging
import functions as func

from random import randint
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient
from logging.handlers import TimedRotatingFileHandler

class IUFI(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.iufi: iufi.CardPool = iufi.CardPool()
        self.questions: iufi.QuestionPool = iufi.QuestionPool()

    async def on_message(self, message: discord.Message, /) -> None:
        if message.author.bot or not message.guild:
            return False

        if message.channel.id == func.settings.MUSIC_TEXT_CHANNEL:
            player: iufi.Player = message.guild.voice_client
            if player:
                await player.check_answer(message)

        if message.channel.id == 1147547592469782548:
            emojis = ()
            for attachment in message.attachments:
                if attachment.filename.endswith((".png", ".jpg")):
                    emojis = ("🥬", "🌸", "💎", "👑")
                    break
                elif attachment.filename.endswith(".gif"):
                    emojis = ("✅", "❌")
                    break
            
            for emoji in emojis:
                await message.add_reaction(emoji)

        if message.channel.category_id not in func.settings.ALLOWED_CATEGORY_IDS:
            return False
        
        if message.channel.id in func.settings.IGNORE_CHANNEL_IDS:
            return False
        
        elif message.channel.id == 987354574304190476:
            if message.content.split(" ")[0].lower() not in ("qi", "qcardinfo", "qil", "qcardinfolast", "qt", "qtl", "qtade", "qtadelast", "qte", "qtradeeveryone", "qtel", "qtradeeveryonelast"):
                return False
            
        await self.process_commands(message)

    async def connect_db(self) -> None:
        if not ((db_name := func.tokens.mongodb_name) and (db_url := func.tokens.mongodb_url)):
            raise Exception("MONGODB_NAME and MONGODB_URL can't not be empty in .env")

        try:
            func.MONGO_DB = AsyncIOMotorClient(host=db_url, serverSelectionTimeoutMS=5000)
            await func.MONGO_DB.server_info()
            if db_name not in await func.MONGO_DB.list_database_names():
                raise Exception(f"{db_name} does not exist in your mongoDB!")
            func.logger.info(f"Successfully connected to [{db_name}] MongoDB!")

        except Exception as e:
            raise Exception("Not able to connect MongoDB! Reason:", e)
        
        func.CARDS_DB = func.MONGO_DB[db_name]["cards"]
        func.USERS_DB = func.MONGO_DB[db_name]["users"]
        func.QUESTIONS_DB = func.MONGO_DB[db_name]["questions"]
        func.MUSIC_DB = func.MONGO_DB[db_name]["musics"]

    async def setup_hook(self) -> None:
        await self.connect_db()

        all_card_data: dict[str, dict] = {doc["_id"]: doc async for doc in func.CARDS_DB.find()}
        image_folder = os.path.join(func.ROOT_DIR, 'images')

        for category in os.listdir(image_folder):
            if category.startswith("."): continue
            for image in os.listdir(os.path.join(image_folder, category)):
                card_id = os.path.basename(image).split(".")[0]
                card_data = all_card_data.get(card_id, {"_id": card_id})

                if "stars" not in card_data:
                    card_data["stars"] = (stars := randint(1, 5))
                    await func.update_card(card_id, {"$set": {"stars": stars}}, insert=True)
                self.iufi.add_card(tier=category, **card_data)

        if len(NEW_IMAGES_DIR := os.listdir(os.path.join(func.ROOT_DIR, "newImages"))):
            available_ids = [str(index) for index in range(1, 10000) if str(index) not in self.iufi._cards]
            for new_image in NEW_IMAGES_DIR:
                for category in os.listdir(image_folder):
                    if new_image.startswith(category):
                        card_id = available_ids.pop(0)
                        os.rename(os.path.join(func.ROOT_DIR, "newImages", new_image), os.path.join(image_folder, category, f"{card_id}.webp"))
                        await func.update_card(card_id, {"$set": {"stars": (stars := randint(1, 5))}}, insert=True)
                        self.iufi.add_card(_id=card_id, tier=category, stars=stars)

                        func.logger.info(f"Added New Image {new_image}({category}) -> ID: {card_id}")

        async for question_doc in func.QUESTIONS_DB.find():
            iufi.QuestionPool.add_question(iufi.Question(**question_doc))

        await iufi.MusicPool.fetch_data()
        
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
        func.logger.info(f"Loaded {len(self.iufi._cards)} images")
        func.logger.info(f"Loaded {len(self.questions._questions)} questions")

    async def on_command_error(self, ctx: commands.Context, exception, /) -> None:
        error = getattr(exception, 'original', exception)
        if ctx.interaction:
            error = getattr(error, 'original', error)

        if isinstance(error, commands.CommandNotFound):
            return

        elif isinstance(error, (commands.CommandOnCooldown, commands.MissingPermissions, commands.RangeError, commands.BadArgument)):
            pass

        elif isinstance(error, (commands.MissingRequiredArgument, commands.MissingRequiredAttachment)):
            command = f"{ctx.prefix}" + (f"{ctx.command.parent.qualified_name} " if ctx.command.parent else "") + f"{ctx.command.name} {ctx.command.signature}"
            position = command.find(f"<{ctx.current_parameter.name}>") + 1
            description = f"**Correct Usage:**\n```{command}\n" + " " * position + "^" * len(ctx.current_parameter.name) + "```\n"
            if ctx.command.aliases:
                description += f"**Aliases:**\n`{', '.join([f'{ctx.prefix}{alias}' for alias in ctx.command.aliases])}`\n\n"
            description += f"**Description:**\n{ctx.command.help}\n\u200b"

            embed = discord.Embed(description=description, color=discord.Color.random())
            embed.set_footer(icon_url=ctx.me.display_avatar.url, text="More Help: Ask the staff!")
            return await ctx.reply(embed=embed)

        elif not issubclass(error.__class__, iufi.IUFIException):
            error = "An unexpected error occurred. Please try again later!"
            func.logger.error(f"An unexpected error occurred in the `{ctx.command.name}` command on the {ctx.guild.name}({ctx.guild.id}) executed by {ctx.author.name}({ctx.author.id}).", exc_info=exception)
           
        try:
            return await ctx.reply(error)
        except:
            pass

func.settings.load()
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

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = IUFI(
    command_prefix=["q", "Q"],
    help_command=None,
    chunk_guilds_at_startup=True,
    activity=discord.Activity(type=discord.ActivityType.listening, name="qhelp"),
    case_insensitive=True,
    intents=intents
)
  
if __name__ == "__main__":
    bot.run(token=func.tokens.token, root_logger=True)