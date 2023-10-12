import discord, time, asyncio
import functions as func

from iufi import (
    QuestionPool,
    Question
)

LEVELS_BASE: dict[str, tuple[int, int, hex]] = {
    "easy": (1, 3, 0x7CD74B),
    "medium": (2, 2, 0xF9E853),
    "hard": (3, 1, 0xD75C4B),
}

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
        self._timeout: float = None
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

        self.current += 1
        self._answering_time = time.time()
        await self.response.edit(embed=self.build_embed())

    async def end_game(self) -> None:
        if self._ended_time:
            return
        
        self._ended_time = time.time()
        summary, total_points = self.cal_results()

        user = await func.get_user(self.author.id)
        state = user.get("game_state", {}).get("quiz_game", {
            "points": 0,
            "last_update": 0
        })

        sow, eow = func.get_week_unix_timestamps()
        if not (sow <= state["last_update"] <= eow):
            state["points"] = 0
        
        state["points"] += total_points
        state["last_update"] = time.time()

        embed = discord.Embed(title="Quiz Result", color=discord.Color.random())
        embed.description = f"```{summary}```" \
                            f"```{'🕔 Time Used:':<12} {func.convert_seconds(self.used_time)}\n" \
                            f"{'🕘 Avg Time:':<12} {func.convert_seconds(sum(self._average_time) / len(self.questions))}\n" \
                            f"{'🔥 Points:':<12} {state['points']} ({'+' if total_points >= 0 else '-'}{abs(total_points)})```"

        await func.update_user(self.author.id, {"$set": {"game_state.quiz_game": state}})
        await self.response.edit(content="This quiz has expired.", embed=embed, view=None)

    def build_embed(self) -> discord.Embed:
        question: Question = self.currect_question

        embed = discord.Embed(title=f"Question {self.current + 1} out of {len(self.questions)}", color=LEVELS_BASE.get(question.level)[2])
        embed.description = f"**Answer Time: <t:{round(time.time() + question.average_time)}:R>**\n```{question.question}```"
        if question.attachment:
            embed.set_image(url=question.attachment)

        embed.set_footer(text=f"Correct: {question.correct_rate}% Wrong: {question.wrong_rate}%")

        self._timeout = self._answering_time + question.average_time
        return embed
    
    def cal_results(self) -> tuple[str, float]:
        summary = ""
        total_points = 0.0
        symbols = {True: "✅", False: "❌", None: "⬛"}

        for question, result in zip(self.questions, self._results):
            summary += symbols[result] + " "

            if result is not None:
                points = LEVELS_BASE.get(question.level)
                total_points += points[0] if result else -points[1]
            else:
                total_points -= 0.5

        return summary, total_points

    @property
    def total_time(self) -> float:
        return sum([question.average_time for question in self.questions])
    
    @property
    def used_time(self) -> float:
        return round(self._ended_time - self._start_time, 2)
    
    @property
    def currect_question(self) -> Question:
        return self.questions[self.current - 1]

    @discord.ui.button(label="Answer", style=discord.ButtonStyle.green)
    async def answer(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self._results[self.current] is not None:
            return await interaction.response.send_message("You are already answered! Please for the next question.", ephemeral=True, delete_after=5)

        question = self.currect_question
        modal = AnswerModal()
        await interaction.response.send_modal(modal)
        await modal.wait()

        if self._ended_time:
            return 

        used_time = time.time() - self._answering_time
        self._average_time.append(used_time)
        
        if self._timeout < time.time():
            msg = f"You take too long to answer! Next question will be <t:{round(time.time() + 5)}:R>."
        
        elif modal.answer:
            question.update_average_time(used_time)
            correct = question.check_answer(modal.answer)
            
            msg = f"You are correct! Next question will be <t:{round(time.time() + 5)}:R>." if correct else f"The correct response is `{self.currect_question.answers[0]}.`\nNext question will be <t:{round(time.time() + 5)}:R>."
            self._results[self.current] = correct

        message: discord.Message = await interaction.followup.send(msg, ephemeral=True)
        await message.delete(delay=5)
        return await self.next_question()