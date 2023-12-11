import discord, asyncio, iufi, time, random
import functions as func

from discord.ext import commands, tasks
from views import GiftDropView

class Tasks(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.invisible = False
        self.game_channel_ids: list[int] = [1155772660979093555, 1155772719909044224, 1155772738858913792, 1155772756730859580]
        self.gift_drop_images: list[str] = [
            "https://cdn.discordapp.com/attachments/1183364758175498250/1183364809274695690/gift1.gif?ex=6588115c&is=65759c5c&hm=c0464d404859420db49f1a92f1501f681b63cab15d23c51b483546859dc70f1a&",
            "https://cdn.discordapp.com/attachments/1183364758175498250/1183364813229924402/gift1.jpg?ex=6588115d&is=65759c5d&hm=245c2b8e3099ade40ea17bdfb8fd04fd686635fe3f63ac13c53d373003fbbaee&",
            "https://cdn.discordapp.com/attachments/1183364758175498250/1183364859270811758/gift2.jpg?ex=65881168&is=65759c68&hm=6793d93b9dad5a1ea44faacae42642a94c63e1b7eacb4a7682c058fc1fb98c81&",
            "https://cdn.discordapp.com/attachments/1183364758175498250/1183364863666429972/gift2.gif?ex=65881169&is=65759c69&hm=390bac8d35313bcb4101e2ca3e68aaa163cb684b931ac6a6659951fe92c0e93e&"
        ]

        self.cache_clear.start()
        self.reminder.start()
        self.gift_drop.start()

    def cog_unload(self):
        self.cache_clear.cancel()
        self.reminder.cancel()
        self.gift_drop.cancel()
    
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

    @tasks.loop(minutes=30)
    async def gift_drop(self):
        await self.bot.wait_until_ready()
        random_channel = random.choice(self.game_channel_ids)
        channel = self.bot.get_channel(random_channel)
        if channel:
            random_image = random.choice(self.gift_drop_images)
            view = GiftDropView(random_image)
            view.message = await channel.send(
                f"Christmas gifts have appeared.! ** (Disappears: <t:{round(time.time()) + 360}:R>) ** [.]({random_image}))",
                view=view
            )
            await view.timeout_count()

    @tasks.loop(minutes=3.0)
    async def reminder(self) -> None:
        time_range = {"$gt": (current_time := time.time()), "$lt": current_time + 180}
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