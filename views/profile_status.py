import discord
import iufi
import functions as func

from discord.ext import commands
from pydantic import BaseModel
from typing import Optional, List, Dict

class QuizGame(BaseModel):
    points: float = 0
    correct: int = 0
    wrong: int = 0
    timeout: int = 0
    average_time: float = 0
    highest_points: float = 0
    last_update: float = 0

    @property
    def accuracy(self) -> float:
        return round((self.correct / self.total_questions * 100), 1) if self.total_questions > 0 else 0

    @property
    def total_questions(self) -> int:
        return self.correct + self.wrong + self.timeout
    
    @property
    def total_wrong(self) -> int:
        return self.wrong + self.timeout
    
    @property
    def rank_name(self) -> str:
        return iufi.QuestionPool.get_rank(self.points)[0].title()

    @property
    def rank_emoji(self) -> str:
        return iufi.QuestionPool.get_rank(self.points)[1]
    
class MatchGameLevel(BaseModel):
    click_left: int = 0
    matched: int = 0
    last_update: float
    finished_time: float = 0
    monthly_click_left: int = 0
    monthly_matched: int = 0
    monthly_finished_time: float = 0

class MusicGame(BaseModel):
    points: int = 0
    last_update: float = 0
    monthly_points: int = 0

class EmojiQuiz(BaseModel):
    points: float = 0
    correct: int = 0
    wrong: int = 0
    timeout: int = 0
    average_time: float = 0
    highest_points: float = 0
    last_update: float = 0

    @property
    def total_questions(self) -> int:
        return self.correct + self.wrong + self.timeout

    @property
    def total_wrong(self) -> int:
        return self.wrong + self.timeout
    
    @property
    def accuracy(self) -> float:
        return round((self.correct / self.total_questions * 100), 1) if self.total_questions > 0 else 0

class MVGuess(BaseModel):
    monthly_points: int = 0
    last_update: float = 0

class GameStates(BaseModel):
    quiz_game: Optional[QuizGame] = None
    match_game: Optional[Dict[str, MatchGameLevel]] = None
    music_game: Optional[MusicGame] = None
    emoji_quiz: Optional[EmojiQuiz] = None
    mv_guess: Optional[MVGuess] = None

class PVPStats(BaseModel):
    wins: int = 0
    losses: int = 0
    total_matches: int = 0

    @property
    def total_matches(self) -> int:
        return self.wins + self.losses
    
    @property
    def win_rate(self) -> float:
        return round((self.wins / self.total_matches) * 100, 1) if self.total_matches > 0 else 0
    
