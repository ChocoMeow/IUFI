import discord, iufi
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

        self.message: discord.Message = None

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        
        await self.message.edit(view=self)

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title="⤵️ Trade", color=discord.Color.random())
        embed.description = f"```Seller: {self.seller.display_name}\n" \
                            f"Buyer: {self.buyer.display_name if self.buyer else 'Anyone'}\n" \
                            f"{iufi.get_main_currency_name()}: {iufi.get_main_currency_emoji()} {self.candies}\n\n" \
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
        
        user = await func.get_user(buyer.id)
        if user["candies"] < self.candies:
            return await interaction.response.send_message(f"You don't have enough candies! You only have `{user['candies']}` candies", ephemeral=True)

        if len(user["cards"]) >= func.MAX_CARDS:
            return await interaction.response.send_message(f"**Your inventory is full.**", ephemeral=True)
        
        await interaction.response.defer()
        self.card.change_owner(buyer.id)
        await func.update_user(self.seller.id, {"$pull": {"cards": self.card.id}, "$inc": {"candies": self.candies}})
        await func.update_user(buyer.id, {"$push": {"cards": self.card.id}, "$inc": {"candies": -self.candies}})
        await func.update_card(self.card.id, {"$set": {"owner_id": buyer.id}})
        await func.add_daily_quest_progress(buyer.id, 4, 1)
        await func.add_daily_quest_progress(self.seller.id, 4, 1)

        embed = discord.Embed(title="✅ Traded", color=discord.Color.random())
        embed.description = f"```{self.card.display_id}\n{iufi.get_main_currency_emoji()} - {self.candies}```"

        await self.on_timeout()
        await interaction.followup.send(content=f"{self.seller.mention}, {buyer.mention} has made a trade with you for the card!", embed=embed)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if interaction.user == self.seller:
            await self.on_timeout()
            self.stop()