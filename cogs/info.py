import discord, iufi
import functions as func

from discord import app_commands
from discord.ext import commands
from views import HelpView, MusicLeaderboardView

LEADERBOARD_EMOJIS: list[str] = ["🥇", "🥈", "🥉", "🏅"]

def highlight_text(text: str, need: bool = True) -> str:
    if not need:
        return text + "\n"
    return "[0;1;35m" + text + " [0m\n"

class LeaderboardGroup(app_commands.Group):
    def __init__(self, bot: commands.Bot):
        super().__init__(name="leaderboard", description="Shows the IUFI leaderboards.")
        self.bot = bot

    @app_commands.command(name="exp", description="Shows the IUFI exp/level leaderboard.")
    async def exp(self, interaction: discord.Interaction):
        user = await func.get_user(interaction.user.id)
        users = await func.USERS_DB.find().sort("exp", -1).limit(10).to_list(10)
        rank = await func.USERS_DB.count_documents({'exp': {'$gt': user.get('exp', 0)}}) + 1

        embed = discord.Embed(title="🏆   IUFI Leaderboard", color=discord.Color.random())
        embed.description = f"**Your current position is `{rank}`**\n"

        description = ""
        for index, top_user in enumerate(users):
            level, _ = func.calculate_level(top_user["exp"])
            member = self.bot.get_user(top_user['_id'])

            if member:
                description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + highlight_text(f"{func.truncate_string(member.display_name):<18} {level:>5} ⚔️", member == interaction.user)

        if rank > len(users):
            level, _ = func.calculate_level(user['exp'])
            description += ("┇\n" if rank > len(users) + 1 else "") + f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(f"{func.truncate_string(interaction.user.display_name):<18} {level:>5} ⚔️")

        if not description:
            description = "The leaderboard is currently empty."

        embed.description += f"```ansi\n{description}```"
        embed.set_thumbnail(url=icon.url if (icon := interaction.guild.icon) else None)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="level", description="[Admin] Shows the IUFI level leaderboard with a custom limit.")
    @app_commands.describe(limit="How many top users to show (default 10)")
    @app_commands.check(func.is_admin_interaction)
    async def level(self, interaction: discord.Interaction, limit: str = "10"):
        users = await func.USERS_DB.find().sort("exp", -1).limit(int(limit)).to_list(int(limit))
        user = await func.get_user(interaction.user.id)
        rank = await func.USERS_DB.count_documents({'exp': {'$gt': user.get('exp', 0)}}) + 1

        embed = discord.Embed(title="🏆   Level Leaderboard", color=discord.Color.random())
        embed.description = f"**Your current position is `{rank}`**\n"

        description = ""
        member = None
        for index, top_user in enumerate(users):
            level, _ = func.calculate_level(top_user["exp"])
            member = self.bot.get_user(top_user['_id'])
            if member:
                description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + highlight_text(f"{func.truncate_string(member.display_name):<18} {level:>5} ⚔️", member == interaction.user)

        if rank > int(limit):
            level, _ = func.calculate_level(user['exp'])
            description += ("┇\n" if rank > int(limit) + 1 else "") + f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(f"{func.truncate_string(interaction.user.display_name):<18} {level:>5} ⚔️", member == interaction.user)

        if not description:
            description = "The leaderboard is currently empty."

        embed.description += f"```ansi\n{description}```"
        embed.set_thumbnail(url=icon.url if (icon := interaction.guild.icon) else None)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="candies", description="Shows the IUFI Starcandies leaderboard.")
    async def candies(self, interaction: discord.Interaction):
        users = await func.USERS_DB.find().sort("candies", -1).limit(10).to_list(10)
        user = await func.get_user(interaction.user.id)
        rank = await func.USERS_DB.count_documents({'candies': {'$gt': user.get('candies', 0)}}) + 1

        embed = discord.Embed(title="🏆   Starcandies Leaderboard", color=discord.Color.random())
        embed.description = f"**Your current position is `{rank}`**\n"

        description = ""
        member = None
        for index, top_user in enumerate(users):
            member = self.bot.get_user(top_user['_id'])
            if member:
                description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + highlight_text(f"{func.truncate_string(member.display_name):<18} {top_user['candies']:>5} 🍬", member == interaction.user)

        if rank > len(users):
            description += ("┇\n" if rank > len(users) + 1 else "") + f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(f"{func.truncate_string(interaction.user.display_name):<18} {user.get('candies', 0):>5} 🍬", member == interaction.user)

        if not description:
            description = "The leaderboard is currently empty."

        embed.description += f"```ansi\n{description}```"
        embed.set_thumbnail(url=icon.url if (icon := interaction.guild.icon) else None)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="matchgame", description="Shows the IUFI Matching Game leaderboard.")
    @app_commands.describe(level="The match game level")
    async def matchgame(self, interaction: discord.Interaction, level: str = "1"):
        if level not in (levels := func.settings.MATCH_GAME_SETTINGS.keys()):
            return await interaction.response.send_message(f"Invalid level selection! Please select a valid level: `{', '.join(levels)}`")

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

        description = ""
        for index, top_user in enumerate(users):
            game_state: dict[str, float | int] = top_user.get("game_state", {}).get("match_game", {}).get(level)
            if not game_state:
                continue

            member = self.bot.get_user(top_user['_id'])
            if member:
                description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + highlight_text(f"{func.truncate_string(member.display_name):<18} 🃏{game_state['matched']:<2} 🕒{func.convert_seconds(game_state['finished_time']):<10}", member == interaction.user)

        if user and rank > len(users):
            description += ("┇\n" if rank > len(users) + 1 else "") + f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(f"{func.truncate_string(interaction.user.display_name):<18} 🃏{user['matched']:<2} 🕒{func.convert_seconds(user['finished_time']):<10}")

        if not description:
            description = "The leaderboard is currently empty."

        embed.description += f"```ansi\n{description}```"
        embed.set_thumbnail(url=icon.url if (icon := interaction.guild.icon) else None)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="quiz", description="Shows the IUFI Quiz leaderboard.")
    async def quiz(self, interaction: discord.Interaction):
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

        description = ""
        for top_user in users:
            game_state: dict[str, float | int] = top_user.get("game_state", {}).get("quiz_game")
            if not game_state:
                continue

            member = self.bot.get_user(top_user['_id'])
            if not member:
                member = self.bot.get_user(236400388847173632)
            if member:
                _rank = iufi.QuestionPool.get_rank(game_state['points'])
                description += f"<:{_rank[0]}:{_rank[1]}> `{func.truncate_string(member.display_name):<18} {game_state['points']:>6} 🔥`\n"

        if description and rank > len(users):
            _rank = iufi.QuestionPool.get_rank(user.get("points", 0))
            description += ("┇\n" if rank > len(users) + 1 else "") + f"<:{_rank[0]}:{_rank[1]}> `{func.truncate_string(interaction.user.display_name):<18} {user.get('points', 0):>6} 🔥`"

        if not description:
            description = "The leaderboard is currently empty."

        embed.description = f"**The next reset is <t:{int(end_time)}:R>**\n**" + (f"Your current position is `{rank}`" if user else "You haven't played any quiz game!") + f"**\n{description}"
        embed.set_thumbnail(url=icon.url if (icon := interaction.guild.icon) else None)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="music", description="Shows the IUFI Music leaderboard.")
    async def music(self, interaction: discord.Interaction):
        users = await func.USERS_DB.find().sort("game_state.music_game.points", -1).limit(10).to_list(10)
        user = await func.get_user(interaction.user.id)
        user = user.get("game_state", {}).get("music_game", {})
        rank = await func.USERS_DB.count_documents({'game_state.music_game.points': {'$gt': user.get('points', 0)}}) + 1

        embed = discord.Embed(title="🏆   Music Leaderboard", color=discord.Color.random())
        embed.description = (f"**Your current position is `{rank}`**" if user else "**You haven't played any music quiz!**") + "\n"

        description = ""
        for index, user_data in enumerate(users):
            game_state: dict[str, float | int] = user_data.get("game_state", {}).get("music_game", {})
            if not game_state:
                continue

            member = self.bot.get_user(user_data['_id'])
            if member:
                description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + highlight_text(f"{func.truncate_string(member.display_name):<18} {user_data['game_state']['music_game']['points']:>6} 𝄞", member == interaction.user)

        if user and rank > len(users):
            description += ("┇\n" if rank > len(users) + 1 else "") + f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(f"{func.truncate_string(interaction.user.display_name):<18} {user['points']:>6} 𝄞", member == interaction.user)

        if not description:
            description = "The leaderboard is currently empty."

        embed.description += f"```ansi\n{description}```"
        embed.set_thumbnail(url=icon.url if (icon := interaction.guild.icon) else None)

        view = MusicLeaderboardView(interaction.user)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

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
