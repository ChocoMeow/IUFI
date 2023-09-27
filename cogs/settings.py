import discord
import functions as func

from discord.ext import commands

class Settings(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.emoji = "⚙️"
        self.invisible = False

    @commands.command(aliases=["qtr"])
    async def togglereminder(self, ctx: commands.Context) -> None:
        """Turns reminders on for your cooldowns. Make sure you are not blocking DMs."""

        user = await func.get_user(ctx.author.id)
        toggle = not user.get("reminder", False)
        await func.update_user(ctx.author.id, {"$set": {"reminder": toggle}})

        toggle_text = "On" if toggle else "Off"
        embed = discord.Embed(f"🔔 Reminder {toggle_text}", color=discord.Color.random())
        embed.description = f"Reminders have been turned {toggle_text}"
        await ctx.reply(embed=embed)

async def setup(bot: commands.Bot):
    bot.add_cog(Settings)