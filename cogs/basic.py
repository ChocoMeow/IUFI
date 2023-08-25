import discord, iufi, time
import functinos as func

from discord.ext import commands
from PIL import Image
from io import BytesIO
from views import RollView

class Basic(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(aliases=["r"])
    async def roll(self, ctx: commands.Context):
        retry = func.check_user_cooldown(ctx.author.id)
        if retry:
            return await ctx.reply(f"You are on cooldown, Please try again in {retry}")
        
        cards = iufi.CardPool.roll()

        # Create a new image for output
        padding = 20
        card_width = cards[0].image.width
        output_image = Image.new('RGBA', (card_width * len(cards) + padding * (len(cards) - 1), cards[0].image.height), (0, 0, 0, 0))

        # # Paste images into the output image with 10 pixels padding
        space = 0
        for card in cards:
            output_image.paste(card.image, (space, 0))
            space += card.image.width + padding

        resized_image_bytes = BytesIO()
        output_image.save(resized_image_bytes, format='PNG')
        resized_image_bytes.seek(0)

        view = RollView(ctx.author, cards)
        message = await ctx.send(file=discord.File(resized_image_bytes, filename='resized_image.png'), view=view)
        view.message = message
        func.update_user(ctx.author.id, {"cooldown.roll": time.time() + func.COOLDOWN_BASE["roll"]}, "set")
        await view.timeout_count()

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Basic(bot))