import asyncio
import random
import time
from typing import Any

import discord
import iufi
import functions as func

from collections import Counter
from discord import app_commands
from discord.ext import commands
from views.shop import QuantityModal

LEADERBOARD_EMOJIS: list[str] = ["🥇", "🥈", "🥉", "🏅"]
EVENT_PATH = "game_state.halloween_event"
TREATS_PATH = f"{EVENT_PATH}.treats"
TREATS_SPENT_PATH = f"{EVENT_PATH}.treats_spent"
TREATS_GRANTED_PATH = f"{EVENT_PATH}.treats_granted"
MIN_PUMPKINS = 20
MAX_PUMPKINS = 50
CARD_LOSS_CANDIES = 50
PROTECTED_TIERS = {"mystic", "celestial"}
MAX_STORE_QUANTITY = 50

STORE_ITEMS: dict[str, dict[str, Any]] = {
    "halloween_bag_3": {"label": "Halloween Bag Lv.3", "emoji": "👜", "price": 10},
    "halloween_bag_2": {"label": "Halloween Bag Lv.2", "emoji": "👜", "price": 7},
    "halloween_bag_1": {"label": "Halloween Bag Lv.1", "emoji": "👜", "price": 5},
    "potion_iii": {"label": "Potion III Bundle", "emoji": "🧪", "price": 5},
    "potion_ii": {"label": "Potion II Bundle", "emoji": "🧪", "price": 3},
    "potion_i": {"label": "Potion I Bundle", "emoji": "🧪", "price": 1},
    "roll_legendary": {"label": "Legendary Roll", "tier": "legendary", "price": 5},
    "roll_epic": {"label": "Epic Roll", "tier": "epic", "price": 3},
    "roll_rare": {"label": "Rare Roll", "tier": "rare", "price": 1},
    "inventory_slot": {"label": "Inventory Slot", "emoji": "📦", "price": 4},
    "candy_bag": {"label": "Candy Bag (40-60)", "emoji": "🍬", "price": 1},
}


def highlight_text(text: str, need: bool = True) -> str:
    if not need:
        return text + "\n"
    return "\u001b[0;1;35m" + text + " \u001b[0m\n"


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _event_state(user: dict[str, Any]) -> dict[str, Any]:
    return (user.get("game_state") or {}).get("halloween_event") or {}


def treats_of(user: dict[str, Any]) -> int:
    """Treats earned from trick or treat. This is the leaderboard score and never goes down."""
    return _as_int(_event_state(user).get("treats"))


def treat_balance(user: dict[str, Any]) -> int:
    state = _event_state(user)
    return treats_of(user) + _as_int(state.get("treats_granted")) - _as_int(state.get("treats_spent"))


def _event_time(key: str) -> float:
    return float((func.settings.EVENT_SETTINGS or {}).get(key) or 0)


def trick_or_treat_over() -> bool:
    ends_at = _event_time("trick_or_treat_ends_at")
    return bool(ends_at) and time.time() >= ends_at


def treat_store_open() -> bool:
    opens_at, closes_at = _event_time("treat_store_opens_at"), _event_time("treat_store_closes_at")
    now = time.time()
    return bool(opens_at) and opens_at <= now and (not closes_at or now < closes_at)


def item_emoji(item: dict[str, Any]) -> str:
    if tier := item.get("tier"):
        return func.settings.TIERS_BASE.get(tier, ["🎲"])[0]
    return item["emoji"]


def item_label(item_id: str) -> str:
    if item_id == "candy_bag":
        return f"{func.currency_name('Starcandies').title()} Bag (40-60)"
    return STORE_ITEMS[item_id]["label"]


def _potion_bundle(rewards: Counter, level: str, amount: int) -> None:
    rewards[f"potions.speed_{level}"] += amount
    rewards[f"potions.luck_{level}"] += amount


