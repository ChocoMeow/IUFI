import asyncio
import random
import time
from typing import Any

import discord
import iufi
import functions as func

from discord import app_commands
from discord.ext import commands

LEADERBOARD_EMOJIS: list[str] = ["🥇", "🥈", "🥉", "🏅"]
MIN_PUMPKINS = 20
MAX_PUMPKINS = 50
CARD_LOSS_CANDIES = 50
PROTECTED_TIERS = {"mystic", "celestial"}


def highlight_text(text: str, need: bool = True) -> str:
    if not need:
        return text + "\n"
    return "\u001b[0;1;35m" + text + " \u001b[0m\n"


def pumpkin_battlepass_xp(amount: int) -> int:
    """Battle Pass XP bundled with a pumpkin payout. Maxed players receive none."""
    if amount <= 30:
        return 5
    if amount <= 40:
        return 10
    return 20


def _merge_query(query: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    for mode, payload in extra.items():
        if isinstance(payload, dict):
            query.setdefault(mode, {}).update(payload)
        else:
            query[mode] = payload
    return query


class Halloween(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "🎃"
        self.invisible = False

        self.tricks: dict[str, dict[str, Any]] = {
            "cooldown_increase": {"func": self.on_cooldown_increase, "weight": 0.5},
            "pumpkins_loss": {"func": self.on_pumpkin_loss, "weight": 0.5},
            "last_card_loss": {"func": self.on_last_card_loss, "weight": 0.05},
            "mystic_fake": {"func": self.on_fake_mystic, "weight": 0.01},
            "celestial_fake": {"func": self.on_fake_celestial, "weight": 0.01},
        }
        self.treats: dict[str, dict[str, Any]] = {
            "treat": {"func": self.on_treat, "weight": 0.1},
            "cooldown_reset": {"func": self.on_cooldown_reset, "weight": 0.5},
            "pumpkins_gain": {"func": self.on_pumpkin_gain, "weight": 0.5},
            "random_card": {"func": self.on_random_card_gain, "weight": 0.2},
            "random_potion": {"func": self.on_potion_gain, "weight": 0.1},
            "random_roll": {"func": self.on_random_roll, "weight": 0.1},
        }

    def _closed(self) -> bool:
        return not func.trick_or_treat_enabled()

    @app_commands.command(name="trickortreatleaderboard", description="Shows the trick or treat leaderboard.")
    async def trickortreatleaderboard(self, interaction: discord.Interaction):
        if self._closed():
            return await interaction.response.send_message("Trick or treat isn't running right now.")

        user = await func.get_user(interaction.user.id)
        users = await func.USERS_DB.find().sort("game_state.halloween_event.treats", -1).limit(10).to_list(10)
        treats = user.get("game_state", {}).get("halloween_event", {}).get("treats", 0)
        rank = await func.USERS_DB.count_documents({"game_state.halloween_event.treats": {"$gt": treats}}) + 1

        embed = discord.Embed(title="🎃   Trick Or Treat Leaderboard", color=discord.Color.random())
        embed.description = f"**Your current position is `{rank}`**\n"
        description = ""
        rank_1_user = None
        for index, top_user in enumerate(users):
            level = top_user.get("game_state", {}).get("halloween_event", {}).get("treats", 0)
            member = (interaction.guild.get_member(top_user["_id"]) if interaction.guild else None) or self.bot.get_user(top_user["_id"])
            name = member.display_name if member else str(top_user["_id"])
            if index == 0 and member:
                rank_1_user = member
            description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + highlight_text(
                f"{func.truncate_string(name):<18} {level:>5} 🍬",
                top_user["_id"] == interaction.user.id,
            )

        if rank > len(users):
            description += ("┇\n" if rank > len(users) + 1 else "") + f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(
                f"{func.truncate_string(interaction.user.display_name):<18} {treats:>5} 🍬"
            )

        if not description:
            description = "The leaderboard is currently empty."

        icon = rank_1_user.display_avatar if rank_1_user else (interaction.guild.icon if interaction.guild else None)
        embed.description += f"```ansi\n{description}```"
        if icon:
            embed.set_thumbnail(url=icon.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="trickortreat", description="Will you get a trick or a treat?")
    @app_commands.checks.cooldown(1, 5, key=lambda i: i.user.id)
    async def trickortreat(self, interaction: discord.Interaction):
        if self._closed():
            return await interaction.response.send_message("Trick or treat isn't running right now.")

        user = await func.get_user(interaction.user.id)
        retry = user.get("cooldown", {}).get("trick_or_treat", 0)
        if retry > time.time():
            return await interaction.response.send_message(
                f"{interaction.user.mention} your trick or treat will be available <t:{round(retry)}:R>",
                ephemeral=True,
            )

        duration = func.settings.COOLDOWN_BASE.get("trick_or_treat", ["🎃", 600])[1]
        query: dict[str, Any] = {"$set": {"cooldown.trick_or_treat": time.time() + duration}}

        table = random.choices([self.tricks, self.treats], weights=[40, 60])[0]
        action_type = random.choices(list(table), weights=[info["weight"] for info in table.values()], k=1)[0]
        await table[action_type]["func"](interaction, query, user)
        await func.update_user(interaction.user.id, query)
        func.logger.info(f"User {interaction.user.name}({interaction.user.id}) performed trick or treat action: {action_type}")

    async def on_treat(self, interaction: discord.Interaction, query: dict[str, Any], user: dict[str, Any]) -> None:
        query["$inc"] = {"game_state.halloween_event.treats": 1}
        await interaction.response.send_message(f"{interaction.user.mention} you got a treat! 🍬 Beware of the tricks! 🎃")

    async def on_random_roll(self, interaction: discord.Interaction, query: dict[str, Any], user: dict[str, Any]) -> None:
        roll_type = random.choices(["rare", "epic", "legendary"], weights=[0.2, 0.05, 0.001], k=1)[0]
        query["$inc"] = {f"roll.{roll_type}": 1}
        await interaction.response.send_message(
            f"{interaction.user.mention} you summoned a `{roll_type}` roll! 🎃 Will it be a trick... or a treat?"
        )

    async def on_potion_gain(self, interaction: discord.Interaction, query: dict[str, Any], user: dict[str, Any]) -> None:
        potion = random.choices(
            ["speed_i", "speed_ii", "speed_iii", "luck_i", "luck_ii", "luck_iii"],
            weights=[0.2, 0.05, 0.001, 0.2, 0.05, 0.001],
            k=1,
        )[0]
        query["$inc"] = {f"potions.{potion}": 1}
        await interaction.response.send_message(
            f"{interaction.user.mention} you brewed up a `{potion.replace('_', ' ').title()}` potion! 🧪 Don't drink it all at once! 🎃"
        )

    async def on_random_card_gain(self, interaction: discord.Interaction, query: dict[str, Any], user: dict[str, Any]) -> None:
        if len(user.get("cards", [])) >= func.get_user_card_limit(user):
            return await self.on_random_roll(interaction, query, user)

        try:
            card = iufi.CardPool.roll(amount=1)[0]
        except (ValueError, IndexError):
            return await self.on_random_roll(interaction, query, user)

        query["$push"] = {"cards": card.id}
        _merge_query(query, func.update_pity_from_cards(user, [card], increment=False))
        card.change_owner(interaction.user.id)
        iufi.CardPool.remove_available_card(card)
        await func.update_card(card.id, {"$set": {"owner_id": interaction.user.id}})

        emoji, name = card.tier
        await interaction.response.send_message(f"{interaction.user.mention} you got a {name} card! {emoji}")
        embed = discord.Embed(title="ℹ️ Card Info", color=0x949fb8)
        embed.description = (
            f"```{card.display_id}\n"
            f"{card.display_tag}\n"
            f"{card.display_frame}\n"
            f"{card.tier[0]} {card.tier[1].capitalize()}\n"
            f"{card.display_stars}```\n"
            "**Owned by: **" + (f"<@{card.owner_id}>" if card.owner_id else "None")
        )
        embed.set_image(url=f"attachment://image.{card.format}")
        try:
            await interaction.followup.send(
                file=discord.File(await card.image_bytes(True), filename=f"image.{card.format}"),
                embed=embed,
            )
        except Exception:
            func.logger.exception(f"Trick or treat granted {card.id} to {interaction.user.id}, but the card image failed to send.")

    async def on_pumpkin_gain(self, interaction: discord.Interaction, query: dict[str, Any], user: dict[str, Any]) -> None:
        gain = random.randint(MIN_PUMPKINS, MAX_PUMPKINS)
        query["$inc"] = {"candies": gain}
        xp = pumpkin_battlepass_xp(gain)
        query = func.add_battlepass_xp(user, xp, query=query, apply_modifiers=False)
        old_xp, new_xp = func.get_battlepass_xp_change(user, query)
        granted = new_xp - old_xp

        message = f"{interaction.user.mention} you harvested {gain} {func.currency_name()}! {func.currency_emoji()}"
        if granted > 0:
            message += f" Battle Pass +{granted} XP."
        await interaction.response.send_message(message)

    async def on_cooldown_reset(self, interaction: discord.Interaction, query: dict[str, Any], user: dict[str, Any]) -> None:
        cooldown = random.choice(["roll", "quiz_game", "match_game"])
        query["$set"][f"cooldown.{cooldown}"] = 0
        await interaction.response.send_message(
            f"{interaction.user.mention} your `{cooldown.replace('_', ' ').upper()}` cooldown has been reset by the spirits of Halloween! 🎃"
        )

    async def _fake_drop(self, interaction: discord.Interaction, tier: str) -> None:
        emoji = (func.settings.TIERS_BASE.get(tier) or ["✨"])[0]
        await interaction.response.send_message(
            f"{interaction.user.mention} you got a {tier.capitalize()} card! {emoji}",
            delete_after=3,
        )
        await asyncio.sleep(3)
        await interaction.followup.send(f"{interaction.user.mention} Just kidding! You got nothing! 🎃")

    async def on_fake_mystic(self, interaction: discord.Interaction, query: dict[str, Any], user: dict[str, Any]) -> None:
        await self._fake_drop(interaction, "mystic")

    async def on_fake_celestial(self, interaction: discord.Interaction, query: dict[str, Any], user: dict[str, Any]) -> None:
        await self._fake_drop(interaction, "celestial")

    def _card_to_take(self, user: dict[str, Any], user_id: int) -> iufi.Card | None:
        for card_id in reversed(user.get("cards") or []):
            card = iufi.CardPool.get_card(card_id)
            if not card or card.owner_id != user_id:
                continue
            if card.locked or card.tier[1] in PROTECTED_TIERS:
                continue
            return card
        return None

    async def on_last_card_loss(self, interaction: discord.Interaction, query: dict[str, Any], user: dict[str, Any]) -> None:
        card = self._card_to_take(user, interaction.user.id)
        if card:
            query["$pull"] = {"cards": card.id}
            iufi.CardPool.add_available_card(card)
            await func.update_card(card.id, {"$set": {"owner_id": None, "tag": None, "frame": None, "last_trade_time": 0, "locked": False}})
            await interaction.response.send_message(
                f"{interaction.user.mention} `{card.id}` vanished into the shadows! 🎃"
            )
            return

        balance = int(user.get("candies", 0) or 0)
        if balance <= 0:
            await interaction.response.send_message(
                f"{interaction.user.mention} you got nothing! 🎃 The spirits couldn't find a card or any {func.currency_name()} to take."
            )
            return

        loss = min(CARD_LOSS_CANDIES, balance)
        query["$inc"] = {"candies": -loss}
        await interaction.response.send_message(
            f"{interaction.user.mention} no card could be taken, so the spirits snatched {loss} {func.currency_name()}! {func.currency_emoji()}"
        )

    async def on_pumpkin_loss(self, interaction: discord.Interaction, query: dict[str, Any], user: dict[str, Any]) -> None:
        balance = int(user.get("candies", 0) or 0)
        if balance <= 0:
            await interaction.response.send_message(f"{interaction.user.mention} you got... nothing! 🎃 The trick is on you! 👻")
            return

        loss = min(random.randint(MIN_PUMPKINS, MAX_PUMPKINS), balance)
        query["$inc"] = {"candies": -loss}
        await interaction.response.send_message(
            f"{interaction.user.mention} you dropped {loss} {func.currency_name()}! {func.currency_emoji()} Looks like the gremlins stole them!"
        )

    async def on_cooldown_increase(self, interaction: discord.Interaction, query: dict[str, Any], user: dict[str, Any]) -> None:
        increase = random.randint(1, 3)
        cooldown = random.choice(["roll", "quiz_game", "match_game", "trick_or_treat"])
        increase_multiplier = 3_600 if cooldown == "match_game" else 600
        prev_cooldown = user.get("cooldown", {}).get(cooldown, 0)
        query["$set"][f"cooldown.{cooldown}"] = (increase * increase_multiplier) + max(prev_cooldown, time.time())

        if cooldown == "match_game":
            message = (
                f"{interaction.user.mention} your `{cooldown.replace('_', ' ').upper()}` cooldown got cursed! "
                f"Increased by {increase} hour{'s' if increase > 1 else ''}! 🎃"
            )
        else:
            message = (
                f"{interaction.user.mention} your `{cooldown.replace('_', ' ').upper()}` cooldown got cursed. It has "
                f"been increased by {increase * 10} minutes! 🎃"
            )
        await interaction.response.send_message(message)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Halloween(bot))
