import discord, asyncio, iufi, time
import functions as func

from discord.ext import commands, tasks

class Tasks(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.invisible = False
        self.cache_clear.start()

    def cog_unload(self):
        self.cache_clear.cancel()
    
    async def schedule_message(self, user: discord.User, wait_time: int, message: str) -> None:
        await asyncio.sleep(wait_time)
        try:
            await user.send(content=message)
        except Exception as _:
            return

    async def check_and_schedule(self, user, current_time, cd_time, message):
        if (cd := round(cd_time - current_time)) <= 600:
            self.bot.loop.create_task(self.schedule_message(user, cd, message))

    @tasks.loop(hours=2.0)
    async def cache_clear(self):
        func.USERS_BUFFER.clear()

        iufi.CardPool.search_image = None
        for card in iufi.CardPool._cards.values():
            card._image = None

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

            cd = doc["cooldown"]
            await self.check_and_schedule(user, current_time, cd["roll"], "Your roll is ready!")
            await self.check_and_schedule(user, current_time, cd["daily"], "Your daily is ready!")
            await self.check_and_schedule(user, current_time, cd["match_game"], "Your game is ready!")

async def setup(bot: commands.Bot):
    await bot.add_cog(Tasks(bot))