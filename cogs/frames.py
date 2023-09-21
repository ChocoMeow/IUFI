import discord, iufi
import functions as func

from discord.ext import commands

class Frames(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "🖼️"
        self.invisible = False
        
    @commands.command(aliases=["sf"])
    async def setframe(self, ctx: commands.Context, card_id: str, frame: str):
        """Sets the frame for the photocard. Both card and frame can be identified by id or given tag."""
        user = await func.get_user(ctx.author.id)
        frame = frame.lower()

        if frame not in iufi.FRAMES_BASE:
            return await ctx.reply(content=f"Frame `{frame}` does not exist!")
        
        frame_card = user.get("frames", {}).get(frame, 0)
        if not frame_card:
            return await ctx.reply(content=f"You’ve used up all your `{frame}` frame for now.")
            
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await ctx.reply("The card was not found. Please try again.")

        if card.owner_id != ctx.author.id:
            return await ctx.reply("You are not the owner of this card.")
        
        if card.stars < 5:
            return await ctx.reply("Only cards with 5 stars or above can apply for the frame")
        
        await func.update_user(ctx.author.id, {"$inc": {f"frames.{frame}": -1}})
        await func.update_card(card.id, {"$set": {"frame": frame}})
        card.change_frame(frame)
        embed = discord.Embed(title="🖼️  Set Frame", color=discord.Color.random())
        embed.description = f"```🆔 {card.tier[0]} {card.id}\n🖼️ {frame.title()}```"

        embed.set_image(url=f"attachment://image.{card.format}")
        await ctx.reply(file=discord.File(card.image_bytes, filename=f"image.{card.format}"), embed=embed)

    @commands.command(aliases=["sfl"])
    async def setframelast(self, ctx: commands.Context, card_id: str, frame: str):
        """Sets the frame for the last photocard. Frame can be identified by its id or given tag."""
        frame = frame.lower()
        if frame not in iufi.FRAMES_BASE:
            return await ctx.reply(content=f"Frame `{frame}` does not exist!")
        
        user = await func.get_user(ctx.author.id)
        frame_card = user.get("frames", {}).get(frame, 0)
        if not frame_card:
            return await ctx.reply(content=f"You’ve used up all your `{frame}` frame for now.")
            
        if not user["cards"]:
            return await ctx.reply(f"**{ctx.author.mention} you have no photocards.**", delete_after=5)
        
        card_id = user["cards"][-1]
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await ctx.reply("The card was not found. Please try again.")

        if card.owner_id != ctx.author.id:
            return await ctx.reply("You are not the owner of this card.")
        
        if card.stars < 5:
            return await ctx.reply("Only cards with 5 stars or above can apply for the frame")
        
        await func.update_user(ctx.author.id, {"$inc": {f"frames.{frame}": -1}})
        await func.update_card(card.id, {"$set": {"frame": frame}})
        card.change_frame(frame)
        embed = discord.Embed(title="🖼️  Set Frame", color=discord.Color.random())
        embed.description = f"```🆔 {card.tier[0]} {card.id}\n🖼️ {frame.title()}```"

        embed.set_image(url=f"attachment://image.{card.format}")
        await ctx.reply(file=discord.File(card.image_bytes, filename=f"image.{card.format}"), embed=embed)

    @commands.command(aliases=["rf"])
    async def removeframe(self, ctx: commands.Context, card_id: str):
        """Removes the frame from the photocard. Card can be identified by its ID or given tag."""
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await ctx.reply("The card was not found. Please try again.")

        if card.owner_id != ctx.author.id:
            return await ctx.reply("You are not the owner of this card.")
        
        card.change_frame()
        await func.update_card(card.id, {"$set": {"frame": None}})
        embed = discord.Embed(title="🖼️  Set Frame", color=discord.Color.random())
        embed.description = f"```🆔 {card.tier[0]} {card.id}\n{card.display_frame}```"
        await ctx.reply(embed=embed)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Frames(bot))