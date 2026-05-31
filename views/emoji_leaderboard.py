import discord
import functions as func
from typing import List

LEADERBOARD_EMOJIS: List[str] = ["🥇", "🥈", "🥉", "🏅"]

class EmojiLeaderboardView(discord.ui.View):
    def __init__(self, author: discord.Member) -> None:
        super().__init__(timeout=60)
        self.author = author
        self.message: discord.Message = None

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        try:
            await self.message.edit(view=self)
        except:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.author

