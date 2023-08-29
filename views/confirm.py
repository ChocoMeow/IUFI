import discord

class ConfirmView(discord.ui.View):
    def __init__(self, timeout: float | None = 10) -> None:
        super().__init__(timeout=timeout)

        self.is_confirm: bool = False
        self.message: discord.Message = None

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        
        await self.message.edit(view=self)

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.is_confirm = True
        button.disabled = True
        self.stop()