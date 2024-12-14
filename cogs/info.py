import discord, iufi
import functions as func

from discord.ext import commands
from views import HelpView, MusicLeaderboardView

LEADERBOARD_EMOJIS: list[str] = ["🥇", "🥈", "🥉", "🏅"]

def highlight_text(text: str, need: bool = True) -> str:
    if not need:
        return text + "\n"
    return "[0;1;35m" + text + " [0m\n"

class Info(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "ℹ️"
        self.invisible = False
        
    @commands.group(aliases=["l"], invoke_without_command=True)
    async def leaderboard(self, ctx: commands.Context):
        """Shows the IUFI leaderboard."""
        user = await func.get_user(ctx.author.id)
        users = await func.USERS_DB.find().sort("exp", -1).limit(10).to_list(10)
        rank = await func.USERS_DB.count_documents({'exp': {'$gt': user.get('exp', 0)}}) + 1

        embed = discord.Embed(title="🏆   IUFI Leaderboard", color=discord.Color.random())
        embed.description = f"**Your current position is `{rank}`**\n"

        description = ""
        for index, top_user in enumerate(users):
            level, _ = func.calculate_level(top_user["exp"])
            member = self.bot.get_user(top_user['_id'])

            if member:
                description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + highlight_text(f"{func.truncate_string(member.display_name):<18} {level:>5} ⚔️", member == ctx.author)
        
        if rank > len(users):
            level, _ = func.calculate_level(user['exp'])
            description += ("┇\n" if rank > len(users) + 1 else "") + f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(f"{func.truncate_string(ctx.author.display_name):<18} {level:>5} ⚔️")

        if not description:
            description = "The leaderboard is currently empty."

        embed.description += f"```ansi\n{description}```"
        embed.set_thumbnail(url=icon.url if (icon := ctx.guild.icon) else None)

        await ctx.reply(embed=embed)

    @leaderboard.command(aliases=["l"],hidden=True)
    async def level(self, ctx: commands.Context, limit: str = "10"):
        """Shows the IUFI level leaderboard with a limit. Only for admins."""
        if ctx.author.id not in func.settings.ADMIN_IDS:
            return

        users = await func.USERS_DB.find().sort("exp", -1).limit(int(limit)).to_list(int(limit))
        user = await func.get_user(ctx.author.id)
        rank = await func.USERS_DB.count_documents({'exp': {'$gt': user.get('exp', 0)}}) + 1

        embed = discord.Embed(title="🏆   Level Leaderboard", color=discord.Color.random())
        embed.description = f"**Your current position is `{rank}`**\n"

        description = ""
        for index, top_user in enumerate(users):
            level, _ = func.calculate_level(top_user["exp"])
            member = self.bot.get_user(top_user['_id'])
            if member:
                description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + highlight_text(f"{func.truncate_string(member.display_name):<18} {level:>5} ⚔️", member == ctx.author)

        if rank > int(limit):
            level, _ = func.calculate_level(user['exp'])
            description += ("┇\n" if rank > int(limit) + 1 else "") + f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(f"{func.truncate_string(ctx.author.display_name):<18} {level:>5} ⚔️", member == ctx.author)

        if not description:
            description = "The leaderboard is currently empty."

        embed.description += f"```ansi\n{description}```"
        embed.set_thumbnail(url=icon.url if (icon := ctx.guild.icon) else None)

        await ctx.reply(embed=embed)

    @leaderboard.command(aliases=["c"])
    async def candies(self, ctx: commands.Context):
        """Shows the IUFI Snowflakes leaderboard."""
        users = await func.USERS_DB.find().sort("candies", -1).limit(10).to_list(10)
        user = await func.get_user(ctx.author.id)
        rank = await func.USERS_DB.count_documents({'candies': {'$gt': user.get('candies', 0)}}) + 1

        embed = discord.Embed(title="🏆   Snowflakes Leaderboard", color=discord.Color.random())
        embed.description = f"**Your current position is `{rank}`**\n"

        description = ""
        for index, top_user in enumerate(users):
            member = self.bot.get_user(top_user['_id'])
            if member:
                description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + highlight_text(f"{func.truncate_string(member.display_name):<18} {top_user['candies']:>5} ❄️", member == ctx.author)

        if rank > len(users):
            description += ("┇\n" if rank > len(users) + 1 else "") + f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(f"{func.truncate_string(ctx.author.display_name):<18} {user.get('candies', 0):>5} ❄️", member == ctx.author)

        if not description:
            description = "The leaderboard is currently empty."

        embed.description += f"```ansi\n{description}```"
        embed.set_thumbnail(url=icon.url if (icon := ctx.guild.icon) else None)
        await ctx.reply(embed=embed)


    @leaderboard.command(aliases=["mg"])
    async def matchgame(self, ctx: commands.Context, level: str = "1"):
        """Shows the IUFI Matching Game leaderboard."""
        if level not in (levels := func.settings.MATCH_GAME_SETTINGS.keys()):
            return await ctx.reply(f"Invalid level selection! Please select a valid level: `{', '.join(levels)}`")
        
        users = await func.USERS_DB.find().sort([
            (f"game_state.match_game.{level}.matched", -1),
            (f"game_state.match_game.{level}.click_left", -1),
            (f"game_state.match_game.{level}.finished_time", 1)
        ]).limit(10).to_list(10)

        user = await func.get_user(ctx.author.id)
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
                description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + highlight_text(f"{func.truncate_string(member.display_name):<18} 🃏{game_state['matched']:<2} 🕒{func.convert_seconds(game_state['finished_time']):<10}", member == ctx.author)
        
        if user and rank > len(users):
            description += ("┇\n" if rank > len(users) + 1 else "") + f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(f"{func.truncate_string(ctx.author.display_name):<18} 🃏{user['matched']:<2} 🕒{func.convert_seconds(user['finished_time']):<10}")

        if not description:
            description = "The leaderboard is currently empty."

        embed.description += f"```ansi\n{description}```"
        embed.set_thumbnail(url=icon.url if (icon := ctx.guild.icon) else None)
        await ctx.reply(embed=embed)
    
    @leaderboard.command(aliases=["q"])
    async def quiz(self, ctx: commands.Context):
        """Shows the IUFI Quiz leaderboard."""
        start_time, end_time = func.get_month_unix_timestamps()
        user = await func.get_user(ctx.author.id)
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
            description += ("┇\n" if rank > len(users) + 1 else "") + f"<:{_rank[0]}:{_rank[1]}> `{func.truncate_string(ctx.author.display_name):<18} {user.get('points', 0):>6} 🔥`"

        if not description:
            description = "The leaderboard is currently empty."

        embed.description = f"**The next reset is <t:{int(end_time)}:R>**\n**" + (f"Your current position is `{rank}`" if user else "You haven't played any quiz game!") + f"**\n{description}"
        embed.set_thumbnail(url=icon.url if (icon := ctx.guild.icon) else None)
        await ctx.reply(embed=embed)

    @leaderboard.command(aliases=["m"])
    async def music(self, ctx: commands.Context):
        """Shows the IUFI Music leaderboard."""
        users = await func.USERS_DB.find().sort("game_state.music_game.points", -1).limit(10).to_list(10)
        user = await func.get_user(ctx.author.id)
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
                description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + highlight_text(f"{func.truncate_string(member.display_name):<18} {user_data['game_state']['music_game']['points']:>6} 𝄞", member == ctx.author)

        if user and rank > len(users):
            description += ("┇\n" if rank > len(users) + 1 else "") + f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(f"{func.truncate_string(ctx.author.display_name):<18} {user['points']:>6} 𝄞", member == ctx.author)

        if not description:
            description = "The leaderboard is currently empty."

        embed.description += f"```ansi\n{description}```"
        embed.set_thumbnail(url=icon.url if (icon := ctx.guild.icon) else None)

        view = MusicLeaderboardView(ctx.author)
        view.message = await ctx.reply(embed=embed, view=view)


    @leaderboard.command(aliases=["x"])
    async def xmas(self, ctx: commands.Context):
        """Shows the IUFI Christmas leaderboard."""

        #find christmas_game_state and find top 1 in each, and show them in the leaderboard
        # rolls, match_game.1, match_game.2, match_game.3, quiz_game, music_game
        top_roll_user = await func.USERS_DB.find().sort("christmas_game_state.rolls", -1).limit(1).to_list(1)
        top_match_game_1_user = await self.getMatchGameTopUser(1)
        top_match_game_2_user = await self.getMatchGameTopUser(2)
        top_match_game_3_user = await self.getMatchGameTopUser(3)
        top_quiz_user = await func.USERS_DB.find().sort("christmas_game_state.quiz_game", -1).limit(1).to_list(1)
        top_music_user = await func.USERS_DB.find().sort("christmas_game_state.music_quiz", -1).limit(1).to_list(1)

        embed = discord.Embed(title="🏆   Christmas Leaderboard", color=discord.Color.random())
        embed.description = "```ansi\n"
        if top_roll_user and top_roll_user[0].get('christmas_game_state') and top_roll_user[0]['christmas_game_state'].get('rolls'):
            top_roll_user = top_roll_user[0]
            member = self.bot.get_user(top_roll_user['_id'])
            embed.description += f"Top Roll : {func.truncate_string(member.display_name):<18} {top_roll_user['christmas_game_state']['rolls']:>6} 🎲\n"
        else:
            embed.description += "No rolls have been made yet.\n"

        if top_match_game_1_user and top_match_game_1_user[0].get('christmas_game_state') and top_match_game_1_user[0]['christmas_game_state'].get('match_game') and top_match_game_1_user[0]['christmas_game_state']['match_game'].get('1'):
            top_match_game_1_user = top_match_game_1_user[0]
            member = self.bot.get_user(top_match_game_1_user['_id'])
            embed.description += f"Top MG 1 : {func.truncate_string(member.display_name):<18} {top_match_game_1_user['christmas_game_state']['match_game']['1']['matched']:>6} 🃏\n"
        else:
            embed.description += "No match game level 1 has been played yet.\n"

        if top_match_game_2_user and top_match_game_2_user[0].get('christmas_game_state') and top_match_game_2_user[0]['christmas_game_state'].get('match_game') and top_match_game_2_user[0]['christmas_game_state']['match_game'].get('2'):
            top_match_game_2_user = top_match_game_2_user[0]
            member = self.bot.get_user(top_match_game_2_user['_id'])
            embed.description += f"Top MG 2 : {func.truncate_string(member.display_name):<18} {top_match_game_2_user['christmas_game_state']['match_game']['2']['matched']:>6} 🃏\n"
        else:
            embed.description += "No match game level 2 has been played yet.\n"

        if top_match_game_3_user and top_match_game_3_user[0].get('christmas_game_state') and top_match_game_3_user[0]['christmas_game_state'].get('match_game') and top_match_game_3_user[0]['christmas_game_state']['match_game'].get('3'):
            top_match_game_3_user = top_match_game_3_user[0]
            member = self.bot.get_user(top_match_game_3_user['_id'])
            embed.description += f"Top MG 3 : {func.truncate_string(member.display_name):<18} {top_match_game_3_user['christmas_game_state']['match_game']['3']['matched']:>6} 🃏\n"
        else:
            embed.description += "No match game level 3 has been played yet.\n"

        if top_quiz_user and top_quiz_user[0].get('christmas_game_state') and top_quiz_user[0]['christmas_game_state'].get('quiz_game'):
            top_quiz_user = top_quiz_user[0]
            member = self.bot.get_user(top_quiz_user['_id'])
            embed.description += f"Top Quiz : {func.truncate_string(member.display_name):<18} {top_quiz_user['christmas_game_state']['quiz_game']:>6} 🔥\n"
        else:
            embed.description += "No quiz game has been played yet.\n"

        if top_music_user and top_music_user[0].get('christmas_game_state') and top_music_user[0]['christmas_game_state'].get('music_quiz'):
            top_music_user = top_music_user[0]
            member = self.bot.get_user(top_music_user['_id'])
            embed.description += f"Top Music : {func.truncate_string(member.display_name):<18} {top_music_user['christmas_game_state']['music_quiz']:>6} 𝄞\n"
        else:
            embed.description += "No music game has been played yet.\n"

        embed.description += "```"
        embed.set_thumbnail(url=icon.url if (icon := ctx.guild.icon) else None)
        await ctx.reply(embed=embed)

    async def getMatchGameTopUser(self, level):
        return await func.USERS_DB.find().sort([
            (f"game_state.match_game.{level}.matched", -1),
            (f"game_state.match_game.{level}.click_left", -1),
            (f"game_state.match_game.{level}.finished_time", 1)
        ]).limit(1).to_list(1)

    @commands.command(aliases=["h"])
    async def help(self, ctx: commands.Context, *, command: str = None):
        """Lists all the commands in IUFI.
        
        **Example:**
        qhelp roll
        qh roll
        """
        if command:
            command: commands.Command = self.bot.get_command(command)
            if command and not command.hidden:
                return await ctx.reply(embed=func.create_help_embed(ctx, command))

        view = HelpView(self.bot, ctx.author, ctx.prefix)
        await ctx.reply(embed=view.build_embed(), view=view)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Info(bot))