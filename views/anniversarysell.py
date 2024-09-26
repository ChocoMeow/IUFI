import asyncio
import random
import iufi
import discord
import functions as func
from iufi import CardPool

from discord.ext import commands


class AnniversarySellView(discord.ui.View):
    def __init__(
            self,
            seller: discord.ClientUser,
            buyer: discord.Member | None,
            card: iufi.Card,
            candies: int,
            timeout: float | None = 43_200,
    ) -> None:
        super().__init__(timeout=timeout)

        self.seller: discord.ClientUser = seller
        self.buyer: discord.Member | None = buyer
        self.card: iufi.Card = card
        self.candies: int = candies

        self.message: discord.Message = None
        self._lock: asyncio.Lock = asyncio.Lock()

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
        await interaction.response.defer()
        async with self._lock:
            buyer = self.buyer or interaction.user

            if interaction.user != buyer:
                return await interaction.followup.send(f"This card is being bought by {buyer.mention}", ephemeral=True)

            _buyer = await func.get_user(buyer.id)

            if _buyer["candies"] < self.candies:
                return await interaction.followup.send(
                    f"You don't have enough Musical Notes! You only have `{_buyer['candies']}` Musical Notes",
                    ephemeral=True)

            if len(_buyer["cards"]) >= func.settings.MAX_CARDS:
                return await interaction.followup.send(f"**Your inventory is full.**", ephemeral=True)

            if self.card.owner_id != self.seller.id:
                await self.on_timeout()
                self.stop()
                return await interaction.followup.send(
                    f"This card is ineligible for trading because its owner has already converted it or being traded to another user!", ephemeral=True)

            self.card.change_owner(buyer.id)

            # Buyer
            buyer_query = func.update_quest_progress(_buyer, "TRADE_ANY_CARD",
                                                     query={"$push": {"cards": self.card.id},
                                                            "$inc": {"candies": -self.candies}}
                                                     )

            seller_query = {"$pull": {"cards": self.card.id},
                            "$inc": {"candies": self.candies}}

            await func.update_user(self.seller.id, seller_query)

            await func.update_user(buyer.id, buyer_query)
            await func.update_card(self.card.id, {"$set": {"owner_id": buyer.id}})

            embed = discord.Embed(title="🎊 Mystery Card", color=discord.Color.random())
            embed.description = f"```{self.card.display_id}\n" \
                                f"{self.card.display_tag}\n" \
                                f"{self.card.display_frame}\n" \
                                f"{self.card.tier[0]} {self.card.tier[1].capitalize()}\n" \
                                f"{self.card.display_stars}```\n"

            image_bytes, image_format = await asyncio.to_thread(self.card.image_bytes), self.card.format
            embed.set_image(url=f"attachment://image.{self.card.format}")

            await self.on_timeout()
            await interaction.followup.send(
                content=random.choice(iufi.BUY_MESSAGE).format(interaction.user.mention),
                embed=embed,
                file=discord.File(image_bytes, filename=f'image.{image_format}')
            )
