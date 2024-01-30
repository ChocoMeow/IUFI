from discord.ext import commands

class Music(commands.Cog):
    """Music related commands."""

    __slots__ = ('bot', 'players')

    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.emoji = "🎵"
        self.invisible = False

    

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Music(bot))