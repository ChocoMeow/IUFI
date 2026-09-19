import discord


class HDBtn(discord.ui.Button):
    def __init__(self, *, row: int | None = None, gif_message: str | None = None) -> None:
        super().__init__(emoji="⚡", label="HD Image", row=row)
        self._gif_message = gif_message or "Some of these cards do not support HD."

    async def callback(self, interaction: discord.Interaction) -> None:
        reason = None
        if hasattr(self.view, "hd_blocked_reason"):
            reason = self.view.hd_blocked_reason()
        elif self.view.is_gif():
            reason = self._gif_message

        if reason:
            return await interaction.response.send_message(reason, ephemeral=True)

        await self.view.apply_hd(interaction)
