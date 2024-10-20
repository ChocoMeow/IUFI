import time
import random
import discord, iufi, asyncio
import functions as func

from discord.ext import commands

from iufi import CardPool


# tricks - nothing, roll cooldown set to 1 hour/2 hour/3 hour later, same for quiz, match game, and trick or treat, lose x pumpkins, lose last card, show celestial like they got it and few seconds later, boom you got nothing
# treats - treat, roll cooldown reset, quiz cooldown reset, match game cooldown reset, gain x pumpkins, gain a random card, gain a random potion
class Halloween(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "🎃"
        self.invisible = False

    @commands.command(aliases=["tot"])
    #@commands.cooldown(1, 10, commands.BucketType.user)
    async def trickortreat(self, ctx: commands.Context):
        """Will you get a trick or a treat?

        **Examples:**
        qtrickortreat
        qtot
        """
        user = await func.get_user(ctx.author.id)
        if (retry := user.get("cooldown", {}).setdefault("trick_or_treat", 0)) > time.time():
            return await ctx.reply(f"{ctx.author.mention} your trick or teat will be available in <t:{round(retry)}:R>",
                                   delete_after=10)

        query = await self.get_trick_or_treat_cooldown_query()

        if random.choice([True, False]):
            trick_type = await self.get_trick_type()
            if trick_type == "nothing":
                await ctx.reply(f"{ctx.author.mention} you got nothing! 🎃")
            elif trick_type == "cooldown_increase":
                await self.on_cooldown_increase(ctx, query, user)
            elif trick_type == "pumpkins_loss":
                await self.on_pumpkin_loss(ctx, query)
            elif trick_type == "last_card_loss":
                await self.on_last_card_loss(ctx, query, user)
            elif trick_type == "celestial_fake":
                await self.on_phake_celestial(ctx)
        else:
            treat_type = await self.get_treat_type()

            if treat_type == "treat":
                await ctx.reply(f"{ctx.author.mention} you got a treat! 🎃") #need to add treats to a leaderboard
            elif treat_type == "cooldown_reset":
                await self.on_cooldown_reset(ctx, query)
            elif treat_type == "pumpkins_gain":
                await self.on_pumpkin_gain(ctx, query)
            elif treat_type == "random_card":
                await self.on_random_card_gain(ctx, query)
            elif treat_type == "random_potion":
                await self.on_potion_gain(ctx, query)

        await func.update_user(ctx.author.id, query)

    async def on_potion_gain(self, ctx, query):
        potion = random.choices(
            ["potions.speed_i", "potions.speed_ii", "potions.speed_iii", "potions.luck_i", "potions.luck_ii",
             "potions.luck_iii"],
            weights=[0.2, 0.05, 0.001, 0.2, 0.05, 0.001],
            k=1
        )[0]
        query["$inc"] = {potion: 1}
        await ctx.reply(f"{ctx.author.mention} you got a `{potion}` potion! 🎃")

    async def on_random_card_gain(self, ctx, query):
        cards = iufi.CardPool.roll(amount=1, avoid=["mystic", "celestial"])
        card = cards[0]
        query["$push"] = {"cards": card.id}
        card.change_owner(ctx.author.id)
        CardPool.remove_available_card(card)
        emoji, name = card.tier
        await ctx.reply(f"{ctx.author.mention} you got a {name} card! {emoji}")

    async def get_trick_or_treat_cooldown_query(self):
        query = {"$set": {"cooldown.trick_or_treat": time.time() + func.settings.COOLDOWN_BASE["trick_or_treat"][1]}}
        return query

    async def on_pumpkin_gain(self, ctx, query):
        gain = random.randint(1, 5)
        query["$inc"] = {"candies": gain}
        await ctx.reply(f"{ctx.author.mention} you gained {gain} pumpkins! 🎃")

    async def on_cooldown_reset(self, ctx, query):
        cooldowns = ["roll", "quiz_game", "match_game"]
        cooldown = random.choice(cooldowns)
        query["$set"][f"cooldown.{cooldown}"] = 0
        await ctx.reply(f"{ctx.author.mention} your `{cooldown}` cooldown has been reset! 🎃")

    async def get_treat_type(self):
        type = random.choices(
            ["treat", "cooldown_reset", "pumpkins_gain", "random_card", "random_potion"],
            weights=[0.1, 0.5, 0.5, 0.2, 0.1],
            k=1
        )[0]
        return type

    async def get_trick_type(self):
        type = random.choices(
            ["nothing", "cooldown_increase", "pumpkins_loss", "last_card_loss", "celestial_fake"],
            weights=[0.1, 0.5, 0.5, 0.05, 0.01],
            k=1
        )[0]
        return type

    async def on_phake_celestial(self, ctx):
        await ctx.reply(f"{ctx.author.mention} you got a Celestial card! 💫", delete_after=3)
        await asyncio.sleep(3)
        await ctx.reply(f"Just kidding! You got nothing! 🎃")

    async def on_last_card_loss(self, ctx, query, user):
        if not user["cards"]:
            await ctx.reply(f"{ctx.author.mention} you got nothing! 🎃")
        else:
            last_card = iufi.CardPool.get_card(user["cards"][-1])
            if last_card.tier not in ["mystic", "celestial"]:  # don't want to lose those
                query["$pull"] = {"cards": user["cards"][-1]}
                iufi.CardPool.add_available_card(last_card)
                await func.update_card(last_card.id, {
                    "$set": {"owner_id": None, "tag": None, "frame": None, "last_trade_time": 0}})

                await ctx.reply(f"{ctx.author.mention} you lost your last card! 🎃")
            else:
                await ctx.reply(f"{ctx.author.mention} you got nothing! 🎃")

    async def on_pumpkin_loss(self, ctx, query):
        loss = random.randint(1, 5)
        query["$inc"] = {"candies": -loss}
        await ctx.reply(f"{ctx.author.mention} you lost {loss} pumpkins! 🎃")

    async def on_cooldown_increase(self, ctx, query, user):
        cooldowns = ["roll", "quiz_game", "match_game", "trick_or_treat"]
        cooldown = random.choice(cooldowns)
        increase = random.randint(1, 3)
        prev_cooldown = user["cooldown"].get(cooldown, 0)
        if prev_cooldown > time.time():
            query["$set"][f"cooldown.{cooldown}"] = (prev_cooldown + (increase * 3_600))
        else:
            query["$set"][f"cooldown.{cooldown}"] = (time.time() + (increase * 3_600))
        await ctx.reply(
            f"{ctx.author.mention} your `{cooldown}` cooldown has been increased by {increase} hours! 🎃")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Halloween(bot))
