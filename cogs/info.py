import discord, iufi
import functions as func

from discord.ext import commands
from views import HelpView, MusicLeaderboardView, EmojiLeaderboardView

LEADERBOARD_EMOJIS: list[str] = ["🥇", "🥈", "🥉", "🏅"]

def highlight_text(text: str, need: bool = True) -> str:
    if not need:
        return text + "\n"
    return "\x1b[0;1;35m" + text + " \x1b[0m\n"

class Info(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "ℹ️"
        self.invisible = False
        
    @commands.group(aliases=["l"], invoke_without_command=True)
    async def leaderboard(self, ctx: commands.Context):
        """Shows the IUFI leaderboard (monthly)."""
        start_time, end_time = func.get_month_unix_timestamps()

        user = await func.get_user(ctx.author.id)
        # show monthly exp leaderboard
        users = await func.USERS_DB.find({"monthly.exp_last_update": {"$gt": start_time, "$lte": end_time}}).sort("monthly.exp", -1).limit(10).to_list(10)
        rank = await func.USERS_DB.count_documents({"monthly.exp_last_update": {"$gt": start_time, "$lte": end_time}, 'monthly.exp': {'$gt': user.get('monthly', {}).get('exp', 0)}}) + 1

        embed = discord.Embed(title="🏆   IUFI Leaderboard (Monthly)", color=discord.Color.random())
        embed.description = f"**The next reset is <t:{int(end_time)}:R>**\n**Your current position is `{rank}`**\n"

        description = ""
        for index, top_user in enumerate(users):
            level, _ = func.calculate_level(top_user.get("exp", 0))
            member = self.bot.get_user(top_user['_id'])

            if member:
                # show monthly exp converted to level for display if available
                monthly_exp = top_user.get('monthly', {}).get('exp', 0)
                m_level, _ = func.calculate_level(monthly_exp)
                description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + highlight_text(f"{func.truncate_string(member.display_name):<18} {m_level:>5} ⚔️", member == ctx.author)

        if rank > len(users):
            level, _ = func.calculate_level(user.get('exp', 0))
            monthly_exp = user.get('monthly', {}).get('exp', 0)
            m_level, _ = func.calculate_level(monthly_exp)
            description += ("┇\n" if rank > len(users) + 1 else "") + f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(f"{func.truncate_string(ctx.author.display_name):<18} {m_level:>5} ⚔️", True)

        if not description:
            description = "The leaderboard is currently empty."

        embed.description += f"```ansi\n{description}```"
        embed.set_thumbnail(url=icon.url if (icon := ctx.guild.icon) else None)

        await ctx.reply(embed=embed)

    @leaderboard.command(aliases=["l"],hidden=True)
    async def level(self, ctx: commands.Context, limit: str = "10"):
        """Shows the IUFI level leaderboard with a limit (monthly). Only for admins."""
        if ctx.author.id not in func.settings.ADMIN_IDS:
            return

        start_time, end_time = func.get_month_unix_timestamps()
        users = await func.USERS_DB.find({"monthly.exp_last_update": {"$gt": start_time, "$lte": end_time}}).sort("monthly.exp", -1).limit(int(limit)).to_list(int(limit))
        user = await func.get_user(ctx.author.id)
        rank = await func.USERS_DB.count_documents({"monthly.exp_last_update": {"$gt": start_time, "$lte": end_time}, 'monthly.exp': {'$gt': user.get('monthly', {}).get('exp', 0)}}) + 1

        embed = discord.Embed(title="🏆   Level Leaderboard (Monthly)", color=discord.Color.random())
        embed.description = f"**The next reset is <t:{int(end_time)}:R>**\n**Your current position is `{rank}`**\n"

        description = ""
        for index, top_user in enumerate(users):
            level, _ = func.calculate_level(top_user.get("exp", 0))
            member = self.bot.get_user(top_user['_id'])
            if member:
                monthly_exp = top_user.get('monthly', {}).get('exp', 0)
                m_level, _ = func.calculate_level(monthly_exp)
                description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + highlight_text(f"{func.truncate_string(member.display_name):<18} {m_level:>5} ⚔️", member == ctx.author)

        if rank > int(limit):
            monthly_exp = user.get('monthly', {}).get('exp', 0)
            m_level, _ = func.calculate_level(monthly_exp)
            description += ("┇\n" if rank > int(limit) + 1 else "") + f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(f"{func.truncate_string(ctx.author.display_name):<18} {m_level:>5} ⚔️", True)

        if not description:
            description = "The leaderboard is currently empty."

        embed.description += f"```ansi\n{description}```"
        embed.set_thumbnail(url=icon.url if (icon := ctx.guild.icon) else None)

        await ctx.reply(embed=embed)

    @leaderboard.command(aliases=["c"])
    async def candies(self, ctx: commands.Context):
        """Shows the IUFI Starcandies leaderboard."""
        users = await func.USERS_DB.find().sort("candies", -1).limit(10).to_list(10)
        user = await func.get_user(ctx.author.id)
        rank = await func.USERS_DB.count_documents({'candies': {'$gt': user.get('candies', 0)}}) + 1

        embed = discord.Embed(title="🏆   Starcandies Leaderboard", color=discord.Color.random())
        embed.description = f"**Your current position is `{rank}`**\n"

        description = ""
        for index, top_user in enumerate(users):
            member = self.bot.get_user(top_user['_id'])
            if member:
                description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + highlight_text(f"{func.truncate_string(member.display_name):<18} {top_user['candies']:>5} 🍬", member == ctx.author)

        if rank > len(users):
            description += ("┇\n" if rank > len(users) + 1 else "") + f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(f"{func.truncate_string(ctx.author.display_name):<18} {user.get('candies', 0):>5} 🍬", True)

        if not description:
            description = "The leaderboard is currently empty."

        embed.description += f"```ansi\n{description}```"
        embed.set_thumbnail(url=icon.url if (icon := ctx.guild.icon) else None)
        await ctx.reply(embed=embed)


    @leaderboard.command(aliases=["mg"])
    async def matchgame(self, ctx: commands.Context, level: str = "1"):
        """Shows the IUFI Matching Game leaderboard (monthly)."""
        if level not in (levels := func.settings.MATCH_GAME_SETTINGS.keys()):
            return await ctx.reply(f"Invalid level selection! Please select a valid level: `{', '.join(levels)}`")

        start_time, end_time = func.get_month_unix_timestamps()
        users = await func.USERS_DB.find({f"game_state.match_game.{level}.last_update": {"$gt":start_time, "$lte":end_time}}).sort([
            (f"game_state.match_game.{level}.monthly_matched", -1),
            (f"game_state.match_game.{level}.monthly_click_left", -1),
            (f"game_state.match_game.{level}.monthly_finished_time", 1)
        ]).limit(10).to_list(10)

        user = await func.get_user(ctx.author.id)
        user = user.get("game_state", {}).get("match_game", {}).get(level, {})
        rank = (await func.USERS_DB.count_documents({
            '$and': [
                {f"game_state.match_game.{level}.last_update": {"$gt":start_time, "$lte":end_time}},
                {'$or': [
                    {f"game_state.match_game.{level}.monthly_matched": {'$gt': user.get('monthly_matched', 0)}},
                    {'$and': [
                        {f"game_state.match_game.{level}.monthly_matched": user.get('monthly_matched', 0)},
                        {f"game_state.match_game.{level}.monthly_click_left": {'$gt': user.get('monthly_click_left', 0)}}
                    ]},
                    {'$and': [
                        {f"game_state.match_game.{level}.monthly_matched": user.get('monthly_matched', 0)},
                        {f"game_state.match_game.{level}.monthly_click_left": user.get('monthly_click_left', 0)},
                        {f"game_state.match_game.{level}.monthly_finished_time": {'$lt': user.get('monthly_finished_time', float('inf'))}}
                    ]}
                ]}
            ]
        }) if user else 0) + 1
        
        embed = discord.Embed(title=f"🏆   Level {level} Matching Game Leaderboard (Monthly)", color=discord.Color.random())
        embed.description = (f"**Your current position is `{rank}`**" if user else "**You haven't played any match game!**") + "\n"
        embed.description = f"**The next reset is <t:{int(end_time)}:R>**\n" + embed.description

        description = ""
        for index, top_user in enumerate(users):
            game_state: dict[str, float | int] = top_user.get("game_state", {}).get("match_game", {}).get(level)
            if not game_state:
                continue

            member = self.bot.get_user(top_user['_id'])
            if member:
                description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + highlight_text(f"{func.truncate_string(member.display_name):<18} 🃏{game_state.get('monthly_matched', 0):<2} 🕒{func.convert_seconds(game_state.get('monthly_finished_time', 0)):<10}", member == ctx.author)

        if user and rank > len(users):
            description += ("┇\n" if rank > len(users) + 1 else "") + f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(f"{func.truncate_string(ctx.author.display_name):<18} 🃏{user.get('monthly_matched', 0):<2} 🕒{func.convert_seconds(user.get('monthly_finished_time', 0)):<10}", True)

        if not description:
            description = "The leaderboard is currently empty."

        embed.description += f"```ansi\n{description}```"
        embed.set_thumbnail(url=icon.url if (icon := ctx.guild.icon) else None)
        await ctx.reply(embed=embed)
    
    @leaderboard.command(aliases=["q"])
    async def quiz(self, ctx: commands.Context):
        """Shows the IUFI Quiz leaderboard (monthly)."""
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
        """Shows the IUFI Music leaderboard (monthly)."""
        start_time, end_time = func.get_month_unix_timestamps()
        users = await func.USERS_DB.find({f"game_state.music_game.last_update": {"$gt":start_time, "$lte":end_time}}).sort("game_state.music_game.monthly_points", -1).limit(10).to_list(10)
        user = await func.get_user(ctx.author.id)
        user = user.get("game_state", {}).get("music_game", {})
        rank = await func.USERS_DB.count_documents({"$and": [{f"game_state.music_game.last_update": {"$gt":start_time, "$lte":end_time}}, {"game_state.music_game.monthly_points": {'$gt': user.get('monthly_points', 0)}}]}) + 1

        embed = discord.Embed(title="🏆   Music Leaderboard", color=discord.Color.random())
        embed.description = (f"**The next reset is <t:{int(end_time)}:R>\nYour current position is `{rank}`**" if user else "**You haven't played any music quiz!**") + "\n"

        description = ""
        for index, user_data in enumerate(users):
            game_state: dict[str, float | int] = user_data.get("game_state", {}).get("music_game", {})
            if not game_state:
                continue

            member = self.bot.get_user(user_data['_id'])
            if member:
                description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + highlight_text(f"{func.truncate_string(member.display_name):<18} {game_state.get('monthly_points', 0):>6} 𝄞", member == ctx.author)

        if user and rank > len(users):
            description += ("┇\n" if rank > len(users) + 1 else "") + f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(f"{func.truncate_string(ctx.author.display_name):<18} {user.get('monthly_points', 0):>6} 𝄞", True)

        if not description:
            description = "The leaderboard is currently empty."

        embed.description += f"```ansi\n{description}```"
        embed.set_thumbnail(url=icon.url if (icon := ctx.guild.icon) else None)

        view = MusicLeaderboardView(ctx.author)
        view.message = await ctx.reply(embed=embed, view=view)

    @leaderboard.command(aliases=["eq","elb","e"])
    async def emoji(self, ctx: commands.Context):
        """Shows the Emoji Quiz leaderboard (monthly)."""
        start_time, end_time = func.get_month_unix_timestamps()
        user = await func.get_user(ctx.author.id)
        user = user.get("game_state", {}).get("emoji_quiz", {})
        users = await func.USERS_DB.find({f"game_state.emoji_quiz.last_update": {"$gt":start_time, "$lte":end_time}}).sort("game_state.emoji_quiz.points", -1).limit(10).to_list(10)
        rank = await func.USERS_DB.count_documents({
            "$and": [
                {"game_state.emoji_quiz.last_update": {"$gt":start_time, "$lte":end_time}},
                {"game_state.emoji_quiz.points": {'$gt': user.get('points', 0)}}
            ]}) + 1

        embed = discord.Embed(title=f"🏆   Emoji Quiz Leaderboard", color=discord.Color.random())

        description = ""
        for top_user in users:
            game_state: dict[str, float | int] = top_user.get("game_state", {}).get("emoji_quiz")
            if not game_state:
                continue

            member = self.bot.get_user(top_user['_id'])
            if not member:
                member = self.bot.get_user(236400388847173632)
            if member:
                description += f"`{func.truncate_string(member.display_name):<18} {game_state['points']:>6} 🔥`\n"

        if description and rank > len(users):
            description += ("┇\n" if rank > len(users) + 1 else "") + f"`{func.truncate_string(ctx.author.display_name):<18} {user.get('points', 0):>6} 🔥`"

        if not description:
            description = "The leaderboard is currently empty."

        embed.description = f"**The next reset is <t:{int(end_time)}:R>**\n**" + (f"Your current position is `{rank}`" if user else "You haven't played any emoji quiz!") + f"**\n{description}"
        embed.set_thumbnail(url=icon.url if (icon := ctx.guild.icon) else None)

        view = EmojiLeaderboardView(ctx.author)
        view.message = await ctx.reply(embed=embed, view=view)

    @leaderboard.command(aliases=["mv"])
    async def guessmv(self, ctx: commands.Context):
        """Shows the MV Guess leaderboard (monthly)."""
        start_time, end_time = func.get_month_unix_timestamps()
        user = await func.get_user(ctx.author.id)
        user_game = user.get("game_state", {}).get("mv_guess", {})

        users = await func.USERS_DB.find({f"game_state.mv_guess.last_update": {"$gt":start_time, "$lte":end_time}}).sort("game_state.mv_guess.monthly_points", -1).limit(10).to_list(10)
        rank = await func.USERS_DB.count_documents({
            "$and": [
                {f"game_state.mv_guess.last_update": {"$gt":start_time, "$lte":end_time}},
                {"game_state.mv_guess.monthly_points": {'$gt': user_game.get('monthly_points', 0)}}
            ]
        }) + 1

        embed = discord.Embed(title=f"🏆   MV Guess Leaderboard", color=discord.Color.random())

        description = ""
        for top_user in users:
            game_state: dict[str, float | int] = top_user.get("game_state", {}).get("mv_guess")
            if not game_state:
                continue

            member = self.bot.get_user(top_user['_id'])
            if not member:
                member = self.bot.get_user(236400388847173632)
            if member:
                description += f"`{func.truncate_string(member.display_name):<18} {game_state.get('monthly_points', 0):>6} 🎬`\n"

        if description and rank > len(users):
            description += ("┇\n" if rank > len(users) + 1 else "") + f"`{func.truncate_string(ctx.author.display_name):<18} {user_game.get('monthly_points', 0):>6} 🎬`"

        if not description:
            description = "The leaderboard is currently empty."

        embed.description = f"**The next reset is <t:{int(end_time)}:R>**\n**" + (f"Your current position is `{rank}`" if user_game else "You haven't played any MV guess game!") + f"**\n{description}"
        embed.set_thumbnail(url=icon.url if (icon := ctx.guild.icon) else None)

        await ctx.reply(embed=embed)

    @leaderboard.command(aliases=["p"])
    async def pvp(self, ctx: commands.Context):
        """Shows the IUFI PVP Wins leaderboard (monthly)."""
        start_time, end_time = func.get_month_unix_timestamps()
        users = await func.USERS_DB.find({"monthly.pvp_last_update": {"$gt": start_time, "$lte": end_time}}).sort("monthly.pvp.wins", -1).limit(10).to_list(10)
        user = await func.get_user(ctx.author.id)
        rank = await func.USERS_DB.count_documents({"monthly.pvp_last_update": {"$gt": start_time, "$lte": end_time}, 'monthly.pvp.wins': {'$gt': user.get('monthly', {}).get('pvp', {}).get('wins', 0)}}) + 1

        embed = discord.Embed(title="🏆   PVP Wins Leaderboard (Monthly)", color=discord.Color.random())
        embed.description = f"**The next reset is <t:{int(end_time)}:R>**\n**Your current position is `{rank}`**\n"

        description = ""
        for index, top_user in enumerate(users):
            member = self.bot.get_user(top_user['_id'])
            wins = top_user.get('monthly', {}).get('pvp', {}).get('wins', 0)
            matches = top_user.get('monthly', {}).get('pvp', {}).get('total_matches', 0)
            losses = top_user.get('monthly', {}).get('pvp', {}).get('losses', 0)
            if member:
                description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + highlight_text(f"{func.truncate_string(member.display_name):<18} 🏆{wins:<3} 💀{losses:<3} ⚔️{matches:<3}", member == ctx.author)

        # Show current user if not in top 10
        user_wins = user.get('monthly', {}).get('pvp', {}).get('wins', 0)
        user_matches = user.get('monthly', {}).get('pvp', {}).get('total_matches', 0)
        user_losses = user.get('monthly', {}).get('pvp', {}).get('losses', 0)
        if rank > len(users):
            description += ("┇\n" if rank > len(users) + 1 else "") + f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(f"{func.truncate_string(ctx.author.display_name):<18} 🏆{user_wins:<3} 💀{user_losses:<3} ⚔️{user_matches:<3}", True)

        if not description:
            description = "The leaderboard is currently empty."

        embed.description += f"```ansi\n{description}```"
        embed.set_thumbnail(url=icon.url if (icon := ctx.guild.icon) else None)
        await ctx.reply(embed=embed)

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