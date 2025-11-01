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

    @discord.ui.button(label="Top Points", emoji="🔥")
    async def top_points(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        # retrieve all users buffer and sort by game_state.emoji_quiz.points
        users = func.USERS_BUFFER.values()
        users_list = []
        for user in users:
            gs = user.get('game_state', {}).get('emoji_quiz', {})
            points = gs.get('points', 0)
            users_list.append((user.get('_id'), points))

        users_list = sorted(users_list, key=lambda i: i[1], reverse=True)[:15]
        description = ""
        for idx, (user_id, pts) in enumerate(users_list):
            member = interaction.guild.get_member(user_id)
            name = member.display_name if member else str(user_id)
            description += f"{LEADERBOARD_EMOJIS[idx if idx < 4 else 3]} {name:<18} {pts:>6} pts\n"

        embed = discord.Embed(title="Emoji Quiz Leaderboard (Top Points)", description=f"{description}", color=discord.Color.random())
        embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
        await self.message.edit(embed=embed)

    @discord.ui.button(label="Most Correct", emoji="✅")
    async def most_correct(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        users = func.USERS_BUFFER.values()
        users_list = []
        for user in users:
            gs = user.get('game_state', {}).get('emoji_quiz', {})
            correct = gs.get('correct', 0)
            users_list.append((user.get('_id'), correct))

        users_list = sorted(users_list, key=lambda i: i[1], reverse=True)[:15]
        description = ""
        for idx, (user_id, correct) in enumerate(users_list):
            member = interaction.guild.get_member(user_id)
            name = member.display_name if member else str(user_id)
            description += f"{LEADERBOARD_EMOJIS[idx if idx < 4 else 3]} {name:<18} {correct:>6} correct\n"

        embed = discord.Embed(title="Emoji Quiz Leaderboard (Most Correct)", description=f"{description}", color=discord.Color.random())
        embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
        await self.message.edit(embed=embed)

