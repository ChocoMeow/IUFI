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

        roles = {
            rank: guild.get_role(data["discord_role"])
            for rank, data in func.settings.RANK_BASE.items() if data["discord_role"]
        }
        for role in roles.values():
            if not role: continue
            for member in role.members:
                await member.remove_roles(role)


        # Feature flag: Skip monthly rewards if reward card system is enabled
        if func.settings.GIVE_REWARD_CARD:
            # Instead of giving reward cards, assign the same rank roles we give in the non-reward-card flow
            # to the top-3 users in each monthly leaderboard (quiz, match_game per level, pvp, exp).
            updated_users: dict[str, int] = {}

            async def _assign_role(member: discord.Member, points: int | None) -> None:
                # Directly assign the configured leaderboard role to the member
                if not member:
                    return
                try:
                    role = guild.get_role(func.settings.MONTHLY_LEADERBOARD_ROLE) if func.settings.MONTHLY_LEADERBOARD_ROLE else None
                    if role:
                        await member.add_roles(role)
                        key = str(role.id)
                        updated_users[key] = updated_users.get(key, 0) + 1
                except Exception:
                    func.logger.exception("Failed to assign direct leaderboard role to %s", member.id if member else None)

            # 1) Quiz top 3
            try:
                quiz_users = await func.USERS_DB.find({f"game_state.quiz_game.last_update": {"$gt": start_time, "$lte": end_time}}).sort("game_state.quiz_game.points", -1).limit(3).to_list(3)
                for ud in quiz_users:
                    member = guild.get_member(ud["_id"]) if ud else None
                    points = ud.get("game_state", {}).get("quiz_game", {}).get("points", 0)
                    await _assign_role(member, points)
            except Exception:
                func.logger.exception("Failed to assign quiz monthly roles")

            # 2) Match game top 3 — per-level
            try:
                for lvl in (list(func.settings.MATCH_GAME_SETTINGS.keys()) if func.settings.MATCH_GAME_SETTINGS else []):
                    users = await func.USERS_DB.find({f"game_state.match_game.{lvl}.last_update": {"$gt": start_time, "$lte": end_time}}).sort([
                        (f"game_state.match_game.{lvl}.monthly_matched", -1),
                        (f"game_state.match_game.{lvl}.monthly_click_left", -1),
                        (f"game_state.match_game.{lvl}.monthly_finished_time", 1)
                    ]).limit(3).to_list(3)

                    for ud in users:
                        member = guild.get_member(ud["_id"]) if ud else None
                        # try to obtain quiz points to determine rank; if absent, skip
                        points = ud.get("game_state", {}).get("quiz_game", {}).get("points")
                        await _assign_role(member, points)
            except Exception:
                func.logger.exception("Failed to assign match-game monthly roles")

            # 3) PVP top 3
            try:
                pvp_users = await func.USERS_DB.find({"monthly.pvp_last_update": {"$gt": start_time, "$lte": end_time}}).sort("monthly.pvp.wins", -1).limit(3).to_list(3)
                for ud in pvp_users:
                    member = guild.get_member(ud["_id"]) if ud else None
                    points = ud.get("game_state", {}).get("quiz_game", {}).get("points")
                    await _assign_role(member, points)
            except Exception:
                func.logger.exception("Failed to assign pvp monthly roles")

            # 4) EXP (level) top 3
            try:
                exp_users = await func.USERS_DB.find({"monthly.exp_last_update": {"$gt": start_time, "$lte": end_time}}).sort("monthly.exp", -1).limit(3).to_list(3)
                for ud in exp_users:
                    member = guild.get_member(ud["_id"]) if ud else None
                    points = ud.get("game_state", {}).get("quiz_game", {}).get("points")
                    await _assign_role(member, points)
            except Exception:
                func.logger.exception("Failed to assign exp monthly roles")

            func.logger.info("Assigned monthly roles to leaderboard users: %s", ", ".join(f"{k}: {v}" for k, v in updated_users.items()))
            return

        else:
            users = func.USERS_DB.find({f"game_state.quiz_game.last_update": {"$gt": start_time, "$lte": end_time}})
            updated_users: dict[str, int] = {}
            async for user_data in users:
                user = guild.get_member(user_data["_id"])
                if user:
                    rank = iufi.QuestionPool.get_rank(user_data["game_state"]["quiz_game"]["points"])[0]
                    if rank in roles.keys() and roles[rank] is not None:
                        updated_users[rank] = updated_users.get(rank, 0) + 1
                        await user.add_roles(roles[rank])

            func.logger.info("Updated user roles: %s",
                             ", ".join(f"{role_name}: {count}" for role_name, count in updated_users.items()))

    async def clean_user_cards(self, user: dict) -> int:
        user_id = user.get("_id")
        if user_id not in self.warned_users:
            return 0
        
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
            f"User ({user_id}) has been inactive for over {func.settings.RESET_CARD_DAY} days, resulting in the clearing of their inventory. "
            f"Converted {len(converted_cards)} card(s): [{', '.join(card.id for card in converted_cards)}]. Successfully gained {candies} candies."
        )
        self.warned_users.remove(user_id)
        return len(converted_cards)

    async def reset_user_cards(self) -> None:
        current_time = time.time()
        last_warning_threshold = current_time - ((func.settings.RESET_CARD_DAY - 1) * 24 * 60 * 60)
        cutoff_threshold = current_time - (func.settings.RESET_CARD_DAY * 24 * 60 * 60)

        user_cursor = func.USERS_DB.find({
            "$or": [
                {"last_active_time": {"$lt": last_warning_threshold}},
                {"last_active_time": {"$exists": False}}
            ]
        })
        
        users_to_warn = []
        users_cleared = []
        converted_cards = 0

        async for user in user_cursor:
            if not len(user.get("cards", [])):
                continue

            user_id = user.get("_id")
            last_active_time = user.get("last_active_time")

            # Warn users who are inactive and haven't been notified yet
            if last_active_time is None or last_active_time < last_warning_threshold:
                if user_id not in self.warned_users:
                    users_to_warn.append(user_id)
                    self.warned_users.add(user_id)

            # Clean user cards if they are still active after receiving a warning
            if (last_active_time is None or last_active_time < cutoff_threshold) and user_id in self.warned_users:
                users_cleared.append(user_id)
                converted_cards += await self.clean_user_cards(user)

        channel = self.bot.get_channel(func.settings.MAIN_CHAT_CHANNEL)
        if users_to_warn:
            chunks = func.text_in_chunks(
                message=f"Hi {', '.join(f'<@{user_id}>' for user_id in users_to_warn)},\n\n"
                        f"We've noticed you've been inactive for over {func.settings.RESET_CARD_DAY - 1} days. This is your final reminder: "
                        "your cards will be converted tomorrow if you remain inactive. Don't worry—once converted, "
                        "you can still recover your candies later. We hope to see you back in the game soon!"
                )
            for chunk in chunks:
                await channel.send(chunk, allowed_mentions=discord.AllowedMentions().none())

        if users_cleared:            
            chunks = func.text_in_chunks(
                message=f"Hi {', '.join(f'<@{user_id}>' for user_id in users_cleared)},\n\n"
                        "We hope you're doing well! Since we didn't see you back in the game after our last reminder, "
                        "your cards have now been converted. The good news is that you can still recover your candies!"
                        f" `{converted_cards}` cards have been returned to the pool."
                )
            for chunk in chunks:
                await channel.send(chunk, allowed_mentions=discord.AllowedMentions().none())

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

    @tasks.loop(minutes=60.0)
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
            # Attempt a monthly leaderboard reset near month end
            self.bot.loop.create_task(self.reset_monthly_leaderboards())

        except Exception as e:
            func.logger.error("An exception occurred in the cache clear task.", exc_info=e)

    async def reset_monthly_leaderboards(self) -> None:
        """Reset monthly leaderboard fields near the end of month.
        This will zero monthly counters and last_update timestamps for the supported leaderboards:
        - music_game (monthly_points)
        - quiz_game (points handled via existing flow but ensure monthly state)
        - emoji_quiz
        - mv_guess
        - pvp (monthly.pvp)
        - match_game per-level monthly fields
        Also calls iufi.MusicPool.reset() to reset per-track stats.
        The function is a no-op unless the current time is within 1 hour of month boundary.
        """
        try:
            start_time, end_time = func.get_month_unix_timestamps()
            # only run the reset task when we're within 1 hour of the end of month
            if end_time - time.time() > 3_600:
                return

            # # Reset music pool per-track stats
            # try:
            #     await iufi.MusicPool.reset()
            # except Exception:
            #     func.logger.exception("Failed to reset MusicPool stats")

            # Build update doc to zero monthly fields for known game states
            update_doc_set = {}

            # Reset per-game monthly counters
            # music_game, quiz_game, emoji_quiz, mv_guess
            for game in ("music_game", "quiz_game", "emoji_quiz", "mv_guess"):
                update_doc_set[f"game_state.{game}.monthly_points"] = 0
                update_doc_set[f"game_state.{game}.last_update"] = 0

            # Reset match_game per-level monthly fields
            match_levels = list(func.settings.MATCH_GAME_SETTINGS.keys()) if func.settings.MATCH_GAME_SETTINGS else []
            for lvl in match_levels:
                prefix = f"game_state.match_game.{lvl}"
                update_doc_set[f"{prefix}.monthly_matched"] = 0
                update_doc_set[f"{prefix}.monthly_finished_time"] = 0
                update_doc_set[f"{prefix}.monthly_click_left"] = 0
                update_doc_set[f"{prefix}.last_update"] = 0

            # Reset monthly pvp counters
            update_doc_set["monthly.pvp.wins"] = 0
            update_doc_set["monthly.pvp.losses"] = 0
            update_doc_set["monthly.pvp.total_matches"] = 0
            update_doc_set["monthly.pvp_last_update"] = 0

            # Apply the reset to all users
            if update_doc_set:
                await func.USERS_DB.update_many({}, {"$set": update_doc_set})

            func.logger.info("Monthly leaderboard fields reset executed")
        except Exception as e:
            func.logger.error("Failed to run monthly leaderboard reset", exc_info=e)

    @tasks.loop(minutes=10.0)
    async def reminder(self) -> None:
        try:
            # Querying the Game’s Ready Time for the Next 10 Minutes Range
            time_range = {"$gt": (current_time := time.time()), "$lt": current_time + 600}
            # include users who either have global reminder True or have a per-key reminder set to True
            cooldown_keys = [k for k in func.settings.COOLDOWN_BASE.keys() if k != "claim"]
            reminder_or_clauses = [{"reminder": True}] + [{f"reminder.{k}": True} for k in cooldown_keys]

            query = {
                "$and": [
                    {"$or": reminder_or_clauses},
                    {"$or": [
                        {f"cooldown.{name}": time_range}
                        for name in cooldown_keys
                    ]}
                ]
            }

            # Verifying and Dispatching Game Readiness Notification to Player
            notification_count = 0
            async for doc in func.USERS_DB.find(query):
                user = self.bot.get_user(doc["_id"])
                if not user:
                    continue

                cd: dict[str, float] = doc["cooldown"]
                for name, (emoji, _) in func.settings.COOLDOWN_BASE.items():
                    if name != "claim":
                        # Check whether the user wants reminders for this specific cooldown.
                        reminder_pref = doc.get("reminder", False)

                        # Interpret legacy boolean or new dict format
                        enabled = False
                        if isinstance(reminder_pref, bool):
                            enabled = reminder_pref
                        elif isinstance(reminder_pref, dict):
                            enabled = bool(reminder_pref.get(name, False))

                        if enabled:
                            await self.check_and_schedule(user, current_time, cd.get(name, 0), f"{emoji} Your {name.split('_')[0]} is ready! Join <#{random.choice(func.settings.GAME_CHANNEL_IDS)}> and roll now.")
                            notification_count += 1

            func.logger.info(f"Notifications sent to {notification_count} users regarding game readiness.")

        except Exception as e:
            func.logger.error("An exception occurred in the reminder task.", exc_info=e)

async def setup(bot: commands.Bot):
    await bot.add_cog(Tasks(bot))