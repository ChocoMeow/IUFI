import discord, time, asyncio, copy
import functions as func
from discord.ext import commands

from discord.ext import commands
from random import choice
from iufi import (
    Question,
    QuestionPool as QP,
    QUIZ_LEVEL_BASE
)
from iufi.events import is_april_fools, is_user_naughty

from typing import Any

QUESTION_RESPONSE_BASE: dict[str, dict[str, list]] = {
    True: {
        "emojis": ["IUgiggles:1144937008037384204", "IUwow:1144937211943452712", "IUkek:1144937045534449694", "IUclap:1144936954782302262", "IUomo:1144937081169264692"],
        "responses": [
            "Fantastic! You’ve answered correctly in {time}.",
            "Brilliant! You got it right in just {time}.",
            "Superb! Your answer is correct and it took you {time}.",
            "Impressive! You nailed the answer in {time}.",
            "Awesome! You’ve got the right answer in {time}.",
            "Excellent work! You answered correctly in {time}.",
            "Good going! You got it right in {time}."
        ]
    },
    False: {
        "emojis": ["IUnice:1144937060600401950", "IUcry:1144936965054152714", "IUthinking:1144937196630069249", "IUweary:1144937203689062523"],
        "responses":  [
            "That’s not quite right, sweetie. The correct answer should be {correct_answer}.",
            "Good attempt, but that’s not the correct answer, darling. It should be {correct_answer}.",
            "Unfortunately, that’s not correct, honey. The right answer is {correct_answer}.",
            "That’s not the right answer, but don’t lose hope! The correct answer is {correct_answer}.",
            "That’s incorrect, but don’t worry! The correct answer is {correct_answer}.",
            "Oops, that’s not correct, sweetheart. The correct answer is {correct_answer}.",
            "That’s not the right answer, but keep going! The correct answer is {correct_answer}."
        ]
    },
    None: {
        "emojis": ["IUfacepalm3:1144937000739274842", "IUsilentmad:1144937146592006195", "IUdone:1144936980275265536"],
        "responses": [
            "Time's up, sweetie! You didn't answer within the given time. But it's okay, let's try the next one!",
            "It seems like you ran out of time to answer this one, darling. Don't worry, there's always next time!",
            "Unfortunately, time has run out and I didn't receive an answer from you, honey.",
            "Looks like you didn't manage to answer this one within the time limit, sweetheart.",
            "Time has run out for this question and I didn't get your response, darling.",
            "Unfortunately, you didn't manage to respond within the given time frame for this one, sweetie.",
            "Looks like time ran out before you could respond to this one, honey. But don't worry, there's always a next time!"
        ]
    },
    "next_question": [
        'The next question will be {next}, sweetie! Are you ready?',
        'Get ready for the next question {next}, darling! Let\'s do this together!',
        'The next question is coming up {next}, honey! I\'m excited to see your answer!',
        'Stay tuned for the next question {next}, sweetheart! I believe in you!'
    ]
}

APRIL = [
    "Seriously? That’s your answer? IU is *disappointed* in you. The correct answer is {correct_answer}.",
    "Wrong. Just wrong. Do better. The right answer is {correct_answer}.",
    "I can’t believe you just typed that. IU expected more from you. It’s {correct_answer}.",
    "That was *painful* to witness. Fix yourself. The correct answer is {correct_answer}.",
    "Nope. Absolutely not. Try harder. The correct answer is {correct_answer}.",
    "IU is shaking her head right now. The right answer is {correct_answer}.",
    "I thought you had potential, but then you answered *that*. It’s {correct_answer}, genius.",
    "Are you even trying? IU is embarrassed for you. The correct answer is {correct_answer}.",
    "Wow… just wow. Even my goldfish could do better. The right answer is {correct_answer}.",
    "That was so wrong it physically hurt me. The correct answer is {correct_answer}.",
    "If I had a dollar for every bad answer you gave, I’d be rich. The right answer is {correct_answer}.",
    "IU just sighed heavily. The correct answer is {correct_answer}.",
    "You really thought that was right? Oh, sweet summer child. It’s actually {correct_answer}.",
    "I have *lost faith* in humanity. The correct answer is {correct_answer}.",
    "Even a broken clock is right twice a day… but not you, apparently. It’s {correct_answer}.",
    "You just made IU facepalm. The correct answer is {correct_answer}.",
    "I’m not mad, just *disappointed*. It’s {correct_answer}.",
    "If this was a test for the worst answer, you’d pass. But the real answer is {correct_answer}.",
    "I’d explain why you’re wrong, but I don’t have *that* much time. The answer is {correct_answer}.",
    "Let’s pretend you didn’t just say that. The real answer is {correct_answer}.",
    "I thought we were friends… and then you gave *this* answer. It’s {correct_answer}.",
    "This is why IU can’t trust you with important decisions. The right answer is {correct_answer}."
]

