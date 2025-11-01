import discord, time, json, asyncio
import functions as func
from random import choice
from typing import List, Tuple
from discord.ext import commands

# Emoji quiz settings
EMOJI_QUIZ_SETTINGS = {
    "reset_price": 30,
    "default": {
        "points": 0,
        "last_update": 0,
        "correct": 0,
        "wrong": 0,
        "timeout": 0,
        "average_time": 0,
        "highest_points": 0
    }
}

# Load song emojis from file
try:
    with open(func.ROOT_DIR + "/song_emojis.json", encoding="utf8") as f:
        SONG_EMOJIS: dict = json.load(f)
except Exception:
    SONG_EMOJIS = {}

class EmojiAnswerModal(discord.ui.Modal):
    def __init__(self, prompt: str, *args, **kwargs) -> None:
        super().__init__(title="Enter your guess")
        self.answer: str = ""
        self.add_item(discord.ui.TextInput(
            label="Your answer",
            placeholder=prompt if len(prompt) <= 100 else prompt[:97] + "...",
            min_length=1,
            max_length=80,
            style=discord.TextStyle.short
        ))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        # store answer then stop
        self.answer = self.children[0].value
        self.stop()

class EmojiQuizView(discord.ui.View):
    """A multi-question emoji quiz view (5 questions).
    Each question is a dict: {"name": str, "emojis": [str], "type": "song"|"drama"}
    """
    def __init__(self, author: discord.Member, questions: List[dict], timeout_per_question: float = 20):
        super().__init__(timeout=timeout_per_question * len(questions) + (len(questions) * 5))
        self.author = author
        self.questions = questions  # list of question dicts
        self._start_time = time.time()
        self._ended_time = None
        self.current: int = 0
        self._results: List[bool|None] = [None] * len(self.questions)
        self._answer_times: List[float] = []
        self._answering_time: float = time.time()
        self._timeout_per_question = timeout_per_question
        self._delay_between_questions = 5
        self.response: discord.Message = None
        self._current_emoji: str = self._pick_emoji_for_current()

    def _pick_emoji_for_current(self) -> str:
        if not self.questions:
            return ""
        entry = self.questions[self.current]
        ems = entry.get("emojis") if isinstance(entry, dict) else None
        return choice(ems) if ems else ""

    def build_embed(self) -> discord.Embed:
        entry = self.questions[self.current]
        qtype = entry.get("type", "song").lower()
        label = "drama" if qtype == "drama" else "song"
        embed = discord.Embed(title=f"Emoji Quiz — Question {self.current + 1}/{len(self.questions)}", color=discord.Color.random())
        remaining = max(0, round(self._answering_time + self._timeout_per_question - time.time()))
        embed.description = f"**Guess the IU {label}:**\n```{self._current_emoji}```\n**Time left:** {remaining}s"
        embed.set_footer(text=f"Answer the question or Skip — You'll see the next one in {self._delay_between_questions}s after each reply")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.author

    async def next_question(self) -> None:
        if self._ended_time:
            return
        if self.current + 1 >= len(self.questions):
            return await self.end_game()
        await asyncio.sleep(self._delay_between_questions)
        self.current += 1
        self._current_emoji = self._pick_emoji_for_current()
        self._answering_time = time.time()
        await self.response.edit(embed=self.build_embed(), view=self)

    async def end_game(self) -> None:
        if self._ended_time:
            return
        self._ended_time = time.time()

        summary_icons = {True: "✅", False: "❌", None: "⬛"}
        summary = ""
        total_points = 0
        for idx, (q, _) in enumerate(self.questions):
            res = self._results[idx]
            summary += summary_icons[res]
            if res is True:
                total_points += 5
            elif res is False:
                total_points -= 2
            else:
                total_points -= 1  # small penalty for timeout

        # update user's game_state.emoji_quiz
        user = await func.get_user(self.author.id)
        state = user.get("game_state", {}).get("emoji_quiz", EMOJI_QUIZ_SETTINGS["default"].copy())
        start_time, end_time = func.get_month_unix_timestamps()
        if not (start_time <= state.get("last_update", 0) <= end_time):
            state = EMOJI_QUIZ_SETTINGS["default"].copy()

        old_highest = state.get("highest_points", 0)
        state["points"] = max(0, state.get("points", 0) + total_points)
        if state["points"] > old_highest:
            state["highest_points"] = state["points"]

        state["last_update"] = time.time()
        state["correct"] += self._results.count(True)
        state["wrong"] += self._results.count(False)
        state["timeout"] += self._results.count(None)

        # average time
        answered_count = len(self._answer_times)
        avg_time = round(sum(self._answer_times) / answered_count, 1) if answered_count else 0
        # roll existing average into stored average
        total_played = state["correct"] + state["wrong"] + state["timeout"]
        if state.get("average_time"):
            state["average_time"] = round(((state["average_time"] * (total_played - 1)) + avg_time) / total_played, 1) if total_played > 0 else avg_time
        else:
            state["average_time"] = avg_time

        await func.update_user(self.author.id, {"$set": {"game_state.emoji_quiz": state}})

        embed = discord.Embed(title="Emoji Quiz Result", color=discord.Color.random())
        embed.description = f"```{summary}```\n**Total points:** {total_points}\n**Correct:** {self._results.count(True)} | **Wrong:** {self._results.count(False)} | **Timeout:** {self._results.count(None)}\n**Avg Answer Time:** {func.convert_seconds(avg_time)}"

        try:
            await self.response.edit(content=None, embed=embed, view=None)
        except:
            pass
        self.stop()

    @discord.ui.button(label="Answer", style=discord.ButtonStyle.green)
    async def answer(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._results[self.current] is not None:
            return await interaction.response.send_message("You already answered this question.", ephemeral=True)
        modal = EmojiAnswerModal(self._current_emoji)
        await interaction.response.send_modal(modal)
        await modal.wait()
        if self._ended_time:
            return
        used_time = time.time() - self._answering_time
        self._answer_times.append(used_time)

        user_answer = func.clean_text(modal.answer, convert_to_lower=True)
        correct = func.clean_text(self.questions[self.current].get("name", ""), convert_to_lower=True)
        is_correct = False
        if user_answer:
            # simple fuzzy check: equality or substring
            if user_answer == correct or correct in user_answer or user_answer in correct:
                is_correct = True
        self._results[self.current] = is_correct

        msg = f"<:IUgiggles:1144937008037384204> {'Correct' if is_correct else 'Incorrect'}. "
        if is_correct:
            msg += f"You answered in `{func.convert_seconds(used_time)}`"
        else:
            msg += f"The correct answer: `{self.questions[self.current].get('name')}`"

        await interaction.followup.send(msg, ephemeral=True)
        await self.next_question()

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.gray)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self._results[self.current] is not None:
            return await interaction.response.send_message("You already answered this question.", ephemeral=True)
        self._results[self.current] = False
        self._answer_times.append(self._timeout_per_question)
        await interaction.response.send_message(f"Skipped. The correct answer was `{self.questions[self.current].get('name')}`.", ephemeral=True)
        await self.next_question()

    async def on_timeout(self) -> None:
        # mark unanswered questions as timeout
        for idx, res in enumerate(self._results):
            if res is None:
                self._results[idx] = None
        try:
            if self.response:
                await self.response.edit(content="Emoji quiz expired.", view=None)
        except:
            pass
        self.stop()

    @property
    def total_time(self) -> float:
        return len(self.questions) * (self._timeout_per_question + self._delay_between_questions)

    async def run(self) -> None:
        """Run the per-question timer loop until the quiz ends."""
        # ensure answering_time is set
        self._answering_time = self._answering_time or time.time()
        while not self._ended_time:
            # wait until current question timeout
            remaining = (self._answering_time + self._timeout_per_question) - time.time()
            if remaining > 0:
                await asyncio.sleep(remaining)

            # If already ended while sleeping, break
            if self._ended_time:
                break

            # If current question still unanswered, treat as timeout
            if self._results[self.current] is None:
                # record timeout
                self._answer_times.append(self._timeout_per_question)
                # send ephemeral-ish notification (channel message deleted shortly after)
                try:
                    await self.response.channel.send(f"Time's up for question {self.current + 1}! The correct answer was `{self.questions[self.current].get('name')}`.", delete_after=self._delay_between_questions)
                except:
                    pass

                # move to next question (this function will call end_game when done)
                await self.next_question()
                # continue loop for next question
            else:
                # already answered; wait briefly and loop
                await asyncio.sleep(0.1)

        # ensure end_game called
        if not self._ended_time:
            await self.end_game()

class EmojiResetAttemptView(discord.ui.View):
    def __init__(self, ctx: commands.Context, user_data: dict, price: int, timeout: float = 20):
        super().__init__(timeout=timeout)

        self.ctx: commands.Context = ctx
        self.data: dict = user_data
        self.price: int = price
        self.response: discord.Message = None

    async def on_timeout(self) -> None:
        for child in self.children:
            child.TextStyle = discord.ButtonStyle.grey
            child.disabled = True
        try:
            await self.response.edit(view=self)
        except:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.ctx.author

    @discord.ui.button(label="Buy", emoji="🛍️", style=discord.ButtonStyle.green)
    async def buy(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.data.get("candies") < self.price:
            await interaction.response.send_message("You do not have enough candies to initiate the reset!", ephemeral=True)
            return await self.on_timeout()

        await func.update_user(self.ctx.author.id, {
            "$set": {"cooldown.quiz_game": 0},
            "$inc": {"candies": -self.price}
        })

        if self.response:
            try:
                await self.response.delete()
            except:
                pass

        # invoke emojiquiz command (not the normal quiz)
        await self.ctx.invoke(self.ctx.bot.get_command("emojiquiz"))
