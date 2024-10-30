import discord
from discord.ext import commands
import functions as func
import iufi
from iufi import CardPool


def is_admin_account(user_id) -> bool:
    if user_id in func.settings.ADMIN_IDS:
        return True
    return False


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.emoji = "🔧"
        self.invisible = True

    @commands.command(hidden=True)
    async def givecandies(self, ctx: commands.Context, user: discord.Member, amount: int):
        """Give candies to a user."""
        if not is_admin_account(ctx.author.id):
            return

        user_data = await func.get_user(user.id)
        if not user_data:
            return await ctx.reply("User not found.")
        await func.update_user(user.id, {"$inc": {"candies": amount}})
        await ctx.reply(f"{amount} candies have been given to {user.display_name}.")

    @commands.command(hidden=True)
    async def removecandies(self, ctx: commands.Context, user: discord.Member, amount: int):
        """Remove candies from a user."""
        if not is_admin_account(ctx.author.id):
            return

        user_data = await func.get_user(user.id)
        if not user_data:
            return await ctx.reply("User not found.")
        await func.update_user(user.id, {"$inc": {"candies": -amount}})
        await ctx.reply(f"{amount} candies have been removed from {user.display_name}.")

    @commands.command(hidden=True)
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

    @commands.command(hidden=True)
    async def resetCardTradeCooldown(self, ctx: commands.Context, card_id: str):
        """Remove cooldown of a card."""
        if not is_admin_account(ctx.author.id):
            return

        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await ctx.reply("Card not found.")

        await func.update_card(card_id, {"$set": {"last_trade_time": 0}})
        await ctx.reply(f"Cooldown has been reset for card {card_id}.")

    @commands.command(hidden=True)
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

    @commands.command(hidden=True)
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

    @commands.command(hidden=True)
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

        await func.update_user(user.id, {"$inc": {f"rolls.{roll_type}": amount}})
        await ctx.reply(f"{amount} {roll_type} rolls have been given to {user.display_name}.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))