import asyncio

import discord
import functions as func
import time
import random
from discord.ext import commands
import iufi
from discord.ext import commands, tasks

from views import AnniversarySellView


class DebutAnniversary(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.debut_anniversary.start()

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

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DebutAnniversary(bot))
