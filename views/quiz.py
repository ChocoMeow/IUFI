import discord
import functions as func

from iufi import (
    QuestionPool,
    Question
)

class QuizView(discord.ui.View):
    def __init__(self, author: discord.Member, timeout: float = None):
        super().__init__(timeout=timeout)

        self.author: discord.Member = author
        self.questions: list[Question] = QuestionPool.get_question()

        self.current: int = 1
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return self.author == interaction.user

    def build_embed(self) -> discord.Embed:
        question: Question = self.questions[self.current]

        embed = discord.Embed(title=f"Question {self.current} out of {len(self.questions)}", color=discord.Color.random())
        embed.description = f"```{question.question}```"
        if question.attachment:
            embed.set_thumbnail(url=question.attachment)

        embed.set_footer(text=f"Correct: {question.correct_rate} Wrong: {question.wrong_rate}")
        return embed