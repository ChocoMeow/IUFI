import discord, iufi, asyncio
import functions as func

from discord.ext import commands
from views import FrameView

class Frames(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "🖼️"
        self.invisible = False
        
    @commands.command(aliases=["sf"])
    async def setframe(self, ctx: commands.Context, card_id: str):
        """Sets the frame for the photocard. Both card and frame can be identified by id or given tag.

        **Examples:**
        qsetframe 01
        qsf 01
        """
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await ctx.reply("The card was not found. Please try again.")

        if card.owner_id != ctx.author.id:
            return await ctx.reply("You are not the owner of this card.")
        
        if card.tier[1] in ["mystic"]:
            return await ctx.reply("The card does not support the frame!")
        
        view = FrameView(ctx.author, card)
        embed, file = await view.build()
        view.response = await ctx.reply(file=file, embed=embed, view=view)
        
    @commands.command(aliases=["sfl"])
    async def setframelast(self, ctx: commands.Context):
        """Sets the frame for the last photocard. Frame can be identified by its id or given tag.
        
        **Examples:**
        qsetframelast
        qsfl
        """
        user = await func.get_user(ctx.author.id)  
        if not user["cards"]:
            return await ctx.reply(f"**{ctx.author.mention} you have no photocards.**", delete_after=5)
        
        card_id = user["cards"][-1]
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await ctx.reply("The card was not found. Please try again.")

        if card.owner_id != ctx.author.id:
            return await ctx.reply("You are not the owner of this card.")
        
        if card.tier[1] in ["mystic"]:
            return await ctx.reply("The card does not support the frame!")
        
        view = FrameView(ctx.author, card)
        embed, file = await view.build()
        view.response = await ctx.reply(file=file, embed=embed, view=view)

    @commands.command(aliases=["rf"])
    async def removeframe(self, ctx: commands.Context, card_id: str):
        """Removes the frame from the photocard. Card can be identified by its ID or given tag.
        
        **Examples:**
        qremoveframe 01
        qrf 01
        """
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await ctx.reply("The card was not found. Please try again.")

        if card.owner_id != ctx.author.id:
            return await ctx.reply("You are not the owner of this card.")
        
        card.change_frame()
        await func.update_card(card.id, {"$set": {"frame": None}})

        func.logger.info(f"User {ctx.author.name}({ctx.author.id}) removed frame from card [{card.id}].")

        embed = discord.Embed(title="🖼️  Set Frame", color=discord.Color.random())
        embed.description = f"```🆔 {card.tier[0]} {card.id}\n{card.display_frame}```"
        await ctx.reply(embed=embed)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Frames(bot))