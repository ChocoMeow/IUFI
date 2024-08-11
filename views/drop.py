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

class DropView(discord.ui.View):
    def __init__(
        self,
        card: Card,
        timeout: float | None = 70,
    ) -> None:
        
        super().__init__(timeout=timeout)

        self.card: Card = card[0]

        self.is_loading: bool = False
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
        if self.is_loading:
            return await interaction.response.send_message("<:IUpray:294109405497131009> Oops! This claim is currently having a party with another user. Please try again later!", ephemeral=True)
        self.is_loading = True

        if self.card.owner_id != None:
            await self.on_timeout()
            self.stop()
            return await interaction.response.send_message("<:IUsad3:1071179718969266318> Oops! This card has already been claimed by someone else!", ephemeral=True)
        
        user_data = await func.get_user(interaction.user.id)
        if len(user_data["cards"]) >= func.settings.MAX_CARDS:
            self.is_loading = False
            return await interaction.response.send_message(f"**Your inventory is full.**", ephemeral=True)
        
        self.card.change_owner(interaction.user.id)
        CardPool.remove_available_card(self.card)
        await interaction.response.defer()

        await func.update_user(interaction.user.id, {"$push": {"cards": self.card.id}})
        await func.update_card(self.card.id, {"$set": {"owner_id": interaction.user.id}})

        embed = discord.Embed(title="🎊 Random Drop", color=discord.Color.random())
        embed.description = f"```{self.card.display_id}\n" \
                            f"{self.card.display_tag}\n" \
                            f"{self.card.display_frame}\n" \
                            f"{self.card.tier[0]} {self.card.tier[1].capitalize()}\n" \
                            f"{self.card.display_stars}```\n"
        
        image_bytes, image_format = await asyncio.to_thread(self.card.image_bytes), self.card.format
        embed.set_image(url=f"attachment://image.{self.card.format}")

        self.is_loading = False
        await self.on_timeout()
        await interaction.followup.send(content=choice(REPLY_MESSAGES).format(interaction.user.mention), embed=embed, file=discord.File(image_bytes, filename=f'image.{image_format}'))