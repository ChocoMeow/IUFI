import time
import random
import discord, iufi, asyncio
import functions as func

from typing import (
    Dict,
    Any,
    Union,
    Callable
)
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
        self.bot: commands.Bot = bot
        self.emoji: str = "🎃"
        self.invisible: bool = False

        self.tricks: Dict[str, Dict[str, Union[Callable, float]]] = {
            "cooldown_increase": {
                "func": self.on_cooldown_increase,
                "weight": .5
            },
            "pumpkins_loss": {
                "func": self.on_pumpkin_loss,
                "weight": .5
            },
            "last_card_loss": {
                "func": self.on_last_card_loss,
                "weight": .05
            },
            "celestial_fake": {
                "func": self.on_phake_celestial,
                "weight": .01
            },
        }

        self.treats: Dict[str, Dict[str, Union[Callable, float]]] = {
            "treat": {
                "func": self.on_treat,
                "weight": .1
            },
            "cooldown_reset": {
                "func": self.on_cooldown_reset,
                "weight": .5
            },
            "pumpkins_gain": {
                "func": self.on_pumpkin_gain,
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

    @commands.command(aliases=["totl"])
    async def trickortreatleaderboard(self, ctx: commands.Context):
        """Shows the leaderboard for the trick or treat event.

        **Examples:**
        qtrickortreatleaderboard
        qtotl
        """
        user = await func.get_user(ctx.author.id)
        users = await func.USERS_DB.find().sort("game_state.halloween_event.treats", -1).limit(10).to_list(10)
        rank = await func.USERS_DB.count_documents({'game_state.halloween_event.treats': {
            '$gt': user.get('game_state', {}).get('halloween_event', {}).get('treats', 0)}}) + 1
        embed = discord.Embed(title="🎃   Trick Or Treat Leaderboard", color=discord.Color.random())
        embed.description = f"**Your current position is `{rank}`**\n"
        rank_1_user = None
        description = ""
        for index, top_user in enumerate(users):
            level = top_user.get('game_state', {}).get('halloween_event', {}).get('treats', 0)
            member = self.bot.get_user(top_user['_id'])

            if member:
                if index == 0:
                    rank_1_user = member
                description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + highlight_text(
                    f"{func.truncate_string(member.display_name):<18} {level:>5} 🍬", member == ctx.author)

        if rank > len(users):
            level = user.get('game_state', {}).get('halloween_event', {}).get('treats', 0)
            description += ("┇\n" if rank > len(users) + 1 else "") + f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(
                f"{func.truncate_string(ctx.author.display_name):<18} {level:>5} 🍬")

        if not description:
            description = "The leaderboard is currently empty."
        icon = rank_1_user.display_avatar if rank_1_user else ctx.guild.icon
        embed.description += f"```ansi\n{description}```"
        embed.set_thumbnail(url=icon.url if (icon := icon) else None)
        await ctx.reply(embed=embed)

    @commands.command(aliases=["tot"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def trickortreat(self, ctx: commands.Context):
        """Will you get a trick or a treat?

        **Examples:**
        qtrickortreat
        qtot
        """
        user = await func.get_user(ctx.author.id)
        if (retry := user.get("cooldown", {}).setdefault("trick_or_treat", 0)) > time.time():
            return await ctx.reply(
                f"{ctx.author.mention} your trick or teat will be available in <t:{round(retry)}:R>",
                delete_after=10
            )

        query = {"$set": {"cooldown.trick_or_treat": time.time() + func.settings.COOLDOWN_BASE["trick_or_treat"][1]}}

        actions = random.choices([self.tricks, self.treats], weights=[40, 60])[0]
        action_type = random.choices(list(actions.keys()), weights=[info["weight"] for info in actions.values()], k=1)[
            0]

        await actions[action_type]["func"](ctx, query, user)
        await func.update_user(ctx.author.id, query)
        func.logger.info(f"User {ctx.author.name}({ctx.author.id}) performed trick or treat action: {action_type}")

    async def on_treat(self, ctx: commands.Context, query: Dict[str, Any], user: Dict[str, Any]) -> None:
        query["$inc"] = {"game_state.halloween_event.treats": 1}
        await ctx.reply(f"{ctx.author.mention} you got a treat! 🍬 Beware of the tricks! 🎃")

    async def on_random_roll(self, ctx: commands.Context, query: Dict[str, Any], user: Dict[str, Any]) -> None:
        roll_type = random.choices(["rare", "epic", "legendary"], weights=[0.2, 0.05, 0.001], k=1)[0]
        query["$inc"] = {f"roll.{roll_type}": 1}
        await ctx.reply(f"{ctx.author.mention} you summoned a `{roll_type}` roll! 🎃 Will it be a trick... or a treat?")

    async def on_potion_gain(self, ctx: commands.Context, query: Dict[str, Any], user: Dict[str, Any]) -> None:
        potion = random.choices(
            ["speed_i", "speed_ii", "speed_iii", "luck_i", "luck_ii", "luck_iii"],
            weights=[0.2, 0.05, 0.001, 0.2, 0.05, 0.001],
            k=1
        )[0]
        query["$inc"] = {f"potions.{potion}": 1}
        potion = potion.replace("_", " ").capitalize()
        await ctx.reply(
            f"{ctx.author.mention} you brewed up a `{potion}` potion! 🧪 Don't drink it all at once! 🎃")

    async def on_random_card_gain(self, ctx: commands.Context, query: Dict[str, Any], user: Dict[str, Any]) -> None:
        if len(user["cards"]) >= func.settings.MAX_CARDS:
            return await self.on_random_roll(ctx, query, user)

        card = iufi.CardPool.roll(amount=1, avoid=["mystic", "celestial"])[0]

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

    async def on_pumpkin_gain(self, ctx: commands.Context, query: Dict[str, Any], user: Dict[str, Any]) -> None:
        gain = random.randint(MIN_PUMPKINS, MAX_PUMPKINS)
        query["$inc"] = {"candies": gain}
        await ctx.reply(
            f"{ctx.author.mention} you harvested {gain} pumpkins! 🎃 Just watch out for the headless horseman! 🐴💀")

    async def on_cooldown_reset(self, ctx: commands.Context, query: Dict[str, Any], user: Dict[str, Any]) -> None:
        cooldowns = ["roll", "quiz_game", "match_game"]
        cooldown = random.choice(cooldowns)
        query["$set"][f"cooldown.{cooldown}"] = 0
        await ctx.reply(f"{ctx.author.mention} your `{cooldown.replace('_', ' ').upper()}` cooldown has been reset by the spirits of Halloween! 🎃")

    async def on_phake_celestial(self, ctx: commands.Context, query: Dict[str, Any], user: Dict[str, Any]) -> None:
        await ctx.reply(f"{ctx.author.mention} you got a Mystic card! 🦄", delete_after=3)
        await asyncio.sleep(3)
        await ctx.reply(f"Just kidding! You got nothing! 🎃")

    async def on_last_card_loss(self, ctx: commands.Context, query: Dict[str, Any], user: Dict[str, Any]) -> None:
        if not user["cards"]:
            await ctx.reply(f"{ctx.author.mention} you got nothing! 🎃 Oof... even the ghosts ignored you! 👻")
            return

        last_card = iufi.CardPool.get_card(user["cards"][-1])
        if last_card.tier[1] not in ["mystic", "celestial"]:  # don't want to lose those
            query["$pull"] = {"cards": last_card.id}
            iufi.CardPool.add_available_card(last_card)
            await func.update_card(last_card.id,
                                   {"$set": {"owner_id": None, "tag": None, "frame": None, "last_trade_time": 0}})
            await ctx.reply(f"{ctx.author.mention} your last card vanished into the shadows! 🎃")
            return

        await ctx.reply(f"{ctx.author.mention} you got... nothing! 🎃 The spirits tricked you!")

    async def on_pumpkin_loss(self, ctx: commands.Context, query: Dict[str, Any], user: Dict[str, Any]) -> None:
        if user.get("candies", 0) <= 0:
            await ctx.reply(f"{ctx.author.mention} you got... nothing! 🎃 The trick is on you! 👻")
            return

        loss = random.randint(MIN_PUMPKINS, MAX_PUMPKINS)
        loss = min(loss, user["candies"])
        query["$inc"] = {"candies": -loss}
        await ctx.reply(f"{ctx.author.mention} you dropped {loss} pumpkins! 🎃 Looks like the gremlins stole them!")

    async def on_cooldown_increase(self, ctx: commands.Context, query: Dict[str, Any], user: Dict[str, Any]) -> None:
        increase = random.randint(1, 3)
        cooldown = random.choice(["roll", "quiz_game", "match_game", "trick_or_treat"])
        increase_multiplier = 3_600 if cooldown == "match_game" else 600

        prev_cooldown = user["cooldown"].get(cooldown, 0)
        query["$set"][f"cooldown.{cooldown}"] = (increase * increase_multiplier) + max(prev_cooldown, time.time())

        if cooldown in ["match_game"]:
            message = (f"{ctx.author.mention} your `{cooldown.replace('_', ' ').upper()}` cooldown got cursed! "
                       f"Increased by {increase} hour{'s' if increase > 1 else ''}! 🎃")
        else:
            message = (f"{ctx.author.mention} your `{cooldown.replace('_', ' ').upper()}` cooldown got cursed. It has "
                       f"been increased by {increase * 10} minutes! 🎃")
        await ctx.reply(message)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Halloween(bot))
