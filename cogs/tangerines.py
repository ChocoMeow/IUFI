import discord
from discord.ext import commands
import time
import random
import functions as func
import iufi

# Define leaderboard emojis for ranks
LEADERBOARD_EMOJIS = ["🥇", "🥈", "🥉", "🏅"]

# Define fish types with their emoji, point values and catch probabilities
FISH_TYPES = [
    {"name": "Trash", "emoji": "🗑️", "points": 1, "self_prob": 0.15, "other_prob": 0.10},
    {"name": "Seaweed", "emoji": "🌿", "points": 2, "self_prob": 0.15, "other_prob": 0.10},
    {"name": "Shrimp", "emoji": "🦐", "points": 5, "self_prob": 0.15, "other_prob": 0.12},
    {"name": "Crab", "emoji": "🦀", "points": 7, "self_prob": 0.12, "other_prob": 0.12},
    {"name": "Squid", "emoji": "🦑", "points": 10, "self_prob": 0.12, "other_prob": 0.12},
    {"name": "Octopus", "emoji": "🐙", "points": 15, "self_prob": 0.10, "other_prob": 0.11},
    {"name": "Tropical Fish", "emoji": "🐠", "points": 20, "self_prob": 0.08, "other_prob": 0.10},
    {"name": "Blowfish", "emoji": "🐡", "points": 25, "self_prob": 0.06, "other_prob": 0.09},
    {"name": "Fish", "emoji": "🐟", "points": 30, "self_prob": 0.05, "other_prob": 0.08},
    {"name": "Dolphin", "emoji": "🐬", "points": 50, "self_prob": 0.02, "other_prob": 0.06}
]

