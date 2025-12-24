import discord, iufi, asyncio
from collections import Counter
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

    @commands.command(aliases=["w"])
    async def wrapped(self, ctx: commands.Context):
        """Shows your IUFI Wrapped stats for the year."""
        user_stats = func.open_json("data/user_stats.json")
        global_stats = func.open_json("data/global_stats.json")
        
        user_id = str(ctx.author.id)
        if user_id not in user_stats:
            return await ctx.reply("You don't have any stats recorded for this year yet! Start playing to generate your story.")
            
        user_data = user_stats[user_id]
        
        view = WrappedView(ctx, user_data, global_stats, user_stats)
        embed, file = await view.get_page(0)
        
        if file:
            await ctx.reply(embed=embed, file=file, view=view)
        else:
            await ctx.reply(embed=embed, view=view)

class WrappedView(discord.ui.View):
    def __init__(self, ctx: commands.Context, user_data: dict, global_stats: dict, users_stats: dict):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.user_data = user_data
        self.global_stats = global_stats
        self.users_stats = users_stats
        self.page = 0
        self.total_pages = 6

    async def get_page(self, page: int):
        embed = discord.Embed(title=f"✨ IUFI Wrapped 2025 - {self.ctx.author.display_name} ✨", color=0xB784B7)
        file = None

        if page == 0:
            # Slide 1: Intro & Playtime
            first_roll = self.user_data.get("first_roll_date", "N/A")
            active_days = self.user_data.get("active_days_count", 0)
            percentage = (active_days / 365) * 100
            
            embed.add_field(name="📅 The First Roll", value=f"Your first pull this year was on **{first_roll}**.\nLook how far you've come!", inline=False)
            embed.add_field(name="⏳ Your Total Playtime", value=f"You interacted with IUFI on **{active_days}** different days this year.\nThat’s **{percentage:.1f}%** of your year spent with IU!", inline=False)
            
            streak = self.user_data.get("longest_streak", 0)
            streak_msg = "Keep it up!"
            if streak > 100:
                streak_msg = "Incredible dedication! 💯"
            elif streak > 50:
                streak_msg = "You're on fire! 🔥"
            elif streak > 10: 
                streak_msg = "Nice streak! 🚀"
            elif streak > 3:
                streak_msg = "Good start!"

            embed.add_field(name="🔥 Longest Streak", value=f"**{streak} days**. {streak_msg}", inline=False)

        elif page == 1:
            # Slide 2: First High Rarity
            card_id = self.user_data.get("first_high_rarity_card_id")
            if card_id:
                card = iufi.CardPool.get_card(card_id)
                if card:
                    embed.title = "🍀 Your Luckiest Moment"
                    embed.add_field(name="💎 First High Rarity", value=f"Card ID: `{card_id}`\nRarity: {self.user_data.get('first_high_rarity_rarity')}\nDate: {self.user_data.get('first_high_rarity_date')}", inline=False)
                    
                    rolls = self.user_data.get("rolls_until_high_rarity", 0)
                    title = "🍀 Pure Luck!" if rolls <= 100 else "💪 True Persistence!" if rolls > 1000 else "✨ Well Deserved!"
                    embed.add_field(name=title, value=f"It took you **{rolls}** rolls to find this gem.", inline=False)
                    
                    image_bytes = await card.image_bytes()
                    file = discord.File(image_bytes, filename=f"{card_id}.webp")
                    embed.set_image(url=f"attachment://{card_id}.webp")
            else:
                embed.description = "You haven't found a high rarity card yet this year. Keep rolling! 🍀"

        elif page == 2:
            # Slide 3: Activity & Most active day
            active_day = self.user_data.get("most_active_day", {})
            date = active_day.get("date", "N/A")
            count = active_day.get("count", 0)
            
            embed.add_field(name="📅 Most Active Day", value=f"On **{date}**, you used **{count}** commands!\nYou were really grinding that day! 🏃‍♂️💨", inline=False)
            
            # Top 5 commands
            command_counts = Counter()
            # Aggregate room commands
            for room_cmds in self.user_data.get("room_command_counts", {}).values():
                command_counts.update(room_cmds)
            
            top_cmds = command_counts.most_common(5)
            cmd_text = "\n".join([f"`{cmd}`: {cnt}" for cmd, cnt in top_cmds]) if top_cmds else "No commands used."
            embed.add_field(name="⌨️ Top Commands", value=cmd_text, inline=False)
            
            # Collection Stats
            collected = self.user_data.get("cards_collected_count", 0)
            rarity_counts = self.user_data.get("rarity_counts", {})
            rarity_text = " • ".join([f"{k} {v}" for k, v in rarity_counts.items()])
            
            embed.add_field(name="🃏 Collection Stats", value=f"Total Cards: **{collected}**", inline=False)
            if rarity_text:
                embed.add_field(name="✨ Rarity Breakdown", value=rarity_text, inline=False)

        elif page == 3:
            # Slide 4: Titles/Persona
            embed.title = "🏆 Your IUFI Persona"
            description = ""
            
            # Silent Supporter
            msg_count = self.user_data.get("iufi_chat_msgs", 0)
            react_count = self.user_data.get("iufi_chat_reactions_given", 0)
            if msg_count < react_count and react_count > 10:
                description += "**🤫 The Silent Supporter**\nYou react more than you type! A true observer.\n\n"
            
            # Resident of Room X
            room_counts = self.user_data.get("room_command_counts", {})
            total_commands = sum(sum(cmds.values()) for cmds in room_counts.values())
            if total_commands > 0:
                for room, cmds in room_counts.items():
                    if sum(cmds.values()) / total_commands >= 0.9:
                        description += f"**🏠 Resident of {room}**\nThis is your home. You rarely leave!\n\n"
                        break
            
            # Flexer / Gallery
            gallery_posts = self.user_data.get("gallery_posts", 0)
            gallery_reactions = self.user_data.get("gallery_reactions_received", 0)
            if gallery_posts > 10: 
                 description += "**💪 The Flexer**\nYou love showing off your collection!\n\n"
            
            if gallery_reactions > 0:
                highest_post = self.user_data.get("highest_reaction_gallery_post", {})
                description += f"**📸 Gallery Star**\nYour gallery posts received **{gallery_reactions}** reactions!\nBest post: {highest_post.get('count', 0)} reactions on specific post.\n\n"
            
            # Chatty
            game_msgs = self.user_data.get("game_room_msgs", 0)
            if game_msgs > 100:
                 description += "**🗣️ Chatterbox**\nYou love chatting in the game rooms!\n\n"

            if not description:
                description = "You are a mysterious player with no specific traits yet!"
            
            embed.description = description

        elif page == 4:
            # Slide 5: Percentiles
            coll_count = self.user_data.get("cards_collected_count", 0)
            if coll_count > 0:
                # Calculate rank
                all_counts = [u.get("cards_collected_count", 0) for u in self.users_stats.values()]
                all_counts.sort(reverse=True)
                try:
                    rank = all_counts.index(coll_count) + 1
                    percentile = (rank / len(all_counts)) * 100
                    
                    if percentile <= 1:
                        top_text = "Top 1%"
                    elif percentile <= 5:
                        top_text = "Top 5%"
                    elif percentile <= 10:
                        top_text = "Top 10%"
                    elif percentile <= 25:
                        top_text = "Top 25%"
                    else:
                        top_text = f"Top {int(percentile)}%"
                        
                    embed.add_field(name="🌟 Global Standing", value=f"You are among the **{top_text}** of collectors in the server!", inline=False)
                    embed.add_field(name="📊 Your Rank", value=f"#{rank} out of {len(all_counts)} users", inline=False)
                except ValueError:
                    pass
            else:
                embed.description = "Start collecting cards to see your global ranking!"

        elif page == 5:
            # Slide 6: Community Milestones
            total_cards = self.global_stats.get("total_cards_collected", 0)
            stadium_capacity = 50000 
            stadiums = total_cards / stadium_capacity
            
            embed.title = "🌍 Community Milestones"
            embed.add_field(name="🃏 Total Pulled Cards", value=f"Together, this server pulled **{total_cards:,}** IU cards this year!", inline=False)
            embed.add_field(name="🏟️ That's a lot!", value=f"That’s enough to fill **{stadiums:.1f}** stadiums with cards!", inline=False)
            
            embed.description = "Thank you for being part of this amazing journey! ❤️"

        embed.set_footer(text=f"Page {page + 1}/{self.total_pages}")
        return embed, file

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            embed, file = await self.get_page(self.page)
            # Edit the message
            await interaction.response.edit_message(embed=embed, attachments=[file] if file else [], view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.total_pages - 1:
            self.page += 1
            embed, file = await self.get_page(self.page)
            # Edit the message
            await interaction.response.edit_message(embed=embed, attachments=[file] if file else [], view=self)
        else:
             await interaction.response.defer()

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Info(bot))