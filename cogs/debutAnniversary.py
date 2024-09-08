import asyncio

import discord
import functions as func
import time
import random
from discord.ext import commands
import iufi
from discord.ext import commands, tasks

from views import AnniversarySellView

LEADERBOARD_EMOJIS: list[str] = ["🥇", "🥈", "🥉", "🏅"]

class DebutAnniversary(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.debut_anniversary.start()
        self.invisible = True
        self.emoji = "🎤"


    @commands.command(hidden=True)
    async def debut(self, ctx: commands.Context) -> None:  # delete
        user = await func.get_user(ctx.author.id)
        if user["debut_anniversary"]:
            await ctx.send("You have already claimed your debut anniversary reward!")
            return

        await ctx.send("Happy Debut Anniversary! 🎉" + "\n" + "You have received 1000🎤 Mics!")
        await func.update_user(ctx.author.id, {"candies": user["candies"] + 1000, "debut_anniversary": True})

    @commands.command(hidden=True)
    async def sendMessage(self, ctx: commands.Context, channel: discord.TextChannel, *, message: str) -> None:
        """Sends admin message to channel specified"""
        if ctx.author.id in func.settings.ADMIN_IDS:
            await channel.send(message)

    @tasks.loop(hours=24)
    async def debut_anniversary(self) -> None:
        await self.bot.wait_until_ready()
        if iufi.is_debut_anniversary_day():
            cards_to_sell = iufi.GetTodayCardSell()
            channel = self.bot.get_channel(iufi.MARKET_ID)
            for card_details in cards_to_sell:
                card_id = card_details[0]
                card_price = card_details[1]
                card = iufi.CardPool.get_card(card_id)
                if card.owner_id == self.bot.user.id:
                    view = AnniversarySellView(self.bot, None, card, card_price)
                    view.message = await channel.send(
                        content=f"Special Debut Anniversary Sale",
                        file=discord.File(await asyncio.to_thread(card.image_bytes), filename=f"image.{card.format}"),
                        embed=view.build_embed(),
                        view=view
                    )

    @commands.command(aliases=["aq"])
    async def anniversaryquest(self, ctx: commands.Context) -> None:
        """Displays the leaderboard for the Debut Anniversary event"""
        anniversary_data = await func.get_anniversary()
        users = anniversary_data["users"]
        current_milestone = anniversary_data["current_milestone"]
        if current_milestone >= len(iufi.MILESTONES):
            current_milestone = len(iufi.MILESTONES) - 1
        required_progress = iufi.MILESTONES[current_milestone]
        quest_progress = anniversary_data["quest_progress"]
        percentage = quest_progress / required_progress * 100
        progress_bar = generate_progress_bar(20, percentage)
        endtime = int(iufi.get_end_time().timestamp())
        if time.time() > endtime:
            await ctx.reply("The Debut Anniversary event has ended.")
            return
        milestone_name = "QUEST MILESTONE " + str(current_milestone + 1)
        details = f"Quest ends <t:{endtime}:R>\n\n"
        details += f"**   {milestone_name}**\n\n"
        details += f"{'✅' if quest_progress >= required_progress else '❌'} ROLL {required_progress} TIMES\n"
        details += f"```ansi\n➢ Reward: " + " | ".join(
            f"{r[0]} {f'{r[2][0]} ~ {r[2][1]}' if isinstance(r[2], list) else r[2]}" for r in
            iufi.ANNIVERSARY_QUEST_REWARDS[current_milestone]) + f"\n➢ {progress_bar} {int(percentage)}% ({quest_progress}/{required_progress})```\n"

        rank = users.index(ctx.author.id) + 1 if ctx.author.id in users else None
        embed = discord.Embed(title="❤️   Debut Anniversary Global Quest", color=discord.Color.purple())
        embed.description = details
        embed.description += f"\n🏆   Debut Anniversary Leaderboard\n"
        if rank:
            embed.description += f"**Your current position is `{rank}`**\n"

        description = ""
        top_users = users[:10]
        for index, top_user in enumerate(top_users):
            user_progress = top_user["progress"]
            member = self.bot.get_user(top_user['_id'])

            if member:
                description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + highlight_text(
                    f"{func.truncate_string(member.display_name):<18} {user_progress:>5} ⚔️", member == ctx.author)

        if rank and rank > len(top_users):
            if rank <= len(users):
                user_progress = users[rank - 1]["progress"]
                description += f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(
                    f"{func.truncate_string(ctx.author.display_name):<18} {user_progress:>5} ⚔️")

        if not description:
            description = "The leaderboard is currently empty."

        embed.description += f"```ansi\n{description}```"
        embed.set_thumbnail(url=icon.url if (icon := ctx.guild.icon) else None)

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
    await bot.add_cog(DebutAnniversary(bot))
