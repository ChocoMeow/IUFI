import discord
from discord.ext import commands
import functions as func
import iufi
from iufi import CardPool
from views import ConfirmView

import os
import datetime
import asyncio

def is_admin_account(user_id) -> bool:
    if user_id in func.settings.ADMIN_IDS:
        return True
    return False


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.emoji = "🔧"
        self.invisible = True

    @commands.command()
    async def givecandies(self, ctx: commands.Context, user: discord.Member, amount: int):
        """Give candies to a user."""
        if not is_admin_account(ctx.author.id):
            return

        user_data = await func.get_user(user.id)
        if not user_data:
            return await ctx.reply("User not found.")
        await func.update_user(user.id, {"$inc": {"candies": amount}})
        await ctx.reply(f"{amount} candies have been given to {user.display_name}.")

    @commands.command()
    async def removecandies(self, ctx: commands.Context, user: discord.Member, amount: int):
        """Remove candies from a user."""
        if not is_admin_account(ctx.author.id):
            return

        user_data = await func.get_user(user.id)
        if not user_data:
            return await ctx.reply("User not found.")
        await func.update_user(user.id, {"$inc": {"candies": -amount}})
        await ctx.reply(f"{amount} candies have been removed from {user.display_name}.")

    @commands.command()
    async def resetCooldown(self, ctx: commands.Context, user: discord.Member, cooldown: str):
        """Reset cooldown of a user. Cooldowns: roll, quiz, mg"""
        if not is_admin_account(ctx.author.id):
            return
        cooldowns = {"roll": "roll", "quiz": "quiz_game", "mg": "match_game"}

        if cooldown not in cooldowns:
            return await ctx.reply("Cooldown not found.")

        cooldown = cooldowns[cooldown]

        user_data = await func.get_user(user.id)
        if not user_data:
            return await ctx.reply("User not found.")

        await func.update_user(user.id, {"$set": {f"cooldown.{cooldown}": 0}})
        await ctx.reply(f"{cooldown} cooldown has been reset for {user.display_name}.")

    @commands.command(aliases=["resetcontract", "reset_contract"])
    async def resetEventContract(self, ctx: commands.Context, user: discord.Member):
        """Clear a user's Royal Contract team so they can pick again (`contract`)."""
        if not is_admin_account(ctx.author.id):
            return

        user_data = await func.get_user(user.id)
        if not user_data:
            return await ctx.reply("User not found.")

        if not user_data.get("event_team"):
            return await ctx.reply(f"{user.display_name} has no active Royal Contract to reset.")

        await func.update_user(user.id, {"$unset": {"event_team": ""}})
        await ctx.reply(
            f"Royal Contract cleared for {user.mention}. They can register again with `contract`."
        )

    @commands.command()
    async def resetCardTradeCooldown(self, ctx: commands.Context, card_id: str):
        """Remove cooldown of a card."""
        if not is_admin_account(ctx.author.id):
            return

        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await ctx.reply("Card not found.")

        await func.update_card(card_id, {"$set": {"last_trade_time": 0}})
        await ctx.reply(f"Cooldown has been reset for card {card_id}.")

    @commands.command()
    async def giveCardToUser(self, ctx: commands.Context, user: discord.Member, card_id: str):
        """Give a card to a user."""
        if not is_admin_account(ctx.author.id):
            return

        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await ctx.reply("Card not found.")

        if card.owner_id:
            return await ctx.reply("Card already owned by someone.")

        user_data = await func.get_user(user.id)

        if not user_data:
            return await ctx.reply("User not found.")

        if len(user_data["cards"]) >= func.settings.MAX_CARDS:
            return await ctx.reply(f"{user.display_name} already has maximum cards.")

        card.change_owner(user.id)
        CardPool.remove_available_card(card)
        await func.update_card(card_id, {"$set": {"owner_id": user.id}})
        await func.update_user(user.id, {"$push": {"cards": card_id}})

        await ctx.reply(f"Card {card_id} has been given to {user.display_name}.")

    @commands.command()
    async def removeCardFromUser(self, ctx: commands.Context, card_id: str):
        """Remove a card from a user."""
        if not is_admin_account(ctx.author.id):
            return

        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await ctx.reply("Card not found.")

        if not card.owner_id:
            return await ctx.reply("Card is not owned by anyone.")

        card.change_owner(None)
        CardPool.add_available_card(card)
        await func.update_card(card_id, {"$set": {"owner_id": None, "tag": None, "frame": None, "last_trade_time": 0}})
        await func.update_user(card.owner_id, {"$pull": {"cards": card.id}})

        await ctx.reply(f"Card {card_id} has been removed from user.")

    @commands.command()
    async def giveRollToUser(self, ctx: commands.Context, user: discord.Member, roll_type: str, amount: int = 1):
        """Give rolls to a user."""
        if not is_admin_account(ctx.author.id):
            return

        roll_types = ["rare", "epic", "legendary", "mystic", "celestial"]

        if roll_type not in roll_types:
            return await ctx.reply("Roll type not found.")

        user_data = await func.get_user(user.id)
        if not user_data:
            return await ctx.reply("User not found.")

        await func.update_user(user.id, {"$inc": {f"roll.{roll_type}": amount}})
        await ctx.reply(f"{amount} {roll_type} rolls have been given to {user.display_name}.")

    @commands.command()
    async def giveBirthdayCard(self, ctx: commands.Context, user: discord.Member, day_number: int):
        """Give a birthday card to a user."""
        if not is_admin_account(ctx.author.id):
            return

        if day_number < 1 or day_number > 31:
            return await ctx.reply("Invalid day number. Must be between 1 and 31.")

        user_data = await func.get_user(user.id)
        if not user_data:
            return await ctx.reply("User not found.")

        # Convert day number to string for storage in the collection
        day_str = str(day_number)

        # Check if user already has this card
        birthday_collection = user_data.get("birthday_collection", {})
        if day_str in birthday_collection:
            return await ctx.reply(f"{user.display_name} already has birthday card #{day_number}.")

        # Add card to user's collection
        update_query = {
            "$set": {f"birthday_collection.{day_str}": True},
            "$inc": {"birthday_cards_count": 1, "exp": 20}
        }

        await func.update_user(user.id, update_query)
        await ctx.reply(f"Birthday card #{day_number} has been given to {user.display_name}.")

    @commands.command()
    async def setBirthdayCardsCount(self, ctx: commands.Context, user: discord.Member, count: int):
        """Set the birthday cards count for a user."""
        if not is_admin_account(ctx.author.id):
            return

        user_data = await func.get_user(user.id)
        if not user_data:
            return await ctx.reply("User not found.")

        # Set the birthday cards count
        await func.update_user(user.id, {"$set": {"birthday_cards_count": count}})
        await ctx.reply(f"Birthday cards count for {user.display_name} has been set to {count}.")

    @commands.command()
    async def quit(self, ctx: commands.Context, member: discord.Member = None):
        """[ADMIN ONLY] Deletes a user's profile after confirmation. All cards will be converted.

        If no member is specified, it will delete the profile of the user who called the command.

        **Examples:**
        @prefix@quit @username
        @prefix@quit
        """
        if not is_admin_account(ctx.author.id):
            return await ctx.reply("You don't have permission to use this command.")

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
        candies = sum([card.cost for card in converted_cards])

        for card in converted_cards:
            iufi.CardPool.add_available_card(card)

        # Log the action
        func.logger.info(
            f"Admin {ctx.author.name}({ctx.author.id}) deleted the profile of {target_user.name}({target_user.id}). "
            f"Returned {len(converted_cards)} card(s) to the available pool."
        )

        # Update the cards in the database to remove owner, tag, etc.
        if card_ids:
            await func.update_card(card_ids,
                                   {"$set": {"owner_id": None, "tag": None, "frame": None, "last_trade_time": 0}})

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

    @commands.command()
    async def fetch_messages(self, ctx: commands.Context, channel_id: int, fetch_reactions: bool = False):
        """
        Fetches all messages sent in this year in a given channel ID and stores them locally in a text file.
        
        **Parameters:**
        `channel_id`: The ID of the channel to fetch messages from.
        `fetch_reactions`: Whether to also fetch and store information about reactions (emojis and who reacted). Default is False.

        **Examples:**
        @prefix@fetch_messages 123456789012345678
        @prefix@fetch_messages 123456789012345678 True
        """

        if not is_admin_account(ctx.author.id):
            return await ctx.reply("You don't have permission to use this command.")

        try:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                channel = await self.bot.fetch_channel(channel_id)
        except:
            return await ctx.reply("Channel not found or I don't have access to it.")

        if not isinstance(channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel, discord.StageChannel)):
            return await ctx.reply("The provided ID does not belong to a text-based channel.")

        current_year = datetime.datetime.now().year
        start_of_year = datetime.datetime(current_year, 1, 1)

        status_text = f"Starting to fetch messages from {channel.mention} since {start_of_year.date()}"
        if fetch_reactions:
            status_text += " (including reactions)..."
        else:
            status_text += "..."
        
        status_msg = await ctx.reply(status_text)

        suffix = "_with_reactions" if fetch_reactions else ""
        file_name = f"logs/messages_{channel.name.replace('/', '-')}_{current_year}{suffix}.txt"
        
        # Ensure directory exists
        os.makedirs("logs", exist_ok=True)
        
        # Clear/Create the file
        with open(file_name, "w", encoding="utf-8") as f:
            pass

        log_buffer = []
        count = 0
        BATCH_SIZE = 1000 if fetch_reactions else 2500

        async for message in channel.history(after=start_of_year, limit=None, oldest_first=True):
            timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
            content = message.content.replace('\n', ' ')
            line = f"[{timestamp}] ({message.id}) {message.author} ({message.author.id}): {content}"
            
            if fetch_reactions and message.reactions:
                reactions_data = []
                for reaction in message.reactions:
                    users = [f"{u.name}#{u.discriminator}" if u.discriminator != "0" else u.name async for u in reaction.users()]
                    reactions_data.append(f"{reaction.emoji} (Users: {', '.join(users)})")
                
                if reactions_data:
                    line += f" | Reactions: {' | '.join(reactions_data)}"

            log_buffer.append(line + "\n")
            
            count += 1

            if count % 100 == 0:
                await asyncio.sleep(0.1)

            if count % 500 == 0:
                await status_msg.edit(content=f"Fetched {count} messages{' (with reactions)' if fetch_reactions else ''} so far...")
            
            if len(log_buffer) >= BATCH_SIZE:
                # Write batch to file
                with open(file_name, "a", encoding="utf-8") as f:
                    f.writelines(log_buffer)
                log_buffer.clear()

        # Write remaining
        if log_buffer:
            with open(file_name, "a", encoding="utf-8") as f:
                f.writelines(log_buffer)

        if count == 0:
            return await status_msg.edit(content="No messages found in this channel for the current year.")

        await ctx.send(f"Successfully fetched {count} messages and saved them to `{file_name}`.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
