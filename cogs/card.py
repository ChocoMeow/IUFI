import discord, iufi, time
import functions as func

from discord import app_commands
from discord.ext import commands

from views import (
    ConfirmView,
    TradeView
)

class Card(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "🎴"
        self.invisible = False

    @commands.command(aliases=["i"])
    async def cardinfo(self, ctx: commands.Context, *, card_ids: str):
        """Shows the details of a photocard. Card can be identified by its ID or given tag.
        
        **Examples:**
        @prefix@cardinfo 01
        @prefix@i 01 02 03
        """
        cards: list[iufi.Card] = []

        card_ids = card_ids.split(" ")[:8]
        for card_id in card_ids:
            card = iufi.CardPool.get_card(card_id)
            if card:
                cards.append(card)

        if not cards:
            return await ctx.reply("The card was not found. Please try again.")
        
        if len(cards) > 1:
            desc = "```"
            for card in cards:
                member = ctx.guild.get_member(card.owner_id)
                desc += f"{card.display_id} {card.display_tag} {card.display_frame} {card.display_stars} {card.tier[0]} 👤{member.display_name if member else 'None':5}\n"
            desc += "```"

            image_bytes, image_format = await iufi.gen_cards_view(cards, 4, hide_image_if_no_owner=True)
            
        elif len(cards) == 1:
            card = cards[0]
            desc = f"```{card.display_id}\n" \
                   f"{card.display_tag}\n" \
                   f"{card.display_frame}\n" \
                   f"{card.tier[0]} {card.tier[1].capitalize()}\n" \
                   f"{card.display_stars}```\n" \
                   "**Owned by: **" + (f"<@{card.owner_id}>" if card.owner_id else "None")

            image_bytes, image_format = await card.image_bytes(True), card.format

        embed = discord.Embed(title=f"ℹ️ Card Info", description=desc, color=0x949fb8)
        embed.set_image(url=f"attachment://image.{image_format}")
        await ctx.reply(file=discord.File(image_bytes, filename=f"image.{image_format}"), embed=embed)

    @commands.command(aliases=["il"])
    async def cardinfolast(self, ctx: commands.Context):
        """Shows the details of your last photocard.
        
        **Examples:**
        @prefix@cardinfolast
        @prefix@il
        """
        user = await func.get_user(ctx.author.id)

        if not user["cards"]:
            return await ctx.reply(f"**{ctx.author.mention} you have no photocards.**", delete_after=5)
        
        card_id = user["cards"][-1]
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await ctx.reply("Card not found! Please try again.")
        
        embed = discord.Embed(title=f"ℹ️ Card Info", color=0x949fb8)
        embed.description = f"```{card.display_id}\n" \
                            f"{card.display_tag}\n" \
                            f"{card.display_frame}\n" \
                            f"{card.tier[0]} {card.tier[1].capitalize()}\n" \
                            f"{card.display_stars}```\n" \
                            "**Owned by: **" + (f"<@{card.owner_id}>" if card.owner_id else "None")
        
        embed.set_image(url=f"attachment://image.{card.format}")
        await ctx.reply(file=discord.File(await card.image_bytes(True), filename=f"image.{card.format}"), embed=embed)

    @commands.command(aliases=["c"])
    async def convert(self, ctx: commands.Context, *, card_ids: str):
        """Converts the photocards into starcandies. Card can be identified by its ID or given tag. The amount of starcandies received is dependent on the card's rarity.

        **Examples:**
        @prefix@concert 01
        @prefix@c 01 02
        """
        converted_cards: list[iufi.Card] = []

        card_ids = card_ids.split(" ")
        candies = 0
        for card_id in card_ids:
            card = iufi.CardPool.get_card(card_id)
            if card and card.owner_id == ctx.author.id:
                candies += card.cost
                iufi.CardPool.add_available_card(card)
                converted_cards.append(card)
        
        user = await func.get_user(ctx.author.id)
        query = func.update_quest_progress(user, "CONVERT_ANY_CARD", progress=len(converted_cards), query={
            "$pull": {"cards": {"$in": (card_ids := [card.id for card in converted_cards])}},
            "$inc": {"candies": candies}
        })
        await func.update_user(ctx.author.id, query)
        await func.update_card(card_ids, {"$set": {"owner_id": None, "tag": None, "frame": None, "last_trade_time": 0}})
        
        func.logger.info(
            f"User {ctx.author.name}({ctx.author.id}) converted {len(converted_cards)} card(s): ["
            f"{', '.join([card.id for card in converted_cards])}]. Gained {candies} candies."
        )
        
        embed = discord.Embed(title="✨ Convert", color=discord.Color.random())
        embed.description = f"```🆔 {', '.join([f'{card}' for card in converted_cards])} \n🍬 + {candies}```"
        await ctx.reply(embed=embed)

    @commands.command(aliases=["cl"])
    async def convertlast(self, ctx: commands.Context):
        """Converts the last photocard of your collection.

        **Examples:**
        @prefix@convertlast
        @prefix@cl
        """
        user = await func.get_user(ctx.author.id)

        if not user["cards"]:
            return await ctx.reply(f"**{ctx.author.mention} you have no photocards.**", delete_after=5)
        
        if not (card := iufi.CardPool.get_card(user["cards"][-1])):
            return
        
        embed = discord.Embed(color=discord.Color.random())
        embed.description = f"```🆔 {card} \n🍬 + {card.cost}```"
        message: discord.Message = None

        if card.tier[1] not in ["common", "rare"] or card.tag:
            embed.title="✨ Confirm to convert?"

            view = ConfirmView(ctx.author)
            view.message = message = await ctx.reply(embed=embed, view=view)
            await view.wait()

            if not view.is_confirm:
                return
            
        if card.owner_id != ctx.author.id:
            return await ctx.reply(content="Your cards cannot be converted because there has been a change in your inventory.")
        
        iufi.CardPool.add_available_card(card)

        query = func.update_quest_progress(user, "CONVERT_ANY_CARD", query={
            "$pull": {"cards": card.id},
            "$inc": {"candies": card.cost}
        })
        await func.update_user(ctx.author.id, query)
        await func.update_card(card.id, {"$set": {"owner_id": None, "tag": None, "frame": None, "last_trade_time": 0}})
        
        func.logger.info(f"User {ctx.author.name}({ctx.author.id}) converted 1 card(s): [{card.id}]. Gained {card.cost} candies.")

        embed.title="✨ Converted"
        await message.edit(embed=embed, view=None) if message else await ctx.reply(embed=embed)
        
    @commands.command(aliases=["ca"])
    async def convertall(self, ctx: commands.Context):
        """Converts all photocard of your collection.

        **Examples:**
        @prefix@convertall
        @prefix@ca
        """
        user = await func.get_user(ctx.author.id)

        if not user["cards"]:
            return await ctx.reply(f"**{ctx.author.mention} you have no photocards.**", delete_after=5)
        
        converted_cards: list[iufi.Card] = []

        for card_id in user["cards"]:
            card = iufi.CardPool.get_card(card_id)
            if card:
                converted_cards.append(card)

        card_ids = [card.id for card in converted_cards]
        candies = sum([card.cost for card in converted_cards])
                       
        embed = discord.Embed(title="✨ Confirm to convert?", color=discord.Color.random())
        embed.description = f"```🆔 {', '.join([f'{card}' for card in converted_cards])} \n🍬 + {candies}```"

        view = ConfirmView(ctx.author)
        view.message = await ctx.reply(embed=embed, view=view)
        await view.wait()

        if view.is_confirm:
            if user["cards"] != card_ids:
                return await ctx.reply(content="Your cards cannot be converted because there has been a change in your inventory.", ephemeral=True)
            
            for card in converted_cards:
                iufi.CardPool.add_available_card(card)

            query = func.update_quest_progress(user, "CONVERT_ANY_CARD", progress=len(converted_cards), query={
                "$pull": {"cards": {"$in": card_ids}},
                "$inc": {"candies": candies}
            })
            await func.update_user(ctx.author.id, query)
            await func.update_card(card_ids, {"$set": {"owner_id": None, "tag": None, "frame": None, "last_trade_time": 0}})

            func.logger.info(
                f"User {ctx.author.name}({ctx.author.id}) converted {len(converted_cards)} card(s): ["
                f"{', '.join([card.id for card in converted_cards])}]. Gained {candies} candies."
            )

            embed.title = "✨ Converted"
            await view.message.edit(embed=embed, view=None)
    
    @commands.command(aliases=["cm"])
    async def convertmass(self, ctx: commands.Context, *, categorys: str):
        """Converts photocards that fit the given mode.

        **Examples:**
        @prefix@convertmass notag
        @prefix@cm notag common rare
        """
        user = await func.get_user(ctx.author.id)
        category_list = categorys.split(" ")
        categories = [func.match_string(category.lower(), set(func.settings.TIERS_BASE.keys()) | {"notag"}) for category in category_list]
        len_categories = len(category_list)

        if not user["cards"]:
            return await ctx.reply(f"**{ctx.author.mention} you have no photocards.**", delete_after=5)
        
        converted_cards: list[iufi.Card] = []
        for card_id in user["cards"]:
            card = iufi.CardPool.get_card(card_id)
            if card:
                if len_categories == 1 and "notag" in categorys and not card.tag:
                    converted_cards.append(card)

                elif card.tier[1] in categories:
                    if "notag" in categories:
                        if not card.tag:
                            converted_cards.append(card)
                    else:
                        converted_cards.append(card)

        card_ids = [card.id for card in converted_cards]
        candies = sum([card.cost for card in converted_cards])
                       
        embed = discord.Embed(title="✨ Confirm to convert?", color=discord.Color.random())
        embed.description = f"```🆔 {', '.join([f'{card}' for card in converted_cards])} \n🍬 + {candies}```"

        view = ConfirmView(ctx.author)
        view.message = await ctx.reply(embed=embed, view=view)
        await view.wait()

        if view.is_confirm:
            if not all(elem in user["cards"] for elem in card_ids):
                return await ctx.reply(content="Your cards cannot be converted because there has been a change in your inventory.", ephemeral=True)
            
            for card in converted_cards:
                iufi.CardPool.add_available_card(card)

            query = func.update_quest_progress(user, "CONVERT_ANY_CARD", progress=len(converted_cards), query={
                "$pull": {"cards": {"$in": card_ids}},
                "$inc": {"candies": candies}
            })
            await func.update_user(ctx.author.id, query)
            await func.update_card(card_ids, {"$set": {"owner_id": None, "tag": None, "frame": None, "last_trade_time": 0}})

            func.logger.info(
                f"User {ctx.author.name}({ctx.author.id}) converted {len(converted_cards)} card(s): ["
                f"{', '.join([card.id for card in converted_cards])}]. Gained {candies} candies."
            )

            embed.title = "✨ Converted"
            await view.message.edit(embed=embed, view=None)

    @commands.command(aliases=["st"])
    async def settag(self, ctx: commands.Context, card_id: str, tag: str):
        """Sets the photocard's tag. Card can be identified by its ID or previous tag.

        **Examples:**
        @prefix@settag 01 IUISBEST
        @prefix@st 01 IUISBEST
        """
        tag = func.clean_text(tag, allow_spaces=False)
        if tag and len(tag) > 10:
            return await ctx.reply(content="Please shorten the tag name as it is too long. (No more than 10 chars)")

        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await ctx.reply("The card was not found. Please try again.")

        if card.owner_id != ctx.author.id:
            return await ctx.reply("You are not the owner of this card.")
        
        func.logger.info(f"User {ctx.author.name}({ctx.author.id}) tagged card [{card.id}] from {card.tag} to {tag}")

        if card.tag:
            iufi.CardPool.change_tag(card, tag)
        else:
            iufi.CardPool.add_tag(card, tag)

        embed = discord.Embed(title="🏷️ Set Tag", color=discord.Color.random())
        embed.description = f"```🆔 {card}\n{card.display_tag}```"
        await ctx.reply(embed=embed)

    @commands.command(aliases=["stl"])
    async def settaglast(self, ctx: commands.Context, tag: str):
        """Sets the tag of the last photocard in your collection.

        **Examples:**
        @prefix@settaglast IUISBEST
        @prefix@stl IUISBEST
        """
        tag = func.clean_text(tag, allow_spaces=False)
        if tag and len(tag) > 10:
            return await ctx.reply(content="Please shorten the tag name as it is too long. (No more than 10 chars)")
        
        user = await func.get_user(ctx.author.id)
        if not user["cards"]:
            return await ctx.reply(f"**{ctx.author.mention} you have no photocards.**", delete_after=5)
        
        card_id = user["cards"][-1]
        card = iufi.CardPool.get_card(card_id)
        if card:
            if card.owner_id != ctx.author.id:
                return await ctx.reply("You are not the owner of this card.")
            
            func.logger.info(f"User {ctx.author.name}({ctx.author.id}) tagged card [{card.id}] from {card.tag} to {tag}")
            
            if card.tag:
                iufi.CardPool.change_tag(card, tag)
            else:
                iufi.CardPool.add_tag(card, tag)
        
            embed = discord.Embed(title="🏷️ Set Tag", color=discord.Color.random())
            embed.description = f"```🆔 {card}\n{card.display_tag}```"
            await ctx.reply(embed=embed)

    @commands.command(aliases=["rt"])
    async def removetag(self, ctx: commands.Context, card_id: str):
        """Removes the photocard's tag. Card can be identified by its ID or given tag.

        **Examples:**
        @prefix@removetag 01
        @prefix@rt 01
        """
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await ctx.reply("The card was not found. Please try again.")

        if card.owner_id != ctx.author.id:
            return await ctx.reply("You are not the owner of this card.")
        
        iufi.CardPool.remove_tag(card)

        func.logger.info(
            f"User {ctx.author.name}({ctx.author.id}) removed the tag from card [{card.id}]. "
            f"Original tag: {card.tag}."
        )

        embed = discord.Embed(title="🏷️ Set Tag", color=discord.Color.random())
        embed.description = f"```🆔 {card}\n{card.display_tag}```"
        await ctx.reply(embed=embed)

    @commands.command(aliases=["t"])
    async def trade(self, ctx: commands.Context, member: discord.Member, candies: int, *, card_ids: str):
        """Trades your card(s) with a member.

        **Examples:**
        @prefix@trade IU 10 01
        @prefix@t IU 10 01
        """
        if member.bot:
            return await ctx.reply("You are not able to trade with a bot.")
        if member == ctx.author:
            return await ctx.reply("You are not able to trade with yourself.")
        if candies < 0:
            return await ctx.reply("The candy count cannot be set to a negative value.")
        
        cards = []
        card_ids = card_ids.split(" ")
        for card_id in card_ids:
            card = iufi.CardPool.get_card(card_id)
            if not card:
                continue

            if card.owner_id != ctx.author.id:
                return await ctx.reply(f"You are not the owner of this `{card_id}` card.")
            
            if time.time() - card.last_trade_time < func.settings.LAST_TRADE_TIMER:
                return await ctx.reply(f"Oopsie! You need to wait a little longer~ You can trade this `{card_id}` card again <t:{int(card.last_trade_time + func.settings.LAST_TRADE_TIMER)}:R>")

            if card not in cards:
                cards.append(card)

        if not cards:
            return await ctx.reply("No cards were found. Please enter a valid card ID!")
        
        if len(cards) > 1:
            image_bytes, image_format = await iufi.gen_cards_view(cards, max(3, min((len(cards) // 2), 8)))
        else:
            image_bytes, image_format = await card.image_bytes(True), card.format

        func.logger.info(
            f"User {ctx.author.name} ({ctx.author.id}) initiated a trade with {member.name}({member.id}). "
            f"Trading card [{card.id}] and offering {candies} candies."
        )

        view = TradeView(ctx.author, member, cards, candies)
        view.message = await ctx.reply(
            content=f"{member.mention}, {ctx.author.mention} want to trade with you.",
            file=discord.File(image_bytes, filename=f"image.{image_format}"),
            embed=view.build_embed(image_format), view=view
        )

    @commands.command(aliases=["te"])
    async def tradeeveryone(self, ctx: commands.Context, candies: int, *, card_ids: str):
        """Trades your card(s) with everyone.
        
        **Examples:**
        @prefix@tradeeveryone 10 01
        @prefix@te 10 01
        """
        if candies < 0:
            return await ctx.reply("The candy count cannot be set to a negative value.")

        cards = []
        card_ids = card_ids.split(" ")
        for card_id in card_ids:
            card = iufi.CardPool.get_card(card_id)
            if not card:
                continue

            if card.owner_id != ctx.author.id:
                return await ctx.reply(f"You are not the owner of this `{card_id}` card.")
            
            if time.time() - card.last_trade_time < func.settings.LAST_TRADE_TIMER:
                return await ctx.reply(f"Oopsie! You need to wait a little longer~ You can trade this `{card_id}` card again <t:{int(card.last_trade_time + func.settings.LAST_TRADE_TIMER)}:R>")

            if card not in cards:
                cards.append(card)

        if not cards:
            return await ctx.reply("No cards were found. Please enter a valid card ID!")
        
        if len(cards) > 1:
            image_bytes, image_format = await iufi.gen_cards_view(cards, max(3, min((len(cards) // 2), 8)))
        else:
            image_bytes, image_format = await card.image_bytes(True), card.format

        func.logger.info(
            f"User {ctx.author.name} ({ctx.author.id}) initiated a trade with everyone. "
            f"Trading card [{card.id}] and offering {candies} candies."
        )

        view = TradeView(ctx.author, None, cards, candies)
        view.message = await ctx.reply(
            content=f"{ctx.author.mention} wants to trade",
            file=discord.File(image_bytes, filename=f"image.{image_format}"),
            embed=view.build_embed(image_format), view=view
        )

    @commands.command(aliases=["tl"])
    async def tradelast(self, ctx: commands.Context, member: discord.Member, candies: int):
        """Trades your last card with a member.

        **Examples:**
        @prefix@tradelast IU 10
        @prefix@tl IU 10
        """
        if member.bot:
            return await ctx.reply("You are not able to trade with a bot.")
        if member == ctx.author:
            return await ctx.reply("You are not able to trade with yourself.")
        if candies < 0:
            return await ctx.reply("The candy count cannot be set to a negative value.")
        
        user = await func.get_user(ctx.author.id)
        if not user["cards"]:
            return await ctx.reply(f"**{ctx.author.mention} you have no photocards.**", delete_after=5)
        
        card_id = user["cards"][-1]
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await ctx.reply("The card was not found. Please try again.")

        if card.owner_id != ctx.author.id:
            return await ctx.reply("You are not the owner of this card.")
        
        if time.time() - card.last_trade_time < func.settings.LAST_TRADE_TIMER:
            return await ctx.reply(f"Oopsie! You need to wait a little longer~ You can trade this card again <t:{int(card.last_trade_time + func.settings.LAST_TRADE_TIMER)}:R>")
        
        func.logger.info(
            f"User {ctx.author.name} ({ctx.author.id}) initiated a trade with {member.name}({member.id}). "
            f"Trading card [{card.id}] and offering {candies} candies."
        )

        view = TradeView(ctx.author, member, [card], candies)
        view.message = await ctx.reply(
            content=f"{member.mention}, {ctx.author.mention} want to trade with you.",
            file=discord.File(await card.image_bytes(), filename=f"image.{card.format}"),
            embed=view.build_embed(card.format),
            view=view
        )

    @commands.command(aliases=["tel"])
    async def tradeeveryonelast(self, ctx: commands.Context, candies: int):
        """Trades your last card with everyone.

        **Examples:**
        @prefix@tradeeveryonelast 10
        @prefix@tel 10
        """
        if candies < 0:
            return await ctx.reply("The candy count cannot be set to a negative value.")

        user = await func.get_user(ctx.author.id)
        if not user["cards"]:
            return await ctx.reply(f"**{ctx.author.mention} you have no photocards.**", delete_after=5)

        card_id = user["cards"][-1]
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await ctx.reply("The card was not found. Please try again.")

        if card.owner_id != ctx.author.id:
            return await ctx.reply("You are not the owner of this card.")
        
        if time.time() - card.last_trade_time < func.settings.LAST_TRADE_TIMER:
            return await ctx.reply(f"Oopsie! You need to wait a little longer~ You can trade this card again <t:{int(card.last_trade_time + func.settings.LAST_TRADE_TIMER)}:R>")
        
        func.logger.info(
            f"User {ctx.author.name} ({ctx.author.id}) initiated a trade with everyone. "
            f"Trading card [{card.id}] and offering {candies} candies."
        )

        view = TradeView(ctx.author, None, [card], candies)
        view.message = await ctx.reply(
            content=f"{ctx.author.mention} wants to trade",
            file=discord.File(await card.image_bytes(), filename=f"image.{card.format}"),
            embed=view.build_embed(card.format),
            view=view
        )

    @commands.command(aliases=["u"])
    async def upgrade(self, ctx: commands.Context, upgrade_card_id: str, *, card_ids: str) -> None:
        """Use cards of the same type to upgrade your card star.

        **Examples:**
        @prefix@upgrade 01 02
        @prefix@u 01 02 03 04 05
        """
        upgrade_card = iufi.CardPool.get_card(upgrade_card_id)
        if not upgrade_card:
            return await ctx.reply("The card was not found. Please try again.")
        
        if upgrade_card.owner_id != ctx.author.id:
            return await ctx.reply("You are not the owner of this card.")
        
        if upgrade_card.stars >= 10:
            return await ctx.reply("Your card has reached the maximum number of stars")
        
        converted_cards: list[iufi.Card] = []
        for card_id in card_ids.split(" "):
            card = iufi.CardPool.get_card(card_id)
            if card and upgrade_card.id != card.id and card.owner_id == ctx.author.id and card.tier[1] == upgrade_card.tier[1]:
                converted_cards.append(card)

        converted_cards = converted_cards[:(10 - upgrade_card.stars)]
        if not converted_cards:
            return await ctx.reply("There are no card can applied into your card.")
        
        for card in converted_cards:
            iufi.CardPool.add_available_card(card)
        
        query = func.update_quest_progress(
            await func.get_user(ctx.author.id),
            "UPGRADE_CARD",
            progress=len(converted_cards), 
            query={"$pull": {"cards": {"$in": (card_ids := [card.id for card in converted_cards])}}}
        )
        await func.update_user(ctx.author.id, query)
        await func.update_card(card_ids, {"$set": {"owner_id": None, "tag": None, "frame": None, "last_trade_time": 0}})
        upgraded_stars = upgrade_card.stars + len(converted_cards)

        func.logger.info(
            f"User {ctx.author.name} ({ctx.author.id}) upgraded a card [{card.id}] from {upgrade_card.stars} to {upgraded_stars}). "
            f"With cards: [{', '.join([card.id for card in converted_cards])}]"
        )

        embed = discord.Embed(title="🆙 Upgraded", color=discord.Color.random())
        embed.description = f"```🆔 {upgrade_card} <- {', '.join([f'{card}' for card in converted_cards])}\n⭐ {upgraded_stars} <- {upgrade_card.stars}```"
        await ctx.reply(embed=embed)
        
        upgrade_card.change_stars(upgraded_stars)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Card(bot))