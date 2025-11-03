import discord, time, random, asyncio
from typing import Dict, Optional
from discord.ext import commands

import functions as func
from iufi import CardPool, Card


class RewardCardView(discord.ui.View):
    """A reward card view with Claim and Reroll functionality.

    Usage:
        view = RewardCardView(ctx, author, probabilities, initial_cost=10)
        await view.send()

    Arguments:
        ctx: commands.Context (used for sending messages and invoking commands)
        author: the only discord.Member allowed to interact with the view
        probabilities: mapping of card tier name -> weight (floats or ints). They will be normalized.
        initial_cost: starting cost (in the user's currency field) for reroll
        cost_currency_field: which user field represents currency (default: "candies")
        timeout: view expiry in seconds (default: 120)
        cost_multiplier: how much the reroll cost multiplies after each reroll (default: 2.0)
    """

    def __init__(
        self,
        ctx: Optional[commands.Context],
        author: discord.Member,
        probabilities: Dict[str, float],
        *,
        initial_cost: int = 10,
        cost_currency_field: str = "candies",
        timeout: float = 120,
        cost_multiplier: float = 2.0,
    ) -> None:
        super().__init__(timeout=timeout)

        self.ctx = ctx
        self.author = author
        self._raw_probs = probabilities or {}
        self._weights = self._normalize_probs(self._raw_probs)
        self.initial_cost = max(0, int(initial_cost))
        self.current_cost = self.initial_cost
        self.cost_currency_field = cost_currency_field
        self.cost_multiplier = float(cost_multiplier)
        self.timeout_seconds = timeout
        # expiry unix timestamp (rounded int) used for Discord-friendly timestamps
        self.expires_at: int = round(time.time() + self.timeout_seconds)

        self._lock = asyncio.Lock()
        self.message: discord.Message | None = None
        self.current_card: Card | None = None
        self.rerolls: int = 0

        # prepare buttons
        # Claim and Reroll added as UI items

    def _normalize_probs(self, probs: Dict[str, float]) -> Dict[str, float]:
        if not probs:
            return {}
        items = {k: float(v) for k, v in probs.items() if v and v > 0}
        total = sum(items.values())
        if total <= 0:
            # fallback equal weights
            n = len(items) or 1
            return {k: 1 / n for k in items}
        return {k: v / total for k, v in items.items()}

    def _format_probs(self) -> str:
        if not self._weights:
            return "No probabilities provided."
        lines = []
        for tier, w in sorted(self._weights.items(), key=lambda i: -i[1]):
            emoji = func.settings.TIERS_BASE.get(tier, ["?"])[0]
            lines.append(f"{emoji} {tier.capitalize()}: {round(w * 100, 2)}%")
        return "\n".join(lines)

    def _choose_tier(self) -> str | None:
        if not self._weights:
            return None
        tiers = list(self._weights.keys())
        weights = list(self._weights.values())
        return random.choices(tiers, weights=weights, k=1)[0]

    def _pick_card_from_tier(self, tier: str) -> Card | None:
        # pick a random available card for the tier
        try:
            pool = CardPool
            avail = pool._available_cards.get(tier, [])
            if not avail:
                # fallback: find any available card
                for cards in pool._available_cards.values():
                    if cards:
                        return random.choice(cards)
                return None

            return random.choice(avail)
        except Exception:
            return None

    async def _roll_card(self) -> Card | None:
        tier = self._choose_tier()
        card = None
        if tier:
            card = self._pick_card_from_tier(tier)
        # final fallback
        if not card:
            # try CardPool.roll to obtain a category first
            try:
                cards = CardPool.roll(1)
                card = cards[0] if cards else None
            except Exception:
                card = None
        self.current_card = card
        return card

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title="Reward Card", color=discord.Color.random())
        embed.add_field(name="Probabilities", value=self._format_probs(), inline=False)

        if self.current_card:
            card = self.current_card
            embed.description = f"{card.tier[0]} **{card._tier.capitalize()}** | {card.display_id} | {card.display_stars}"
            embed.set_footer(text=f"Reroll cost: {self.current_cost} {self.cost_currency_field} — Expires: <t:{self.expires_at}:R>")
        else:
            embed.description = "No card available to display."
            embed.set_footer(text=f"Reroll cost: {self.current_cost} {self.cost_currency_field} — Expires: <t:{self.expires_at}:R>")

        return embed

    async def send(self) -> discord.Message:
        # roll initial card
        await self._roll_card()

        embed = self.build_embed()
        file = None
        if self.current_card:
            try:
                img_bytes = await self.current_card.image_bytes()
                filename = f"{self.current_card.id}.webp"
                file = discord.File(img_bytes, filename=filename)
                embed.set_image(url=f"attachment://{filename}")
            except Exception:
                file = None

        # include friendly discord timestamp in the message content for automatic relative display
        content = f"**{self.author.mention} This reward ends <t:{self.expires_at}:R>**"
        # ctx could be None if the caller intends to send the message manually (some views call RewardCardView without ctx)
        if self.ctx:
            self.message = await self.ctx.send(content=content, embed=embed, file=file, view=self)
        else:
            # fallback: no ctx provided; leave message unset — caller should send the embed and attach the view
            self.message = None
        return self.message

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Only allow the provided author to interact with the view
        if interaction.user != self.author:
            await interaction.response.send_message("Only the user who opened this reward can interact with it.", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
            child.style = discord.ButtonStyle.gray
        try:
            if self.message:
                await self.message.edit(content=f"*⏰ This reward has expired. (expired <t:{round(time.time())}:R>)*", view=self)
        except Exception:
            pass
        self.stop()

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.green)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        async with self._lock:
            if not self.current_card:
                return await interaction.response.send_message("No card to claim.", ephemeral=True)

            card = self.current_card
            if (owner_id := card.owner_id):
                if owner_id != interaction.user.id:
                    return await interaction.response.send_message(f"This card has been claimed by <@{owner_id}>.", ephemeral=True)
                else:
                    return await interaction.response.send_message("You already own this card.", ephemeral=True)

            user = await func.get_user(interaction.user.id)
            # Check inventory limit
            if len(user.get("cards", [])) >= func.get_user_card_limit(user):
                return await interaction.response.send_message("Your inventory is full.", ephemeral=True)

            # Claim the card
            button.disabled = True
            button.style = discord.ButtonStyle.gray
            # disable reroll as well
            for child in self.children:
                if child.label == "Reroll":
                    child.disabled = True

            # change owner and update DB
            card.change_owner(interaction.user.id)
            CardPool.remove_available_card(card)

            actived_potions = func.get_potions(user.get("actived_potions", {}), func.settings.POTIONS_BASE)
            query = func.update_quest_progress(user, ["COLLECT_ANY_CARD", f"COLLECT_{card._tier.upper()}_CARD"], query={
                "$push": {"cards": card.id},
                "$set": {"cooldown.claim": time.time() + (func.settings.COOLDOWN_BASE["claim"][1] * (1 - actived_potions.get("speed", 0)))},
                "$inc": {"exp": 10}
            })
            await func.update_user(interaction.user.id, query)
            await func.update_card(card.id, {"$set": {"owner_id": interaction.user.id}})

            # update message
            try:
                embed = discord.Embed(title="Reward Claimed!", color=discord.Color.green())
                embed.description = f"{interaction.user.mention} claimed {card.tier[0]} **{card._tier.capitalize()}** | {card.display_id} | {card.display_stars}"
                if self.message:
                    await self.message.edit(embed=embed, view=self)
            except Exception:
                pass

            await interaction.response.send_message(f"You claimed {card.display_id}.", ephemeral=True)
            self.stop()

    @discord.ui.button(label="Reroll", style=discord.ButtonStyle.gray, emoji="🔁")
    async def reroll(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        async with self._lock:
            user = await func.get_user(interaction.user.id)
            amount = user.get(self.cost_currency_field, 0)
            if amount < self.current_cost:
                return await interaction.response.send_message(f"You do not have enough {self.cost_currency_field} to reroll! (Need {self.current_cost})", ephemeral=True)

            old_cost = self.current_cost
            # deduct cost
            await func.update_user(interaction.user.id, {"$inc": {self.cost_currency_field: -old_cost}})

            # roll a new card
            await interaction.response.defer()
            old_card = self.current_card
            new_card = await self._roll_card()

            # if we failed to obtain a new_card, restore currency and inform
            if not new_card:
                # give money back
                await func.update_user(interaction.user.id, {"$inc": {self.cost_currency_field: old_cost}})
                return await interaction.followup.send("Failed to reroll. No cards available.", ephemeral=True)

            # success: increment rerolls and update next cost
            self.rerolls += 1
            self.current_cost = max(0, int(old_cost * self.cost_multiplier))

            # update embed and image
            embed = self.build_embed()
            file = None
            try:
                img_bytes = await new_card.image_bytes()
                filename = f"{new_card.id}.webp"
                file = discord.File(img_bytes, filename=filename)
                embed.set_image(url=f"attachment://{filename}")
            except Exception:
                file = None

            try:
                if self.message:
                    if file:
                        await self.message.edit(embed=embed, attachments=[file], view=self)
                    else:
                        await self.message.edit(embed=embed, view=self)
            except Exception:
                try:
                    await interaction.followup.send("Rerolled.", ephemeral=True)
                except:
                    pass

            await interaction.followup.send(f"Rerolled to a new card. Next reroll cost: {self.current_cost} {self.cost_currency_field}", ephemeral=True)


# End of file