class Tangerines(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "🍊"
        self.invisible = False

    @commands.command()
    async def tangerine(self, ctx: commands.Context) -> None:
        """Responds with a tangerine message."""
        await ctx.send("Here's a tangerine! 🍊")
        
    @commands.command(aliases=["fi"])
    @commands.cooldown(1, 1, commands.BucketType.user)
    async def fish(self, ctx: commands.Context, member: discord.Member = None) -> None:
        """Go fishing either for yourself or for someone else.
        
        **Examples:**
        @prefix@fish
        @prefix@f @user
        """
        fisher = ctx.author
        recipient = member or fisher
        fishing_for_self = fisher.id == recipient.id
        
        # Select probabilities based on if fishing for self or others
        prob_key = "self_prob" if fishing_for_self else "other_prob"
        
        # Calculate weighted choice based on probabilities
        probabilities = [fish[prob_key] for fish in FISH_TYPES]
        catch = random.choices(FISH_TYPES, weights=probabilities, k=1)[0]
        
        # Update user's fish score in the database
        user = await func.get_user(recipient.id)
        fishing_score = user.get("fishing_score", 0)
        new_score = fishing_score + catch["points"]
        
        await func.update_user(recipient.id, {"$set": {"fishing_score": new_score}})
        
        # Create an embed for the fishing result
        embed = discord.Embed(
            title=f"🎣 Fishing Results",
            color=discord.Color.blue()
        )
        
        if fishing_for_self:
            embed.description = f"You caught: {catch['emoji']} **{catch['name']}** worth **{catch['points']}** points!\n\n"
            embed.description += f"Your fishing score is now: **{new_score}** points"
        else:
            embed.description = f"{fisher.mention} caught: {catch['emoji']} **{catch['name']}** worth **{catch['points']}** points for {recipient.mention}!\n\n"
            embed.description += f"{recipient.display_name}'s fishing score is now: **{new_score}** points"
        
        embed.set_thumbnail(url=recipient.display_avatar.url)
        await ctx.reply(embed=embed)
    
    @commands.command(aliases=["fl"])
    async def fishingleaderboard(self, ctx: commands.Context) -> None:
        """Displays the fishing leaderboard.
        
        **Examples:**
        @prefix@fishingleaderboard
        @prefix@fl
        """
        # Get all users and sort by fishing score
        all_users = await func.USERS_DB.find({}).to_list()
        fishing_users = [user for user in all_users if user.get("fishing_score", 0) > 0]
        fishing_users.sort(key=lambda x: x.get("fishing_score", 0), reverse=True)
        
        embed = discord.Embed(title="🎣 Fishing Leaderboard", color=discord.Color.blue())
        
        # Find the author's rank
        author_rank = None
        for index, user in enumerate(fishing_users):
            if user["_id"] == ctx.author.id:
                author_rank = index + 1
                break
        
        if author_rank:
            embed.description = f"**Your current position is `{author_rank}`**\n"
        
        description = ""
        top_users = fishing_users[:10]
        rank_1_user = None
        
        for index, top_user in enumerate(top_users):
            user_score = top_user.get("fishing_score", 0)
            member = self.bot.get_user(top_user['_id'])
            
            if member:
                if index == 0:
                    rank_1_user = member
                description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + highlight_text(
                    f"{func.truncate_string(member.display_name):<18} {user_score:>5} 🎣", member == ctx.author)
        
        if author_rank and author_rank > len(top_users):
            if author_rank <= len(fishing_users):
                user_score = fishing_users[author_rank - 1].get("fishing_score", 0)
                description += f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(
                    f"{func.truncate_string(ctx.author.display_name):<18} {user_score:>5} 🎣", True)
        
        if not description:
            description = "The leaderboard is currently empty."
        
        embed.description = (embed.description or "") + f"```ansi\n{description}```"
        icon = rank_1_user.display_avatar if rank_1_user else ctx.guild.icon
        embed.set_thumbnail(url=icon.url if icon else None)
        
        await ctx.reply(embed=embed)

    @commands.command(aliases=["gq"])
    async def globalquest(self, ctx: commands.Context) -> None:
        """Displays the current global quest progress and milestone information"""
        global_data = await func.get_tangerines()
        current_milestone = global_data["current_milestone"]
        if current_milestone >= len(iufi.GLOBAL_MILESTONES):
            current_milestone = len(iufi.GLOBAL_MILESTONES) - 1
        required_progress = iufi.GLOBAL_MILESTONES[current_milestone]
        quest_progress = global_data["quest_progress"]
        percentage = quest_progress / required_progress * 100
        progress_bar = generate_progress_bar(20, percentage)
        endtime = int(iufi.get_global_end_time().timestamp())
        milestone_name = "QUEST MILESTONE " + str(current_milestone + 1)
        
        details = ""
        if time.time() > endtime:
            details = "Global quest has ended\n\n"
        else:
            details = f"Global quest ends <t:{endtime}:R>\n\n"
            
        details += f"**   {milestone_name}**\n\n"
        details += f"{'✅' if quest_progress >= required_progress else '❌'} COMPLETE {required_progress} TASKS\n"
        details += f"```ansi\n➢ Reward: " + " | ".join(
            f"{r[0]} {f'{r[2][0]} ~ {r[2][1]}' if isinstance(r[2], list) else r[2]}" for r in
            iufi.GLOBAL_QUEST_REWARDS[current_milestone]) + f"\n➢ {progress_bar} {int(percentage)}% ({quest_progress}/{required_progress})```\n"

        embed = discord.Embed(title="🌏   Global Community Quest", color=discord.Color.blue())
        embed.description = details
        embed.set_thumbnail(url=icon.url if (icon := ctx.guild.icon) else None)
        await ctx.reply(embed=embed)

    @commands.command(aliases=["gl"])
    async def globalleaderboard(self, ctx: commands.Context) -> None:
        """Displays the leaderboard for the global quest participants"""
        global_data = await func.get_tangerines()
        users = global_data["users"]
        users.sort(key=lambda x: x["progress"], reverse=True)
        embed = discord.Embed(title="🏆   Global Quest Leaderboard", color=discord.Color.blue())
        embed.description = ""
        rank = None
        for index, user in enumerate(users):
            if user["_id"] == ctx.author.id:
                rank = index + 1
                break
        if rank:
            embed.description += f"**Your current position is `{rank}`**\n"

        description = ""
        top_users = users[:10]
        rank_1_user = None

        for index, top_user in enumerate(top_users):
            user_progress = top_user["progress"]
            member = self.bot.get_user(top_user['_id'])

            if member:
                if index == 0:
                    rank_1_user = member
                description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + highlight_text(
                    f"{func.truncate_string(member.display_name):<18} {user_progress:>5} 🌟", member == ctx.author)

        if rank and rank > len(top_users):
            if rank <= len(users):
                user_progress = users[rank - 1]["progress"]
                description += f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(
                    f"{func.truncate_string(ctx.author.display_name):<18} {user_progress:>5} 🌟")

        if not description:
            description = "The leaderboard is currently empty."

        embed.description += f"```ansi\n{description}```"
        icon = rank_1_user.display_avatar if rank_1_user else ctx.guild.icon
        embed.set_thumbnail(url=icon.url if (icon := icon) else None)

        await ctx.reply(embed=embed)


def generate_progress_bar(total, progress_percentage, filled='⣿', in_progress='⣦', empty='⣀'):
    progress = int(total * progress_percentage / 100)
    filled_length = progress
    in_progress_length = 1 if progress_percentage - filled_length > 0 else 0
    empty_length = total - filled_length - in_progress_length

    # ANSI escape code for magenta color
    start_color = f"[0;1;{'32' if total == progress else '35'}m"
    end_color = "[0m"

    progress_bar = start_color + filled * filled_length + in_progress * in_progress_length + end_color + empty * empty_length

    return progress_bar


def highlight_text(text: str, need: bool = True) -> str:
    if not need:
        return text + "\n"
    return "[0;1;35m" + text + " [0m\n"



async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Tangerines(bot))

