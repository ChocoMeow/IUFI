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
    
    @commands.command(aliases=["binfo"])
    async def birthdayinfo(self, ctx: commands.Context):
        """Shows information about the current birthday event.
        
        **Examples:**
        @prefix@birthdayinfo
        @prefix@binfo
        """
        embed = discord.Embed(
            title="🎂 IU Birthday Event Information",
            color=discord.Color.brand_red()
        )
        
        if is_birthday_event_active():
            event_end = get_birthday_event_end()
            current_time = datetime.now(KST)
            time_remaining = event_end - current_time
            days_remaining = time_remaining.days
            
            embed.description = (
                f"**Birthday Event is ACTIVE!** 🎉\n\n"
                f"• Event ends <t:{int(event_end.timestamp())}:R>\n"
                f"• Today's card: #{get_current_birthday_card_day()}\n"
                f"• Birthday buff: {'ACTIVE ✨' if is_birthday_buff_active() else 'Not active'}\n\n"
                f"**Event Benefits:**\n"
                f"• Chance to get special birthday cards when rolling\n"
                f"• 2x candies on conversions during buff\n"
                f"• Complete your collection of 31 birthday cards!\n"
            )
            
            # Show actual birthday highlight if near or on the day
            birthday_date = actual_birthday.date()
            current_date = current_time.date()
            delta_days = (birthday_date - current_date).days
            
            if delta_days >= 0 and delta_days <= 3:
                embed.add_field(
                    name="🌟 IU's Birthday",
                    value=f"IU's birthday is {'today!' if delta_days == 0 else f'in {delta_days} days!'}\n<t:{int(actual_birthday.timestamp())}:F>"
                )
        else:
            embed.description = (
                f"**Birthday Event is currently INACTIVE**\n\n"
                f"The birthday event runs during IU's birthday month.\n"
                f"Check back during May for special birthday cards and bonuses!"
            )
        
        await ctx.reply(embed=embed)
    
    @commands.command(aliases=["bcard", "todaycard"])
    async def birthdaycard(self, ctx: commands.Context):
        """Shows information about today's birthday card.
        
        **Examples:**
        @prefix@birthdaycard
        @prefix@bcard
        @prefix@todaycard
        """
        if not is_birthday_event_active():
            return await ctx.reply("The birthday event is not currently active. Check back during IU's birthday month!")
            
        day = get_current_birthday_card_day()
        if not day:
            return await ctx.reply("No birthday card is available today.")
        
        card = BirthdayCard(day)
        
        embed = discord.Embed(
            title=f"🎂 Birthday Card #{day}",
            color=discord.Color.brand_red()
        )
        embed.description = (
            f"Today's special birthday card is **#{day}**\n\n"
            f"• Roll today for a chance to get this card!\n"
            f"• Each day during the event features a different card\n"
            f"• Collect all 31 cards for special rewards\n"
        )
        
        # Get user's collection status
        user = await func.get_user(ctx.author.id)
        collection = user.get("birthday_collection", {})
        has_card = str(day) in collection
        
        embed.add_field(
            name="Your Status",
            value=f"You have {'already collected ✅' if has_card else 'not yet collected ❌'} today's card."
        )
        
        # If possible, attach the card image
        try:
            file = discord.File(await card.image_bytes(True), filename=f"bcard_{day}.{card.format}")
            embed.set_image(url=f"attachment://bcard_{day}.{card.format}")
            await ctx.reply(embed=embed, file=file)
        except Exception as e:
            func.logger.error(f"Error displaying birthday card image: {e}")
            await ctx.reply(embed=embed)
    
    @commands.command(aliases=["btime", "bevent"])
    async def birthdaytime(self, ctx: commands.Context):
        """Shows the time remaining for the birthday event.
        
        **Examples:**
        @prefix@birthdaytime
        @prefix@btime
        @prefix@bevent
        """
        embed = discord.Embed(
            title="🎂 Birthday Event Timer",
            color=discord.Color.brand_red()
        )
        
        if is_birthday_event_active():
            event_end = get_birthday_event_end()
            current_time = datetime.now(KST)
            time_remaining = event_end - current_time
            days = time_remaining.days
            hours, remainder = divmod(time_remaining.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            embed.description = (
                f"**Birthday Event is ACTIVE!**\n\n"
                f"⏱️ **Time Remaining:**\n"
                f"• {days} days, {hours} hours, {minutes} minutes\n"
                f"• Event ends <t:{int(event_end.timestamp())}:F>\n\n"
                f"Don't miss out on collecting all the birthday cards before the event ends!"
            )
            
            # Add progress bar
            total_duration = (get_birthday_event_end() - datetime(2025, 4, 1, tzinfo=KST)).total_seconds()
            elapsed_duration = (current_time - datetime(2025, 4, 1, tzinfo=KST)).total_seconds()
            progress = min(1.0, elapsed_duration / total_duration)
            
            progress_bar = "["
            bar_length = 20
            filled_length = int(bar_length * progress)
            progress_bar += "█" * filled_length + "▒" * (bar_length - filled_length) + "]"
            percentage = int(progress * 100)
            
            embed.add_field(
                name="Event Progress", 
                value=f"`{progress_bar}` {percentage}%", 
                inline=False
            )
        else:
            embed.description = (
                f"**Birthday Event is currently INACTIVE**\n\n"
                f"The birthday event runs during IU's birthday month.\n"
                f"Check back during May for special birthday cards and bonuses!"
            )
        
        await ctx.reply(embed=embed)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Birthday(bot))
