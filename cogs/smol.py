import time
import random
import discord, iufi, asyncio
from discord import Message

import functions as func

from typing import (
    Dict,
    Any,
    Union,
    Callable, Coroutine
)
from discord.ext import commands

from iufi import CardPool

LEADERBOARD_EMOJIS: list[str] = ["🥇", "🥈", "🥉", "🏅"]
MIN_PUMPKINS = 20
MAX_PUMPKINS = 50
SMOL_ID = 1223531350972174337
MASHOU_ID = 160849769848242176


def highlight_text(text: str, need: bool = True) -> str:
    if not need:
        return text + "\n"
    return "[0;1;35m" + text + " [0m\n"


class Smol(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.emoji: str = "🎂"
        self.invisible: bool = False

        self.curses: Dict[str, Dict[str, Union[Callable, float]]] = {
            "cooldown_increase": {
                "func": self.on_cooldown_increase,
                "weight": .5
            },
            "starcandies_loss": {
                "func": self.on_starcandies_loss,
                "weight": .5
            },
            "last_card_loss": {
                "func": self.on_last_card_loss,
                "weight": .05
            }
        }

        self.blessings: Dict[str, Dict[str, Union[Callable, float]]] = {
            "cooldown_reset": {
                "func": self.on_cooldown_reset,
                "weight": .5
            },
            "pumpkins_gain": {
                "func": self.on_starcandies_gain,
                "weight": .5
            },
            "random_card": {
                "func": self.on_random_card_gain,
                "weight": .2
            },
            "random_potion": {
                "func": self.on_potion_gain,
                "weight": .1
            },
            "random_roll": {
                "func": self.on_random_roll,
                "weight": .1
            }
        }

    @commands.command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def rob(self, ctx: commands.Context, amount : int):
        if ctx.author.id == SMOL_ID:
            return await ctx.reply("You can't rob yourself Smol!", delete_after=10)
        user = await func.get_user(ctx.author.id)
        if (retry := user.get("cooldown", {}).setdefault("rob", 0)) > time.time():
            return await ctx.reply(f"{ctx.author.mention} You can rob Smol in <t:{round(retry)}:R>",delete_after=10)
        query = {"$set": {"cooldown.rob": time.time() + func.settings.COOLDOWN_BASE["rob"][1]}}
        #check if user has the specified amount, then check if smol has enough amount, then do 50/50 chance, max amount 1000
        if amount > 1000:
            return await ctx.reply(f"{ctx.author.mention} You can't rob more than 1000 🍬 at a time!", delete_after=10)

        if amount <= 0:
            return await ctx.reply(f"{ctx.author.mention} Should I rob you instead?", delete_after=10)

        if user["candies"] < amount:
            return await ctx.reply(f"{ctx.author.mention} You don't have enough 🍬 to rob Smol!", delete_after=10)
        smol = await func.get_user(SMOL_ID)
        smol_query = {}
        if smol["candies"] < amount:
            return await ctx.reply(f"{ctx.author.mention} Smol doesn't have enough 🍬 to rob!", delete_after=10)
        smol_discord = self.bot.get_user(SMOL_ID)
        is_success = random.choice([True, False])
        if is_success:
            query["$inc"] = {"candies": amount}
            smol_query["$inc"] = {"candies": -amount}
            await ctx.reply(f"{smol_discord.mention} got robbed by {ctx.author.mention} for {amount} 🍬! 🎉")
        else:
            query["$inc"] = {"candies": -amount}
            smol_query["$inc"] = {"candies": amount}
            await ctx.reply(f"{ctx.author.mention} got caught trying to rob {smol_discord.mention} and lost {amount} 🍬 to smol!")
        await func.update_user(ctx.author.id, query)
        await func.update_user(SMOL_ID, smol_query)
        func.logger.info(f"User {ctx.author.name}({ctx.author.id}) robbed {smol_discord.id} for {amount} candies.")

    @commands.command(aliases=["sl"])
    async def smolleaderboard(self, ctx: commands.Context):
        """Shows the leaderboard for the birthday event.

        **Examples:**
        qbirthdayleaderboard
        qsl
        """
        user = await func.get_user(ctx.author.id)
        users = await func.USERS_DB.find().sort("game_state.birthday_event.wishes", -1).limit(10).to_list(10)
        rank = await func.USERS_DB.count_documents({'game_state.birthday_event.wishes': {
            '$gt': user.get('game_state', {}).get('birthday_event', {}).get('wishes', 0)}}) + 1
        embed = discord.Embed(title="🎉   Birthday Wishes Leaderboard", color=discord.Color.random())
        embed.description = f"**Your current position is `{rank}`**\n"
        rank_1_user = None
        description = ""
        for index, top_user in enumerate(users):
            level = top_user.get('game_state', {}).get('birthday_event', {}).get('wishes', 0)
            member = self.bot.get_user(top_user['_id'])

            if member:
                if index == 0:
                    rank_1_user = member
                description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + highlight_text(
                    f"{func.truncate_string(member.display_name):<18} {level:>5} 🎁", member == ctx.author)

        if rank > len(users):
            level = user.get('game_state', {}).get('birthday_event', {}).get('wishes', 0)
            description += ("┇\n" if rank > len(users) + 1 else "") + f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(
                f"{func.truncate_string(ctx.author.display_name):<18} {level:>5} 🎁")

        if not description:
            description = "The leaderboard is currently empty."
        icon = rank_1_user.display_avatar if rank_1_user else ctx.guild.icon
        embed.description += f"```ansi\n{description}```"
        embed.set_thumbnail(url=icon.url if (icon := icon) else None)
        await ctx.reply(embed=embed)

    @commands.command(aliases=["smoll"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def smol(self, ctx: commands.Context):
        """Will Smol get a trick or a treat?

        **Examples:**
        qbirthday
        qbd
        """

        if ctx.author.id == SMOL_ID:
            return await ctx.reply("Birthday girl, wait for others to wish you!", delete_after=10)

        user = await func.get_user(ctx.author.id)
        if (retry := user.get("cooldown", {}).setdefault("smol", 0)) > time.time():
            return await ctx.reply(
                f"{ctx.author.mention}, your birthday wish will be available in <t:{round(retry)}:R>",
                delete_after=10
            )

        await self.update_wish_user_data(ctx, user)
        action_type = await self.do_smol_wish(ctx)
        func.logger.info(f"User {ctx.author.name}({ctx.author.id}) performed birthday action: {action_type}")

    async def do_smol_wish(self, ctx):
        user = await func.get_user(SMOL_ID)
        query = {}
        wishes_count = user.get('game_state', {}).get('birthday_event', {}).get('wishes', 0)
        actions = random.choices([self.curses, self.blessings], weights=[40, 60])[0]
        if wishes_count <= 1: #first one will always be a blessing
            actions = self.blessings
        action_type = random.choices(list(actions.keys()), weights=[info["weight"] for info in actions.values()], k=1)[
            0]
        await actions[action_type]["func"](ctx, query, user)
        await func.update_user(SMOL_ID, query)
        return action_type

    async def update_wish_user_data(self, ctx, user):
        query = {"$set": {"cooldown.smol": time.time() + func.settings.COOLDOWN_BASE["smol"][1]}}
        await self.on_wish(ctx, query, user)
        await func.update_user(ctx.author.id, query)

    async def on_wish(self, ctx: commands.Context, query: Dict[str, Any], user: Dict[str, Any]) -> None:
        query["$inc"] = {"game_state.birthday_event.wishes": 1}

    async def on_random_roll(self, ctx: commands.Context, query: Dict[str, Any], user: Dict[str, Any]) -> None:
        roll_type = random.choices(["rare", "epic", "legendary"], weights=[0.2, 0.05, 0.001], k=1)[0]
        query["$inc"] = {f"roll.{roll_type}": 1}
        smol_discord = self.bot.get_user(SMOL_ID)
        await ctx.reply(f"{ctx.author.mention} summoned a `{roll_type}` roll for {smol_discord.mention}! 🎉")

    async def on_potion_gain(self, ctx: commands.Context, query: Dict[str, Any], user: Dict[str, Any]) -> None:
        potion = random.choices(
            ["speed_i", "speed_ii", "speed_iii", "luck_i", "luck_ii", "luck_iii"],
            weights=[0.2, 0.05, 0.001, 0.2, 0.05, 0.001],
            k=1
        )[0]
        query["$inc"] = {f"potions.{potion}": 1}
        potion = potion.replace("_", " ").capitalize()
        smol_discord = self.bot.get_user(SMOL_ID)
        await ctx.reply(
            f"{ctx.author.mention} brewed up a `{potion}` potion🧪 for {smol_discord.mention}! 🎉")

    async def on_random_card_gain(self, ctx: commands.Context, query: Dict[str, Any], user: Dict[str, Any]) -> None:
        if len(user["cards"]) >= func.settings.MAX_CARDS:
            return await self.on_random_roll(ctx, query, user)

        card = iufi.CardPool.roll(amount=1, avoid=["mystic", "celestial"])[0]

        query["$push"] = {"cards": card.id}
        card.change_owner(SMOL_ID)
        CardPool.remove_available_card(card)
        await func.update_card(card.id, {"$set": {"owner_id": SMOL_ID}})
        smol_discord = self.bot.get_user(SMOL_ID)

        emoji, name = card.tier
        await ctx.reply(f"{ctx.author.mention} found a {name} card {emoji} for {smol_discord.mention}! 🎉")
        embed = discord.Embed(title=f"ℹ️ Card Info", color=0x949fb8)
        embed.description = f"```{card.display_id}\n" \
                            f"{card.display_tag}\n" \
                            f"{card.display_frame}\n" \
                            f"{card.tier[0]} {card.tier[1].capitalize()}\n" \
                            f"{card.display_stars}```\n" \
                            "**Owned by: **" + (f"<@{card.owner_id}>" if card.owner_id else "None")

        embed.set_image(url=f"attachment://image.{card.format}")
        await ctx.reply(file=discord.File(await card.image_bytes(True), filename=f"image.{card.format}"), embed=embed)

    async def on_starcandies_gain(self, ctx: commands.Context, query: Dict[str, Any], user: Dict[str, Any]) -> None:
        gain = random.randint(MIN_PUMPKINS, MAX_PUMPKINS)
        query["$inc"] = {"candies": gain}
        smol_discord = self.bot.get_user(SMOL_ID)
        await ctx.reply(
            f"{ctx.author.mention} found {gain} 🍬 for {smol_discord.mention}! 🎉")

    async def on_cooldown_reset(self, ctx: commands.Context, query: Dict[str, Any], user: Dict[str, Any]) -> None:
        cooldowns = ["roll", "quiz_game", "match_game"]
        cooldown = random.choice(cooldowns)
        query["$set"] = {f"cooldown.{cooldown}": 0}
        smol_discord = self.bot.get_user(SMOL_ID)
        await ctx.reply(f"{ctx.author.mention} reset {smol_discord.mention}'s `{cooldown.replace('_', ' ').upper()}` cooldown! 🎉")

    async def on_phake_celestial(self, ctx: commands.Context, query: Dict[str, Any], user: Dict[str, Any]) -> None:
        await ctx.reply(f"{ctx.author.mention} Smol got a Mystic card! 🦄", delete_after=3)
        await asyncio.sleep(3)
        await ctx.reply(f"Just kidding! Smol got nothing! 🎉")

    async def on_last_card_loss(self, ctx: commands.Context, query: Dict[str, Any], user: Dict[str, Any]) -> None:
        smol_discord = self.bot.get_user(SMOL_ID)
        if not user["cards"]:
            await ctx.reply(f"{ctx.author.mention}, Smol got... nothing! 🎉 Sad!")
            return

        last_card = iufi.CardPool.get_card(user["cards"][-1])
        if last_card.tier[1] not in ["mystic", "celestial"]:  # don't want to lose those
            query["$pull"] = {"cards": last_card.id}
            iufi.CardPool.add_available_card(last_card)
            await func.update_card(last_card.id,
                                   {"$set": {"owner_id": None, "tag": None, "frame": None, "last_trade_time": 0}})
            await ctx.reply(f"{ctx.author.mention} took {last_card.tier[1].capitalize()} card {last_card.tier[0]} from {smol_discord.mention} and lost it! 🎉")
            return

        await ctx.reply(f"{ctx.author.mention} Smol got... nothing! 🎉 The party crashers tricked Smol!")

    async def on_starcandies_loss(self, ctx: commands.Context, query: Dict[str, Any], user: Dict[str, Any]) -> None:
        if user.get("candies", 0) <= 0:
            await ctx.reply(f"{ctx.author.mention}, Smol got... nothing! 🎉 Sad!")
            return

        loss = random.randint(MIN_PUMPKINS, MAX_PUMPKINS)
        loss = min(loss, user["candies"])
        query["$inc"] = {"candies": -loss}
        smol_discord = self.bot.get_user(SMOL_ID)
        await ctx.reply(f"{ctx.author.mention} made {smol_discord.mention} lose {loss} 🍬! 🎉")

    async def on_cooldown_increase(self, ctx: commands.Context, query: Dict[str, Any], user: Dict[str, Any]) -> None:
        increase = random.randint(1, 3)
        cooldown = random.choice(["roll", "quiz_game", "match_game"])
        increase_multiplier = 3_600 if cooldown == "match_game" else 600

        prev_cooldown = user["cooldown"].get(cooldown, 0)
        query["$set"] = {"cooldown": user["cooldown"]}
        query["$set"][f"cooldown.{cooldown}"] = (increase * increase_multiplier) + max(prev_cooldown, time.time())
        smol_discord = self.bot.get_user(SMOL_ID)

        if cooldown in ["match_game"]:
            message = (f"{ctx.author.mention} cursed Smol. {smol_discord.mention}'s `{cooldown.replace('_', ' ').upper()}` cooldown got extended! "
                       f"Increased by {increase} hour{'s' if increase > 1 else ''}! 🎉")
        else:
            message = (f"{ctx.author.mention} cursed Smol. {smol_discord.mention}'s `{cooldown.replace('_', ' ').upper()}` cooldown got extended. It has "
                       f"been increased by {increase * 10} minutes! 🎉")
        await ctx.reply(message)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Smol(bot))