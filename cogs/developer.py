import discord, iufi, psutil, asyncio

from discord.ext import commands
from concurrent.futures import ThreadPoolExecutor
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
        self.invisible = True
        
        self.ctx_menu = discord.app_commands.ContextMenu(
            name="find similar",
            callback=self._findsimilar
        )
        self.bot.tree.add_command(self.ctx_menu)
        
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

    @commands.is_owner()
    async def _findsimilar(self, interaction: discord.Interaction, message: discord.Message):
        """Find similar image from the card pool."""
        if message.attachments:
            image = message.attachments[0]
            await interaction.response.defer()

            with ThreadPoolExecutor() as executor:
                loop = asyncio.get_event_loop()
                if not iufi.CardPool.search_image:
                    iufi.CardPool.load_search_metadata()

                results = await loop.run_in_executor(
                    executor,
                    iufi.CardPool.search_image.get_similar_images,
                    await image.read()
                )

                cards: list[iufi.Card] = []
                for result in results.values():
                    result = result.split("\\")[-1]
                    card = iufi.CardPool.get_card(result.split(".")[0])
                    if card:
                        cards.append(card)

                if not cards:
                    return await interaction.followup.send("The card was not found. Please try again.")
                
                if len(cards) > 1:
                    desc = "```"
                    for card in cards:
                        desc += f"{card.display_id} {card.display_tag} {card.display_frame} {card.display_stars} {card.tier[0]}\n"
                    desc += "```"

                    image_bytes, is_gif = iufi.gen_cards_view(cards, 4)
                    image_format = "gif" if is_gif else "png"

                else:
                    desc = f"```{card.display_id}\n" \
                        f"{card.display_tag}\n" \
                        f"{card.display_frame}\n" \
                        f"{card.tier[0]} {card.tier[1].capitalize()}\n" \
                        f"{card.display_stars}```\n" \
                        "**Owned by: **" + (f"<@{card.owner_id}>" if card.owner_id else "None")

                    image_bytes, image_format = card.image_bytes, card.format

                embed = discord.Embed(title=f"ℹ️ Card Info", description=desc, color=0x949fb8)
                embed.set_image(url=f"attachment://image.{image_format}")
                await interaction.followup.send(file=discord.File(image_bytes, filename=f"image.{image_format}"), embed=embed)

        else:
            await interaction.response.send_message("No attachment was found in this message!", ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Developer(bot))