import discord, asyncio
import functions as func

from iufi import Card

class FrameDropDown(discord.ui.Select):
    def __init__(self):
        self.view: FrameView
        
        super().__init__(
            options=[
                discord.SelectOption(
                    emoji=data[0],
                    label=frame_name.title(),
                    description=f"🎵 {data[1]}"
                )
                for frame_name, data in func.settings.FRAMES_BASE.items()
            ],
            placeholder="Select a frame to view...",
            min_values=1, max_values=1, row=0
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        self.view._selected_frame = self.values[0].lower()
        self.view._price = func.settings.FRAMES_BASE.get(self.view._selected_frame)[1]
        embed, file = await self.view.build()
        await interaction.response.edit_message(embed=embed, attachments=[file])

class FrameView(discord.ui.View):
    def __init__(self, author: discord.Member, card: Card, timeout: float = 60):
        super().__init__(timeout=timeout)

        self.author: discord.Member = author
        self.card: Card = card

        self._selected_frame: str = ""
        self._price: int = 0
        self.response: discord.Message = None

        self.add_item(FrameDropDown())

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        
        await self.response.edit(view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> None:
        return interaction.user == self.author
    
    async def build(self) -> tuple[discord.Embed, discord.File]:
        embed = discord.Embed(title="🖼️  Frame Preview", color=discord.Color.random())
        embed.description = f"```🆔 {self.card.tier[0]} {self.card.id}\n🖼️ {self._selected_frame.title()}\n🎵 {self._price}```"
        bytes = await asyncio.to_thread(self.card.preview_frame, self._selected_frame)
        embed.set_image(url="attachment://image.webp")

        return embed, discord.File(bytes, filename="image.webp")
    
    @discord.ui.button(label="Apply", style=discord.ButtonStyle.green, row=1)
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._selected_frame:
            return await interaction.response.send_message("You must select a frame to apply!", ephemeral=True)

        user = await func.get_user(self.author.id)
        if user["candies"] < self._price:
            return await interaction.response.send_message(f"You don't have enough Musical Notes! You only have `{user['candies']}` Musical Notes", ephemeral=True)
        
        try:
            self.card.change_frame(self._selected_frame)
        except Exception as e:
            return await interaction.response.send_message(e, ephemeral=True)
        
        query = func.update_quest_progress(user, "FRAME_CONFIG", query={"$inc": {"candies": -self._price}})
        await func.update_user(self.author.id, query)
        await func.update_card(self.card.id, {"$set": {"frame": self._selected_frame}})
        await self.response.edit(view=None)

        embed = discord.Embed(title="🖼️  Set Frame", color=discord.Color.random())
        embed.description = f"```🆔 {self.card.tier[0]} {self.card.id}\n{self.card.display_frame}```"
        await interaction.response.send_message(embed=embed)