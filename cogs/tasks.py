import iufi
import functions as func

from discord.ext import commands, tasks

class Tasks(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.invisible = False
        self.cache_clear.start()

    def cog_unload(self):
        self.cache_clear.cancel()
    
    @tasks.loop(hours=2.0)
    async def cache_clear(self):
        func.USERS_BUFFER.clear()

        iufi.CardPool.search_image = None
        for card in iufi.CardPool._cards.values():
            card._image = None

async def setup(bot: commands.Bot):
    await bot.add_cog(Tasks(bot))