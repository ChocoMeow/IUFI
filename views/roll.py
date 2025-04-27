import discord, time, asyncio
import functions as func
from iufi.events import is_birthday_event_active, get_current_birthday_card_day

from iufi import CardPool, Card
from iufi.birthday import BirthdayCard

class RollButton(discord.ui.Button):
    def __init__(self, card: Card, **kwargs):
        self.card: Card = card
        self.view: RollView

        # Set button style based on card type
        style = discord.ButtonStyle.green
        emoji = card.tier[0]
        
        # Check if it's a birthday card and adjust appearance
        if hasattr(card, 'day_number'):
            style = discord.ButtonStyle.red
            emoji = "🎂"
        
        super().__init__(
            emoji=emoji,
            style=style,
            **kwargs
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        async with self.view._lock:
            if (owner_id := self.card.owner_id):
                if owner_id != interaction.user.id:
                    return await interaction.response.send_message(f"{interaction.user.mention} This card has been claimed by <@{owner_id}>")
                else:
                    return await interaction.response.send_message(f"{interaction.user.mention} This card has claimed by you already!")
            
            user = await func.get_user(interaction.user.id)
            if (retry := user["cooldown"]["claim"]) > time.time() and self.view.author != interaction.user:
                return await interaction.response.send_message(f"{interaction.user.mention} your next claim is <t:{round(retry)}:R>", ephemeral=True)
            
            # Special handling for birthday cards
            if isinstance(self.card, BirthdayCard):
                day = self.card.day_number
                if str(day) in user.get("birthday_collection", {}):
                    return await interaction.response.send_message(
                        f"{interaction.user.mention} You already have birthday card #{day} in your collection!",
                        ephemeral=True
                    )
                
                # Process birthday card claim
                self.view.claimed_users.add(interaction.user)
                if self.view.author == interaction.user:
                    self.view.author_claimed()
                
                self.disabled = True
                self.style = discord.ButtonStyle.gray

                
                await interaction.response.defer()
                actived_potions = func.get_potions(user.get("actived_potions", {}), func.settings.POTIONS_BASE)
                
                # Update user data with birthday card
                query = {
                    "$set": {
                        f"birthday_collection.{day}": True,
                        "cooldown.claim": time.time() + (func.settings.COOLDOWN_BASE["claim"][1] * (1 - actived_potions.get("speed", 0)))
                    },
                    "$inc": {"birthday_cards_count": 1, "exp": 20}
                }
                
                await func.update_user(interaction.user.id, query)
                await func.update_card(self.card.id, {"$set": {"owner_id": interaction.user.id}})

                func.logger.info(f"User {interaction.user.name}({interaction.user.id}) has successfully claimed birthday card #{day}.")

                await self.view.message.edit(view=self.view)
                await interaction.followup.send(f"🎂 {interaction.user.mention} has claimed Birthday Card #{day}")
                return
                
            # Regular card claiming logic
            if len(user["cards"]) >= func.settings.MAX_CARDS:
                return await interaction.response.send_message(f"**{interaction.user.mention} your inventory is full.**", ephemeral=True)
            
            self.view.claimed_users.add(interaction.user)
            if self.view.author == interaction.user:
                self.view.author_claimed()
                
            self.disabled = True
            self.style = discord.ButtonStyle.gray
            
            self.card.change_owner(interaction.user.id)
            CardPool.remove_available_card(self.card)
            
            await interaction.response.defer()
            actived_potions = func.get_potions(user.get("actived_potions", {}), func.settings.POTIONS_BASE)
            query = func.update_quest_progress(user, ["COLLECT_ANY_CARD", f"COLLECT_{self.card._tier.upper()}_CARD"], query={
                "$push": {"cards": self.card.id},
                "$set": {"cooldown.claim": time.time() + (func.settings.COOLDOWN_BASE["claim"][1] * (1 - actived_potions.get("speed", 0)))},
                "$inc": {"exp": 10}
            })
            await func.update_user(interaction.user.id, query)
            await func.update_card(self.card.id, {"$set": {"owner_id": interaction.user.id}})

            func.logger.info(f"User {interaction.user.name}({interaction.user.id}) has successfully claimed the card: [{self.card.id}].")

            await self.view.message.edit(view=self.view)
            await interaction.followup.send(f"{interaction.user.mention} has claimed ` {self.custom_id} | {self.card.display_id} | {self.card.tier[0]} | {self.card.display_stars} `")
        
class RollView(discord.ui.View):
    def __init__(self, author: discord.Member, cards: list[Card], *, timeout: float | None = None):
        super().__init__(timeout=timeout)

        self.author: discord.Member = author
        self.is_expiry: bool = False

        self.claimed_users: set[discord.Member] = set()
        self.message: discord.Message = None
        self._lock: asyncio.Lock = asyncio.Lock()

        for index, card in enumerate(cards, start=1):
            self.add_item(RollButton(card, custom_id=str(index)))
    
    def author_claimed(self):
        self.is_expiry = True

        for child in self.children:
            child.style = discord.ButtonStyle.blurple

    async def timeout_count(self):
        await asyncio.sleep(30)
        if not self.is_expiry:
            self.author_claimed()
            await self.message.edit(view=self)
        await asyncio.sleep(40)
        for child in self.children:
            child.style = discord.ButtonStyle.gray
            child.disabled = True
        await self.message.edit(content="*🕟 This roll has expired.*", view=self)
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not self.is_expiry and interaction.user != self.author:
            await interaction.response.defer()
            return False
        
        if interaction.user in self.claimed_users:
            await interaction.response.send_message("Oops! You have already claimed a card in this roll", ephemeral=True)
            return False

        return True