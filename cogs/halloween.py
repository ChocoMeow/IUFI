import time
import random
import discord, iufi, asyncio
import functions as func

from discord.ext import commands

from iufi import CardPool

LEADERBOARD_EMOJIS: list[str] = ["🥇", "🥈", "🥉", "🏅"]
MIN_PUMPKINS = 20
MAX_PUMPKINS = 50

def highlight_text(text: str, need: bool = True) -> str:
    if not need:
        return text + "\n"
    return "[0;1;35m" + text + " [0m\n"


class Halloween(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "🎃"
        self.invisible = False

    @commands.command(aliases=["totl"])
    async def trickortreatleaderboard(self, ctx: commands.Context):
        """Shows the leaderboard for the trick or treat event.

        **Examples:**
        qtrickortreatleaderboard
        qtotl
        """
        user = await func.get_user(ctx.author.id)
        users = await func.USERS_DB.find().sort("halloween_treats", -1).limit(10).to_list(10)
        rank = await func.USERS_DB.count_documents({'halloween_treats': {'$gt': user.get('halloween_treats', 0)}}) + 1
        embed = discord.Embed(title="🎃   Trick Or Treat Leaderboard", color=discord.Color.random())
        embed.description = f"**Your current position is `{rank}`**\n"

        description = ""
        for index, top_user in enumerate(users):
            level = top_user.get("halloween_treats", 0)
            member = self.bot.get_user(top_user['_id'])

            if member:
                description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + highlight_text(
                    f"{func.truncate_string(member.display_name):<18} {level:>5} 🍬", member == ctx.author)

        if rank > len(users):
            level = user.get('halloween_treats', 0)
            description += ("┇\n" if rank > len(users) + 1 else "") + f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(
                f"{func.truncate_string(ctx.author.display_name):<18} {level:>5} 🍬")

        if not description:
            description = "The leaderboard is currently empty."

        embed.description += f"```ansi\n{description}```"
        embed.set_thumbnail(url=icon.url if (icon := ctx.guild.icon) else None)

        await ctx.reply(embed=embed)

    @commands.command(aliases=["tot"])
    # @commands.cooldown(1, 10, commands.BucketType.user)
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
            if trick_type == "cooldown_increase":
                await self.on_cooldown_increase(ctx, query, user)
            elif trick_type == "pumpkins_loss":
                await self.on_pumpkin_loss(ctx, query, user)
            elif trick_type == "last_card_loss":
                await self.on_last_card_loss(ctx, query, user)
            elif trick_type == "celestial_fake":
                await self.on_phake_celestial(ctx)
        else:
            treat_type = await self.get_treat_type()

            if treat_type == "treat":
                await self.on_treat(ctx, query)
            elif treat_type == "cooldown_reset":
                await self.on_cooldown_reset(ctx, query)
            elif treat_type == "pumpkins_gain":
                await self.on_pumpkin_gain(ctx, query)
            elif treat_type == "random_card":
                await self.on_random_card_gain(ctx, query, user)
            elif treat_type == "random_potion":
                await self.on_potion_gain(ctx, query)
            elif treat_type == "random_roll":
                await self.on_random_roll(ctx, query)

        await func.update_user(ctx.author.id, query)

    async def on_treat(self, ctx, query):
        query["$inc"] = {"halloween_treats": 1}
        await ctx.reply(f"{ctx.author.mention} you got a treat! 🍬")

    async def on_random_roll(self, ctx, query):
        roll_type = random.choices(
            ["roll.rare", "roll.epic", "roll.legendary"],
            weights=[0.2, 0.05, 0.001],
            k=1
        )[0]
        query["$inc"] = {roll_type: 1}
        roll_message = roll_type.split(".")[1]
        await ctx.reply(f"{ctx.author.mention} you got a `{roll_message}` roll! 🎃")

    async def on_potion_gain(self, ctx, query):
        potion = random.choices(
            ["potions.speed_i", "potions.speed_ii", "potions.speed_iii", "potions.luck_i", "potions.luck_ii",
             "potions.luck_iii"],
            weights=[0.2, 0.05, 0.001, 0.2, 0.05, 0.001],
            k=1
        )[0]
        query["$inc"] = {potion: 1}
        potion = potion.split(".")[1]
        potion = potion.replace("_", " ").capitalize()
        await ctx.reply(f"{ctx.author.mention} you got a `{potion}` potion! 🎃")

    async def on_random_card_gain(self, ctx, query, user):
        if len(user["cards"]) >= func.settings.MAX_CARDS:
            return await self.on_random_roll(ctx, query)
        cards = iufi.CardPool.roll(amount=1, avoid=["mystic", "celestial"])
        card = cards[0]
        query["$push"] = {"cards": card.id}
        card.change_owner(ctx.author.id)
        CardPool.remove_available_card(card)
        await func.update_card(card.id, {"$set": {"owner_id": ctx.author.id}})
        emoji, name = card.tier
        await ctx.reply(f"{ctx.author.mention} you got a {name} card! {emoji}")
        embed = discord.Embed(title=f"ℹ️ Card Info", color=0x949fb8)
        embed.description = f"```{card.display_id}\n" \
                            f"{card.display_tag}\n" \
                            f"{card.display_frame}\n" \
                            f"{card.tier[0]} {card.tier[1].capitalize()}\n" \
                            f"{card.display_stars}```\n" \
                            "**Owned by: **" + (f"<@{card.owner_id}>" if card.owner_id else "None")

        embed.set_image(url=f"attachment://image.{card.format}")
        await ctx.reply(file=discord.File(await card.image_bytes(True), filename=f"image.{card.format}"), embed=embed)

    async def get_trick_or_treat_cooldown_query(self):
        query = {"$set": {"cooldown.trick_or_treat": time.time() + func.settings.COOLDOWN_BASE["trick_or_treat"][1]}}
        return query

    async def on_pumpkin_gain(self, ctx, query):
        gain = random.randint(MIN_PUMPKINS, MAX_PUMPKINS)
        query["$inc"] = {"candies": gain}
        await ctx.reply(f"{ctx.author.mention} you gained {gain} pumpkins! 🎃")

    async def on_cooldown_reset(self, ctx, query):
        cooldowns = ["roll", "quiz_game", "match_game"]
        cooldown = random.choice(cooldowns)
        query["$set"][f"cooldown.{cooldown}"] = 0
        await ctx.reply(f"{ctx.author.mention} your `{cooldown}` cooldown has been reset! 🎃")

    async def get_treat_type(self):
        type = random.choices(
            ["treat", "cooldown_reset", "pumpkins_gain", "random_card", "random_potion", "random_roll"],
            weights=[0.1, 0.5, 0.5, 0.2, 0.1, 0.2],
            k=1
        )[0]
        return type

    async def get_trick_type(self):
        type = random.choices(
            ["cooldown_increase", "pumpkins_loss", "last_card_loss", "celestial_fake"],
            weights=[0.5, 0.5, 0.05, 0.01],
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

    async def on_pumpkin_loss(self, ctx, query, user):
        if user.get("candies", 0) <= 0:
            return await ctx.reply(f"{ctx.author.mention} you got nothing! 🎃")
        loss = random.randint(MIN_PUMPKINS, MAX_PUMPKINS)
        loss = min(loss, user["candies"])
        query["$inc"] = {"candies": -loss}
        await ctx.reply(f"{ctx.author.mention} you lost {loss} pumpkins! 🎃")

    async def on_cooldown_increase(self, ctx, query, user):
        cooldowns = ["roll", "quiz_game", "match_game", "trick_or_treat"]
        cooldown = random.choice(cooldowns)
        increase = random.randint(1, 3)
        increase_multiplier = 600  # 10 minutes
        if cooldown == "match_game":
            increase_multiplier = 3_600  # 1 hour
        prev_cooldown = user["cooldown"].get(cooldown, 0)
        if prev_cooldown > time.time():
            query["$set"][f"cooldown.{cooldown}"] = (prev_cooldown + (increase * increase_multiplier))
        else:
            query["$set"][f"cooldown.{cooldown}"] = (time.time() + (increase * increase_multiplier))
        if cooldown == "match_game" or cooldown == "trick_or_treat":
            hour = "hour" if increase == 1 else "hours"
            message = f"{ctx.author.mention} your `{cooldown}` cooldown has been increased by {increase} {hour}! 🎃"
        else:
            message = f"{ctx.author.mention} your `{cooldown}` cooldown has been increased by {increase * 10} minutes! 🎃"
        await ctx.reply(message)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Halloween(bot))
