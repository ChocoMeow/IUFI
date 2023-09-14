import discord
import functions as func

from iufi import Card

class TradeView(discord.ui.View):
    def __init__(
            self,
            seller: discord.Member,
            buyer: discord.Member,
            card: Card, 
            candies: int,
            timeout: float | None = 43_200
        ) -> None:
        super().__init__(timeout=timeout)

        self.seller: discord.Member = seller
        self.buyer: discord.Member = buyer
        self.card: Card = card
        self.candies: int = candies

        self.message: discord.Message = None

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        
        await self.message.edit(view=self)

    @discord.ui.button(label='Trade Now', style=discord.ButtonStyle.green)
    async def trade(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.buyer:
            return await interaction.response.send_message(f"This card is being traded to {self.buyer.mention}", ephemeral=True)
        
        if self.card.owner_id != self.seller.id:
            await self.on_timeout()
            self.stop()
            return await interaction.response.send_message(f"This card is ineligible for trading because its owner has already converted it!", ephemeral=True)
        
        user = func.get_user(self.buyer.id)
        if user["candies"] < self.candies:
            return await interaction.response.send_message(f"You don't have enough candies! You only have `{user['candies']}` candies", ephemeral=True)

        if len(user["cards"]) >= func.MAX_CARDS:
            return await interaction.response.send_message(f"**Your inventory is full.**", ephemeral=True)
        
        await interaction.response.defer()
        self.card.change_owner(self.buyer.id, remove_tag=False)
        func.update_user(self.seller.id, {"$pull": {"cards": self.card.id}, "$inc": {"candies": self.candies}})
        func.update_user(self.buyer.id, {"$push": {"cards": self.card.id}, "$inc": {"candies": self.candies}})
        func.update_card(self.card.id, {"$set": {"owner_id": self.buyer.id}})

        embed = discord.Embed(title="✅ Traded", color=discord.Color.random())
        embed.description = f"```🆔 {self.card.id}\n🍬 - {self.candies}```"

        await self.on_timeout()
        await interaction.followup.send(content=f"{self.seller.mention}, {self.buyer.mention} has made a trade with you for the card!", embed=embed)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if interaction.user == self.seller:
            await self.on_timeout()
            self.stop()