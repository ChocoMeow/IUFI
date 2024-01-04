import discord, asyncio, iufi, time, random
import functions as func

from discord.ext import commands, tasks

class Tasks(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.invisible = False
        self.game_channel_ids: list[int] = [1155772660979093555, 1155772719909044224, 1155772738858913792, 1155772756730859580]

        self.cache_clear.start()
        self.reminder.start()

    def cog_unload(self):
        self.cache_clear.cancel()
        self.reminder.cancel()
    
    async def schedule_message(self, user: discord.User, wait_time: int, message: str) -> None:
        await asyncio.sleep(wait_time)
        try:
            await user.send(content=message)
        except Exception as _:
            return

    async def check_and_schedule(self, user, current_time, cd_time, message):
        if 0 <= (cd := round(cd_time - current_time)) <= 600:
            self.bot.loop.create_task(self.schedule_message(user, cd, message))

    @tasks.loop(hours=2.0)
    async def cache_clear(self):
        func.USERS_BUFFER.clear()

        iufi.CardPool.search_image = None
        for card in iufi.CardPool._cards.values():
            card._image = None

        questions = {f"{i}": q.toDict() for i, q in enumerate(iufi.QuestionPool._questions, start=1) if q.is_updated}
        if questions:
            func.update_json("questions.json", questions)
        
    @tasks.loop(minutes=10.0)
    async def reminder(self) -> None:
        time_range = {"$gt": (current_time := time.time()), "$lt": current_time + 600}
        query = {"$and":[
            {"reminder": True},
            {"$or": [
                {"cooldown.roll": time_range},
                {"cooldown.daily": time_range},
                {"cooldown.match_game": time_range}
            ]}
        ]}

        async for doc in func.USERS_DB.find(query):
            user = self.bot.get_user(doc["_id"])
            if not user:
                continue

            cd: dict[str, float] = doc["cooldown"]
            await self.check_and_schedule(user, current_time, cd.get("roll", 0), f"🎲 Your roll is ready! Join <#{random.choice(self.game_channel_ids)}> and roll now.")
            await self.check_and_schedule(user, current_time, cd.get("daily", 0), f"📅 Your daily is ready! Join <#{random.choice(self.game_channel_ids)}> and claim your daily.")
            await self.check_and_schedule(user, current_time, cd.get("match_game", 0), f"🃏 Your game is ready! Join <#{random.choice(self.game_channel_ids)}> and play now.")

async def setup(bot: commands.Bot):
    await bot.add_cog(Tasks(bot))