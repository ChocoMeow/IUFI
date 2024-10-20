import time
import random
import discord, iufi, asyncio
import functions as func

from discord.ext import commands


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

        query = {"$set": {"cooldown.trick_or_treat": time.time() + func.settings.COOLDOWN_BASE["trick_or_treat"][1]}}

        if random.choice([True, False]):
            type = random.choices(
                ["nothing", "cooldown_increase", "pumpkins_loss", "last_card_loss", "celestial_fake"],
                weights=[0.1, 0.5, 0.5, 0.05, 0.01],
                k=1
            )[0]
            if type == "nothing":
                await ctx.reply(f"{ctx.author.mention} you got nothing! 🎃")
            elif type == "cooldown_increase":
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
            elif type == "pumpkins_loss":
                loss = random.randint(1, 5)
                query["$inc"] = {"candies": -loss}
                await ctx.reply(f"{ctx.author.mention} you lost {loss} pumpkins! 🎃")
            elif type == "last_card_loss":
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
            elif type == "celestial_fake":
                await ctx.reply(f"{ctx.author.mention} you got a Celestial card! 💫" , delete_after=3)
                await asyncio.sleep(3)
                await ctx.reply(f"   Just kidding! You got nothing! 🎃")
        else:
            type = random.choices(
                ["treat", "cooldown_reset", "pumpkins_gain", "random_card", "random_potion"],
                weights=[0.1, 0.5, 0.5, 0.2, 0.1],
                k=1
            )[0]

            if type == "treat":
                await ctx.reply(f"{ctx.author.mention} you got a treat! 🎃")
            elif type == "cooldown_reset":
                cooldowns = ["roll", "quiz_game", "match_game"]
                cooldown = random.choice(cooldowns)
                query["$set"][f"cooldown.{cooldown}"] = 0
                await ctx.reply(f"{ctx.author.mention} your `{cooldown}` cooldown has been reset! 🎃")
            elif type == "pumpkins_gain":
                gain = random.randint(1, 5)
                query["$inc"] = {"candies": gain}
                await ctx.reply(f"{ctx.author.mention} you gained {gain} pumpkins! 🎃")
            elif type == "random_card":
                #implement this
                pass
            elif type == "random_potion":
                #implement this
                pass

        await func.update_user(ctx.author.id, query)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Halloween(bot))