APRIL_EMOJIS = ["IUfacepalm3:774797483514658856", "IUsilentmad:775231679316754442", "IUdone:879254764754444298","IUjudge2:487511217720655874","IUmad:720656104924643339"]

QUIZ_SETTINGS: dict[str, int] = {
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

class AnswerModal(discord.ui.Modal):
    def __init__(self, question: Question, *args, **kwargs) -> None:
        super().__init__(title="Enter your answer", *args, **kwargs)
        self.answer: str = ""

        self.add_item(
            discord.ui.TextInput(
                label="Answer",
                placeholder=question.question if len(question.question) <= 100 else question.question[:97] + "...",
                min_length=1,
                max_length=50,
                style=discord.TextStyle.short,
            )
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        self.answer = self.children[0].value
        self.stop()

class ResetAttemptView(discord.ui.View):
    def __init__(self, ctx: commands.Context, user_data: dict[str, Any], price: int, timeout: float = 20):
        super().__init__(timeout=timeout)

        self.ctx: commands.Context = ctx
        self.data: dict[str, Any] = user_data
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
            await interaction.response.send_message("You do not have enough Tangerines to initiate the reset!", ephemeral=True)
            return await self.on_timeout()
        
        await func.update_user(self.ctx.author.id, {
            "$set": {"cooldown.quiz_game": 0},
            "$inc": {"candies": -self.price}
        })
        
        if self.response:
            await self.response.delete()

        await self.ctx.invoke(self.ctx.bot.get_command("quiz"))

class QuizView(discord.ui.View):
    def __init__(self, author: discord.Member, questions: list[Question], timeout: float = None, bot: commands.Bot = None):
        super().__init__(timeout=timeout)
        self.bot = bot

        self.author: discord.Member = author
        self.questions: list[Question] = questions
        self._start_time: float = time.time()
        self._ended_time: float = None

        self._answering_time: float = time.time()
        self._timeout: float = None
        self._results: list[bool] = [None for _ in range(len(self.questions))]
        self._average_time: list[float] = []
        self._delay_between_questions: int = 5

        self.current: int = 0
        self.response: discord.Message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return self.author == interaction.user
    
    async def next_question(self) -> None:
        if self._ended_time:
            return
        
        if len(self.questions) <= (self.current + 1):
            return await self.end_game()
        
        await asyncio.sleep(self._delay_between_questions)

        self.current += 1
        self._answering_time = time.time()
        await self.response.edit(embed=self.build_embed())

    async def end_game(self) -> None:
        if self._ended_time:
            return
        
        self._ended_time = time.time()
        summary, total_points = self.cal_results()
        total_answered_count = (len(self.questions) - self._results.count(None))
        if total_answered_count == 0:
            average_time = 0
        else:
            average_time = sum(self._average_time) / total_answered_count
        query = {}
        new_record = False

        user = await func.get_user(self.author.id)
        state = user.get("game_state", {}).get("quiz_game", copy.deepcopy(QUIZ_SETTINGS["default"]))

        start_time, end_time = func.get_month_unix_timestamps()
        if not (start_time <= state["last_update"] <= end_time):
            state = copy.deepcopy(QUIZ_SETTINGS["default"])

        # Increase points by total_points and ensure it's not less than 0 and update the highest_points
        old_highest_points = state["highest_points"]
        state["points"] = max(0, state["points"] + total_points)
        if state["points"] > old_highest_points:
            state["highest_points"] = state["points"]
            new_record = True

        # Update the last update time
        state["last_update"] = time.time()

        # Update the count of correct and wrong answers
        state["correct"] += self._results.count(True)
        state["wrong"] += self._results.count(False)
        state["timeout"] += self._results.count(None)

        # Calculate the new average time
        total_average_time = state["correct"] + state["wrong"] + state["timeout"]
        state["average_time"] = round(((total_average_time * state["average_time"]) + average_time) / (total_average_time + 1), 1) if state["average_time"] else average_time
        query["$set"] = {"game_state.quiz_game": state}

        embed = discord.Embed(title="Quiz Result", color=discord.Color.random())
        embed.description = f"```{summary}```" \
                            f"```{'🕔 Time Used:':<12} {func.convert_seconds(self.used_time)}\n" \
                            f"{'🕘 Avg Time:':<12} {func.convert_seconds(average_time)} {'🔺' if average_time < state['average_time'] else '🔻'}\n" \
                            f"{'🔥 Points:':<12} {state['points']} ({'+' if total_points >= 0 else '-'}{abs(total_points)})```"

        if new_record:
            rank: tuple[str, int] = QP.get_rank(state["points"])
            highest_rank: tuple[str, int] = QP.get_rank(old_highest_points)
            rank_list = list(func.settings.RANK_BASE.keys())

            if rank[0] in rank_list[rank_list.index(highest_rank[0]) + 1:]:
                embed.description += f"\n<:{rank[0]}:{rank[1]}> **{rank[0].title()} Promotion Rewards**```"
                for index, reward in func.settings.RANK_BASE[rank[0]]["rewards"].items():
                    if isinstance(reward[0], list):
                        reward = choice(reward)
                    
                    reward_name, amount = reward
                    if "$inc" not in query:
                        query["$inc"] = {}

                    query["$inc"][reward_name] = amount
                    reward_name = reward_name.split(".")

                    embed.description += f"{index}. "
                    if reward_name[0] == "candies":
                        embed.description += f"{'🍊 Tangerines':<18} x{amount}\n"
                    
                    elif reward_name[0] == "roll":
                        roll_data = func.settings.TIERS_BASE.get(reward_name[1])
                        embed.description += f"{roll_data[0]} {reward_name[1].title() + ' Roll':<16} x{amount}\n"

                    elif reward_name[0] == "exp":
                        embed.description += f"{'⚔️ Exp':<19} x{amount}\n"

                    else:
                        reward_name = reward_name[1].split("_")
                        potion_data = func.settings.POTIONS_BASE.get(reward_name[0])
                        embed.description += f"{potion_data.get('emoji') + ' ' + reward_name[0].title() + ' ' + reward_name[1].upper() + ' Potion':<18} x{amount}\n"

                embed.description += "```"

        score_for_tangerines = max(0, int(total_points/5))
        if score_for_tangerines > 0:
            await func.add_tangerines_quest_progress(int(score_for_tangerines), self.author.id, self.bot)
        await func.update_user(self.author.id, query)

        func.logger.info(
            f"User {self.author.name}({self.author.id}) completed a quiz. "
            f"Start time: {self._start_time}, End time: {self._ended_time}. "
            f"Average time: {average_time}s, "
            f"Correct answers: {self._results.count(True)}, "
            f"Wrong answers: {self._results.count(False)}, "
            f"Unanswered: {self._results.count(None)}. "
            f"Total points: {total_points}, Current points: {state['points']}."
        )

        await self.response.edit(content="This quiz has expired.", embed=embed, view=None)
        self.stop()
        
    def build_embed(self) -> discord.Embed:
        question: Question = self.currect_question
        best_record = question.best_record()
        
        record_msg = f"**Best Record: <@{best_record[0]}> (`{best_record[1]}s`)**\n" if best_record else ""
        embed = discord.Embed(title=f"Question {self.current + 1} out of {len(self.questions)}", color=QUIZ_LEVEL_BASE.get(question.level)[1][2])
        embed.description = f"**Answer Time: <t:{round(time.time() + question.average_time)}:R>**\n{record_msg}```{question.question}```"
        if question.attachment:
            embed.set_image(url=question.attachment)
            embed.description += f"\n\n**Attachment:** {question.attachment}"

        embed.set_footer(text=f"Correct: {question.correct_rate:.1f}% | Wrong: {question.wrong_rate:.1f}%")

        self._timeout = self._answering_time + question.average_time
        return embed
    
    def cal_results(self) -> tuple[str, float]:
        summary = ""
        total_points = 0.0
        symbols = {True: "✅", False: "❌", None: "⬛"}

        for question, result in zip(self.questions, self._results):
            summary += symbols[result] + " "

            points = QUIZ_LEVEL_BASE.get(question.level)[1]
            total_points += points[0] if result else -points[1] if result is False else -points[1] * (1 - .5)

            if result is True:
                question._correct += 1
            else:
                question._wrong += 1

        return summary, total_points

    def gen_response(self, result: bool = None) -> str:
        response_base = QUESTION_RESPONSE_BASE.get(result)
        response = f"<:{choice(response_base.get('emojis'))}> {choice(response_base.get('responses'))} "
        if (self.current + 1) < len(self.questions):
            response += choice(QUESTION_RESPONSE_BASE.get('next_question'))

        return response

    def gen_response_april(self) -> str:
        response_base = APRIL
        response = f"<:{choice(APRIL_EMOJIS)}> {choice(response_base)} "
        if (self.current + 1) < len(self.questions):
            response += choice(QUESTION_RESPONSE_BASE.get('next_question'))

        return response

    @property
    def total_time(self) -> float:
        return sum([question.average_time for question in self.questions]) + (len(self.questions) * self._delay_between_questions)
    
    @property
    def used_time(self) -> float:
        return round(self._ended_time - self._start_time, 2)
    
    @property
    def currect_question(self) -> Question:
        return self.questions[self.current]

    @discord.ui.button(label="Answer", style=discord.ButtonStyle.green)
    async def answer(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self._results[self.current] is not None:
            return await interaction.response.send_message("You are already answered! Please for the next question.", ephemeral=True, delete_after=5)

        question = self.currect_question
        modal = AnswerModal(question)
        await interaction.response.send_modal(modal)
        await modal.wait()

        if self._ended_time:
            return 

        used_time = time.time() - self._answering_time
        self._average_time.append(used_time)
        _next = f"<t:{round(time.time() + self._delay_between_questions)}:R>"

        if self._timeout < time.time():
            question.update_average_time(question.average_time * (1 + .1))
            msg = self.gen_response().format(next=_next)
        
        elif modal.answer:
            correct = question.check_answer(modal.answer)
            if is_april_fools() and is_user_naughty(self.author.id):
                displayed_correct = False
                msg = self.gen_response_april().format(
                    time=f"`{func.convert_seconds(used_time)}`",
                    correct_answer=f"`{self.currect_question.answers[0]}`",
                    next=_next
                )
            else:
                displayed_correct = correct
                msg = self.gen_response(displayed_correct).format(
                    time=f"`{func.convert_seconds(used_time)}`",
                    correct_answer=f"`{self.currect_question.answers[0]}`",
                    next=_next
                )

            self._results[self.current] = correct
            if correct:
                question.update_average_time(used_time)
            question.update_user(self.author.id, modal.answer, used_time, correct)

        message: discord.Message = await interaction.followup.send(msg, ephemeral=True)
        await message.delete(delay=self._delay_between_questions)
        return await self.next_question()

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.red)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self._results[self.current] is not None:
            return await interaction.response.send_message("You cannot skip a question that you have already answered!", ephemeral=True, delete_after=5)

        if self._ended_time:
            return 

        self._results[self.current] = False
        used_time = time.time() - self._answering_time
        self._average_time.append(used_time)
        _next = f"<t:{round(time.time() + self._delay_between_questions)}:R>"
        
        msg = choice(QUESTION_RESPONSE_BASE.get('next_question')).format(next=_next)

        await interaction.response.send_message(msg, ephemeral=True, delete_after=self._delay_between_questions)
        return await self.next_question()


