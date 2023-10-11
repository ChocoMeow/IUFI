import discord, time, asyncio
import functions as func

from iufi import (
    QuestionPool,
    Question
)

class AnswerModal(discord.ui.Modal):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(title="Enter your answer", *args, **kwargs)
        self.answer: str = ""

        self.add_item(
            discord.ui.TextInput(
                label="Answer",
                style=discord.TextStyle.long,
            )
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        self.answer = self.children[0].value
        self.stop()

class QuizView(discord.ui.View):
    def __init__(self, author: discord.Member, timeout: float = None):
        super().__init__(timeout=timeout)

        self.author: discord.Member = author
        self.questions: list[Question] = QuestionPool.get_question()
        self._start_time: float = time.time()
        self._ended_time: float = None

        self._answering_time: float = time.time()
        self._is_answered: bool = False
        self._is_timeout: bool = False
        self._results: list[bool] = [None for _ in range(len(self.questions))]
        self._average_time: list[float] = []

        self.current: int = 0
        self.response: discord.Message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return self.author == interaction.user
    
    async def next_question(self) -> None:
        if len(self.questions) <= (self.current + 1):
            return await self.end_game()
        
        await asyncio.sleep(5)
        self._is_timeout = False
        self._is_answered = False

        self.current += 1
        await self.response.edit(embed=self.build_embed())

        self._answering_time = time.time()
        await self.counter(self.currect_question.average_time, self.current)
    
    async def counter(self, count: int, current_question: int) -> None:
        await asyncio.sleep(count)
        if current_question == self.current:
            self._is_timeout = True

    async def end_game(self) -> None:
        self._ended_time = time.time()
        embed = discord.Embed(title="Quiz Result", color=discord.Color.random())
        embed.description = f"```{self.display_results()}```" \
                            f"```{'Time Used:':<12} {func.convert_seconds(self.used_time)}\n" \
                            f"{'Avg Time:':<12} {func.convert_seconds(sum(self._average_time) / len(self.questions))}```"

        await self.response.edit(content="This quiz has expired.", embed=embed, view=None)

    def build_embed(self) -> discord.Embed:
        question: Question = self.currect_question

        embed = discord.Embed(title=f"Question {self.current + 1} out of {len(self.questions)}", color=discord.Color.random())
        embed.description = f"**Answer Time: <t:{round(time.time() + question.average_time)}:R>**\n```{question.question}```"
        if question.attachment:
            embed.set_image(url=question.attachment)

        embed.set_footer(text=f"Correct: {question.correct_rate}% Wrong: {question.wrong_rate}%")
        return embed
    
    def display_results(self) -> str:
        mapping = {True: "✅", False: "❌"}
        string = ' '.join(mapping.get(result, "⬛") for result in self._results)
        return string

    @property
    def used_time(self) -> float:
        return round(self._ended_time - self._start_time, 2)
    
    @property
    def currect_question(self) -> Question:
        return self.questions[self.current - 1]

    @discord.ui.button(label="Answer", style=discord.ButtonStyle.green)
    async def answer(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self._is_answered:
            return await interaction.response.send_message("You are already answered! Please for the next question.", ephemeral=True, delete_after=5)

        question = self.currect_question
        modal = AnswerModal()
        await interaction.response.send_modal(modal)
        await modal.wait()

        if self._ended_time:
            return 

        if self._is_timeout:
            message = await interaction.followup.send(f"You take too long to answer! Next question will be <t:{round(time.time() + 5)}:R>.", ephemeral=True)
        
        elif modal.answer:
            used_time = time.time() - self._answering_time
            self._average_time.append(used_time)
            question.update_average_time(used_time)

            self._is_answered = True
            correct = question.check_answer(modal.answer)

            if not correct:
                question._wrong += 1
                message: discord.Message = await interaction.followup.send(f"The correct response is `{self.currect_question.answers[0]}.`\nNext question will be <t:{round(time.time() + 5)}:R>.", ephemeral=True)
            else:
                question._correct += 1
                message: discord.Message = await interaction.followup.send(f"You are correct! Next question will be <t:{round(time.time() + 5)}:R>.", ephemeral=True)

            self._results[self.current] = correct

        await message.delete(delay=5)
        return await self.next_question()

