import discord, time
import functions as func
from discord.ext import commands
from datetime import datetime, timedelta
from iufi.events import (
    is_birthday_event_active,
    is_birthday_buff_active,
    get_birthday_event_end,
    get_current_birthday_card_day,
    KST,
    actual_birthday
)
from iufi.birthday import BirthdayCard

class Birthday(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "🎂"
        self.invisible = False
    
    @commands.command(aliases=["bday", "bd"])
    async def birthdayinfo(self, ctx: commands.Context):
        """Shows quick overview of birthday event with card, buffs, and time information.
        
        **Examples:**
        @prefix@qbirthdayinfo
        @prefix@qbday
        """
        
        # Create embed
        embed = discord.Embed(
            title="🎂 IU Birthday Event Overview",
            color=discord.Color.brand_red()
        )
        
        if not is_birthday_event_active():
            embed.description = (
                f"**Birthday Event is currently INACTIVE**\n\n"
                f"The birthday event runs during IU's birthday month.\n"
                f"Check back during May for special birthday cards and bonuses!"
            )
            return await ctx.reply(embed=embed)
        
        # Get the current time and event end time
        event_end = get_birthday_event_end()
        current_time = datetime.now(KST)
        
        # Get today's card info
        day = get_current_birthday_card_day()
        card = BirthdayCard(day) if day else None
        
        # Get user's collection status
        user = await func.get_user(ctx.author.id)
        collection = user.get("birthday_collection", {})
        has_card = str(day) in collection if day else False
        
        # Calculate time remaining
        time_remaining = event_end - current_time
        days = time_remaining.days
        hours, remainder = divmod(time_remaining.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        # Build the description
        embed.description = (
            f"**Birthday Event is ACTIVE!** 🎉\n\n"
            f"⏱️ **Event ends <t:{int(event_end.timestamp())}:R>**\n"
            f"• {days}d {hours}h {minutes}m remaining\n\n"
        )
        
        # Add card information
        attachment = None
        if day:
            embed.add_field(
                name=f"Today's Card: #{day}",
                value=f"You have {'already collected ✅' if has_card else 'not yet collected ❌'} this card.",
                inline=False
            )
            
            # Try to display the card image
            try:
                file = discord.File(await card.image_bytes(False), filename=f"bcard_{day}.{card.format}")
                embed.set_image(url=f"attachment://bcard_{day}.{card.format}")
                attachment = file
            except Exception as e:
                func.logger.error(f"Error displaying birthday card image: {e}")
                attachment = None
        else:
            embed.add_field(
                name="Today's Card",
                value="No birthday card is available today.",
                inline=False
            )
        
        # Add active buffs section
        active_buffs = []
        
        if is_birthday_buff_active("2x_candy"):
            active_buffs.append("• 2x candies on card conversions")
                
        if is_birthday_buff_active("2x_quiz_points"):
            active_buffs.append("• 2x points in quiz games")
                
        if is_birthday_buff_active("2x_music_points"):
            active_buffs.append("• 2x points in music quiz")
                
        if is_birthday_buff_active("extra_moves_match_game"):
            active_buffs.append("• +2 extra moves in match games")
        
        # Add active buffs section if any are active
        if active_buffs:
            embed.add_field(
                name="✨ Today's Active Buffs",
                value="\n".join(active_buffs),
                inline=False
            )
        else:
            embed.add_field(
                name="✨ Today's Active Buffs",
                value="No special buffs are active today.",
                inline=False
            )
        
        # Send the response
        if attachment:
            await ctx.reply(embed=embed, file=attachment)
        else:
            await ctx.reply(embed=embed)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Birthday(bot))
