import discord

class ConfirmView(discord.ui.View):
    def __init__(self, author: discord.Member, timeout: float | None = 10) -> None:
        super().__init__(timeout=timeout)

        self.is_confirm: bool = False
        self.author: discord.Member = author
        self.message: discord.Message = None

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        
        await self.message.edit(view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return self.author == interaction.user
    
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.is_confirm = True
        await self.on_timeout()
        self.stop()