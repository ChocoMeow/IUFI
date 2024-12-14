import discord, asyncio
import functions as func

from iufi import Card, CardPool
from random import choice

REPLY_MESSAGES = [
    "{0} just snagged the stunning random drop! Is it a shimmering jewel or just IU's charm? Only one way to find out!",
    "Congratulations, {0}! You’ve won the random drop! Is it a rare card or IU in a sparkly outfit? Let the guessing game begin!",
    "{0} has won the fabulous random drop! Will it be a card so beautiful it sings, or just IU's latest selfie?",
    "Hold the applause! {0} has won the random drop! Will it dazzle us like IU or just leave us guessing?",
    "Look out, world! {0} has scored the random drop! Is it a gorgeous card or IU’s secret talent? The suspense is real!",
    "Drumroll, please! {0} has won the random drop! Is it a work of art or just IU’s latest hairstyle? Prepare for a reveal!",
    "Cheers to {0} for winning the random drop! Will it be a breathtaking card or IU’s magical aura? Stay tuned!",
    "Big news! {0} has snagged the random drop! Is it a beauty that could rival IU or just a really nice rock?",
    "Surprise! {0} has won the random drop! Will it sparkle like IU or just shine a little? Only time will tell!",
    "Hooray for {0}! You’ve won the random drop! Is it a card worthy of IU's collection or just a really shiny paper? Let’s find out!"
]

NAUGHTY_LIST = [122062302865391616,160849769848242176]
class DropView(discord.ui.View):
    def __init__(
        self,
        card: Card,
        timeout: float | None = 70,
    ) -> None:
        
        super().__init__(timeout=timeout)

        self.card: Card = card

        self._lock: asyncio.Lock = asyncio.Lock()
        self.message: discord.Message = None

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        
        await self.message.edit(content="This drop has expired", view=self)

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title="🎁 Random Card Drop", color=discord.Color.random())
        embed.set_image(url=f"attachment://image.{self.card.format}")
        return embed

    @discord.ui.button(label='Claim Now', style=discord.ButtonStyle.green)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        async with self._lock:
            if self.card.owner_id != None:
                await self.on_timeout()
                self.stop()
                return await interaction.followup.send("<:IUsad3:1071179718969266318> Oops! This card has already been claimed by someone else!", ephemeral=True)

            if interaction.user.id in NAUGHTY_LIST:
                return await interaction.followup.send(f"**No drops for you! You're on the naughty list!**", ephemeral=True)
            
            user_data = await func.get_user(interaction.user.id)
            if len(user_data["cards"]) >= func.settings.MAX_CARDS:
                return await interaction.followup.send(f"**Your inventory is full.**", ephemeral=True)
            
            self.card.change_owner(interaction.user.id)
            CardPool.remove_available_card(self.card)

            await func.update_user(interaction.user.id, {"$push": {"cards": self.card.id}})
            await func.update_card(self.card.id, {"$set": {"owner_id": interaction.user.id}})

            func.logger.info(f"User {interaction.user.name}({interaction.user.id}) has successfully claimed a card from a random drop: {self.card}.")

            embed = discord.Embed(title="🎊 Random Drop", color=discord.Color.random())
            embed.description = f"```{self.card.display_id}\n" \
                                f"{self.card.display_tag}\n" \
                                f"{self.card.display_frame}\n" \
                                f"{self.card.tier[0]} {self.card.tier[1].capitalize()}\n" \
                                f"{self.card.display_stars}```\n"
            
            image_bytes, image_format = await self.card.image_bytes(), self.card.format
            embed.set_image(url=f"attachment://image.{self.card.format}")

            await self.on_timeout()
            await interaction.followup.send(content=choice(REPLY_MESSAGES).format(interaction.user.mention), embed=embed, file=discord.File(image_bytes, filename=f'image.{image_format}'))