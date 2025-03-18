import discord, asyncio, iufi, time, random
import functions as func

from discord.ext import commands, tasks
from views import DropView

class Tasks(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.invisible = False
        self.warned_users = set()

        self.drop_card.start()
        self.cache_clear.start()
        self.reminder.start()

    def cog_unload(self):
        self.drop_card.cancel()
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

    async def distribute_monthly_quiz_rewards(self) -> None:
        start_time, end_time = func.get_month_unix_timestamps()
        if end_time - time.time() > 3_600:
            return
        
        guild: discord.Guild = self.bot.get_guild(func.settings.MAIN_GUILD)
        if not guild:
            return
        
        roles: dict[str, discord.Role] = {
            rank: guild.get_role(data["discord_role"])
            for rank, data in func.settings.RANK_BASE.items() if data["discord_role"]
        }
        for role in roles.values():
            if not role: continue
            for member in role.members:
                await member.remove_roles(role)

        users = func.USERS_DB.find({f"game_state.quiz_game.last_update": {"$gt":start_time, "$lte":end_time}})
        updated_users: dict[str, int] = {}
        async for user_data in users:
            user = guild.get_member(user_data["_id"])
            if user:
                rank = iufi.QuestionPool.get_rank(user_data["game_state"]["quiz_game"]["points"])[0]
                if rank in roles.keys() and roles[rank] is not None:
                    updated_users[rank] = updated_users.get(rank, 0) + 1
                    await user.add_roles(roles[rank])
        
        func.logger.info("Updated user roles: %s", ", ".join(f"{role_name}: {count}" for role_name, count in updated_users.items()))

    async def clean_user_cards(self, user: dict) -> None:
        user_id = user.get("_id")
        if user_id not in self.warned_users:
            return
        
        converted_cards: list[iufi.Card] = []
        for card_id in user["cards"]:
            card = iufi.CardPool.get_card(card_id)
            if card:
                converted_cards.append(card)

        card_ids = [card.id for card in converted_cards]
        candies = sum([card.cost for card in converted_cards])
            
        for card in converted_cards:
            iufi.CardPool.add_available_card(card)

        await func.update_user(user_id, {
            "$pull": {"cards": {"$in": card_ids}},
            "$inc": {"candies": candies}
        })
        await func.update_card(card_ids, {"$set": {"owner_id": None, "tag": None, "frame": None, "last_trade_time": 0}})

        func.logger.info(
            f"User ({user_id}) has been inactive for over 100 days, resulting in the clearing of their inventory. "
            f"Converted {len(converted_cards)} card(s): [{', '.join(card.id for card in converted_cards)}]. Successfully gained {candies} candies."
        )
        self.warned_users.remove(user_id)

    async def reset_user_cards(self) -> None:
        current_time = time.time()
        last_warning_threshold = current_time - (99 * 24 * 60 * 60)  # 99 days in seconds
        cutoff_threshold = current_time - (100 * 24 * 60 * 60)  # 100 days in seconds

        user_cursor = func.USERS_DB.find({
            "$or": [
                {"last_active_time": {"$lt": last_warning_threshold}},
                {"last_active_time": {"$exists": False}}
            ]
        })

        users_to_warn = []
        users_cleared = []

        async for user in user_cursor:
            if not len(user.get("cards")):
                continue

            user_id = user.get("_id")
            last_active_time = user.get("last_active_time")

            # Warn users who are inactive and haven't been notified yet
            if last_active_time is None or last_warning_threshold < last_active_time < cutoff_threshold:
                if user_id not in self.warned_users:
                    users_to_warn.append(user_id)
                    self.warned_users.add(user_id)

            # Clean user cards if they are still active after receiving a warning
            if last_active_time is not None and last_active_time >= cutoff_threshold and user_id in self.warned_users:
                users_cleared.append(user_id)
                await self.clean_user_cards(user)

        channel = self.bot.get_channel(func.settings.MAIN_CHAT_CHANNEL)
        if users_to_warn:
            await channel.send(
                f"Hi {', '.join(f'<@{user_id}>' for user_id in users_to_warn)},\n\n"
                "We've noticed you've been inactive for over 99 days. This is your final reminder: "
                "your cards will be converted tomorrow if you remain inactive. Don't worry—once converted, "
                "you can still recover your candies later. We hope to see you back in the game soon!"
            )
        
        if users_cleared:
            await channel.send(
                f"Hi {', '.join(f'<@{user_id}>' for user_id in users_cleared)},\n\n"
                "We hope you're doing well! Since we didn't see you back in the game after our last reminder, "
                "your cards have now been converted. The good news is that you can still recover your candies!"
            )

    @tasks.loop(minutes=5.0)
    async def drop_card(self) -> None:
        await self.bot.wait_until_ready()

        try:
            if random.randint(1, 6) == 1:
                cards = iufi.CardPool.roll(amount=1)
                channel = self.bot.get_channel(random.choice(func.settings.GAME_CHANNEL_IDS))
                if channel:
                    view = DropView(cards[0])
                    covered_card: iufi.TempCard = iufi.TempCard(f"cover/level{random.randint(1, 3)}.webp")
                    image_bytes, image_format = await covered_card.image_bytes(), covered_card.format
                    view.message = await channel.send(
                        content=f"**Hurry up! This claim ends in: <t:{round(time.time()) + 70}:R>**",
                        embed=view.build_embed(),
                        file=discord.File(image_bytes, filename=f'image.{image_format}'),
                        view=view
                    )

                    func.logger.info(f"A card has been dropped in {channel.name}({channel.id}) with card [{cards[0].id}]")

        except Exception as e:
            func.logger.error("An exception occurred in the drop card task.", exc_info=e)

    @tasks.loop(minutes=30.0)
    async def cache_clear(self):
        await self.bot.wait_until_ready()

        try:
            func.USERS_BUFFER.clear()

            # Syncing Question Data with Database
            for q in iufi.QuestionPool._questions:
                if q.is_updated:
                    await func.QUESTIONS_DB.update_one({"_id": q.id}, {"$set": q.toDict()})
            
            # Syncing Music Data with Database
            await iufi.MusicPool.save()

            # Verifying and Updating Quiz Reward Data in Database
            self.bot.loop.create_task(self.distribute_monthly_quiz_rewards())
            self.bot.loop.create_task(self.reset_user_cards())

        except Exception as e:
            func.logger.error("An exception occurred in the cache clear task.", exc_info=e)

    @tasks.loop(minutes=10.0)
    async def reminder(self) -> None:
        try:
            # Querying the Game’s Ready Time for the Next 10 Minutes Range
            time_range = {"$gt": (current_time := time.time()), "$lt": current_time + 600}
            query = {
                "$and":[
                    {"reminder": True},
                    {"$or": [
                        {f"cooldown.{name}": time_range}
                        for name in func.settings.COOLDOWN_BASE.keys() if name != "claim"
                ]}
            ]}

            # Verifying and Dispatching Game Readiness Notification to Player
            notification_count = 0
            async for doc in func.USERS_DB.find(query):
                user = self.bot.get_user(doc["_id"])
                if not user:
                    continue

                cd: dict[str, float] = doc["cooldown"]
                for name, (emoji, _) in func.settings.COOLDOWN_BASE.items():
                    if name != "claim":
                        await self.check_and_schedule(user, current_time, cd.get(name, 0), f"{emoji} Your {name.split('_')[0]} is ready! Join <#{random.choice(func.settings.GAME_CHANNEL_IDS)}> and roll now.")        
                        notification_count += 1

            func.logger.info(f"Notifications sent to {notification_count} users regarding game readiness.")

        except Exception as e:
            func.logger.error("An exception occurred in the reminder task.", exc_info=e)

async def setup(bot: commands.Bot):
    await bot.add_cog(Tasks(bot))