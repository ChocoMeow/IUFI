import time

import discord, iufi, asyncio
import functions as func
from discord.ext import commands, tasks
import random

from views import GiftDropView

GIFT_REWARDS = {
    'roll.rare': .5,
    'roll.epic': .1,
    'roll.legendary': .01,
    'candies': .10,
    'cooldown_reset': .5,
}

class Gift(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "🎁"
        self.invisible = False


    @commands.command(aliases=["gg"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def givegift(self, ctx: commands.Context, member: discord.Member, amount: int = 1):
        """Give a gift to a user"""
        if amount <= 0:
            return await ctx.reply("You can't give less than 1 gift.")

        user = await func.get_user(ctx.author.id)
        if user["gift"] < amount:
            return await ctx.reply("You don't have enough gifts.")

        await func.update_user(member.id, {"$inc": {"gifts": amount}})
        await func.update_user(ctx.author.id, {"$inc": {"gifts": -amount}})
        await ctx.reply(f"You have given {amount} gifts to {member.mention}.")

    @commands.command(aliases=["og"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def opengift(self, ctx: commands.Context):
        """Open a gift"""
        user = await func.get_user(ctx.author.id)
        if user["gifts"] <= 0:
            return await ctx.reply("You don't have any gifts.")

        await func.update_user(ctx.author.id, {"$inc": {"gifts": -1}})
        reward = random.choices(list(GIFT_REWARDS.keys()), weights=list(GIFT_REWARDS.values()), k=1)[0]
        if reward == 'cooldown_reset':
            rand = random.randint(1, 3)
            await func.update_user(ctx.author.id, {"$set": {f"cooldown.{rand == 1 and 'roll' or rand == 2 and 'daily' or 'claim'}": time.time()}})
            return await ctx.reply("Your { rand == 1 and 'roll' or rand == 2 and 'daily' or 'claim' } cooldown has "
                                   "been reset.")
        if reward == 'candies':
            candies = random.randint(10, 100)
            await func.update_user(ctx.author.id, {"$inc": {"candies": candies}})
            return await ctx.reply(f"You have received {candies} candies.")

        if reward.startswith('roll'):
            await func.update_user(ctx.author.id, {"$inc": {reward: 1}})
            return await ctx.reply(f"You have received {reward.replace('roll.', '').title()} roll.")

        await ctx.reply(f"Unknown reward: {reward}")


async def setup(bot: commands.Bot) -> None:
    bot.add_cog(Gift(bot))