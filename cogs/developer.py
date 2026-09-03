import iufi
import psutil
import asyncio
import time
import random
import discord
import functions as func

from discord import app_commands
from discord.ext import commands
from views import DebugView, ConfirmView, BattlepassXPDropView

def formatBytes(bytes: int, unit: bool = False):
    if bytes <= 1_000_000_000:
        return f"{bytes / (1024 ** 2):.1f}" + ("MB" if unit else "")

    else:
        return f"{bytes / (1024 ** 3):.1f}" + ("GB" if unit else "")

class DevGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="dev", description="[Admin] Developer/administration commands.")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not func.is_admin_interaction(interaction):
            raise app_commands.CheckFailure("You do not have permission to use this command.")
        return True

    @app_commands.command(name="givecandies", description="Gives a specified number of candies to a user.")
    @app_commands.describe(member="The member to give candies to", amount="The amount of candies to give")
    async def givecandies(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        user_data = await func.get_user(member.id)
        if not user_data:
            return await interaction.response.send_message("User not found.")
        await func.update_user(member.id, {"$inc": {"candies": amount}})
        await interaction.response.send_message(f"{amount} candies have been given to {member.display_name}.")

    @app_commands.command(name="removecandies", description="Removes a specified number of candies from a user's inventory.")
    @app_commands.describe(member="The member to remove candies from", amount="The amount of candies to remove")
    async def removecandies(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        user_data = await func.get_user(member.id)
        if not user_data:
            return await interaction.response.send_message("User not found.")
        await func.update_user(member.id, {"$inc": {"candies": -amount}})
        await interaction.response.send_message(f"{amount} candies have been removed from {member.display_name}.")

    @app_commands.command(name="resetcooldown", description="Resets a specific cooldown for a user.")
    @app_commands.describe(member="The member whose cooldown to reset", cooldown="One of: roll, quiz, mg")
    async def resetcooldown(self, interaction: discord.Interaction, member: discord.Member, cooldown: str):
        cd_types = {"roll": "roll", "quiz": "quiz_game", "mg": "match_game"}

        if not (cooldown := cd_types.get(cooldown)):
            return await interaction.response.send_message(f"Cooldown not found. Available cooldown type: {', '.join(cd_types.keys())}")

        user_data = await func.get_user(member.id)
        if not user_data:
            return await interaction.response.send_message("User not found.")

        await func.update_user(member.id, {"$set": {f"cooldown.{cooldown}": 0}})
        await interaction.response.send_message(f"{cooldown} cooldown has been reset for {member.display_name}.")

    @app_commands.command(name="resetcardtradecooldown", description="Resets the trade cooldown for a specific card.")
    @app_commands.describe(card_id="The card ID")
    async def resetcardtradecooldown(self, interaction: discord.Interaction, card_id: str):
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await interaction.response.send_message("Card not found.")

        await func.update_card(card_id, {"$set": {"last_trade_time": 0}})
        await interaction.response.send_message(f"Cooldown has been reset for card {card_id}.")

    @app_commands.command(name="givecardtouser", description="Gives a specific card to a user.")
    @app_commands.describe(member="The member to give the card to", card_id="The card ID")
    async def givecardtouser(self, interaction: discord.Interaction, member: discord.Member, card_id: str):
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await interaction.response.send_message("Card not found.")

        if card.owner_id:
            return await interaction.response.send_message("Card already owned by someone.")

        user_data = await func.get_user(member.id)

        if not user_data:
            return await interaction.response.send_message("User not found.")

        if len(user_data["cards"]) >= func.settings.MAX_CARDS:
            return await interaction.response.send_message(f"{member.display_name} already has maximum cards.")

        card.change_owner(member.id)
        iufi.CardPool.remove_available_card(card)
        await func.update_card(card_id, {"$set": {"owner_id": member.id}})
        await func.update_user(member.id, {"$push": {"cards": card_id}})

        await interaction.response.send_message(f"Card {card_id} has been given to {member.display_name}.")

    @app_commands.command(name="removecardfromuser", description="Removes a specific card from a user's collection.")
    @app_commands.describe(card_id="The card ID")
    async def removecardfromuser(self, interaction: discord.Interaction, card_id: str):
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await interaction.response.send_message("Card not found.")

        if not card.owner_id:
            return await interaction.response.send_message("Card is not owned by anyone.")

        card.change_owner(None)
        iufi.CardPool.add_available_card(card)
        await func.update_card(card_id, {"$set": {"owner_id": None, "tag": None, "frame": None, "last_trade_time": 0}})
        await func.update_user(card.owner_id, {"$pull": {"cards": card.id}})

        await interaction.response.send_message(f"Card {card_id} has been removed from user.")

    @app_commands.command(name="giverolltouser", description="Grants a specified number of rolls of a given type to a user.")
    @app_commands.describe(member="The member to give rolls to", roll_type="rare, epic, legendary, mystic, or celestial", amount="How many rolls to give (default 1)")
    async def giverolltouser(self, interaction: discord.Interaction, member: discord.Member, roll_type: str, amount: int = 1):
        roll_types = ["rare", "epic", "legendary", "mystic", "celestial"]

        if roll_type not in roll_types:
            return await interaction.response.send_message("Roll type not found. Available roll types: " + ", ".join(roll_types))

        user_data = await func.get_user(member.id)
        if not user_data:
            return await interaction.response.send_message("User not found.")

        await func.update_user(member.id, {"$inc": {f"roll.{roll_type}": amount}})
        await interaction.response.send_message(f"{amount} {roll_type} rolls have been given to {member.display_name}.")

    @app_commands.command(name="givebirthdaycard", description="Gives a birthday card to a specified user for a particular day.")
    @app_commands.describe(member="The member to give the card to", day_number="The day of month (1-31)")
    async def givebirthdaycard(self, interaction: discord.Interaction, member: discord.Member, day_number: int):
        if day_number < 1 or day_number > 31:
            return await interaction.response.send_message("Invalid day number. Must be between 1 and 31.")

        user_data = await func.get_user(member.id)
        if not user_data:
            return await interaction.response.send_message("User not found.")

        # Convert day number to string for storage in the collection
        day_str = str(day_number)

        # Check if user already has this card
        birthday_collection = user_data.get("birthday_collection", {})
        if day_str in birthday_collection:
            return await interaction.response.send_message(f"{member.display_name} already has birthday card #{day_number}.")

        # Add card to user's collection
        update_query = {
            "$set": {f"birthday_collection.{day_str}": True},
            "$inc": {"birthday_cards_count": 1, "exp": 20}
        }

        await func.update_user(member.id, update_query)
        await interaction.response.send_message(f"Birthday card #{day_number} has been given to {member.display_name}.")

    @app_commands.command(name="setbirthdaycardscount", description="Set the birthday cards count for a user.")
    @app_commands.describe(member="The member to update", count="The new birthday cards count")
    async def setbirthdaycardscount(self, interaction: discord.Interaction, member: discord.Member, count: int):
        user_data = await func.get_user(member.id)
        if not user_data:
            return await interaction.response.send_message("User not found.")

        # Set the birthday cards count
        await func.update_user(member.id, {"$set": {"birthday_cards_count": count}})
        await interaction.response.send_message(f"Birthday cards count for {member.display_name} has been set to {count}.")

    @app_commands.command(name="quit", description="[ADMIN ONLY] Deletes a user's profile after confirmation. All cards will be converted.")
    @app_commands.describe(member="The member whose profile to delete (defaults to yourself)")
    async def quit(self, interaction: discord.Interaction, member: discord.Member = None):
        target_user = member or interaction.user
        user = await func.get_user(target_user.id)

        # Create confirmation embed
        embed = discord.Embed(title="⚠️ Delete Account", color=discord.Color.red())
        embed.description = f"**WARNING: This action cannot be undone!**\n\nThis will:\n- Conver all {target_user.display_name}'s cards \n- Delete their entire profile and progress\n- Remove all inventory items and collections\n\nAre you sure you want to continue?"

        # Create confirmation view
        view = ConfirmView(interaction.user)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()
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
            f"Admin {interaction.user.name}({interaction.user.id}) deleted the profile of {target_user.name}({target_user.id}). "
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

class TestGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="test", description="Personal Battle Pass testing commands.")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not (func.is_tester_interaction(interaction) or func.is_admin_interaction(interaction)):
            raise app_commands.CheckFailure("You do not have permission to use this command.")
        return True

    @app_commands.command(name="resetcd", description="Reset your quiz, roll, match game, and daily cooldowns.")
    async def resetcd(self, interaction: discord.Interaction):
        await func.update_user(interaction.user.id, {
            "$set": {
                "cooldown.roll": 0,
                "cooldown.quiz_game": 0,
                "cooldown.match_game": 0,
                "cooldown.daily": 0,
            }
        })
        await interaction.response.send_message("Reset quiz, roll, match game, and daily cooldowns.", ephemeral=True)

    @app_commands.command(name="bpxp", description="Grant yourself Battle Pass XP for testing.")
    @app_commands.describe(amount="Battle Pass XP to grant")
    async def bpxp(self, interaction: discord.Interaction, amount: int):
        if amount <= 0:
            return await interaction.response.send_message("Amount must be greater than 0.", ephemeral=True)

        user = await func.get_user(interaction.user.id)
        state = func.get_battlepass_state(user)
        if not func.battlepass_enabled():
            return await interaction.response.send_message("Battle Pass is currently disabled.", ephemeral=True)

        old_xp = int(state.get("xp", 0))
        old_level, _, _ = func.calculate_battlepass_level(old_xp)
        query = func.add_battlepass_xp(user, amount)
        await func.update_user(interaction.user.id, query)

        user = await func.get_user(interaction.user.id)
        new_state = func.get_battlepass_state(user)
        new_xp = int(new_state.get("xp", 0))
        new_level, _, _ = func.calculate_battlepass_level(new_xp)
        granted = new_xp - old_xp
        claimed = query.get("$push", {}).get("battlepass.claimed_rewards", {})
        levels = claimed.get("$each", []) if isinstance(claimed, dict) else []

        extra = f"\nReached level(s): {', '.join(str(level) for level in levels)}" if levels else ""
        await interaction.response.send_message(
            f"Granted `{granted}` Battle Pass XP (`{old_xp}` → `{new_xp}`).\n"
            f"Level `{old_level}` → `{new_level}`.{extra}",
            ephemeral=True
        )

    @app_commands.command(name="xpdrop", description="Spawn a Battle Pass XP drop in this channel.")
    async def xpdrop(self, interaction: discord.Interaction):
        if not func.battlepass_enabled():
            return await interaction.response.send_message("Battle Pass is currently disabled.", ephemeral=True)

        xp_amount = func.pick_battlepass_drop_xp()
        view = BattlepassXPDropView(xp_amount)
        await interaction.response.send_message(
            content=f"**Hurry up! This claim ends in: <t:{round(time.time()) + 70}:R>**",
            embed=view.build_embed(),
            view=view
        )
        view.message = await interaction.original_response()
        func.logger.info(
            f"Tester {interaction.user.name}({interaction.user.id}) spawned a Battle Pass XP drop ({xp_amount})"
        )

    @app_commands.command(name="teaser", description="Post a random event teaser in this channel, then delete it.")
    async def teaser(self, interaction: discord.Interaction):
        teaser = func.settings.TEASER_SETTINGS or {}
        messages = [msg for msg in teaser.get("messages", []) if isinstance(msg, str) and msg.strip()]
        if not messages:
            return await interaction.response.send_message("No teaser messages are configured.", ephemeral=True)

        content = random.choice(messages)
        delete_after = max(int(teaser.get("delete_after_seconds", 10) or 10), 0)
        await interaction.response.send_message("Posted a teaser in this channel.", ephemeral=True)
        message = await interaction.channel.send(content)
        func.logger.info(
            f"Tester {interaction.user.name}({interaction.user.id}) spawned a teaser in "
            f"{getattr(interaction.channel, 'name', 'unknown')}({interaction.channel_id})"
        )
        if delete_after:
            await asyncio.sleep(delete_after)
            try:
                await message.delete()
            except discord.HTTPException:
                pass

    @app_commands.command(name="bplevels", description="Add community Battle Pass levels to test global milestones.")
    @app_commands.describe(amount="Community levels to add")
    async def bplevels(self, interaction: discord.Interaction, amount: int):
        if amount <= 0:
            return await interaction.response.send_message("Amount must be greater than 0.", ephemeral=True)

        import events
        await events.add_community_levels(amount)
        await interaction.response.send_message(
            f"Added `{amount}` community Battle Pass levels.\n{events.community_progress_text()}",
            ephemeral=True
        )

class Developer(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "⚙️"
        self.invisible = True

        self.dev_group = DevGroup()
        self.test_group = TestGroup()
        self.bot.tree.add_command(self.dev_group)
        self.bot.tree.add_command(self.test_group)

        self.ctx_menu = discord.app_commands.ContextMenu(
            name="find similar",
            callback=self._findsimilar
        )
        self.bot.tree.add_command(self.ctx_menu)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.dev_group.name)
        self.bot.tree.remove_command(self.test_group.name)
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    @app_commands.command(name="debug", description="[Owner only] Executes developer-only debugging actions.")
    async def debug(self, interaction: discord.Interaction):
        if not await self.bot.is_owner(interaction.user):
            return await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)

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

        await interaction.response.send_message(embed=embed, view=DebugView(self.bot, interaction.user), ephemeral=True)

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
