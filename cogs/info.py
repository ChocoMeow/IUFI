import asyncio, time, discord, iufi
import functions as func

from discord import app_commands
from discord.ext import commands
from views import HelpView, MusicLeaderboardView

LEADERBOARD_EMOJIS: list[str] = ["🥇", "🥈", "🥉", "🏅"]
NAME_CACHE_TTL: int = 900

def highlight_text(text: str, need: bool = True) -> str:
    if not need:
        return text + "\n"
    return "\u001b[0;1;35m" + text + " \u001b[0m\n"

class LeaderboardGroup(app_commands.Group):
    def __init__(self, bot: commands.Bot):
        super().__init__(name="leaderboard", description="Shows the IUFI leaderboards.")
        self.bot = bot
        self.name_cache: dict[int, tuple[float, str]] = {}

    async def display_names(self, interaction: discord.Interaction, user_ids: list[int]) -> dict[int, str]:
        """Names for leaderboard rows, including players who are not in the bot's member cache."""
        names: dict[int, str] = {}
        missing: list[int] = []
        now = time.time()

        for user_id in user_ids:
            member = (interaction.guild.get_member(user_id) if interaction.guild else None) or self.bot.get_user(user_id)
            if member:
                names[user_id] = member.display_name
                continue

            cached = self.name_cache.get(user_id)
            if cached and now - cached[0] < NAME_CACHE_TTL:
                names[user_id] = cached[1]
            else:
                missing.append(user_id)

        if missing:
            results = await asyncio.gather(
                *(self.bot.fetch_user(user_id) for user_id in missing),
                return_exceptions=True
            )
            for user_id, result in zip(missing, results):
                name = "Unknown user" if isinstance(result, BaseException) else result.display_name
                names[user_id] = name
                self.name_cache[user_id] = (now, name)

        return names

    @app_commands.command(name="exp", description="Shows the IUFI exp/level leaderboard.")
    async def exp(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user = await func.get_user(interaction.user.id)
        users = await func.USERS_DB.find().sort("exp", -1).limit(10).to_list(10)
        rank = await func.USERS_DB.count_documents({'exp': {'$gt': user.get('exp', 0)}}) + 1
        names = await self.display_names(interaction, [top_user["_id"] for top_user in users])

        embed = discord.Embed(title="🏆   IUFI Leaderboard", color=discord.Color.random())
        embed.description = f"**Your current position is `{rank}`**\n"

        description = ""
        for index, top_user in enumerate(users):
            level, _ = func.calculate_level(top_user.get("exp", 0))
            description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + highlight_text(f"{func.truncate_string(names[top_user['_id']]):<18} {level:>5} ⚔️", top_user["_id"] == interaction.user.id)

        if rank > len(users):
            level, _ = func.calculate_level(user['exp'])
            description += ("┇\n" if rank > len(users) + 1 else "") + f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(f"{func.truncate_string(interaction.user.display_name):<18} {level:>5} ⚔️")

        if not description:
            description = "The leaderboard is currently empty."

        embed.description += f"```ansi\n{description}```"
        embed.set_thumbnail(url=icon.url if (icon := interaction.guild.icon) else None)

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="level", description="[Admin] Shows the IUFI level leaderboard with a custom limit.")
    @app_commands.describe(limit="How many top users to show (default 10)")
    @app_commands.check(func.is_admin_interaction)
    async def level(self, interaction: discord.Interaction, limit: str = "10"):
        await interaction.response.defer()
        users = await func.USERS_DB.find().sort("exp", -1).limit(int(limit)).to_list(int(limit))
        user = await func.get_user(interaction.user.id)
        rank = await func.USERS_DB.count_documents({'exp': {'$gt': user.get('exp', 0)}}) + 1
        names = await self.display_names(interaction, [top_user["_id"] for top_user in users])

        embed = discord.Embed(title="🏆   Level Leaderboard", color=discord.Color.random())
        embed.description = f"**Your current position is `{rank}`**\n"

        description = ""
        for index, top_user in enumerate(users):
            level, _ = func.calculate_level(top_user.get("exp", 0))
            description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + highlight_text(f"{func.truncate_string(names[top_user['_id']]):<18} {level:>5} ⚔️", top_user["_id"] == interaction.user.id)

        if rank > int(limit):
            level, _ = func.calculate_level(user['exp'])
            description += ("┇\n" if rank > int(limit) + 1 else "") + f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(f"{func.truncate_string(interaction.user.display_name):<18} {level:>5} ⚔️")

        if not description:
            description = "The leaderboard is currently empty."

        embed.description += f"```ansi\n{description}```"
        embed.set_thumbnail(url=icon.url if (icon := interaction.guild.icon) else None)

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="candies", description="Shows the IUFI Starcandies leaderboard.")
    async def candies(self, interaction: discord.Interaction):
        await interaction.response.defer()
        users = await func.USERS_DB.find().sort("candies", -1).limit(10).to_list(10)
        user = await func.get_user(interaction.user.id)
        rank = await func.USERS_DB.count_documents({'candies': {'$gt': user.get('candies', 0)}}) + 1
        names = await self.display_names(interaction, [top_user["_id"] for top_user in users])

        embed = discord.Embed(title="🏆   Starcandies Leaderboard", color=discord.Color.random())
        embed.description = f"**Your current position is `{rank}`**\n"

        description = ""
        for index, top_user in enumerate(users):
            description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + highlight_text(f"{func.truncate_string(names[top_user['_id']]):<18} {top_user.get('candies', 0):>5} 🍬", top_user["_id"] == interaction.user.id)

        if rank > len(users):
            description += ("┇\n" if rank > len(users) + 1 else "") + f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(f"{func.truncate_string(interaction.user.display_name):<18} {user.get('candies', 0):>5} 🍬")

        if not description:
            description = "The leaderboard is currently empty."

        embed.description += f"```ansi\n{description}```"
        embed.set_thumbnail(url=icon.url if (icon := interaction.guild.icon) else None)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="battlepass", description="Shows the IUFI Battle Pass leaderboard for the current season.")
    async def battlepass(self, interaction: discord.Interaction):
        if not func.battlepass_enabled():
            return await interaction.response.send_message("The Battle Pass is currently disabled.")

        await interaction.response.defer()
        bp_settings = func.get_battlepass_settings()
        season_id = str(bp_settings.get("season_id", "default"))
        max_level = max(1, int(bp_settings.get("max_level", 100)))
        season_filter = {"battlepass.season_id": season_id}

        user = await func.get_user(interaction.user.id)
        state = func.get_battlepass_state(user)
        user_xp = max(0, int(state.get("xp", 0) or 0))

        users = await func.USERS_DB.find(season_filter).sort("battlepass.xp", -1).limit(10).to_list(10)
        rank = await func.USERS_DB.count_documents({**season_filter, "battlepass.xp": {"$gt": user_xp}}) + 1
        names = await self.display_names(interaction, [top_user["_id"] for top_user in users])

        embed = discord.Embed(title="🎫   Battle Pass Leaderboard", color=discord.Color.random())
        embed.description = f"**Season `{season_id}`**\n**Your current position is `{rank}`**\n"

        description = ""
        for index, top_user in enumerate(users):
            xp = max(0, int(top_user.get("battlepass", {}).get("xp", 0) or 0))
            level, _, _ = func.calculate_battlepass_level(xp)
            description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} {func.truncate_string(names[top_user['_id']]):<18} Lv{level:>3}/{max_level:<3} {xp:>6} XP\n"

        if description and rank > len(users):
            level, _, _ = func.calculate_battlepass_level(user_xp)
            description += ("┇\n" if rank > len(users) + 1 else "")
            description += f"{LEADERBOARD_EMOJIS[3]} {func.truncate_string(interaction.user.display_name):<18} Lv{level:>3}/{max_level:<3} {user_xp:>6} XP\n"

        if not description:
            description = "The leaderboard is currently empty."

        embed.description += f"```\n{description}```"
        embed.set_thumbnail(url=icon.url if (icon := interaction.guild.icon) else None)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="matchgame", description="Shows the IUFI Matching Game leaderboard.")
    @app_commands.describe(level="The match game level")
    async def matchgame(self, interaction: discord.Interaction, level: str = "1"):
        if level not in (levels := func.settings.MATCH_GAME_SETTINGS.keys()):
            return await interaction.response.send_message(f"Invalid level selection! Please select a valid level: `{', '.join(levels)}`")

        await interaction.response.defer()
        users = await func.USERS_DB.find().sort([
            (f"game_state.match_game.{level}.matched", -1),
            (f"game_state.match_game.{level}.click_left", -1),
            (f"game_state.match_game.{level}.finished_time", 1)
        ]).limit(10).to_list(10)

        user = await func.get_user(interaction.user.id)
        user = user.get("game_state", {}).get("match_game", {}).get(level, {})
        rank = (await func.USERS_DB.count_documents({
            '$or': [
                {f"game_state.match_game.{level}.matched": {'$gt': user['matched']}},
                {'$and': [
                    {f"game_state.match_game.{level}.matched": user['matched']},
                    {f"game_state.match_game.{level}.click_left": {'$gt': user['click_left']}}
                ]},
                {'$and': [
                    {f"game_state.match_game.{level}.matched": user['matched']},
                    {f"game_state.match_game.{level}.click_left": user['click_left']},
                    {f"game_state.match_game.{level}.finished_time": {'$lt': user['finished_time']}}
                ]}
            ]
        }) if user else 0) + 1

        embed = discord.Embed(title=f"🏆   Level {level} Matching Game Leaderboard", color=discord.Color.random())
        embed.description = (f"**Your current position is `{rank}`**" if user else "**You haven't played any match game!**") + "\n"

        ranked = [
            (top_user["_id"], game_state)
            for top_user in users
            if (game_state := top_user.get("game_state", {}).get("match_game", {}).get(level))
        ]
        names = await self.display_names(interaction, [user_id for user_id, _ in ranked])

        description = ""
        for index, (user_id, game_state) in enumerate(ranked):
            description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + highlight_text(f"{func.truncate_string(names[user_id]):<18} 🃏{game_state['matched']:<2} 🕒{func.convert_seconds(game_state['finished_time']):<10}", user_id == interaction.user.id)

        if user and rank > len(users):
            description += ("┇\n" if rank > len(users) + 1 else "") + f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(f"{func.truncate_string(interaction.user.display_name):<18} 🃏{user['matched']:<2} 🕒{func.convert_seconds(user['finished_time']):<10}")

        if not description:
            description = "The leaderboard is currently empty."

        embed.description += f"```ansi\n{description}```"
        embed.set_thumbnail(url=icon.url if (icon := interaction.guild.icon) else None)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="quiz", description="Shows the IUFI Quiz leaderboard.")
    async def quiz(self, interaction: discord.Interaction):
        await interaction.response.defer()
        start_time, end_time = func.get_month_unix_timestamps()
        user = await func.get_user(interaction.user.id)
        user = user.get("game_state", {}).get("quiz_game", {})
        users = await func.USERS_DB.find({f"game_state.quiz_game.last_update": {"$gt":start_time, "$lte":end_time}}).sort("game_state.quiz_game.points", -1).limit(10).to_list(10)
        rank = await func.USERS_DB.count_documents({
            "$and": [
                {"game_state.quiz_game.last_update": {"$gt":start_time, "$lte":end_time}},
                {"game_state.quiz_game.points": {'$gt': user.get("points", 0)}}
            ]}) + 1

        embed = discord.Embed(title=f"🏆   Quiz Leaderboard", color=discord.Color.random())

        ranked = [
            (top_user["_id"], game_state)
            for top_user in users
            if (game_state := top_user.get("game_state", {}).get("quiz_game"))
        ]
        names = await self.display_names(interaction, [user_id for user_id, _ in ranked])

        description = ""
        for user_id, game_state in ranked:
            _rank = iufi.QuestionPool.get_rank(game_state['points'])
            description += f"<:{_rank[0]}:{_rank[1]}> `{func.truncate_string(names[user_id]):<18} {game_state['points']:>6} 🔥`\n"

        if description and rank > len(users):
            _rank = iufi.QuestionPool.get_rank(user.get("points", 0))
            description += ("┇\n" if rank > len(users) + 1 else "") + f"<:{_rank[0]}:{_rank[1]}> `{func.truncate_string(interaction.user.display_name):<18} {user.get('points', 0):>6} 🔥`"

        if not description:
            description = "The leaderboard is currently empty."

        embed.description = f"**The next reset is <t:{int(end_time)}:R>**\n**" + (f"Your current position is `{rank}`" if user else "You haven't played any quiz game!") + f"**\n{description}"
        embed.set_thumbnail(url=icon.url if (icon := interaction.guild.icon) else None)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="music", description="Shows the IUFI Music leaderboard.")
    async def music(self, interaction: discord.Interaction):
        await interaction.response.defer()
        users = await func.USERS_DB.find().sort("game_state.music_game.points", -1).limit(10).to_list(10)
        user = await func.get_user(interaction.user.id)
        user = user.get("game_state", {}).get("music_game", {})
        rank = await func.USERS_DB.count_documents({'game_state.music_game.points': {'$gt': user.get('points', 0)}}) + 1

        embed = discord.Embed(title="🏆   Music Leaderboard", color=discord.Color.random())
        embed.description = (f"**Your current position is `{rank}`**" if user else "**You haven't played any music quiz!**") + "\n"

        ranked = [
            (user_data["_id"], game_state)
            for user_data in users
            if (game_state := user_data.get("game_state", {}).get("music_game", {}))
        ]
        names = await self.display_names(interaction, [user_id for user_id, _ in ranked])

        description = ""
        for index, (user_id, game_state) in enumerate(ranked):
            description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + highlight_text(f"{func.truncate_string(names[user_id]):<18} {game_state.get('points', 0):>6} 𝄞", user_id == interaction.user.id)

        if user and rank > len(users):
            description += ("┇\n" if rank > len(users) + 1 else "") + f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(f"{func.truncate_string(interaction.user.display_name):<18} {user['points']:>6} 𝄞")

        if not description:
            description = "The leaderboard is currently empty."

        embed.description += f"```ansi\n{description}```"
        embed.set_thumbnail(url=icon.url if (icon := interaction.guild.icon) else None)

        view = MusicLeaderboardView(interaction.user)
        view.message = await interaction.followup.send(embed=embed, view=view, wait=True)

class Info(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "ℹ️"
        self.invisible = False
        self.leaderboard_group = LeaderboardGroup(bot)
        bot.tree.add_command(self.leaderboard_group)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.leaderboard_group.name)

    @app_commands.command(name="help", description="Lists all the commands in IUFI.")
    @app_commands.describe(command="A specific command name to get help for")
    async def help(self, interaction: discord.Interaction, command: str = None):
        if command:
            found = discord.utils.get(self.bot.tree.walk_commands(), qualified_name=command)
            if found:
                embed = discord.Embed(title=f"/{found.qualified_name}", description=found.description or "No description provided.", color=discord.Color.random())
                return await interaction.response.send_message(embed=embed)

        view = HelpView(self.bot, interaction.user)
        await interaction.response.send_message(embed=view.build_embed(), view=view)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Info(bot))
