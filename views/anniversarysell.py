import asyncio

import discord
import functions as func
from discord.ext import commands

from iufi import Card


class AnniversarySellView(discord.ui.View):
    def __init__(
            self,
            seller: commands.Bot,
            buyer: discord.Member | None,
            card: Card,
            candies: int,
            timeout: float | None = 43_200,
    ) -> None:

        super().__init__(timeout=timeout)

        self.seller: commands.Bot = seller
        self.buyer: discord.Member | None = buyer
        self.card: Card = card
        self.candies: int = candies

        self.is_loading: bool = False
        self.message: discord.Message = None

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True

        await self.message.edit(view=self)

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title="⤵️ SALE", color=discord.Color.random())
        embed.description = f"```Musical Notes: 🎵 {self.candies}\n\n" \
                            f"{self.card.tier[0]} {self.card.tier[1].capitalize()}\n" \
                            f"{self.card.display_stars}```\n"

        embed.set_image(url=f"attachment://image.{self.card.format}")
        return embed

    @discord.ui.button(label='Buy', style=discord.ButtonStyle.green)
    async def trade(self, interaction: discord.Interaction, button: discord.ui.Button):
        buyer = self.buyer or interaction.user

        if interaction.user != buyer:
            return await interaction.response.send_message(f"This card is being traded to {buyer.mention}",
                                                           ephemeral=True)

        if interaction.user == self.seller:
            return await interaction.response.send_message("You can't trade with yourself!", ephemeral=True)

        if self.is_loading:
            return await interaction.response.send_message(
                "This sale is currently being processed for another user. Please try again later!", ephemeral=True)
        self.is_loading = True

        _buyer = await func.get_user(buyer.id)
        if _buyer["candies"] < self.candies:
            self.is_loading = False
            return await interaction.response.send_message(
                f"You don't have enough Musical Notes! You only have `{_buyer['candies']}` Musical Notes", ephemeral=True)

        if len(_buyer["cards"]) >= func.settings.MAX_CARDS:
            self.is_loading = False
            return await interaction.response.send_message(f"**Your inventory is full.**", ephemeral=True)

        self.card.change_owner(buyer.id)
        await interaction.response.defer()

        # Buyer
        buyer_query = func.update_quest_progress(_buyer, "TRADE_ANY_CARD", query={"$push": {"cards": self.card.id},
                                                                                  "$inc": {"candies": -self.candies}})
        await func.update_user(buyer.id, buyer_query)
        await func.update_card(self.card.id, {"$set": {"owner_id": buyer.id}})

        self.is_loading = False
        await self.on_timeout()
        await interaction.followup.send(
            content=f"{buyer.mention} has bought the card! (id : {self.card.id})",file=discord.File(await asyncio.to_thread(self.card.image_bytes), filename=f"image.{self.card.format}"))