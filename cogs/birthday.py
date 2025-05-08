import discord, time
import functions as func
from discord.ext import commands
from datetime import datetime, timedelta
from iufi.events import (
    is_birthday_event_active,
    is_birthday_buff_active,
    get_birthday_event_end,
    get_current_birthday_card_day,
    is_event_shop_active,
    KST,
    actual_birthday
)
from iufi.birthday import BirthdayCard

# Define shop items once, to be used by multiple classes
BIRTHDAY_SHOP_ITEMS = [
    {"name": "Inventory +1", "emoji": "🎒", "id": "inventory", "cost": 8, "description": "Permanent +1 card inventory"},
    {"name": "Mystic Roll", "emoji": "🦄", "id": "mystic", "cost": 30, "description": "1 Mystic roll 🦄"},
    {"name": "Celestial Roll", "emoji": "💫", "id": "celestial", "cost": 32, "description": "1 Celestial roll 💫"}
]

class BirthdayShopConfirm(discord.ui.View):
    def __init__(self, author: discord.Member):
        super().__init__(timeout=60)
        self.author = author
        self.value = None
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author.id
        
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.value = True
        self.stop()
        
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.value = False
        self.stop()

class BirthdayShopDropdown(discord.ui.Select):
    def __init__(self) -> None:
        # Use the global shop items definition
        self.shop_items = BIRTHDAY_SHOP_ITEMS
        
        # Create options from shop items (simpler format like normal shop)
        options = [
            discord.SelectOption(
                label=f"{item['name']}",
                emoji=item['emoji'],
                value=item['id']
            ) for item in self.shop_items
        ]
        
        super().__init__(
            placeholder="Select an item to purchase...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        # Fetch selected item details
        selected_id = self.values[0]
        selected_item = next((item for item in self.shop_items if item["id"] == selected_id), None)
        
        if not selected_item:
            return await interaction.response.send_message("Item not found.", ephemeral=True)
        
        # Get user data
        user = await func.get_user(interaction.user.id)
        birthday_cards = user.get("birthday_cards_count", 0)
        
        # Check if user has enough cards
        if birthday_cards < selected_item["cost"]:
            return await interaction.response.send_message(
                f"You don't have enough birthday cards! You need {selected_item['cost']} but only have {birthday_cards}.",
                ephemeral=True
            )
        
        # Show confirmation dialog
        embed = discord.Embed(
            title="Confirm Purchase",
            description=f"Are you sure you want to buy **{selected_item['name']}** for **{selected_item['cost']} birthday cards**?",
            color=discord.Color.brand_red()
        )
        
        view = BirthdayShopConfirm(interaction.user)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        # Wait for confirmation
        await view.wait()
        if view.value:
            # Process purchase based on item
            query = {"$inc": {"birthday_cards_count": -selected_item["cost"]}}
            
            if selected_id == "inventory":
                # Increase inventory by 5 slots
                new_max = await func.increase_max_cards(interaction.user.id, 5)
                success_msg = f"🎒 {interaction.user.mention} successfully increased their inventory capacity to {new_max} slots (+5)!"
                
            elif selected_id == "mystic":
                # Add mystic roll token
                query["$inc"]["roll.mystic"] = 1
                success_msg = f"🦄 {interaction.user.mention} successfully purchased **1 Mystic Roll**!"

            elif selected_id == "celestial":
                # Add celestial roll token
                query["$inc"]["roll.celestial"] = 1
                success_msg = f"💫 {interaction.user.mention} successfully purchased **1 Celestial Roll**!"
            
            await func.update_user(interaction.user.id, query)

            #delete confirmation message
            await interaction.delete_original_response()

            # Log the transaction
            func.logger.info(f"User {interaction.user.name}({interaction.user.id}) purchased {selected_id} for {selected_item['cost']} birthday cards")
            
            # Send success message
            success_embed = discord.Embed(
                title="🎂 Purchase Successful!",
                description=success_msg,
                color=discord.Color.green()
            )
            await interaction.message.reply(embed=success_embed)
        else:
            # Purchase canceled
            await interaction.delete_original_response()
            await interaction.followup.send("Purchase canceled.", ephemeral=True)

class BirthdayShopView(discord.ui.View):
    def __init__(self, author: discord.Member):
        super().__init__(timeout=60)
        self.author = author
        self.add_item(BirthdayShopDropdown())
        self.message = None
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author.id
    
    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message:
            await self.message.edit(view=self)
    
    async def build_embed(self) -> discord.Embed:
        user = await func.get_user(self.author.id)
        birthday_cards = user.get("birthday_cards_count", 0)
        
        # Use the global shop items definition
        shop_items = BIRTHDAY_SHOP_ITEMS

        embed = discord.Embed(title="🎂 Birthday Event Shop", color=discord.Color.brand_red())
        embed.description = f"🎂 Birthday Cards: `{birthday_cards}`\n```"
        
        # Format items in the same style as normal shop
        for item in shop_items:
            # Display item name in uppercase for the shop display
            embed.description += f"{item['emoji']} {item['name'].upper():<20} {item['cost']:>3} 🎂\n"
            
        embed.description += "```"
        embed.set_thumbnail(url=self.author.display_avatar.url)
        
        return embed

class Birthday(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "🎂"
        self.invisible = not is_birthday_event_active()
    
    @commands.command(aliases=["bday", "bd"])
    async def birthday(self, ctx: commands.Context):
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
            active_buffs.append("• 50% discount on all frames")
            
        if is_birthday_buff_active("shop_discount"):
            active_buffs.append("• 25% discount on shop items")
        
        if is_birthday_buff_active("inventory_increase"):
            active_buffs.append("• +10 inventory slots")
        
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

        from iufi.events import get_current_birthday_card_day,is_birthday_event_active

        if not is_birthday_event_active():
            embed.description = (
                f"**Birthday Event is currently INACTIVE**\n\n"
                f"The birthday event runs during IU's birthday month.\n"
                f"Check back during May for special birthday cards and bonuses!"
            )
            return await ctx.reply(embed=embed)
        
        # Create a visual representation of collected cards
        collection_display = ""
        current_day_number = get_current_birthday_card_day()
        for day in range(1, 33):  # Days 1-31
            if day > 0:
                day_str = str(day)
                if day_str in collection:
                    collection_display += f"✅ {day:02d} "
                else:
                    if day < current_day_number:
                        collection_display += f"❌ {day:02d} "
                    else:
                        collection_display += f"❔ {day:02d} "
                
                
                # Add line breaks for readability
                if day % 5 == 0:
                    collection_display += "\n"
                
        embed.description = (
            f"\n**Collected:** {len(collection)}/32 cards\n"
            f"**Cards in your inventory:** {total_cards}\n\n"
            f"```{collection_display}```\n"
            f"*Collect all 32 cards during IU's birthday month!*"
        )
        
        if is_birthday_event_active():
            from iufi.events import get_birthday_event_end
            embed.set_footer(text=f"Birthday event ends on {get_birthday_event_end().strftime('%B %d, %Y')}")
        else:
            embed.set_footer(text="The birthday event is not currently active.")
            
        await ctx.reply(embed=embed)

    @commands.command(aliases=["es", "bs"])
    async def eventshop(self, ctx: commands.Context):
        """IU Birthday Event shop where you can spend birthday cards.
        
        **Examples:**
        @prefix@eventshop
        @prefix@es
        @prefix@bs
        """
        # Check if the birthday event is active
        if not is_birthday_event_active():
            embed = discord.Embed(
                title="🎂 Birthday Event Shop",
                description="The birthday event shop is currently closed.\nPlease come back during IU's birthday month!",
                color=discord.Color.brand_red()
            )
            return await ctx.reply(embed=embed)
        
        # check if event shop is active
        if not is_event_shop_active():
            embed = discord.Embed(
                title="🎂 Birthday Event Shop",
                description="The birthday event shop will be unlocked from IU's birthday.\nPlease come back on May 16th!",
                color=discord.Color.brand_red()
            )
            return await ctx.reply(embed=embed)

        # Create shop view with the new style
        view = BirthdayShopView(ctx.author)
        embed = await view.build_embed()
        
        # Send shop view
        message = await ctx.reply(embed=embed, view=view)
        view.message = message

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Birthday(bot))
