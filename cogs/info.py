import discord, iufi
import functions as func

from discord.ext import commands
from views import (
    HelpView, 
    GAME_SETTINGS
)

LEADERBOARD_EMOJIS: list[str] = ["🥇", "🥈", "🥉", "🏅"]

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

        embed = discord.Embed(title="🏆   IUFI Leaderboard", color=discord.Color.random())
        embed.description = f"**Your current position is `{await func.USERS_DB.count_documents({'exp': {'$gt': user.get('exp', 0)}}) + 1}`**\n"

        description = ""
        for index, user in enumerate(users):
            level, _ = func.calculate_level(user["exp"])
            member = self.bot.get_user(user['_id'])

            if member:
                description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} {member.display_name:<15} {level:>4} ⚔️\n"
        
        if not description:
            description = "The leaderboard is currently empty."

        embed.description += f"```{description}```"
        embed.set_thumbnail(url=icon.url if (icon := ctx.guild.icon) else None)

        await ctx.reply(embed=embed)

    @leaderboard.command(aliases=["mg"])
    async def matchgame(self, ctx: commands.Context, level: str = "1"):
        """Shows the IUFI Matching Game leaderboard."""
        if level not in (levels := GAME_SETTINGS.keys()):
            return await ctx.reply(f"Invalid level selection! Please select a valid level: `{', '.join(levels)}`")
        
        users = await func.USERS_DB.find().sort([
            (f"game_state.match_game.{level}.matched", -1),
            (f"game_state.match_game.{level}.click_left", -1),
            (f"game_state.match_game.{level}.finished_time", 1)
        ]).limit(10).to_list(10)

        user = await func.get_user(ctx.author.id)
        user = user.get("game_state", {}).get("match_game", {}).get(level, {})
        better_states = await func.USERS_DB.count_documents({
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
        }) if user else 0
        
        embed = discord.Embed(title=f"🏆   Level {level} Matching Game Leaderboard", color=discord.Color.random())
        embed.description = (f"**Your current position is `{better_states + 1}`**" if user else "**You haven't play any match game!**") + "\n"

        description = ""
        for index, user in enumerate(users):
            game_state: dict[str, float | int] = user.get("game_state", {}).get("match_game", {}).get(level)
            if not game_state:
                continue

            member = self.bot.get_user(user['_id'])
            if member:
                description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} {member.display_name:<14} 🃏{game_state['matched']:<2} 🕒{func.convert_seconds(game_state['finished_time']):<10}\n"
        
        if not description:
            description = "The leaderboard is currently empty."

        embed.description += f"```{description}```"
        embed.set_thumbnail(url=icon.url if (icon := ctx.guild.icon) else None)
        await ctx.reply(embed=embed)
    
    @leaderboard.command(aliases=["q"])
    async def quiz(self, ctx: commands.Context):
        """Shows the IUFI Quiz leaderboard."""
        start_time, end_time = func.get_month_unix_timestamps()
        users = await func.USERS_DB.find({f"game_state.quiz_game.last_update": {"$gt":start_time, "$lte":end_time}}).sort(f"game_state.quiz_game.points", -1).limit(10).to_list(10)

        embed = discord.Embed(title=f"🏆   Quiz Leaderboard", color=discord.Color.random())

        description = ""
        for user in users:
            game_state: dict[str, float | int] = user.get("game_state", {}).get("quiz_game")
            if not game_state:
                continue

            member = self.bot.get_user(user['_id'])
            if member:
                rank = iufi.QuestionPool.get_rank(game_state['points'])
                description += f"<:{rank[0]}:{rank[1]}> `{member.display_name:<14} {game_state['points']:<6} 🔥`\n"
        
        if not description:
            description = "The leaderboard is currently empty."

        embed.description = f"The next reset is <t:{int(end_time)}:R>\n{description}"
        embed.set_thumbnail(url=icon.url if (icon := ctx.guild.icon) else None)
        await ctx.reply(embed=embed)

    @commands.command(aliases=["h"])
    async def help(self, ctx: commands.Context, *, command: str = None):
        "Lists all the commands in IUFI."

        if command:
            command: commands.Command = self.bot.get_command(command)
            if command:
                command_str = f"{ctx.prefix}" + (f"{command.parent.qualified_name} " if command.parent else "") + f"{command.name} {command.signature}"
                description = f"**Usage:**\n```{command_str}```\n"
                if command.aliases:
                    description += f"**Aliases:**\n`{', '.join([f'{ctx.prefix}{alias}' for alias in command.aliases])}`\n\n"
                description += f"**Description:**\n{command.help}\n\u200b"

                embed = discord.Embed(description=description, color=discord.Color.random())
                embed.set_footer(icon_url=self.bot.user.display_avatar.url, text="More Help: Ask the staff!")
                return await ctx.reply(embed=embed)

        view = HelpView(self.bot, ctx.author, ctx.prefix)
        view.response = await ctx.reply(embed=view.build_embed(), view=view)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Info(bot))