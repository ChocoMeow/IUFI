import discord, os, iufi, traceback
import functinos as func

from discord.ext import commands

class IUFI(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.iufi: iufi.CardPool = iufi.CardPool()

    async def setup_hook(self) -> None:
        all_card_data = {}

        for document in func.CARDS_DB.find():
            all_card_data[document["_id"]] = document

        image_folder = os.path.join(func.ROOT_DIR, 'images')
        for category in os.listdir(image_folder):
            for image in os.listdir(os.path.join(image_folder, category)):
                filename: str = os.path.join(image_folder, category, image).split("/")[-1]
                card_id = filename.split(".")[0]

                card_data = all_card_data.get(card_id, {"_id": card_id})
                self.iufi.add_card(tier=category, **card_data)

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
            command = f" Correct Usage: {ctx.prefix}" + (f"{ctx.command.parent.qualified_name} " if ctx.command.parent else "") + f"{ctx.command.name} {ctx.command.signature}"
            position = command.find(f"<{ctx.current_parameter.name}>") + 1
            error = f"```css\n[You are missing argument!]\n{command}\n" + " " * position + "^" * len(ctx.current_parameter.name) + "```"

        else:
            print(traceback.print_exc())
            
        try:
            return await ctx.reply(error)
        except:
            pass

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
member_cache = discord.MemberCacheFlags(
    voice=True,
    joined=False
)

bot = IUFI(
    command_prefix=["q", "Q"],
    help_command=None,
    chunk_guilds_at_startup=False,
    member_cache_flags=member_cache,
    activity=discord.Activity(type=discord.ActivityType.playing, name="IU Card Game"),
    case_insensitive=True,
    intents=intents
)
    
if __name__ == "__main__":
    bot.run(token=func.tokens.token)