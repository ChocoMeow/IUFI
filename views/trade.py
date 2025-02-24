import discord, time, asyncio
import functions as func

from typing import List

from iufi import Card

class TradeView(discord.ui.View):
    def __init__(
        self,
        seller: discord.Member,
        buyer: discord.Member | None,
        cards: List[Card],
        candies: int,
        timeout: float | None = 43_200,
    ) -> None:
        
        super().__init__(timeout=timeout)

        self.seller: discord.Member = seller
        self.buyer: discord.Member | None = buyer
        self.cards: List[Card] = cards
        self.candies: int = candies

        self._lock: asyncio.Lock = asyncio.Lock()
        self.message: discord.Message = None

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        
        await self.message.edit(view=self)
        self.stop()

    def build_embed(self, image_format: str) -> discord.Embed:
        embed = discord.Embed(title="⤵️ Trade", color=discord.Color.random())
        embed.description = f"```Seller: {self.seller.display_name}\n" \
               f"Buyer: {self.buyer.display_name if self.buyer else 'Anyone'}\n" \
               f"Candies: 🍬 {self.candies}\n\n"

        if len(self.cards) > 1:
            for card in self.cards:
                embed.description += f"{card.display_id} {card.display_tag} {card.display_frame} {card.display_stars} {card.tier[0]}\n"

        else:
            card = self.cards[0]
            embed.description += f"{card.display_id}\n" \
                                 f"{card.display_tag}\n" \
                                 f"{card.display_frame}\n" \
                                 f"{card.tier[0]} {card.tier[1].capitalize()}\n" \
                                 f"{card.display_stars}\n" 
        embed.description += "```"

        embed.set_image(url=f"attachment://image.{image_format}")
        return embed

    @discord.ui.button(label='Trade Now', style=discord.ButtonStyle.green)
    async def trade(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        async with self._lock:
            buyer = self.buyer or interaction.user

            if interaction.user != buyer:
                return await interaction.followup.send(f"This card is being traded to {buyer.mention}", ephemeral=True)
            
            if interaction.user == self.seller:
                return await interaction.followup.send("You can't trade with yourself!", ephemeral=True)
            
            if any(card.owner_id != self.seller.id for card in self.cards):
                await self.on_timeout()
                return await interaction.followup.send(f"This card is ineligible for trading because its owner has already converted it!", ephemeral=True)
            
            _buyer = await func.get_user(buyer.id)
            if _buyer["candies"] < self.candies:
                return await interaction.followup.send(f"You don't have enough candies! You only have `{_buyer['candies']}` candies", ephemeral=True)

            if (len(_buyer["cards"]) + len(self.cards)) > func.settings.MAX_CARDS:
                return await interaction.followup.send(f"**Your inventory is full.**", ephemeral=True)
            
            last_trade_time = time.time()
            card_ids = [card.id for card in self.cards]
            for card in self.cards:
                card.change_owner(buyer.id)
                card.last_trade_time = last_trade_time

            # Seller
            tax = 0.1
            if self.seller.id == 160849769848242176: #mashou 25% tax cause of kiss gif
                tax = 0.25
            elif self.seller.id == 1223531350972174337: #0% for birthday girl
                tax = 0

            smol_tax = round(self.candies * 0.1)
            seller_quantity = self.candies - smol_tax

            _seller = await func.get_user(self.seller.id)
            seller_query = func.update_quest_progress(_seller, "TRADE_ANY_CARD", progress=len(self.cards), query={"$pull": {"cards": {"$in": card_ids}}, "$inc": {"candies": seller_quantity}})
            await func.update_user(self.seller.id, seller_query)
            
            # Buyer
            buyer_query = func.update_quest_progress(_buyer, "TRADE_ANY_CARD", progress=len(self.cards), query={"$push": {"cards": {"$each": card_ids}}, "$inc": {"candies": -self.candies}})
            await func.update_user(buyer.id, buyer_query)
            await func.update_card(card_ids, {"$set": {"owner_id": buyer.id, "last_trade_time": last_trade_time}})

            if smol_tax > 0:
                await func.update_user(1223531350972174337, {"$inc": {"candies": smol_tax}})
            
            func.logger.info(
                f"User {buyer.name}({buyer.id}) traded a card from "
                f"User '{self.seller.name}({self.seller.id}). "
                f"Cards involved: [{', '.join(card_ids)}] "
                f"for {self.candies} candies."
            )

            embed = discord.Embed(title="✅ Traded", color=discord.Color.random())
            embed.description = f"```{', '.join(card.display_id for card in self.cards)}\n🍬 - {self.candies}```"

            await self.on_timeout()
            tax_message= ""
            if smol_tax > 0:
                tax_message = f"Smol tax: {smol_tax} 🍬"
            await interaction.followup.send(content=f"{self.seller.mention}, {buyer.mention} has made a trade with you for the card(s)! {tax_message}", embed=embed)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if interaction.user == self.seller:
            await self.on_timeout()
            self.stop()