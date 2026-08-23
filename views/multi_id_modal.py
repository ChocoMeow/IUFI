import discord

from typing import Awaitable, Callable, List

class MultiIDModal(discord.ui.Modal):
    """Collects a space/comma separated list of card IDs for slash commands that used to take variadic args."""

    def __init__(self, *, title: str, label: str, callback: Callable[[discord.Interaction, List[str]], Awaitable[None]], placeholder: str = "e.g. 01 02 03 or 01, 02, 03") -> None:
        super().__init__(title=title)
        self._callback = callback

        self.ids_input = discord.ui.TextInput(
            label=label,
            style=discord.TextStyle.paragraph,
            placeholder=placeholder,
            required=True
        )
        self.add_item(self.ids_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = self.ids_input.value.replace(",", " ")
        card_ids = [card_id for card_id in raw.split() if card_id]

        if not card_ids:
            return await interaction.response.send_message("No card IDs were provided. Please try again.", ephemeral=True)

        await self._callback(interaction, card_ids)
