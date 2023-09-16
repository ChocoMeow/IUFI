import discord, iufi, psutil

from discord.ext import commands
from views import DebugView

def formatBytes(bytes: int, unit: bool = False):
    if bytes <= 1_000_000_000:
        return f"{bytes / (1024 ** 2):.1f}" + ("MB" if unit else "")
    
    else:
        return f"{bytes / (1024 ** 3):.1f}" + ("GB" if unit else "")

class Developer(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "⚙️"
        
    @commands.command()
    @commands.is_owner()
    async def debug(self, ctx: commands.Context):
        """For developer to debug"""
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        available_memory, total_memory = memory.available, memory.total
        used_disk_space, total_disk_space = disk.used, disk.total
        embed = discord.Embed(title="📄 Debug Panel", color=discord.Color.random())
        embed.description = "```==    System Info    ==\n" \
                            f"• CPU:     {psutil.cpu_freq().current}Mhz ({psutil.cpu_percent()}%)\n" \
                            f"• RAM:     {formatBytes(total_memory - available_memory)}/{formatBytes(total_memory, True)} ({memory.percent}%)\n" \
                            f"• DISK:    {formatBytes(total_disk_space - used_disk_space)}/{formatBytes(total_disk_space, True)} ({disk.percent}%)```"

        embed.add_field(
            name="🤖 Bot Information",
            value=f"```• LATENCY: {self.bot.latency:.2f}ms\n" \
                  f"• GUILDS:  {len(self.bot.guilds)}\n" \
                  f"• USERS:   {sum([guild.member_count for guild in self.bot.guilds])}\n```",
            inline=False
        )

        categorys = "\n".join([f"{category.title():<11}:  {len(cards)}" for category, cards in iufi.CardPool._available_cards.items()])
        embed.add_field(
            name=f"Card Pool",
            value=f"```• All Cards:  {len(iufi.CardPool._cards)}\n{categorys}```",
            inline=True
        )

        await ctx.reply(embed=embed, view=DebugView(self.bot, ctx.author), ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Developer(bot))