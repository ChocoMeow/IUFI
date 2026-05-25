import iufi
import psutil
import asyncio
import discord
import functions as func

from discord.ext import commands
from views import DebugView, ConfirmView

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
    
    async def cog_check(self, ctx: commands.Context) -> bool:
        if ctx.author.id not in  func.settings.ADMIN_IDS:
            raise commands.CheckFailure("You do not have permission to use this command.")
        return True
    
    @commands.command(name="dev_givecandies")
    async def givecandies(self, ctx: commands.Context, member: discord.Member, amount: int):
        """
        Gives a specified number of candies to a user.

        The `amount` must be a positive integer.  
        Candies are added directly to the user's inventory.  
        If no user is specified, the candies will be given to the command caller.

        **Examples:**
        @prefix@givecandies @username 5
        """
        user_data = await func.get_user(member.id)
        if not user_data:
            return await ctx.reply("User not found.")
        await func.update_user(member.id, {"$inc": {"candies": amount}})
        await ctx.reply(f"{amount} candies have been given to {member.display_name}.")

    @commands.command(name="dev_removecandies")
    async def removecandies(self, ctx: commands.Context, member: discord.Member, amount: int):
        """
        Removes a specified number of candies from a user's inventory.

        The `amount` must be a positive integer.  
        If the user does not have enough candies, the command will fail gracefully.

        **Examples:**
        @prefix@removecandies @username 5
        @prefix@removecandies @username 10
        """
        user_data = await func.get_user(member.id)
        if not user_data:
            return await ctx.reply("User not found.")
        await func.update_user(member.id, {"$inc": {"candies": -amount}})
        await ctx.reply(f"{amount} candies have been removed from {member.display_name}.")

    @commands.command(name="dev_resetCooldown")
    async def resetCooldown(self, ctx: commands.Context, member: discord.Member, cooldown: str):
        """
        Resets a specific cooldown for a user.

        Supported cooldown types include: `roll`, `quiz`, and `mg`.  
        Once reset, the user can immediately perform the associated action again without waiting for the cooldown period.

        **Examples:**
        @prefix@resetCooldown @username roll
        @prefix@resetCooldown @username quiz
        """
        cd_types = {"roll": "roll", "quiz": "quiz_game", "mg": "match_game"}

        if not (cooldown := cd_types.get(cooldown)):
            return await ctx.reply(f"Cooldown not found. Available cooldown type: {', '.join(cd_types.keys())}")

        user_data = await func.get_user(member.id)
        if not user_data:
            return await ctx.reply("User not found.")

        await func.update_user(member.id, {"$set": {f"cooldown.{cooldown}": 0}})
        await ctx.reply(f"{cooldown} cooldown has been reset for {member.display_name}.")

    @commands.command(name="dev_resetCardTradeCooldown")
    async def resetCardTradeCooldown(self, ctx: commands.Context, card_id: str):
        """
        Resets the trade cooldown for a specific card.

        The `card_id` must match the identifier of the card whose cooldown is being cleared.  
        Once reset, the card can be traded again immediately without waiting for the cooldown period.

        **Examples:**
        @prefix@resetCardTradeCooldown 1234
        """
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await ctx.reply("Card not found.")

        await func.update_card(card_id, {"$set": {"last_trade_time": 0}})
        await ctx.reply(f"Cooldown has been reset for card {card_id}.")

    @commands.command(name="dev_giveCardToUser")
    async def giveCardToUser(self, ctx: commands.Context, member: discord.Member, card_id: str):
        """
        Gives a specific card to a user.

        The `card_id` must match the identifier of the card being awarded.  
        If no user is specified, the card will be given to the command caller.

        **Examples:**
        @prefix@giveCardToUser @username 1234
        """
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await ctx.reply("Card not found.")

        if card.owner_id:
            return await ctx.reply("Card already owned by someone.")

        user_data = await func.get_user(member.id)

        if not user_data:
            return await ctx.reply("User not found.")

        if len(user_data["cards"]) >= func.settings.MAX_CARDS:
            return await ctx.reply(f"{member.display_name} already has maximum cards.")

        card.change_owner(member.id)
        iufi.CardPool.remove_available_card(card)
        await func.update_card(card_id, {"$set": {"owner_id": member.id}})
        await func.update_user(member.id, {"$push": {"cards": card_id}})

        await ctx.reply(f"Card {card_id} has been given to {member.display_name}.")

    @commands.command(name="dev_removeCardFromUser")
    async def removeCardFromUser(self, ctx: commands.Context, card_id: str):
        """
        Removes a specific card from a user's collection.

        The `card_id` must match the identifier of the card to be removed.  
        If the card does not exist or is invalid, the command will fail gracefully.

        **Examples:**
        @prefix@removeCardFromUser 1234
        """
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await ctx.reply("Card not found.")

        if not card.owner_id:
            return await ctx.reply("Card is not owned by anyone.")

        card.change_owner(None)
        iufi.CardPool.add_available_card(card)
        await func.update_card(card_id, {"$set": {"owner_id": None, "tag": None, "frame": None, "last_trade_time": 0}})
        await func.update_user(card.owner_id, {"$pull": {"cards": card.id}})

        await ctx.reply(f"Card {card_id} has been removed from user.")

    @commands.command(name="dev_giveRollToUser")
    async def giveRollToUser(self, ctx: commands.Context, member: discord.Member, roll_type: str, amount: int = 1):
        """
        Grants a specified number of rolls of a given type to a user.

        If no amount is provided, the default is 1 roll.  
        The `roll_type` determines the category or kind of roll being awarded.

        **Examples:**
        @prefix@giveRollToUser @username rare 3
        @prefix@giveRollToUser @username epic
        """
        roll_types = ["rare", "epic", "legendary", "mystic", "celestial"]

        if roll_type not in roll_types:
            return await ctx.reply("Roll type not found. Available roll types: " + ", ".join(roll_types))

        user_data = await func.get_user(member.id)
        if not user_data:
            return await ctx.reply("User not found.")

        await func.update_user(member.id, {"$inc": {f"roll.{roll_type}": amount}})
        await ctx.reply(f"{amount} {roll_type} rolls have been given to {member.display_name}.")

    @commands.command(name="dev_giveBirthdayCard")
    async def giveBirthdayCard(self, ctx: commands.Context, member: discord.Member, day_number: int):
        """
        Gives a birthday card to a specified user for a particular day.

        If no user is specified, the card will be given to the command caller.
        The `day_number` represents the day of the month associated with the birthday card.

        **Examples:**
        @prefix@giveBirthdayCard @username 15
        @prefix@giveBirthdayCard 20
        """
        if day_number < 1 or day_number > 31:
            return await ctx.reply("Invalid day number. Must be between 1 and 31.")

        user_data = await func.get_user(member.id)
        if not user_data:
            return await ctx.reply("User not found.")

        # Convert day number to string for storage in the collection
        day_str = str(day_number)

        # Check if user already has this card
        birthday_collection = user_data.get("birthday_collection", {})
        if day_str in birthday_collection:
            return await ctx.reply(f"{member.display_name} already has birthday card #{day_number}.")

        # Add card to user's collection
        update_query = {
            "$set": {f"birthday_collection.{day_str}": True},
            "$inc": {"birthday_cards_count": 1, "exp": 20}
        }

        await func.update_user(member.id, update_query)
        await ctx.reply(f"Birthday card #{day_number} has been given to {member.display_name}.")

    @commands.command(name="dev_setBirthdayCardsCount")
    async def setBirthdayCardsCount(self, ctx: commands.Context, member: discord.Member, count: int):
        """Set the birthday cards count for a user."""
        user_data = await func.get_user(member.id)
        if not user_data:
            return await ctx.reply("User not found.")

        # Set the birthday cards count
        await func.update_user(member.id, {"$set": {"birthday_cards_count": count}})
        await ctx.reply(f"Birthday cards count for {member.display_name} has been set to {count}.")

    @commands.command(name="dev_quit")
    async def quit(self, ctx: commands.Context, member: discord.Member = None):
        """[ADMIN ONLY] Deletes a user's profile after confirmation. All cards will be converted.

        If no member is specified, it will delete the profile of the user who called the command.

        **Examples:**
        @prefix@quit @username
        @prefix@quit
        """
        target_user = member or ctx.author
        user = await func.get_user(target_user.id)

        # Create confirmation embed
        embed = discord.Embed(title="⚠️ Delete Account", color=discord.Color.red())
        embed.description = f"**WARNING: This action cannot be undone!**\n\nThis will:\n- Conver all {target_user.display_name}'s cards \n- Delete their entire profile and progress\n- Remove all inventory items and collections\n\nAre you sure you want to continue?"

        # Create confirmation view
        view = ConfirmView(ctx.author)
        view.message = await ctx.reply(embed=embed, view=view)
        await view.wait()

        if not view.is_confirm:
            embed.title = "❌ Account Deletion Cancelled"
            embed.description = f"{target_user.display_name}'s account has not been deleted."
            embed.color = discord.Color.green()
            await view.message.edit(embed=embed, view=None)
            return

        # Convert all cards to candies (for logging purposes only)
        converted_cards = []
        for card_id in user["cards"]:
            card = iufi.CardPool.get_card(card_id)
            if card:
                converted_cards.append(card)

        card_ids = [card.id for card in converted_cards]
        for card in converted_cards:
            iufi.CardPool.add_available_card(card)

        # Log the action
        func.logger.info(
            f"Admin {ctx.author.name}({ctx.author.id}) deleted the profile of {target_user.name}({target_user.id}). "
            f"Returned {len(converted_cards)} card(s) to the available pool."
        )

        # Update the cards in the database to remove owner, tag, etc.
        if card_ids:
            await func.update_card(card_ids, {"$set": {"owner_id": None, "tag": None, "frame": None, "last_trade_time": 0}})

        # Delete the user from the database
        await func.USERS_DB.delete_one({"_id": target_user.id})

        # Remove user from buffer cache if they exist there
        if target_user.id in func.USERS_BUFFER:
            del func.USERS_BUFFER[target_user.id]

        # Update the confirmation message
        embed.title = "✅ Account Deleted"
        embed.description = f"{target_user.display_name}'s Account has been deleted. All their cards ({len(converted_cards)}) have been returned to the available pool."
        embed.color = discord.Color.green()
        await view.message.edit(embed=embed, view=None)
        
    @commands.command(hidden=True)
    @commands.is_owner()
    async def debug(self, ctx: commands.Context):
        """
        Executes developer-only debugging actions.

        This command is restricted to developers and is used for testing, diagnostics, 
        or troubleshooting within the bot environment. It should not be accessible to 
        regular users.

        **Examples:**
        @prefix@debug
        """
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

    async def _findsimilar(self, interaction: discord.Interaction, message: discord.Message):
        """Find similar image from the card pool."""
        if interaction.guild_id not in [1144810748158165042]:
            return await interaction.response.send_message("You are not able to use this command on this server!", ephemeral=True)
        
        if message.attachments:
            image = message.attachments[0]
            await interaction.response.defer()


            if not iufi.CardPool.search_image:
                await asyncio.to_thread(iufi.CardPool.load_search_metadata)

            results = await asyncio.to_thread(iufi.CardPool.search_image.get_similar_images, await image.read())

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
                
                image_bytes, image_format = await iufi.gen_cards_view(cards, 4)
            else:
                desc = f"```{card.display_id}\n" \
                    f"{card.display_tag}\n" \
                    f"{card.display_frame}\n" \
                    f"{card.tier[0]} {card.tier[1].capitalize()}\n" \
                    f"{card.display_stars}```\n" \
                    "**Owned by: **" + (f"<@{card.owner_id}>" if card.owner_id else "None")

                image_bytes, image_format = await card.image_bytes(), card.format

            embed = discord.Embed(title=f"ℹ️ Card Info", description=desc, color=0x949fb8)
            embed.set_image(url=f"attachment://image.{image_format}")
            await interaction.followup.send(file=discord.File(image_bytes, filename=f"image.{image_format}"), embed=embed)

        else:
            await interaction.response.send_message("No attachment was found in this message!", ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Developer(bot))