class ProfileStatsView(discord.ui.View):
    def __init__(self, ctx: commands.Context, member: discord.Member, daily_rows: List[str]):
        super().__init__(timeout=180.0)  # 3 minutes timeout
        self.ctx = ctx
        self.member = member
        self.daily_rows = daily_rows
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the command invoker and the profile owner to use buttons"""
        if interaction.user.id not in (self.ctx.author.id, self.member.id):
            await interaction.response.send_message(
                "❌ You cannot use these buttons. Only the command invoker or profile owner can interact.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        """Disable buttons when view times out"""
        if self.message:
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True
            try:
                await self.message.edit(view=self)
            except:
                pass  # Message might be deleted

    @discord.ui.button(label="Game Stats", style=discord.ButtonStyle.primary, emoji="📊")
    async def show_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Sends the full game stats when the button is clicked."""
        # Re-fetch user data
        user = await func.get_user(self.member.id)
        raw_game_state = user.get("game_state") or {}
        game_state = GameStates(**raw_game_state)

        pvp_raw = user.get("pvp")
        pvp_stats = PVPStats(**pvp_raw) if pvp_raw else None

        embed = discord.Embed(
            title=f"🎮 {self.member.display_name}'s Detailed Stats",
            color=discord.Color.from_rgb(138, 43, 226)
        )
        embed.set_thumbnail(url=self.member.display_avatar.url)

        # Quiz Game field (inline)
        if (quiz := game_state.quiz_game) and quiz.points > 0:
            quiz_value = (
                "```yaml\n"
                f"Rank:         {quiz.rank_name}\n"
                f"Points:       {quiz.points:,}\n"
                f"Accuracy:     {quiz.accuracy}%\n"
                f"Correct:      {quiz.correct:,}\n"
                f"Wrong:        {quiz.total_wrong:,}\n"
                f"Avg Time:     {func.convert_seconds(quiz.average_time)}\n"
                "```"
            )
        else:
            quiz_value = "```No quiz stats available.```"

        embed.add_field(name=func.framed_title("Quiz Game"), value=quiz_value, inline=False)

        # Card Match field (inline)
        if match_game := game_state.match_game:
            lines = []
            # iterate the configured levels (ensure stable iteration by casting to list)
            for level_key in list(func.settings.MATCH_GAME_SETTINGS.keys()):
                mg = match_game.get(str(level_key))
                prefix = self.daily_rows[int(level_key) - 4]
                lines.append(f"{prefix} Lvl {level_key}: " + f"{mg.matched:>2} cards | {func.convert_seconds(mg.finished_time)}" if mg else "Not attempted")
            match_value = "```\n" + "\n".join(lines) + "\n```"
        else:
            match_value = "```No card match stats available.```"

        embed.add_field(name=func.framed_title("Card Match"), value=match_value, inline=False)

        # Music Game field (inline)
        if (quiz := game_state.music_game) and quiz.points > 0:
            music_value = (
                "```yaml\n"
                f"Points:       {quiz.points:,}\n"
                f"Monthly Pts:  {quiz.monthly_points:,}\n"
                "```"
            )
        else:
            music_value = "```No music game stats available.```"
        
        embed.add_field(name=func.framed_title("Music Game"), value=music_value, inline=False)
        
        # Emoji Quiz field (inline)
        if (quiz := game_state.emoji_quiz) and quiz.points > 0:
            emoji_value = (
                "```yaml\n"
                f"Points:       {quiz.points:,}\n"
                f"Accuracy:     {quiz.accuracy}%\n"
                f"Correct:      {quiz.correct:,}\n"
                f"Wrong:        {quiz.total_wrong:,}\n"
                f"Avg Time:     {func.convert_seconds(quiz.average_time)}\n"
                "```"
            )
        else:
            emoji_value = "```No emoji quiz stats available.```"

        embed.add_field(name=func.framed_title("Emoji Quiz"), value=emoji_value, inline=False)

        # PvP Game field (inline)
        if pvp_stats:
            wins = getattr(pvp_stats, "wins", 0)
            losses = getattr(pvp_stats, "losses", 0)
            total = getattr(pvp_stats, "total_matches", 0)
            win_rate = getattr(pvp_stats, "win_rate", 0)

            wl_ratio = f"{round(wins / losses, 2)}" if losses > 0 else "∞"

            pvp_bar = ""
            if total > 0:
                win_blocks = int((wins / total) * 10)
                win_blocks = max(0, min(10, win_blocks))
                loss_blocks = 10 - win_blocks
                pvp_bar = f"{'🟩' * win_blocks}{'🟥' * loss_blocks}"

            pvp_value = (
                "```yaml\n"
                f"Total Matches:  {total}\n"
                f"Wins:           {wins}\n"
                f"Losses:         {losses}\n"
                f"Win Rate:       {win_rate}%\n"
                f"W/L Ratio:      {wl_ratio}\n"
                "```"
            )
            if pvp_bar:
                pvp_value += f"{pvp_bar} `{win_rate}%`\n"
        else:
            pvp_value = "```No PVP stats available.```"

        embed.add_field(name=func.framed_title("PVP Stats"), value=pvp_value, inline=False)
        embed.set_footer(text="Keep playing to improve your stats! 🌟")

        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="Collections", style=discord.ButtonStyle.primary, emoji="💕")
    async def show_collections(self, interaction: discord.Interaction[commands.Bot], button: discord.ui.Button):
        """Shows the member's collections using the existing CollectionView."""
        await interaction.response.defer()
        await interaction.client.get_command("f")(self.ctx)