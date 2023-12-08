import discord, time, random
import functions as func

from discord.ext import commands

GIFT_REWARDS: dict[str, float] = {
    'roll.rare': .5,
    'roll.epic': .1,
    'roll.legendary': .01,
    'candies': .1,
    'cooldown_reset': .5,
}

COOLDOWN_TYPE: tuple[str] = ("roll", "claim", "match_game")

class Gift(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "🎁"
        self.invisible = False

    @commands.command(aliases=["gg"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def givegift(self, ctx: commands.Context, member: discord.Member, amount: int = 1):
        """Give a Christmas gift to a user"""
        if amount <= 0:
            return await ctx.reply("<:IUreindeer:782937791092883496> Oh, it looks like you can't give less than one gift. After all, sharing even a single gift can bring so much joy! 🎁")

        user = await func.get_user(ctx.author.id)
        if user.get("gifts", 0) < amount:
            return await ctx.reply("<:IUreindeer:782937791092883496> Oh, it seems like you don’t have enough gifts at the moment")

        await func.update_user(member.id, {"$inc": {"gifts": amount}})
        await func.update_user(ctx.author.id, {"$inc": {"gifts": -amount}})
        await ctx.reply(f"🎁 You have given `{amount}` gifts to {member.mention}.")

    @commands.command(aliases=["og"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def opengift(self, ctx: commands.Context):
        """Open a Christmas gift"""
        user = await func.get_user(ctx.author.id)
        if user.get("gifts", 0) <= 0:
            return await ctx.reply("<:IUreindeer:782937791092883496> Oh, it seems like you haven’t received any gifts yet. But don’t worry, surprises might be just around the corner! 🎁")

        update_fields = {"$inc": {"gifts": -1}}
        reward = random.choices(list(GIFT_REWARDS.keys()), weights=list(GIFT_REWARDS.values()), k=1)[0]
        if reward == 'cooldown_reset':
            rand = random.randint(1, len(COOLDOWN_TYPE)) - 1
            update_fields["$set"] = {f"cooldown.{COOLDOWN_TYPE[rand]}": time.time()}
            msg =  f"Your `{COOLDOWN_TYPE[rand].replace('_', ' ')}` cooldown has been reset."
        
        elif reward == 'candies':
            candies = random.randint(10, 100)
            update_fields["$inc"]["candies"] = candies
            msg =  f":snowflake: You have received {candies} candies."

        elif reward.startswith('roll'):
            update_fields["$inc"][reward] = 1
            msg =  f"You have received {reward.split('.')[1].title()} roll."

        else:
            msg = "Unknown reward: {reward}"

        await func.update_user(ctx.author.id, update_fields)
        await ctx.reply(msg)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Gift(bot))