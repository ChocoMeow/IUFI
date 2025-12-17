import discord, iufi
import functions as func

from typing import Callable
from discord.ext import commands
from dataclasses import dataclass
from views import HelpView, MusicLeaderboardView

LEADERBOARD_EMOJIS: list[str] = ["🥇", "🥈", "🥉", "🏅"]

@dataclass
class LeaderboardConfig:
    title: str
    query_filter: dict
    sort_fields: list | tuple
    limit: int = 10
    icon_emoji: str = "🏆"
    is_monthly: bool = True
    is_admin_only: bool = False
    is_code_block: bool = True,
    get_display_value: Callable = None
    get_user_value: Callable = None

def highlight_text(text: str, need: bool = True) -> str:
    if not need:
        return text + "\n"
    return "\x1b[0;1;35m" + text + " \x1b[0m\n"

class Info(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "ℹ️"
        self.invisible = False

    async def build_leaderboard_embed(self, ctx: commands.Context, config: LeaderboardConfig, users: list, user: dict, rank: int) -> discord.Embed:
        embed = discord.Embed(title=f"{config.icon_emoji}   {config.title}", color=discord.Color.random())
        
        description = ""
        for index, top_user in enumerate(users):
            member = self.bot.get_user(top_user['_id'])
            if not member:
                continue
            
            display_value = config.get_display_value(top_user)
            emoji = LEADERBOARD_EMOJIS[min(index, 3)]
            description += f"{emoji} " + highlight_text(display_value, (member == ctx.author and config.is_code_block))
        
        if rank > len(users):
            user_value = config.get_user_value(user)
            description += ("┇\n" if rank > len(users) + 1 else "") + f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(user_value, config.is_code_block)
        
        if not description:
            description = "The leaderboard is currently empty."
        
        embed.description = f"```ansi\n{description}```" if config.is_code_block else description
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        return embed

    async def get_rank(self, filter_query: dict, user_compare: dict) -> int:
        return await func.USERS_DB.count_documents({**filter_query, **user_compare}) + 1

    async def get_users(self, query: dict, sort: list | tuple, limit: int) -> list:
        return await func.USERS_DB.find(query).sort(sort).limit(limit).to_list(limit)

    async def render_leaderboard(self, ctx: commands.Context, config: LeaderboardConfig, filter_query: dict, compare_query: dict, extract_user: Callable):
        user = await func.get_user(ctx.author.id)
        user_data = extract_user(user)
        
        users = await self.get_users(filter_query, config.sort_fields, config.limit)
        rank = await self.get_rank(filter_query, compare_query) if user_data else 0
        
        embed = await self.build_leaderboard_embed(ctx, config, users, user_data, rank)
        
        if config.is_monthly:
            _, end_time = func.get_month_unix_timestamps()
            embed.description = f"**The next reset is <t:{int(end_time)}:R>**\n**Your current position is `{rank}`**\n" + embed.description
        
        await ctx.reply(embed=embed)

    @commands.group(aliases=["l"], invoke_without_command=True)
    async def leaderboard(self, ctx: commands.Context):
        """Shows the IUFI leaderboard (monthly)."""
        start_time, end_time = func.get_month_unix_timestamps()
        
        config = LeaderboardConfig(
            title="IUFI Leaderboard (Monthly)",
            query_filter={"monthly.exp_last_update": {"$gt": start_time, "$lte": end_time}},
            sort_fields=[("monthly.exp", -1)],
            get_display_value=lambda u: f"{func.truncate_string(self.bot.get_user(u['_id']).display_name):<18} {func.calculate_level(u.get('monthly', {}).get('exp', 0))[0]:>5} ⚔️",
            get_user_value=lambda u: f"{func.truncate_string(ctx.author.display_name):<18} {func.calculate_level(u.get('monthly', {}).get('exp', 0))[0]:>5} ⚔️"
        )
        
        user = await func.get_user(ctx.author.id)
        users = await self.get_users(config.query_filter, config.sort_fields, config.limit)
        rank = await self.get_rank(config.query_filter, {'monthly.exp': {'$gt': user.get('monthly', {}).get('exp', 0)}})
        
        embed = await self.build_leaderboard_embed(ctx, config, users, user, rank)
        embed.description = f"**The next reset is <t:{int(end_time)}:R>**\n**Your current position is `{rank}`**\n" + embed.description
        await ctx.reply(embed=embed)

    @leaderboard.command(aliases=["l"], hidden=True)
    async def level(self, ctx: commands.Context, limit: str = "10"):
        """Shows the IUFI level leaderboard with a limit (monthly). Only for admins."""
        if ctx.author.id not in func.settings.ADMIN_IDS:
            return

        start_time, end_time = func.get_month_unix_timestamps()
        limit_int = int(limit)
        
        config = LeaderboardConfig(
            title="Level Leaderboard (Monthly)",
            query_filter={"monthly.exp_last_update": {"$gt": start_time, "$lte": end_time}},
            sort_fields=[("monthly.exp", -1)],
            limit=limit_int,
            get_display_value=lambda u: f"{func.truncate_string(self.bot.get_user(u['_id']).display_name):<18} {func.calculate_level(u.get('monthly', {}).get('exp', 0))[0]:>5} ⚔️",
            get_user_value=lambda u: f"{func.truncate_string(ctx.author.display_name):<18} {func.calculate_level(u.get('monthly', {}).get('exp', 0))[0]:>5} ⚔️"
        )
        
        user = await func.get_user(ctx.author.id)
        users = await self.get_users(config.query_filter, config.sort_fields, limit_int)
        rank = await self.get_rank(config.query_filter, {'monthly.exp': {'$gt': user.get('monthly', {}).get('exp', 0)}})
        
        embed = await self.build_leaderboard_embed(ctx, config, users, user, rank)
        embed.description = f"**The next reset is <t:{int(end_time)}:R>**\n**Your current position is `{rank}`**\n" + embed.description
        await ctx.reply(embed=embed)

    @leaderboard.command(aliases=["c"])
    async def candies(self, ctx: commands.Context):
        """Shows the IUFI Starcandies leaderboard."""
        user = await func.get_user(ctx.author.id)
        users = await self.get_users({}, [("candies", -1)], 10)
        rank = await self.get_rank({}, {'candies': {'$gt': user.get('candies', 0)}})
        
        config = LeaderboardConfig(
            title="Starcandies Leaderboard (LifeTime)",
            query_filter={},
            sort_fields=[("candies", -1)],
            is_monthly=False,
            get_display_value=lambda u: f"{func.truncate_string(self.bot.get_user(u['_id']).display_name):<18} {u['candies']:>5} 🍬",
            get_user_value=lambda u: f"{func.truncate_string(ctx.author.display_name):<18} {user.get('candies', 0):>5} 🍬"
        )
        
        embed = await self.build_leaderboard_embed(ctx, config, users, user, rank)
        embed.description = f"**Your current position is `{rank}`**\n" + embed.description
        await ctx.reply(embed=embed)

    @leaderboard.command(aliases=["mg"])
    async def matchgame(self, ctx: commands.Context, level: str = "1"):
        """Shows the IUFI Matching Game leaderboard (monthly)."""
        if level not in (levels := func.settings.MATCH_GAME_SETTINGS.keys()):
            return await ctx.reply(f"Invalid level selection! Please select a valid level: `{', '.join(levels)}`")

        start_time, end_time = func.get_month_unix_timestamps()
        
        user = await func.get_user(ctx.author.id)
        user_game = user.get("game_state", {}).get("match_game", {}).get(level, {})
        
        filter_query = {f"game_state.match_game.{level}.last_update": {"$gt": start_time, "$lte": end_time}}
        sort_fields = [
            (f"game_state.match_game.{level}.monthly_matched", -1),
            (f"game_state.match_game.{level}.monthly_click_left", -1),
            (f"game_state.match_game.{level}.monthly_finished_time", 1)
        ]
        
        users = await self.get_users(filter_query, sort_fields, 10)
        
        rank_query = {
            '$and': [
                filter_query,
                {'$or': [
                    {f"game_state.match_game.{level}.monthly_matched": {'$gt': user_game.get('monthly_matched', 0)}},
                    {'$and': [
                        {f"game_state.match_game.{level}.monthly_matched": user_game.get('monthly_matched', 0)},
                        {f"game_state.match_game.{level}.monthly_click_left": {'$gt': user_game.get('monthly_click_left', 0)}}
                    ]},
                    {'$and': [
                        {f"game_state.match_game.{level}.monthly_matched": user_game.get('monthly_matched', 0)},
                        {f"game_state.match_game.{level}.monthly_click_left": user_game.get('monthly_click_left', 0)},
                        {f"game_state.match_game.{level}.monthly_finished_time": {'$lt': user_game.get('monthly_finished_time', float('inf'))}}
                    ]}
                ]}
            ]
        }
        rank = (await func.USERS_DB.count_documents(rank_query) if user_game else 0) + 1
        
        def get_match_display(u):
            game_state = u.get("game_state", {}).get("match_game", {}).get(level)
            return f"{func.truncate_string(self.bot.get_user(u['_id']).display_name):<18} 🃏{game_state.get('monthly_matched', 0):<2} 🕒{func.convert_seconds(game_state.get('monthly_finished_time', 0)):<10}"
        
        config = LeaderboardConfig(
            title=f"Level {level} Matching Game Leaderboard (Monthly)",
            query_filter=filter_query,
            sort_fields=sort_fields,
            get_display_value=get_match_display,
            get_user_value=lambda u: f"{func.truncate_string(ctx.author.display_name):<18} 🃏{user_game.get('monthly_matched', 0):<2} 🕒{func.convert_seconds(user_game.get('monthly_finished_time', 0)):<10}"
        )
        
        embed = await self.build_leaderboard_embed(ctx, config, users, user_game, rank)
        embed.description = f"**The next reset is <t:{int(end_time)}:R>**\n**" + (f"Your current position is `{rank}`" if user_game else "You haven't played any match game!") + "**\n" + embed.description
        await ctx.reply(embed=embed)

    @leaderboard.command(aliases=["q"])
    async def quiz(self, ctx: commands.Context):
        """Shows the IUFI Quiz leaderboard (monthly)."""
        start_time, end_time = func.get_month_unix_timestamps()
        
        user = await func.get_user(ctx.author.id)
        user_game = user.get("game_state", {}).get("quiz_game", {})
        
        filter_query = {"game_state.quiz_game.last_update": {"$gt": start_time, "$lte": end_time}}
        users = await self.get_users(filter_query, [("game_state.quiz_game.points", -1)], 10)
        rank = await self.get_rank(filter_query, {"game_state.quiz_game.points": {'$gt': user_game.get("points", 0)}}) if user_game else 0
        
        def get_quiz_display(u):
            game_state = u.get("game_state", {}).get("quiz_game")
            _rank = iufi.QuestionPool.get_rank(game_state['points'])
            return f"<:{_rank[0]}:{_rank[1]}> `{func.truncate_string(self.bot.get_user(u['_id']).display_name):<18} {game_state['points']:>6} 🔥`"
        
        config = LeaderboardConfig(
            title="Quiz Leaderboard (Monthly)",
            query_filter=filter_query,
            is_code_block=False,
            sort_fields=[("game_state.quiz_game.points", -1)],
            get_display_value=get_quiz_display,
            get_user_value=lambda u: f"<:{iufi.QuestionPool.get_rank(user_game.get('points', 0))[0]}:{iufi.QuestionPool.get_rank(user_game.get('points', 0))[1]}> `{func.truncate_string(ctx.author.display_name):<18} {user_game.get('points', 0):>6} 🔥`"
        )
        
        embed = await self.build_leaderboard_embed(ctx, config, users, user_game, rank)
        embed.description = f"**The next reset is <t:{int(end_time)}:R>**\n**" + (f"Your current position is `{rank}`" if user_game else "You haven't played any quiz game!") + "**\n" + embed.description
        await ctx.reply(embed=embed)

    @leaderboard.command(aliases=["m"])
    async def music(self, ctx: commands.Context):
        """Shows the IUFI Music leaderboard (monthly)."""
        start_time, end_time = func.get_month_unix_timestamps()
        
        user = await func.get_user(ctx.author.id)
        user_game = user.get("game_state", {}).get("music_game", {})
        
        filter_query = {"game_state.music_game.last_update": {"$gt": start_time, "$lte": end_time}}
        users = await self.get_users(filter_query, [("game_state.music_game.monthly_points", -1)], 10)
        rank = await self.get_rank(filter_query, {"game_state.music_game.monthly_points": {'$gt': user_game.get('monthly_points', 0)}}) if user_game else 0
        
        config = LeaderboardConfig(
            title="Music Leaderboard (Monthly)",
            query_filter=filter_query,
            sort_fields=[("game_state.music_game.monthly_points", -1)],
            get_display_value=lambda u: f"{func.truncate_string(self.bot.get_user(u['_id']).display_name):<18} {u.get('game_state', {}).get('music_game', {}).get('monthly_points', 0):>6} 𝄞",
            get_user_value=lambda u: f"{func.truncate_string(ctx.author.display_name):<18} {user_game.get('monthly_points', 0):>6} 𝄞"
        )
        
        embed = await self.build_leaderboard_embed(ctx, config, users, user_game, rank)
        embed.description = f"**The next reset is <t:{int(end_time)}:R>**\n**" + (f"Your current position is `{rank}`" if user_game else "You haven't played any music quiz!") + "**\n" + embed.description
        
        view = MusicLeaderboardView(ctx.author, embed)
        view.message = await ctx.reply(embed=embed, view=view)

    @leaderboard.command(aliases=["eq", "e"])
    async def emoji(self, ctx: commands.Context):
        """Shows the Emoji Quiz leaderboard (monthly)."""
        start_time, end_time = func.get_month_unix_timestamps()
        
        user = await func.get_user(ctx.author.id)
        user_game = user.get("game_state", {}).get("emoji_quiz", {})
        
        filter_query = {"game_state.emoji_quiz.last_update": {"$gt": start_time, "$lte": end_time}}
        users = await self.get_users(filter_query, [("game_state.emoji_quiz.points", -1)], 10)
        rank = await self.get_rank(filter_query, {"game_state.emoji_quiz.points": {'$gt': user_game.get('points', 0)}}) if user_game else 0
        
        config = LeaderboardConfig(
            title="Emoji Quiz Leaderboard (Monthly)",
            query_filter=filter_query,
            sort_fields=[("game_state.emoji_quiz.points", -1)],
            get_display_value=lambda u: f"{func.truncate_string(self.bot.get_user(u['_id']).display_name):<18} {u.get('game_state', {}).get('emoji_quiz', {}).get('points', 0):>6} 🔥",
            get_user_value=lambda u: f"{func.truncate_string(ctx.author.display_name):<18} {user_game.get('points', 0):>6} 🔥"
        )
        
        embed = await self.build_leaderboard_embed(ctx, config, users, user_game, rank)
        embed.description = f"**The next reset is <t:{int(end_time)}:R>**\n**" + (f"Your current position is `{rank}`" if user_game else "You haven't played any emoji quiz!") + "**\n" + embed.description
        await ctx.reply(embed=embed)

    @leaderboard.command(aliases=["mv"])
    async def guessmv(self, ctx: commands.Context):
        """Shows the MV Guess leaderboard (monthly)."""
        start_time, end_time = func.get_month_unix_timestamps()
        
        user = await func.get_user(ctx.author.id)
        user_game = user.get("game_state", {}).get("mv_guess", {})
        
        filter_query = {"game_state.mv_guess.last_update": {"$gt": start_time, "$lte": end_time}}
        users = await self.get_users(filter_query, [("game_state.mv_guess.monthly_points", -1)], 10)
        rank = await self.get_rank(filter_query, {"game_state.mv_guess.monthly_points": {'$gt': user_game.get('monthly_points', 0)}}) if user_game else 0
        
        config = LeaderboardConfig(
            title="MV Guess Leaderboard",
            query_filter=filter_query,
            sort_fields=[("game_state.mv_guess.monthly_points", -1)],
            get_display_value=lambda u: f"{func.truncate_string(self.bot.get_user(u['_id']).display_name):<18} {u.get('game_state', {}).get('mv_guess', {}).get('monthly_points', 0):>6} 🎬",
            get_user_value=lambda u: f"{func.truncate_string(ctx.author.display_name):<18} {user_game.get('monthly_points', 0):>6} 🎬"
        )
        
        embed = await self.build_leaderboard_embed(ctx, config, users, user_game, rank)
        embed.description = f"**The next reset is <t:{int(end_time)}:R>**\n**" + (f"Your current position is `{rank}`" if user_game else "You haven't played any MV guess game!") + "**\n" + embed.description
        await ctx.reply(embed=embed)

    @leaderboard.command(aliases=["p"])
    async def pvp(self, ctx: commands.Context):
        """Shows the IUFI PVP Wins leaderboard (monthly)."""
        start_time, end_time = func.get_month_unix_timestamps()
        
        user = await func.get_user(ctx.author.id)
        
        filter_query = {"monthly.pvp_last_update": {"$gt": start_time, "$lte": end_time}}
        users = await self.get_users(filter_query, [("monthly.pvp.wins", -1)], 10)
        rank = await self.get_rank(filter_query, {'monthly.pvp.wins': {'$gt': user.get('monthly', {}).get('pvp', {}).get('wins', 0)}})
        
        def get_pvp_display(u):
            monthly = u.get('monthly', {}).get('pvp', {})
            return f"{func.truncate_string(self.bot.get_user(u['_id']).display_name):<18} 🏆{monthly.get('wins', 0):<3} 💀{monthly.get('losses', 0):<3} ⚔️{monthly.get('total_matches', 0):<3}"
        
        user_monthly = user.get('monthly', {}).get('pvp', {})
        
        config = LeaderboardConfig(
            title="PVP Wins Leaderboard (Monthly)",
            query_filter=filter_query,
            sort_fields=[("monthly.pvp.wins", -1)],
            get_display_value=get_pvp_display,
            get_user_value=lambda u: f"{func.truncate_string(ctx.author.display_name):<18} 🏆{user_monthly.get('wins', 0):<3} 💀{user_monthly.get('losses', 0):<3} ⚔️{user_monthly.get('total_matches', 0):<3}"
        )
        
        embed = await self.build_leaderboard_embed(ctx, config, users, user, rank)
        embed.description = f"**The next reset is <t:{int(end_time)}:R>**\n**Your current position is `{rank}`**\n" + embed.description
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