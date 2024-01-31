import iufi, time
import functions as func
from discord.ext import commands
import discord
from views import ProposeView


class CoupleSystem(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "💞"
        self.invisible = False

    @commands.command(aliases=["pr"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def propose(self, ctx: commands.Context, user: discord.Member):
        """Propose to a user"""
        if user.bot:
            return await ctx.reply("You can't propose to a bot.")
        if user.id == ctx.author.id:
            return await ctx.reply("You can't propose to yourself.")

        user_data = await func.get_user(ctx.author.id)
        if user_data.get("couple_id", 0) != 0:
            return await ctx.reply("You're already in a relationship.")
        if user_data.get("event_items").get("rose", 0) <= 0:
            return await ctx.reply("You don't have a rose.Don't worry, you can get one from the shop.")

        other_user_data = await func.get_user(user.id)
        if other_user_data.get("couple_id", 0) != 0:
            return await ctx.reply("The user is already in a relationship.")

        await func.update_user(ctx.author.id, {"$inc": {"event_items.rose": -1}})
        await ctx.reply(f"{ctx.author.mention} has proposed to {user.mention} with a rose!",
                        view=ProposeView(ctx.author, user))


async def setup(bot: commands.Bot) -> None:
    if iufi.is_valentines_day():
        await bot.add_cog(CoupleSystem(bot))
