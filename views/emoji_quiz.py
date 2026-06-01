import discord, time, json, asyncio
import functions as func
from random import choice
from typing import List, Optional
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
    import os
    with open(os.path.join(func.ROOT_DIR, "data", "song_emojis.json"), encoding="utf8") as f:
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
        self.response: Optional[discord.Message] = None
        # event used to wake the run loop when next_question advances the quiz
        self._advance_event: asyncio.Event = asyncio.Event()
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
        # show a discord-friendly expiry timestamp so the client updates the relative time automatically
        expire_ts = round(self._answering_time + self._timeout_per_question)
        embed.description = f"**Guess the IU {label}:**\n```{self._current_emoji}```\n**Ends:** <t:{expire_ts}:R>"
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
        # notify the run loop that a new question has started
        try:
            self._advance_event.set()
        except Exception:
            pass

    async def end_game(self) -> None:
        if self._ended_time:
            return
        # wake the run loop if it's waiting on the advance event
        try:
            self._advance_event.set()
        except Exception:
            pass
        self._ended_time = time.time()

        summary_icons = {True: "✅", False: "❌", None: "⬛"}
        summary = ""
        total_points = 0
        for idx, q in enumerate(self.questions):
            res = self._results[idx]
            summary += summary_icons[res]
            if res is True:
                total_points += 1

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

        # Log quiz end
        try:
            func.logger.info(f"Emoji quiz ended for user {self.author.name}({self.author.id}) - points={total_points}, correct={self._results.count(True)}, wrong={self._results.count(False)}, timeout={self._results.count(None)}, avg_time={avg_time}s")
        except Exception:
            pass

        # If the player scored >0 points, present a card reward view based on their points.
        # Points are already between 0 and 5 (max questions = 5). If 0, no rewards.
        if total_points and total_points > 0:
            try:
                # Import the RewardCardView from the local views package
                from .reward_card import RewardCardView

                points = min(5, int(total_points))
                # Get probabilities from settings
                probs_config = func.settings.REWARD_CARD_PROBABILITIES or {}
                probs_config = probs_config.get("EMOJI_QUIZ", {})
                probs = probs_config.get(str(points), probs_config.get("5", {}))

                # Create the reward view (we won't call its send method; we'll roll a card and post on the same channel)
                reward_view = RewardCardView(None, self.author, probs, initial_cost=10, cost_currency_field="candies", timeout=120)

                # Roll initial card for the view so build_embed has a card to show
                await reward_view._roll_card()

                # Build the embed & attempt to attach the card image
                reward_embed = reward_view.build_embed()
                file = None
                if reward_view.current_card:
                    try:
                        img_bytes = await reward_view.current_card.image_bytes()
                        filename = f"{reward_view.current_card.id}.webp"
                        file = discord.File(img_bytes, filename=filename)
                        reward_embed.set_image(url=f"attachment://{filename}")
                    except Exception:
                        file = None

                # Post the reward message in the same channel as the quiz response and attach the view
                reward_content = f"**{self.author.mention} This reward ends <t:{reward_view.expires_at}:R>**\n🎁 Card reward for scoring {total_points} point{'s' if total_points != 1 else ''}!"
                reward_msg = await self.response.channel.send(
                    content=reward_content,
                    embed=reward_embed,
                    file=file,
                    view=reward_view
                )
                reward_view.message = reward_msg
            except Exception:
                # Fail silently (don't block quiz end) but log if logger available
                try:
                    func.logger.exception("Failed to present emoji quiz reward view")
                except:
                    pass
        self.stop()

    @discord.ui.button(label="Answer", style=discord.ButtonStyle.green)
    async def answer(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Capture the question index and answering time at the moment the button is pressed.
        question_idx = self.current
        answering_time_at_press = self._answering_time

        # If this question is already answered (fast check at press time), reject immediately.
        if self._results[question_idx] is not None:
            return await interaction.response.send_message("You already answered this question.", ephemeral=True)

        # Show the modal using the emoji snapshot for this question
        modal = EmojiAnswerModal(self._current_emoji)
        await interaction.response.send_modal(modal)
        await modal.wait()

        # If the quiz ended while waiting, ignore submission
        if self._ended_time:
            return

        # If the question index has changed or the time for that question has expired,
        # do not accept the answer (it arrived too late).
        time_since_press = time.time() - answering_time_at_press
        if question_idx != self.current or time_since_press > self._timeout_per_question:
            # Inform the user their answer arrived too late and do not mark as answered.
            try:
                await interaction.followup.send("Too late — the question has already moved on or timed out, your answer wasn't counted.", ephemeral=True)
            except Exception:
                pass
            return

        # Record time and evaluate answer for the captured question index
        used_time = time.time() - answering_time_at_press
        self._answer_times.append(used_time)

        user_answer = func.clean_text(modal.answer, convert_to_lower=True)
        correct = func.clean_text(self.questions[question_idx].get("name", ""), convert_to_lower=True)
        is_correct = False
        if user_answer:
            # Use similarity functions for better fuzzy matching
            jac_sim = func.jac_similarity(user_answer, correct)
            lev_sim = func.lev_similarity(user_answer, correct)

            # Consider correct if either similarity is high (>= 0.8) or exact/substring match
            if jac_sim >= 0.8 or lev_sim >= 0.8 or user_answer == correct:
                is_correct = True

        # Mark the result for the original question index
        self._results[question_idx] = is_correct

        msg = f"<:IUgiggles:1144937008037384204> {'Correct' if is_correct else 'Incorrect'}. "
        if is_correct:
            msg += f"You answered in `{func.convert_seconds(used_time)}`"
        else:
            msg += f"The correct answer: `{self.questions[question_idx].get('name')}`"

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
                await self.response.edit(content=f"Emoji quiz expired <t:{round(time.time())}:R>.", view=None)
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
            # compute remaining time for the current question
            remaining = (self._answering_time + self._timeout_per_question) - time.time()
            if remaining > 0:
                try:
                    # wait until either the question advances (event set) or timeout expires
                    await asyncio.wait_for(self._advance_event.wait(), timeout=remaining)
                    # if event set, clear and continue to monitor the new question
                    self._advance_event.clear()
                    continue
                except asyncio.TimeoutError:
                    # timeout expired for this question
                    pass

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
