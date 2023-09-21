import discord, iufi
import functions as func

from discord.ext import commands

class Potion(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "🧪"

    @commands.command(aliases=["p"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def potion(self, ctx: commands.Context, *, potion_id: str):
        """Use a potion on the user"""
        if potion_id not in iufi.POTIONS_BASE:
            return await ctx.reply("The potion was not found. Please try again.")

        user = await func.get_user(ctx.author.id)
        potion = user["potions"][potion_id]

        if not potion or potion <= 0:
            return await ctx.reply("You don't have this potion.")

        potion = iufi.POTIONS_BASE[potion_id]
        
        await func.USERS_DB.update_one({"_id": ctx.author.id}, {"$inc": {"potions." + potion_id: -1}})

