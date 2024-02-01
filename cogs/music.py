import iufi

from discord.ext import commands

class Music(commands.Cog):
    """Music related commands."""

    __slots__ = ('bot', 'players')

    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.emoji = "🎵"
        self.invisible = False

    @commands.command()
    async def play(self, ctx: commands.Context):
        "Start playing song"
        player: iufi.Player = ctx.guild.voice_client
        if not player:
            player = await iufi.connect_channel(ctx)

        if not player.is_user_join(ctx.author):
            return await ctx.send(f"{ctx.author.mention}, you must be in {player.channel.mention} to use voice commands. Please rejoin if you are in voice!", ephemeral=True)
        
        if not player.is_playing:
            await player.do_next()

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Music(bot))