def open_store_item(item_id: str, rewards: Counter, lucky: Counter) -> None:
    """Adds one unit of `item_id` to `rewards`. Bag bonus hits are also counted in `lucky`."""
    if item_id.startswith("potion_"):
        _potion_bundle(rewards, item_id.split("_", 1)[1], 1)
    elif item_id.startswith("roll_"):
        rewards[f"roll.{item_id.split('_', 1)[1]}"] += 1
    elif item_id == "inventory_slot":
        rewards["extra_props.extra_card_slots"] += 1
        rewards["extra_props.slot_purchases"] += 1
    elif item_id == "candy_bag":
        rewards["candies"] += random.randint(40, 60)
    elif item_id == "halloween_bag_1":
        rewards["roll.rare"] += random.randint(3, 5)
        _potion_bundle(rewards, "i", random.randint(1, 2))
        if random.random() < 0.20:
            amount = random.randint(1, 3)
            rewards["roll.epic"] += amount
            lucky["roll.epic"] += amount
        if random.random() < 0.10:
            amount = random.randint(1, 3)
            rewards["roll.legendary"] += amount
            lucky["roll.legendary"] += amount
    elif item_id == "halloween_bag_2":
        rewards["roll.epic"] += random.randint(2, 3)
        _potion_bundle(rewards, "ii", random.randint(1, 2))
        if random.random() < 0.03:
            rewards["roll.mystic"] += 1
            lucky["roll.mystic"] += 1
    elif item_id == "halloween_bag_3":
        rewards["roll.legendary"] += random.randint(2, 3)
        _potion_bundle(rewards, "iii", random.randint(1, 2))
        if random.random() < 0.05:
            rewards["roll.mystic"] += 1
            lucky["roll.mystic"] += 1
        if random.random() < 0.03:
            rewards["roll.celestial"] += 1
            lucky["roll.celestial"] += 1


def reward_label(key: str) -> str:
    if key == "candies":
        return f"{func.currency_emoji()} {func.currency_name('Starcandies').title()}"
    if key == "extra_props.extra_card_slots":
        return "📦 Inventory Slot"
    if key.startswith("roll."):
        tier = key.split(".", 1)[1]
        return f"{func.settings.TIERS_BASE.get(tier, ['🎲'])[0]} {tier.title()} Roll"
    if key.startswith("potions."):
        potion, level = key.split(".", 1)[1].split("_", 1)
        emoji = (func.settings.POTIONS_BASE.get(potion) or {}).get("emoji", "🧪")
        return f"{emoji} {potion.title()} {level.upper()} Potion"
    return key


