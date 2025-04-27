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
        @prefix@birthdayinfo
        @prefix@bday
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
        
        # Build the description - make it cleaner and more visually appealing
        embed.description = (
            f"**Birthday Event is ACTIVE!** 🎉\n\n"
            f"⏱️ **Event ends <t:{int(event_end.timestamp())}:R>**\n"
            f"• {days}d {hours}h {minutes}m remaining\n"
        )
        
        # Add active buffs section - improved formatting
        active_buffs = []
        
        if is_birthday_buff_active("2x_candy"):
            active_buffs.append("• 2x candies on card conversions")
                
        if is_birthday_buff_active("2x_quiz_points"):
            active_buffs.append("• 2x points in quiz games")
                
        if is_birthday_buff_active("2x_music_points"):
            active_buffs.append("• 2x points in music quiz")
                
        if is_birthday_buff_active("extra_moves_match_game"):
            active_buffs.append("• +2 extra moves in match games")
        
        if is_birthday_buff_active("frame_discount"):
            active_buffs.append("• 20% discount on all frames")
            
        if is_birthday_buff_active("shop_discount"):
            active_buffs.append("• 15% discount on shop items")
        
        # Add active buffs directly to description instead of field
        embed.description += f"\n✨ **Today's Active Buffs**\n"
        if active_buffs:
            embed.description += "\n".join(active_buffs)
        else:
            embed.description += "No special buffs are active today."
        
        # Add card information - improved formatting
        if day:
            embed.description += f"\n**Today's Card: #{day}**\n"
            embed.description += f"You have {'already collected ✅' if has_card else 'not yet collected ❌'} this card.\n"
            
            # Try to display the card image
            try:
                file = discord.File(await card.image_bytes(False), filename=f"bcard_{day}.{card.format}")
                embed.set_image(url=f"attachment://bcard_{day}.{card.format}")
                attachment = file
            except Exception as e:
                func.logger.error(f"Error displaying birthday card image: {e}")
                attachment = None
        else:
            embed.description += f"\n**Today's Card**\n"
            embed.description += "No birthday card is available today.\n"
            attachment = None
        
        # Send the response
        if attachment:
            await ctx.reply(embed=embed, file=attachment)
        else:
            await ctx.reply(embed=embed)

    @commands.command(aliases=["bc"])
    async def birthdaycards(self, ctx: commands.Context, member: discord.Member = None):
        """Shows birthday card collection.

        **Examples:**
        @prefix@birthdaycards
        @prefix@bc @user
        """
        target = member or ctx.author
        user = await func.get_user(target.id)
        
        collection = user.get("birthday_collection", {})
        total_cards = user.get("birthday_cards_count", 0)
        
        embed = discord.Embed(
            title=f"🎂 {target.display_name}'s Birthday Collection", 
            color=discord.Color.brand_red()
        )
        
        # Create a visual representation of collected cards
        collection_display = ""
        for day in range(1, 32):  # Days 1-31
            if day > 0:
                day_str = str(day)
                if day_str in collection:
                    collection_display += f"✅ {day:02d} "
                else:
                    collection_display += f"❌ {day:02d} "
                
                # Add line breaks for readability
                if day % 5 == 0:
                    collection_display += "\n"
                
        embed.description = (
            f"**Collected:** {total_cards}/31 cards\n\n"
            f"```{collection_display}```\n"
            f"*Collect all 31 cards during IU's birthday month!*"
        )
        
        if is_birthday_event_active():
            from iufi.events import get_current_birthday_card_day
            today = get_current_birthday_card_day()
            embed.add_field(
                name="Today's Card", 
                value=f"Card #{today} is available today!"
            )
            from iufi.events import get_birthday_event_end
            embed.set_footer(text=f"Birthday event ends on {get_birthday_event_end().strftime('%B %d, %Y')}")
        else:
            embed.set_footer(text="The birthday event is not currently active.")
            
        await ctx.reply(embed=embed)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Birthday(bot))
