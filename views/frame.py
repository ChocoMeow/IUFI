import discord, asyncio
import functions as func

from iufi import (
    Card,
    FRAMES_BASE
)

FRAMES: tuple[tuple[str, str, int]] = (
    (values[0], frame, values[1]) 
    for frame, values in FRAMES_BASE.items()
)

class FrameDropDown(discord.ui.Select):
    def __init__(self):
        self.view: FrameView
        
        super().__init__(
            options=[
                discord.SelectOption(
                    emoji=emoji,
                    label=frame_name.title(),
                    description=f"🍬 {candy}"
                )
                for emoji, frame_name, candy in FRAMES
            ],
            placeholder="Select a frame to view...",
            min_values=1, max_values=1, row=1
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        self.view._selected_frame = self.values[0].lower()
        embed, file = await self.view.build()
        await interaction.response.edit_message(embed=embed, attachments=[file])

class FrameView(discord.ui.View):
    def __init__(self, author: discord.Member, card: Card, timeout: float = 60):
        super().__init__(timeout=timeout)

        self.author: discord.Member = author
        self.card: Card = card

        self._selected_frame: str = None

        self.add_item(FrameDropDown())

    async def build(self) -> tuple[discord.Embed, discord.File]:
        embed = discord.Embed(title="🖼️ Frame Preview", color=discord.Color.random())
        embed.description = f"```🆔 {self.card.tier[0]} {self.card.id}\n🖼️ {self._selected_frame.title()}```"
        bytes = await asyncio.to_thread(self.card.preview_frame, self._selected_frame)
        embed.set_image(url="attachment://image.png")

        return embed, discord.File(bytes, filename="image.png")
    
    @discord.ui.button(label="Apply", style=discord.ButtonStyle.green)
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._selected_frame:
            return await interaction.response.send_message("You must select a frame to apply!")

        await func.update_card(self.card.id, {"$set": {"frame": self._selected_frame}})
        self.card.change_frame(self._selected_frame)
        