import discord
import functions as func

from discord import app_commands
from discord.ext import commands

class Settings(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.emoji = "⚙️"
        self.invisible = False

    @app_commands.command(name="togglereminder", description="Turns reminders on/off for your cooldowns. Make sure you are not blocking DMs.")
    async def togglereminder(self, interaction: discord.Interaction) -> None:
        user = await func.get_user(interaction.user.id)
        toggle = not user.get("reminder", False)
        await func.update_user(interaction.user.id, {"$set": {"reminder": toggle}})

        toggle_text = "On" if toggle else "Off"
        embed = discord.Embed(title=f"🔔 Reminder {toggle_text}", color=discord.Color.random())
        embed.description = f"Reminders have been turned {toggle_text}"
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="reset", description="Reset jk")
    async def reset(self, interaction: discord.Interaction) -> None:
        if interaction.user.id in func.settings.ADMIN_IDS:
            await interaction.response.send_message("**All game data has been wiped.**")
        else:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Settings(bot))