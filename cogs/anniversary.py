import asyncio

import discord
import functions as func
import time
import random
from discord.ext import commands
import iufi
from discord.ext import commands, tasks

from iufi import CardPool
from views import AnniversarySellView

LEADERBOARD_EMOJIS: list[str] = ["🥇", "🥈", "🥉", "🏅"]


class Anniversary(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.debut_anniversary.start()
        self.invisible = False
        self.emoji = "🎵"

    @commands.command(hidden=True)
    async def sendMessage(self, ctx: commands.Context, channel: discord.TextChannel, *, message: str) -> None:
        """Sends admin message to channel specified"""
        if ctx.author.id in func.settings.ADMIN_IDS:
            await channel.send(message)

    @commands.command(hidden=True)
    async def assignAllCardsToBot(self, ctx: commands.Context) -> None:
        """Assigns all cards to the bot"""
        if ctx.author.id in func.settings.ADMIN_IDS:
            # get all anniversary sale cards and give it to the bot
            all_cards = iufi.GetAllCards()
            card_ids = []
            for card_id, card_price in all_cards:
                card = CardPool.get_card(card_id)
                if card.owner_id:
                    continue
                card_ids.append(card_id)
                card.change_owner(self.bot.user.id)
                CardPool.remove_available_card(card)
            await func.update_card(card_ids, {"$set": {"owner_id": self.bot.user.id}})
            await func.update_user(self.bot.user.id, {"$push": {"cards": {"$each": card_ids}}})
            await ctx.reply("All cards have been assigned to the bot.")

    @commands.command(hidden=True)
    async def removeAssignedCards(self, ctx: commands.Context) -> None:
        """Removes all assigned cards from the bot"""
        if ctx.author.id in func.settings.ADMIN_IDS:
            all_cards = iufi.GetAllCards()
            card_ids = []
            for card_id, card_price in all_cards:
                card = CardPool.get_card(card_id)
                if card.owner_id != self.bot.user.id:
                    continue
                card_ids.append(card_id)
                CardPool.add_available_card(card)
            await func.update_card(card_ids, {"$set": {"owner_id": None}})
            await ctx.reply("All assigned cards have been removed.")

    @commands.command(hidden=True)
    async def startSale(self, ctx: commands.Context) -> None:
        """Starts the sale of cards"""
        if ctx.author.id in func.settings.ADMIN_IDS:
            await self.debut_anniversary()
            await ctx.reply("Sale has started.")

    @tasks.loop(hours=12)
    async def debut_anniversary(self) -> None:
        await self.bot.wait_until_ready()
        if iufi.is_debut_anniversary_day():
            cards_to_sell = iufi.GetTodayCardSell()
            if not cards_to_sell:
                return

            if time.localtime().tm_hour < 12:
                cards_to_sell = cards_to_sell[::2]
            else:
                cards_to_sell = cards_to_sell[1::2]

            if not cards_to_sell:
                return

            channel = self.bot.get_channel(iufi.MARKET_ID)
            for card_details in cards_to_sell:
                card_id = card_details[0]
                card_price = card_details[1]
                card = iufi.CardPool.get_card(card_id)
                if not card:
                    continue
                if card.owner_id == self.bot.user.id:
                    view = AnniversarySellView(self.bot, None, card, card_price)
                    covered_card: iufi.TempCard = iufi.TempCard(f"cover/level{random.randint(1, 3)}.webp")
                    image_bytes, image_format = await asyncio.to_thread(covered_card.image_bytes), covered_card.format
                    sale_message = random.choice(iufi.SALE_MESSAGE)
                    view.message = await channel.send(
                        content=f"**{sale_message}!**",
                        file=discord.File(image_bytes, filename=f'image.{image_format}'),
                        embed=view.build_embed(),
                        view=view
                    )

    @commands.command(hidden=True)
    async def eventEndSaleAssignUnownedCards(self,
                                             ctx: commands.Context) -> None:  # selling the cards of users who left the server
        """Assigns all unowned cards to the bot"""

        if ctx.author.id in func.settings.ADMIN_IDS:
            all_users = await func.get_all_users()
            left_users = [user for user in all_users if not ctx.guild.get_member(user["_id"])]
            card_ids = []
            for user in left_users:
                user_refund = 0
                for card_id in user["cards"]:
                    card = CardPool.get_card(card_id)
                    if not card:
                        continue
                    card.change_owner(self.bot.user.id)
                    user_refund += card.cost
                    card_ids.append(card_id)
                await func.update_user(user["_id"], {"$set": {"cards": []}, "$inc": {"candies": user_refund}})
            await func.update_card(card_ids, {"$set": {"owner_id": self.bot.user.id}})
            await func.update_user(self.bot.user.id, {"$push": {"cards": {"$each": card_ids}}})

    @commands.command(hidden=True)
    async def eventEndSaleStart(self, ctx: commands.Context) -> None:
        """Event End Sale. Schedules all the lost & found cards for sale"""
        common_price = 5
        rare_price = 20
        epic_price = 60
        legendary_price = 300
        mystic_price = 600
        celestial_price = 1000
        if ctx.author.id in func.settings.ADMIN_IDS:
            bot_user = await func.get_user(self.bot.user.id)
            cards_to_sell = bot_user.get("cards", [])

            for card_id in cards_to_sell:
                card = CardPool.get_card(card_id)
                card_price = common_price
                rarity = card.tier[1]
                if rarity == "rare":
                    card_price = rare_price
                elif rarity == "epic":
                    card_price = epic_price
                elif rarity == "legendary":
                    card_price = legendary_price
                elif rarity == "mystic":
                    card_price = mystic_price
                elif rarity == "celestial":
                    card_price = celestial_price
                if not card:
                    continue

                self.bot.loop.create_task(self.schedule_sale(card, card_price))
            await ctx.reply("All lost & found cards have been sold.")

    async def schedule_sale(self, card: iufi.Card, card_price: int) -> None:
        random_wait = random.randint(1, 86400)
        await asyncio.sleep(random_wait)
        channel = self.bot.get_channel(iufi.MARKET_ID)
        view = AnniversarySellView(self.bot, None, card, card_price)
        covered_card: iufi.TempCard = iufi.TempCard(f"cover/level{random.randint(1, 3)}.webp")
        image_bytes, image_format = await asyncio.to_thread(covered_card.image_bytes), covered_card.format
        sale_message = random.choice(iufi.SALE_MESSAGE)
        view.message = await channel.send(
            content=f"**{sale_message}!**",
            file=discord.File(image_bytes, filename=f'image.{image_format}'),
            embed=view.build_embed(),
            view=view
        )

    @commands.command(aliases=["aq"])
    async def anniversaryquest(self, ctx: commands.Context) -> None:
        """Displays the leaderboard for the Debut Anniversary event"""
        anniversary_data = await func.get_anniversary()
        users = anniversary_data["users"]
        current_milestone = anniversary_data["current_milestone"]
        if current_milestone >= len(iufi.MILESTONES):
            current_milestone = len(iufi.MILESTONES) - 1
        required_progress = iufi.MILESTONES[current_milestone]
        quest_progress = anniversary_data["quest_progress"]
        percentage = quest_progress / required_progress * 100
        progress_bar = generate_progress_bar(20, percentage)
        endtime = int(iufi.get_end_time().timestamp())
        milestone_name = "QUEST MILESTONE " + str(current_milestone + 1)
        details = ""
        if time.time() > endtime:
            details = "Quest has ended\n\n"
        else:
            details = f"Quest ends <t:{endtime}:R>\n\n"
        details += f"**   {milestone_name}**\n\n"
        details += f"{'✅' if quest_progress >= required_progress else '❌'} ROLL {required_progress} TIMES\n"
        details += f"```ansi\n➢ Reward: " + " | ".join(
            f"{r[0]} {f'{r[2][0]} ~ {r[2][1]}' if isinstance(r[2], list) else r[2]}" for r in
            iufi.ANNIVERSARY_QUEST_REWARDS[
                current_milestone]) + f"\n➢ {progress_bar} {int(percentage)}% ({quest_progress}/{required_progress})```\n"

        embed = discord.Embed(title="❤️   Debut Anniversary Global Quest", color=discord.Color.purple())
        embed.description = details
        embed.set_thumbnail(url=icon.url if (icon := ctx.guild.icon) else None)
        await ctx.reply(embed=embed)

    @commands.command(aliases=["al"])
    async def anniversaryleaderboard(self, ctx: commands.Context) -> None:
        """Displays the leaderboard for the Debut Anniversary event"""
        anniversary_data = await func.get_anniversary()
        users = anniversary_data["users"]
        users.sort(key=lambda x: x["progress"], reverse=True)
        embed = discord.Embed(title="🏆   Debut Anniversary Leaderboard", color=discord.Color.purple())
        embed.description = ""
        rank = None
        for index, user in enumerate(users):
            if user["_id"] == ctx.author.id:
                rank = index + 1
                break
        if rank:
            embed.description += f"**Your current position is `{rank}`**\n"

        description = ""
        top_users = users[:10]
        rank_1_user = None

        for index, top_user in enumerate(top_users):
            user_progress = top_user["progress"]
            member = self.bot.get_user(top_user['_id'])

            if member:
                if index == 0:
                    rank_1_user = member
                description += f"{LEADERBOARD_EMOJIS[index if index <= 2 else 3]} " + highlight_text(
                    f"{func.truncate_string(member.display_name):<18} {user_progress:>5} ⚔️", member == ctx.author)

        if rank and rank > len(top_users):
            if rank <= len(users):
                user_progress = users[rank - 1]["progress"]
                description += f"{LEADERBOARD_EMOJIS[3]} " + highlight_text(
                    f"{func.truncate_string(ctx.author.display_name):<18} {user_progress:>5} ⚔️")

        if not description:
            description = "The leaderboard is currently empty."

        embed.description += f"```ansi\n{description}```"
        icon = rank_1_user.display_avatar if rank_1_user else ctx.guild.icon
        embed.set_thumbnail(url=icon.url if (icon := icon) else None)

        await ctx.reply(embed=embed)


def generate_progress_bar(total, progress_percentage, filled='⣿', in_progress='⣦', empty='⣀'):
    progress = int(total * progress_percentage / 100)
    filled_length = progress
    in_progress_length = 1 if progress_percentage - filled_length > 0 else 0
    empty_length = total - filled_length - in_progress_length

    # ANSI escape code for magenta color
    start_color = f"[0;1;{'32' if total == progress else '35'}m"
    end_color = "[0m"

    progress_bar = start_color + filled * filled_length + in_progress * in_progress_length + end_color + empty * empty_length

    return progress_bar


def highlight_text(text: str, need: bool = True) -> str:
    if not need:
        return text + "\n"
    return "[0;1;35m" + text + " [0m\n"


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Anniversary(bot))
