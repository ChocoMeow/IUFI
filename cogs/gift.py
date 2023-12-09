import discord, time, random
import functions as func

from discord.ext import commands

GIFT_REWARDS: dict[str, float] = {
    'roll.rare': .5,
    'roll.epic': .1,
    'roll.legendary': .01,
    'candies': .5,
    'cooldown_reset': .2,
    'potion.speed_i': .1,
    'potion.speed_ii': .05,
    'potion.speed_iii': .01,
    'potion.luck_i': .1,
    'potion.luck_ii': .05,
    'potion.luck_iii': .01,
}

COOLDOWN_TYPE: tuple[str] = ("roll", "claim", "match_game")


class Gift(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "🎁"
        self.invisible = False

    @commands.command(aliases=["gg"])
    @commands.cooldown(1, 1, commands.BucketType.user)
    async def givegift(self, ctx: commands.Context, member: discord.Member, amount: int = 1):
        """Give a Christmas gift to a user"""
        if amount <= 0:
            return await ctx.reply(
                "<:IUreindeer:782937791092883496> Oh, it looks like you can't give less than one gift. After all, sharing even a single gift can bring so much joy! 🎁")

        user = await func.get_user(ctx.author.id)
        if user.get("gifts", 0) < amount:
            return await ctx.reply(
                "<:IUreindeer:782937791092883496> Oh, it seems like you don’t have enough gifts at the moment")

        await func.update_user(member.id, {"$inc": {"gifts": amount}})
        await func.update_user(ctx.author.id, {"$inc": {"gifts": -amount}})
        await ctx.reply(f"🎁 {ctx.author.mention} <:IUsanta:786519160083447838> has sent {member.mention} a festive gift🎁! Unwrap it to discover the joy within. Merry Christmas!🎄")

    @commands.command(aliases=["og"])
    @commands.cooldown(1, 1, commands.BucketType.user)
    async def opengift(self, ctx: commands.Context):
        """Open a Christmas gift"""
        user = await func.get_user(ctx.author.id)
        if user.get("gifts", 0) <= 0:
            return await ctx.reply(
                "<:IUreindeer:782937791092883496> Oh, it seems like you haven’t received any gifts yet. But don’t "
                "worry, surprises might be just around the corner! 🎁")

        update_fields = {"$inc": {"gifts": -1}}
        reward = random.choices(list(GIFT_REWARDS.keys()), weights=list(GIFT_REWARDS.values()), k=1)[0]
        if reward == 'cooldown_reset':
            rand = random.choice(COOLDOWN_TYPE)
            update_fields["$set"] = {f"cooldown.{rand}": time.time()}
            msg = f"Tearing off the festive wrapping, you reveal a rare item and it resets your `{rand.replace('_', ' ')}` cooldown"

        elif reward == 'candies':
            candies = random.choices(
                [random.randint(1, 20), random.randint(20, 50), random.randint(50, 80), random.randint(80, 100)],
                weights=[90, 8, 1.5, 0.5], k=1)[0]
            update_fields["$inc"]["candies"] = candies
            msg = f"As you open the gift, a burst of snowflakes fly out and you catch `{candies} :snowflake:`"

        elif reward.startswith('roll'):
            update_fields["$inc"][reward] = 1
            roll_type = reward.split('.')[1]
            emojis = ("🌸", "💎", "👑")
            emoji = emojis[0] if roll_type == 'rare' else emojis[1] if roll_type == 'epic' else emojis[2]
            msg = f"You're unwrapping the gift, and inside, you discover a `{reward.split('.')[1].title()} roll` {emoji}"

        elif reward.startswith('potion'):
            update_fields["$inc"][reward] = 1
            msg = f"As you tear away the wrapping paper, a burst of confetti reveals a `{reward.split('.')[1].split('_')[0].title()} {reward.split('.')[1].split('_')[1].title()} potion`."

        else:
            msg = f"Unknown reward: {reward}"

        await func.update_user(ctx.author.id, update_fields)
        await ctx.reply(msg)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Gift(bot))
