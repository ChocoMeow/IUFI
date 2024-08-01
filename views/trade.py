import discord
import functions as func

from iufi import Card

class TradeView(discord.ui.View):
    def __init__(
            self,
            seller: discord.Member,
            buyer: discord.Member | None,
            card: Card,
            candies: int,
            timeout: float | None = 43_200,
        ) -> None:
        
        super().__init__(timeout=timeout)

        self.seller: discord.Member = seller
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
        embed = discord.Embed(title="⤵️ Trade", color=discord.Color.random())
        embed.description = f"```Seller: {self.seller.display_name}\n" \
                            f"Buyer: {self.buyer.display_name if self.buyer else 'Anyone'}\n" \
                            f"Candies: 🍬 {self.candies}\n\n" \
                            f"{self.card.display_id}\n" \
                            f"{self.card.display_tag}\n" \
                            f"{self.card.display_frame}\n" \
                            f"{self.card.tier[0]} {self.card.tier[1].capitalize()}\n" \
                            f"{self.card.display_stars}```\n"
        
        embed.set_image(url=f"attachment://image.{self.card.format}")
        return embed

    @discord.ui.button(label='Trade Now', style=discord.ButtonStyle.green)
    async def trade(self, interaction: discord.Interaction, button: discord.ui.Button):
        buyer = self.buyer or interaction.user

        if interaction.user != buyer:
            return await interaction.response.send_message(f"This card is being traded to {buyer.mention}", ephemeral=True)
        
        if interaction.user == self.seller:
            return await interaction.response.send_message("You can't trade with yourself!", ephemeral=True)
        
        if self.card.owner_id != self.seller.id:
            await self.on_timeout()
            self.stop()
            return await interaction.response.send_message(f"This card is ineligible for trading because its owner has already converted it!", ephemeral=True)
        
        if self.is_loading:
            return await interaction.response.send_message("This trade is currently being processed for another user. Please try again later!", ephemeral=True)
        self.is_loading = True

        _buyer = await func.get_user(buyer.id)
        if _buyer["candies"] < self.candies:
            self.is_loading = False
            return await interaction.response.send_message(f"You don't have enough candies! You only have `{_buyer['candies']}` candies", ephemeral=True)

        if len(_buyer["cards"]) >= func.settings.MAX_CARDS:
            self.is_loading = False
            return await interaction.response.send_message(f"**Your inventory is full.**", ephemeral=True)
        
        self.card.change_owner(buyer.id)
        await interaction.response.defer()

        # Seller
        _seller = await func.get_user(self.seller.id)
        seller_query = func.update_quest_progress(_seller, "TRADE_ANY_CARD", query={"$pull": {"cards": self.card.id}, "$inc": {"candies": self.candies}})
        await func.update_user(self.seller.id, seller_query)
        
        # Buyer
        buyer_query = func.update_quest_progress(_buyer, "TRADE_ANY_CARD", query={"$push": {"cards": self.card.id}, "$inc": {"candies": -self.candies}})
        await func.update_user(buyer.id, buyer_query)
        await func.update_card(self.card.id, {"$set": {"owner_id": buyer.id}})

        embed = discord.Embed(title="✅ Traded", color=discord.Color.random())
        embed.description = f"```{self.card.display_id}\n🍬 - {self.candies}```"

        self.is_loading = False
        await self.on_timeout()
        await interaction.followup.send(content=f"{self.seller.mention}, {buyer.mention} has made a trade with you for the card!", embed=embed)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if interaction.user == self.seller:
            await self.on_timeout()
            self.stop()