class TreatStoreDropdown(discord.ui.Select):
    def __init__(self) -> None:
        super().__init__(
            placeholder="Select an item to buy...",
            options=[
                discord.SelectOption(
                    label=f"{item_label(item_id)} - {item['price']} Treat{'s' if item['price'] != 1 else ''}",
                    emoji=item_emoji(item),
                    value=item_id,
                )
                for item_id, item in STORE_ITEMS.items()
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        modal = QuantityModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.quantity:
            await self.view.purchase(interaction, self.values[0], modal.quantity)


class TreatStoreView(discord.ui.View):
    def __init__(self, cog: "Halloween", author: discord.Member, timeout: float | None = 120) -> None:
        super().__init__(timeout=timeout)
        self.cog = cog
        self.author = author
        self.message: discord.Message | None = None
        self.add_item(TreatStoreDropdown())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.author

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    async def build_embed(self) -> discord.Embed:
        user = await func.get_user(self.author.id)
        embed = discord.Embed(title="🎃 Halloween Treats Store", color=0xF97316)
        closes_at = _event_time("treat_store_closes_at")
        opens_at = _event_time("treat_store_opens_at")
        if not treat_store_open():
            embed.description = f"🔒 **Admin preview.** The store opens <t:{round(opens_at)}:F>.\n"
        elif closes_at:
            embed.description = f"Closes <t:{round(closes_at)}:R>\n"
        else:
            embed.description = ""
        embed.description += f"🍬 Treats: `{treat_balance(user)}`\n```"
        for item_id, item in STORE_ITEMS.items():
            embed.description += f"{item_emoji(item)} {item_label(item_id).upper():<24} {item['price']:>3} 🍬\n"
        embed.description += "```"
        embed.add_field(
            name="👜 Halloween Bags (opened on purchase)",
            value=(
                "**Lv.1**: 3-5 Rare Rolls, 1-2 Potion I Bundles, 20% for 1-3 Epic Rolls, 10% for 1-3 Legendary Rolls\n"
                "**Lv.2**: 2-3 Epic Rolls, 1-2 Potion II Bundles, 3% for a Mystic Roll\n"
                "**Lv.3**: 2-3 Legendary Rolls, 1-2 Potion III Bundles, 5% for a Mystic Roll, 3% for a Celestial Roll\n"
                "A potion bundle is 1 Speed + 1 Luck potion of that level."
            ),
            inline=False,
        )
        embed.set_thumbnail(url=self.author.display_avatar.url)
        return embed

    async def purchase(self, interaction: discord.Interaction, item_id: str, quantity: int) -> None:
        if quantity > MAX_STORE_QUANTITY:
            return await interaction.followup.send(f"You can buy up to `{MAX_STORE_QUANTITY}` at a time.", ephemeral=True)

        async with self.cog.lock_for(interaction.user.id):
            if not self.cog.store_accessible(interaction):
                return await interaction.followup.send("The Treats Store is closed.", ephemeral=True)

            user = await func.get_user(interaction.user.id)
            item = STORE_ITEMS[item_id]
            cost = item["price"] * quantity
            balance = treat_balance(user)
            if balance < cost:
                return await interaction.followup.send(
                    f"You need `{cost}` treats but only have `{balance}`.", ephemeral=True
                )

            rewards, lucky = Counter(), Counter()
            for _ in range(quantity):
                open_store_item(item_id, rewards, lucky)

            query = func.update_quest_progress(user, "BUY_ITEM", progress=quantity, query={
                "$inc": {TREATS_SPENT_PATH: cost, **rewards}
            })
            await func.update_user(interaction.user.id, query)

        func.logger.info(
            f"User {interaction.user.name}({interaction.user.id}) bought {quantity}x {item_id} for {cost} treats: {dict(rewards)}"
        )

        embed = discord.Embed(title="🎃 Treats Store Purchase", color=0xF97316)
        embed.description = f"```{item_emoji(item)} {item_label(item_id)} x{quantity}\n🍬 - {cost} Treats```\n**You received:**\n"
        embed.description += "\n".join(
            f"{reward_label(key)} x{amount}" for key, amount in rewards.items() if key != "extra_props.slot_purchases"
        )
        if lucky:
            embed.description += "\n\n✨ **Lucky drops:** " + ", ".join(
                f"{reward_label(key)} x{amount}" for key, amount in lucky.items()
            )
        embed.set_footer(text=f"Treats left: {balance - cost}")
        await interaction.followup.send(embed=embed)

        if self.message:
            try:
                await self.message.edit(embed=await self.build_embed(), view=self)
            except discord.HTTPException:
                pass


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

        self._locks: dict[int, asyncio.Lock] = {}

    def _closed(self) -> bool:
        return not func.trick_or_treat_enabled()

    def lock_for(self, user_id: int) -> asyncio.Lock:
        return self._locks.setdefault(user_id, asyncio.Lock())

    def store_accessible(self, interaction: discord.Interaction) -> bool:
        if self._closed():
            return False
        return treat_store_open() or func.is_admin_interaction(interaction)

    @app_commands.command(name="treatstore", description="Spend your Halloween treats in the Treats Store.")
    async def treatstore(self, interaction: discord.Interaction):
        if not self.store_accessible(interaction):
            opens_at = _event_time("treat_store_opens_at")
            if not self._closed() and opens_at and time.time() < opens_at:
                return await interaction.response.send_message(
                    f"The Treats Store opens <t:{round(opens_at)}:R>. Keep collecting treats with `/trickortreat`! 🎃"
                )
            return await interaction.response.send_message("The Treats Store is closed.")

        view = TreatStoreView(self, interaction.user)
        await interaction.response.send_message(embed=await view.build_embed(), view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="trickortreatleaderboard", description="Shows the trick or treat leaderboard.")
    async def trickortreatleaderboard(self, interaction: discord.Interaction):
        if self._closed():
            return await interaction.response.send_message("Trick or treat isn't running right now.")

        user = await func.get_user(interaction.user.id)
        users = await func.USERS_DB.find({TREATS_PATH: {"$gt": 0}}).sort(TREATS_PATH, -1).limit(10).to_list(10)
        treats = treats_of(user)
        rank = await func.USERS_DB.count_documents({TREATS_PATH: {"$gt": treats}}) + 1

        embed = discord.Embed(title="🎃   Trick Or Treat Leaderboard", color=discord.Color.random())
        embed.description = f"**Your current position is `{rank}`**\n"
        description = ""
        rank_1_user = None
        for index, top_user in enumerate(users):
            level = treats_of(top_user)
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
        if trick_or_treat_over():
            message = "Trick or treat has ended! 🎃"
            if treat_store_open():
                message += " Spend your treats with `/treatstore`"
                if closes_at := _event_time("treat_store_closes_at"):
                    message += f" before it closes <t:{round(closes_at)}:R>"
                message += "."
            return await interaction.response.send_message(message)

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
        query["$inc"] = {TREATS_PATH: 1}
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
