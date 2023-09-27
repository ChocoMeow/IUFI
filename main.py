import discord, os, iufi
import functions as func

from random import randint
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient

ALLOWED_CATEGORY_IDS = [987352501172989993, 1144810748158165043]
IGONE_CHANNEL_IDS = [1004494130874953769, 987354694236131418]

class IUFI(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.iufi: iufi.CardPool = iufi.CardPool()

    async def on_message(self, message: discord.Message, /) -> None:
        if message.author.bot or not message.guild:
            return False

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

        if message.channel.category_id not in ALLOWED_CATEGORY_IDS:
            return False
        
        if message.channel.id in IGONE_CHANNEL_IDS:
            return False
        
        elif message.channel.id == 987354574304190476:
            if not message.content.lstrip().lower().startswith(("qi", "qcardinfo", "qil", "qcardinfolast")):
                return False
            
        await self.process_commands(message)

    async def setup_hook(self) -> None:
        all_card_data = {}

        if not ((db_name := func.tokens.mongodb_name) and (db_url := func.tokens.mongodb_url)):
            raise Exception("MONGODB_NAME and MONGODB_URL can't not be empty in .env")

        try:
            func.MONGO_DB = AsyncIOMotorClient(host=db_url, serverSelectionTimeoutMS=5000)
            await func.MONGO_DB.server_info()
            if db_name not in await func.MONGO_DB.list_database_names():
                raise Exception(f"{db_name} does not exist in your mongoDB!")
            print("Successfully connected to MongoDB!")

        except Exception as e:
            raise Exception("Not able to connect MongoDB! Reason:", e)
        
        func.CARDS_DB = func.MONGO_DB[db_name]["cards"]
        func.USERS_DB = func.MONGO_DB[db_name]["users"]
        
        async for document in func.CARDS_DB.find():
            all_card_data[document["_id"]] = document

        image_folder = os.path.join(func.ROOT_DIR, 'images')
        for category in os.listdir(image_folder):
            for image in os.listdir(os.path.join(image_folder, category)):
                filename: str = os.path.join(image_folder, category, image).split("/")[-1]
                card_id = filename.split(".")[0]

                card_data = all_card_data.get(card_id, {"_id": card_id})
                if "stars" not in card_data:
                    stars = randint(1, 5)
                    card_data["stars"] = stars
                    await func.update_card(card_id, {"$set": {"stars": stars}}, insert=True)
                self.iufi.add_card(tier=category, **card_data)

        if len(NEW_IMAGES_DIR := os.listdir(os.path.join(func.ROOT_DIR, "newImages"))):
            available_ids = [str(index) for index in range(1, 10000) if str(index) not in self.iufi._cards]
            for new_image in NEW_IMAGES_DIR:
                for category in os.listdir(image_folder):
                    if new_image.startswith(category):
                        card_id = available_ids.pop(0)
                        os.rename(os.path.join(func.ROOT_DIR, "newImages", new_image), os.path.join(image_folder, category, f"{card_id}.{'gif' if category == 'celestial' else 'jpg'}"))
                        stars = randint(1, 5)
                        await func.update_card(card_id, {"$set": {"stars": stars}}, insert=True)
                        self.iufi.add_card(_id=card_id, tier=category, stars=stars)

                        print(f"Added New Image {new_image}({category}) -> ID: {card_id}")

        for module in os.listdir(os.path.join(func.ROOT_DIR, 'cogs')):
            if module.endswith(".py"):
                await self.load_extension(f"cogs.{module[:-3]}")
                print(f"Loaded {module[:-3]}")

    async def on_ready(self):
        print("------------------")
        print(f"Logging As {self.user}")
        print(f"Bot ID: {self.user.id}")
        print("------------------")
        print(f"Discord Version: {discord.__version__}")
        print(f"Loaded {len(self.iufi._cards)} images")

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

        try:
            return await ctx.reply(error)
        except:
            pass

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
    bot.run(token=func.tokens.token)