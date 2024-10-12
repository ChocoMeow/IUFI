import discord

import functions as func
from iufi import MusicPool

LEADERBOARD_EMOJIS: list[str] = ["🥇", "🥈", "🥉", "🏅"]

class MusicLeaderboardView(discord.ui.View):
    def __init__(self, author: discord.Member) -> None:
        super().__init__(timeout=60)

        self.author: discord.Member = author
        self.message: discord.Message = None

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        
        await self.message.edit(view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.author
    
    @discord.ui.button(label="Most Liked", emoji="❤️")
    async def most_liked(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer()

        description = ""
        sorted_tracks = sorted(list(MusicPool._questions.values()), key=lambda track: track.likes, reverse=True)
        spaces = (len(str(sorted_tracks[0].likes)) if len(sorted_tracks) > 0 else 1) + 1
        for track in sorted_tracks[:15]:
            description += f"‪‪❤︎‬ ` {track.likes:<{spaces}}` [{func.truncate_string(track.title, 42 - spaces)}]({track.url})\n"

        embed = discord.Embed(
            title="❤️   Music Leaderboard (Most Liked)",
            description=f"This leaderboard displays the songs that players like the most.\n\n{description}",
            color=discord.Color.random()
        )
        embed.set_thumbnail(url=icon.url if (icon := interaction.guild.icon) else None)
        await self.message.edit(embed=embed)
    
    @discord.ui.button(label="Most Record", emoji="📼")
    async def most_record(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer()

        records = {}
        description = ""
        
        for track in MusicPool._questions.values():
            member_id, _ = track.best_record
            if member_id:
                records[member_id] = records.get(member_id, 0) + 1

        sorted_records = sorted(records.items(), key=lambda item: item[1], reverse=True)
        sorted_records_dict = dict(sorted_records)

        for index, (member_id, record_nums) in enumerate(sorted_records_dict.items()):
            if member := interaction.guild.get_member(member_id):
                description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + f"{func.truncate_string(member.display_name):<18} {record_nums:>4} 🎙️\n"

        embed = discord.Embed(
            title="🎙️   Music Leaderboard (Most Records)",
            description=f"This leaderboard displays the number of top records each player holds for every question.\n```{description}```",
            color=discord.Color.random()
        )
        embed.set_thumbnail(url=icon.url if (icon := interaction.guild.icon) else None)
        await self.message.edit(embed=embed)