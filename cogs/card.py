import discord, iufi, time
import functions as func
import events

from discord import app_commands
from discord.ext import commands

from views import (
    ConfirmView,
    TradeView,
    PotionTradeView,
    MultiIDModal,
)

class Card(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "🎴"
        self.invisible = False

    def _parse_potion_name(self, potion_type: str, potion_level: str) -> str | None:
        potion_type = potion_type.lower().strip()
        potion_level = potion_level.lower().strip()
        potions_base = func.settings.POTIONS_BASE

        if potion_type not in potions_base:
            return None

        levels = potions_base.get(potion_type, {}).get("levels", {})
        if potion_level not in levels:
            return None

        return f"{potion_type}_{potion_level}"

    @app_commands.command(name="cardinfo", description="Shows the details of one or more photocards (up to 8). Cards can be identified by ID or given tag.")
    async def cardinfo(self, interaction: discord.Interaction):
        async def on_ids(modal_interaction: discord.Interaction, card_ids: list[str]):
            cards: list[iufi.Card] = []

            for card_id in card_ids[:8]:
                card = iufi.CardPool.get_card(card_id)
                if card:
                    cards.append(card)

            if not cards:
                return await modal_interaction.response.send_message("The card was not found. Please try again.")

            if len(cards) > 1:
                desc = "```"
                for card in cards:
                    member = modal_interaction.guild.get_member(card.owner_id)
                    desc += f"{card.display_id} {card.display_tag} {card.display_frame} {card.display_stars} {card.tier[0]} 👤 {member.display_name if member else 'None':5}\n"
                desc += "```"

                image_bytes, image_format = await iufi.gen_cards_view(cards, 4, hide_image_if_no_owner=True)

            else:
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
            await modal_interaction.response.send_message(file=discord.File(image_bytes, filename=f"image.{image_format}"), embed=embed)

        modal = MultiIDModal(title="Card Info", label="Card IDs (up to 8)", callback=on_ids)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="cardinfolast", description="Shows the details of your last photocard.")
    async def cardinfolast(self, interaction: discord.Interaction):
        user = await func.get_user(interaction.user.id)

        if not user["cards"]:
            return await interaction.response.send_message(f"**{interaction.user.mention} you have no photocards.**", ephemeral=True)

        card_id = user["cards"][-1]
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await interaction.response.send_message("Card not found! Please try again.")

        embed = discord.Embed(title=f"ℹ️ Card Info", color=0x949fb8)
        embed.description = f"```{card.display_id}\n" \
                            f"{card.display_tag}\n" \
                            f"{card.display_frame}\n" \
                            f"{card.tier[0]} {card.tier[1].capitalize()}\n" \
                            f"{card.display_stars}```\n" \
                            "**Owned by: **" + (f"<@{card.owner_id}>" if card.owner_id else "None")

        embed.set_image(url=f"attachment://image.{card.format}")
        await interaction.response.send_message(file=discord.File(await card.image_bytes(True), filename=f"image.{card.format}"), embed=embed)

    @app_commands.command(name="convert", description="Converts photocard(s) into starcandies. Cards can be identified by ID or given tag.")
    async def convert(self, interaction: discord.Interaction):
        async def on_ids(modal_interaction: discord.Interaction, card_ids: list[str]):
            converted_cards: list[iufi.Card] = []

            raw_candies = 0
            for card_id in card_ids:
                card = iufi.CardPool.get_card(card_id)
                if card and card.owner_id == modal_interaction.user.id:
                    raw_candies += card.cost
                    iufi.CardPool.add_available_card(card)
                    converted_cards.append(card)

            candies = events.convert_candies(raw_candies)

            user = await func.get_user(modal_interaction.user.id)
            query = func.update_quest_progress(user, "CONVERT_ANY_CARD", progress=len(converted_cards), query={
                "$pull": {"cards": {"$in": (converted_ids := [card.id for card in converted_cards])}},
                "$inc": {"candies": candies}
            })
            await func.update_user(modal_interaction.user.id, query)
            await func.update_card(converted_ids, {"$set": {"owner_id": None, "tag": None, "frame": None, "last_trade_time": 0}})

            func.logger.info(
                f"User {modal_interaction.user.name}({modal_interaction.user.id}) converted {len(converted_cards)} card(s): ["
                f"{', '.join([card.id for card in converted_cards])}]. Gained {candies} candies."
            )

            embed = discord.Embed(title="✨ Convert", color=discord.Color.random())
            embed.description = f"```🆔 {', '.join([f'{card}' for card in converted_cards])} \n🍬 + {candies}```"
            await modal_interaction.response.send_message(embed=embed)

        modal = MultiIDModal(title="Convert Cards", label="Card IDs", callback=on_ids)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="convertlast", description="Converts the last photocard of your collection.")
    async def convertlast(self, interaction: discord.Interaction):
        user = await func.get_user(interaction.user.id)

        if not user["cards"]:
            return await interaction.response.send_message(f"**{interaction.user.mention} you have no photocards.**", ephemeral=True)

        if not (card := iufi.CardPool.get_card(user["cards"][-1])):
            return

        candies = events.convert_candies(card.cost)
        embed = discord.Embed(color=discord.Color.random())
        embed.description = f"```🆔 {card} \n🍬 + {candies}```"
        message: discord.Message = None

        if card.tier[1] not in ["common", "rare"] or card.tag:
            embed.title = "✨ Confirm to convert?"

            view = ConfirmView(interaction.user)
            await interaction.response.send_message(embed=embed, view=view)
            view.message = message = await interaction.original_response()
            await view.wait()

            if not view.is_confirm:
                return
        else:
            await interaction.response.defer()

        if card.owner_id != interaction.user.id:
            content = "Your cards cannot be converted because there has been a change in your inventory."
            return await (message.edit(content=content, embed=None, view=None) if message else interaction.followup.send(content=content))

        iufi.CardPool.add_available_card(card)

        query = func.update_quest_progress(user, "CONVERT_ANY_CARD", query={
            "$pull": {"cards": card.id},
            "$inc": {"candies": candies}
        })
        await func.update_user(interaction.user.id, query)
        await func.update_card(card.id, {"$set": {"owner_id": None, "tag": None, "frame": None, "last_trade_time": 0}})

        func.logger.info(f"User {interaction.user.name}({interaction.user.id}) converted 1 card(s): [{card.id}]. Gained {candies} candies.")

        embed.title = "✨ Converted"
        await message.edit(embed=embed, view=None) if message else await interaction.followup.send(embed=embed)

    @app_commands.command(name="convertall", description="Converts all photocards of your collection.")
    async def convertall(self, interaction: discord.Interaction):
        user = await func.get_user(interaction.user.id)

        if not user["cards"]:
            return await interaction.response.send_message(f"**{interaction.user.mention} you have no photocards.**", ephemeral=True)

        converted_cards: list[iufi.Card] = []

        for card_id in user["cards"]:
            card = iufi.CardPool.get_card(card_id)
            if card:
                converted_cards.append(card)

        card_ids = [card.id for card in converted_cards]
        candies = events.convert_candies(sum(card.cost for card in converted_cards))

        embed = discord.Embed(title="✨ Confirm to convert?", color=discord.Color.random())
        embed.description = f"```🆔 {', '.join([f'{card}' for card in converted_cards])} \n🍬 + {candies}```"

        view = ConfirmView(interaction.user)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()
        await view.wait()

        if view.is_confirm:
            if user["cards"] != card_ids:
                return await interaction.followup.send(content="Your cards cannot be converted because there has been a change in your inventory.", ephemeral=True)

            for card in converted_cards:
                iufi.CardPool.add_available_card(card)

            query = func.update_quest_progress(user, "CONVERT_ANY_CARD", progress=len(converted_cards), query={
                "$pull": {"cards": {"$in": card_ids}},
                "$inc": {"candies": candies}
            })
            await func.update_user(interaction.user.id, query)
            await func.update_card(card_ids, {"$set": {"owner_id": None, "tag": None, "frame": None, "last_trade_time": 0}})

            func.logger.info(
                f"User {interaction.user.name}({interaction.user.id}) converted {len(converted_cards)} card(s): ["
                f"{', '.join([card.id for card in converted_cards])}]. Gained {candies} candies."
            )

            embed.title = "✨ Converted"
            await view.message.edit(embed=embed, view=None)

    @app_commands.command(name="convertmass", description="Converts photocards that fit the given categories (tier names or 'notag').")
    async def convertmass(self, interaction: discord.Interaction):
        async def on_ids(modal_interaction: discord.Interaction, category_list: list[str]):
            user = await func.get_user(modal_interaction.user.id)
            categories = [func.match_string(category.lower(), set(func.settings.TIERS_BASE.keys()) | {"notag"}) for category in category_list]
            len_categories = len(category_list)

            if not user["cards"]:
                return await modal_interaction.response.send_message(f"**{modal_interaction.user.mention} you have no photocards.**", ephemeral=True)

            converted_cards: list[iufi.Card] = []
            for card_id in user["cards"]:
                card = iufi.CardPool.get_card(card_id)
                if card:
                    if len_categories == 1 and "notag" in category_list and not card.tag:
                        converted_cards.append(card)

                    elif card.tier[1] in categories:
                        if "notag" in categories:
                            if not card.tag:
                                converted_cards.append(card)
                        else:
                            converted_cards.append(card)

            card_ids = [card.id for card in converted_cards]
            candies = events.convert_candies(sum(card.cost for card in converted_cards))

            embed = discord.Embed(title="✨ Confirm to convert?", color=discord.Color.random())
            embed.description = f"```🆔 {', '.join([f'{card}' for card in converted_cards])} \n🍬 + {candies}```"

            view = ConfirmView(modal_interaction.user)
            await modal_interaction.response.send_message(embed=embed, view=view)
            view.message = await modal_interaction.original_response()
            await view.wait()

            if view.is_confirm:
                if not all(elem in user["cards"] for elem in card_ids):
                    return await modal_interaction.followup.send(content="Your cards cannot be converted because there has been a change in your inventory.", ephemeral=True)

                for card in converted_cards:
                    iufi.CardPool.add_available_card(card)

                query = func.update_quest_progress(user, "CONVERT_ANY_CARD", progress=len(converted_cards), query={
                    "$pull": {"cards": {"$in": card_ids}},
                    "$inc": {"candies": candies}
                })
                await func.update_user(modal_interaction.user.id, query)
                await func.update_card(card_ids, {"$set": {"owner_id": None, "tag": None, "frame": None, "last_trade_time": 0}})

                func.logger.info(
                    f"User {modal_interaction.user.name}({modal_interaction.user.id}) converted {len(converted_cards)} card(s): ["
                    f"{', '.join([card.id for card in converted_cards])}]. Gained {candies} candies."
                )

                embed.title = "✨ Converted"
                await view.message.edit(embed=embed, view=None)

        modal = MultiIDModal(title="Convert Mass", label="Categories (tier names or notag)", placeholder="e.g. common rare or notag", callback=on_ids)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="settag", description="Sets the photocard's tag. Card can be identified by its ID or previous tag.")
    @app_commands.describe(card_id="The card ID or previous tag", tag="The new tag (max 10 chars)")
    async def settag(self, interaction: discord.Interaction, card_id: str, tag: str):
        tag = func.clean_text(tag, allow_spaces=False)
        if tag and len(tag) > 10:
            return await interaction.response.send_message(content="Please shorten the tag name as it is too long. (No more than 10 chars)")

        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await interaction.response.send_message("The card was not found. Please try again.")

        if card.owner_id != interaction.user.id:
            return await interaction.response.send_message("You are not the owner of this card.")

        func.logger.info(f"User {interaction.user.name}({interaction.user.id}) tagged card [{card.id}] from {card.tag} to {tag}")

        if card.tag:
            iufi.CardPool.change_tag(card, tag)
        else:
            iufi.CardPool.add_tag(card, tag)

        embed = discord.Embed(title="🏷️ Set Tag", color=discord.Color.random())
        embed.description = f"```🆔 {card}\n{card.display_tag}```"
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="settaglast", description="Sets the tag of the last photocard in your collection.")
    @app_commands.describe(tag="The new tag (max 10 chars)")
    async def settaglast(self, interaction: discord.Interaction, tag: str):
        tag = func.clean_text(tag, allow_spaces=False)
        if tag and len(tag) > 10:
            return await interaction.response.send_message(content="Please shorten the tag name as it is too long. (No more than 10 chars)")

        user = await func.get_user(interaction.user.id)
        if not user["cards"]:
            return await interaction.response.send_message(f"**{interaction.user.mention} you have no photocards.**", ephemeral=True)

        card_id = user["cards"][-1]
        card = iufi.CardPool.get_card(card_id)
        if card:
            if card.owner_id != interaction.user.id:
                return await interaction.response.send_message("You are not the owner of this card.")

            func.logger.info(f"User {interaction.user.name}({interaction.user.id}) tagged card [{card.id}] from {card.tag} to {tag}")

            if card.tag:
                iufi.CardPool.change_tag(card, tag)
            else:
                iufi.CardPool.add_tag(card, tag)

            embed = discord.Embed(title="🏷️ Set Tag", color=discord.Color.random())
            embed.description = f"```🆔 {card}\n{card.display_tag}```"
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="removetag", description="Removes the photocard's tag. Card can be identified by its ID or given tag.")
    @app_commands.describe(card_id="The card ID or given tag")
    async def removetag(self, interaction: discord.Interaction, card_id: str):
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await interaction.response.send_message("The card was not found. Please try again.")

        if card.owner_id != interaction.user.id:
            return await interaction.response.send_message("You are not the owner of this card.")

        iufi.CardPool.remove_tag(card)

        func.logger.info(
            f"User {interaction.user.name}({interaction.user.id}) removed the tag from card [{card.id}]. "
            f"Original tag: {card.tag}."
        )

        embed = discord.Embed(title="🏷️ Set Tag", color=discord.Color.random())
        embed.description = f"```🆔 {card}\n{card.display_tag}```"
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="trade", description="Trades your card(s) with a member.")
    @app_commands.describe(member="The member to trade with", candies="The amount of candies to offer")
    async def trade(self, interaction: discord.Interaction, member: discord.Member, candies: int):
        if member.bot:
            return await interaction.response.send_message("You are not able to trade with a bot.")
        if member == interaction.user:
            return await interaction.response.send_message("You are not able to trade with yourself.")
        if candies < 0:
            return await interaction.response.send_message("The candy count cannot be set to a negative value.")

        async def on_ids(modal_interaction: discord.Interaction, card_ids: list[str]):
            cards = []
            for card_id in card_ids:
                card = iufi.CardPool.get_card(card_id)
                if not card:
                    continue

                if card.owner_id != modal_interaction.user.id:
                    return await modal_interaction.response.send_message(f"You are not the owner of this `{card_id}` card.")

                if time.time() - card.last_trade_time < func.settings.LAST_TRADE_TIMER:
                    return await modal_interaction.response.send_message(f"Oopsie! You need to wait a little longer~ You can trade this `{card_id}` card again <t:{int(card.last_trade_time + func.settings.LAST_TRADE_TIMER)}:R>")

                if card not in cards:
                    cards.append(card)

            if not cards:
                return await modal_interaction.response.send_message("No cards were found. Please enter a valid card ID!")

            if len(cards) > 1:
                image_bytes, image_format = await iufi.gen_cards_view(cards, max(3, min((len(cards) // 2), 8)))
            else:
                image_bytes, image_format = await cards[0].image_bytes(True), cards[0].format

            func.logger.info(
                f"User {modal_interaction.user.name} ({modal_interaction.user.id}) initiated a trade with {member.name}({member.id}). "
                f"Trading card(s) {[card.id for card in cards]} and offering {candies} candies."
            )

            view = TradeView(modal_interaction.user, member, cards, candies)
            await modal_interaction.response.send_message(
                content=f"{member.mention}, {modal_interaction.user.mention} want to trade with you.",
                file=discord.File(image_bytes, filename=f"image.{image_format}"),
                embed=view.build_embed(image_format), view=view
            )
            view.message = await modal_interaction.original_response()
            await func.check_wishlist(view.message, [card.id for card in cards])

        modal = MultiIDModal(title="Trade Cards", label="Card IDs", callback=on_ids)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="tradeeveryone", description="Trades your card(s) with everyone.")
    @app_commands.describe(candies="The amount of candies to offer")
    async def tradeeveryone(self, interaction: discord.Interaction, candies: int):
        if candies < 0:
            return await interaction.response.send_message("The candy count cannot be set to a negative value.")

        async def on_ids(modal_interaction: discord.Interaction, card_ids: list[str]):
            cards = []
            for card_id in card_ids:
                card = iufi.CardPool.get_card(card_id)
                if not card:
                    continue

                if card.owner_id != modal_interaction.user.id:
                    return await modal_interaction.response.send_message(f"You are not the owner of this `{card_id}` card.")

                if time.time() - card.last_trade_time < func.settings.LAST_TRADE_TIMER:
                    return await modal_interaction.response.send_message(f"Oopsie! You need to wait a little longer~ You can trade this `{card_id}` card again <t:{int(card.last_trade_time + func.settings.LAST_TRADE_TIMER)}:R>")

                if card not in cards:
                    cards.append(card)

            if not cards:
                return await modal_interaction.response.send_message("No cards were found. Please enter a valid card ID!")

            if len(cards) > 1:
                image_bytes, image_format = await iufi.gen_cards_view(cards, max(3, min((len(cards) // 2), 8)))
            else:
                image_bytes, image_format = await cards[0].image_bytes(True), cards[0].format

            func.logger.info(
                f"User {modal_interaction.user.name} ({modal_interaction.user.id}) initiated a trade with everyone. "
                f"Trading card(s) {[card.id for card in cards]} and offering {candies} candies."
            )

            view = TradeView(modal_interaction.user, None, cards, candies)
            await modal_interaction.response.send_message(
                content=f"{modal_interaction.user.mention} wants to trade",
                file=discord.File(image_bytes, filename=f"image.{image_format}"),
                embed=view.build_embed(image_format), view=view
            )
            view.message = await modal_interaction.original_response()
            await func.check_wishlist(view.message, [card.id for card in cards])

        modal = MultiIDModal(title="Trade Cards", label="Card IDs", callback=on_ids)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="tradelast", description="Trades your last card with a member.")
    @app_commands.describe(member="The member to trade with", candies="The amount of candies to offer")
    async def tradelast(self, interaction: discord.Interaction, member: discord.Member, candies: int):
        if member.bot:
            return await interaction.response.send_message("You are not able to trade with a bot.")
        if member == interaction.user:
            return await interaction.response.send_message("You are not able to trade with yourself.")
        if candies < 0:
            return await interaction.response.send_message("The candy count cannot be set to a negative value.")

        user = await func.get_user(interaction.user.id)
        if not user["cards"]:
            return await interaction.response.send_message(f"**{interaction.user.mention} you have no photocards.**", ephemeral=True)

        card_id = user["cards"][-1]
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await interaction.response.send_message("The card was not found. Please try again.")

        if card.owner_id != interaction.user.id:
            return await interaction.response.send_message("You are not the owner of this card.")

        if time.time() - card.last_trade_time < func.settings.LAST_TRADE_TIMER:
            return await interaction.response.send_message(f"Oopsie! You need to wait a little longer~ You can trade this card again <t:{int(card.last_trade_time + func.settings.LAST_TRADE_TIMER)}:R>")

        func.logger.info(
            f"User {interaction.user.name} ({interaction.user.id}) initiated a trade with {member.name}({member.id}). "
            f"Trading card [{card.id}] and offering {candies} candies."
        )

        view = TradeView(interaction.user, member, [card], candies)
        await interaction.response.send_message(
            content=f"{member.mention}, {interaction.user.mention} want to trade with you.",
            file=discord.File(await card.image_bytes(), filename=f"image.{card.format}"),
            embed=view.build_embed(card.format),
            view=view
        )
        view.message = await interaction.original_response()
        await func.check_wishlist(view.message, [card_id])

    @app_commands.command(name="tradeeveryonelast", description="Trades your last card with everyone.")
    @app_commands.describe(candies="The amount of candies to offer")
    async def tradeeveryonelast(self, interaction: discord.Interaction, candies: int):
        if candies < 0:
            return await interaction.response.send_message("The candy count cannot be set to a negative value.")

        user = await func.get_user(interaction.user.id)
        if not user["cards"]:
            return await interaction.response.send_message(f"**{interaction.user.mention} you have no photocards.**", ephemeral=True)

        card_id = user["cards"][-1]
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await interaction.response.send_message("The card was not found. Please try again.")

        if card.owner_id != interaction.user.id:
            return await interaction.response.send_message("You are not the owner of this card.")

        if time.time() - card.last_trade_time < func.settings.LAST_TRADE_TIMER:
            return await interaction.response.send_message(f"Oopsie! You need to wait a little longer~ You can trade this card again <t:{int(card.last_trade_time + func.settings.LAST_TRADE_TIMER)}:R>")

        func.logger.info(
            f"User {interaction.user.name} ({interaction.user.id}) initiated a trade with everyone. "
            f"Trading card [{card.id}] and offering {candies} candies."
        )

        view = TradeView(interaction.user, None, [card], candies)
        await interaction.response.send_message(
            content=f"{interaction.user.mention} wants to trade",
            file=discord.File(await card.image_bytes(), filename=f"image.{card.format}"),
            embed=view.build_embed(card.format),
            view=view
        )
        view.message = await interaction.original_response()
        await func.check_wishlist(view.message, [card_id])

    @app_commands.command(name="tradepotion", description="Trades your potion with a member for candies.")
    @app_commands.describe(member="The member to trade with", candies="The amount of candies to request", potion_type="speed or luck", potion_level="i, ii, or iii", quantity="How many potions to trade")
    async def tradepotion(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        candies: int,
        potion_type: str,
        potion_level: str,
        quantity: int,
    ):
        if member.bot:
            return await interaction.response.send_message("You are not able to trade with a bot.")
        if member == interaction.user:
            return await interaction.response.send_message("You are not able to trade with yourself.")
        if candies < 0:
            return await interaction.response.send_message("The candy count cannot be set to a negative value.")
        if quantity <= 0:
            return await interaction.response.send_message("Potion quantity must be at least 1.")

        potion_name = self._parse_potion_name(potion_type, potion_level)
        if not potion_name:
            return await interaction.response.send_message("Invalid potion type or level. Use `speed/luck` with level `i/ii/iii`.")

        seller = await func.get_user(interaction.user.id)
        seller_potion_amount = seller.get("potions", {}).get(potion_name, 0)
        if seller_potion_amount < quantity:
            return await interaction.response.send_message(f"You only have `{seller_potion_amount}` of `{potion_name}`.", ephemeral=True)

        func.logger.info(
            f"User {interaction.user.name}({interaction.user.id}) initiated potion trade with {member.name}({member.id}). "
            f"Potion [{potion_name}] x{quantity} for {candies} candies."
        )

        view = PotionTradeView(interaction.user, member, potion_name, quantity, candies)
        await interaction.response.send_message(
            content=f"{member.mention}, {interaction.user.mention} want to trade with you.",
            embed=view.build_embed(),
            view=view,
        )
        view.message = await interaction.original_response()

    @app_commands.command(name="tradepotioneveryone", description="Trades your potion with everyone for candies.")
    @app_commands.describe(candies="The amount of candies to request", potion_type="speed or luck", potion_level="i, ii, or iii", quantity="How many potions to trade")
    async def tradepotioneveryone(
        self,
        interaction: discord.Interaction,
        candies: int,
        potion_type: str,
        potion_level: str,
        quantity: int,
    ):
        if candies < 0:
            return await interaction.response.send_message("The candy count cannot be set to a negative value.")
        if quantity <= 0:
            return await interaction.response.send_message("Potion quantity must be at least 1.")

        potion_name = self._parse_potion_name(potion_type, potion_level)
        if not potion_name:
            return await interaction.response.send_message("Invalid potion type or level. Use `speed/luck` with level `i/ii/iii`.")

        seller = await func.get_user(interaction.user.id)
        seller_potion_amount = seller.get("potions", {}).get(potion_name, 0)
        if seller_potion_amount < quantity:
            return await interaction.response.send_message(f"You only have `{seller_potion_amount}` of `{potion_name}`.", ephemeral=True)

        func.logger.info(
            f"User {interaction.user.name}({interaction.user.id}) initiated potion trade with everyone. "
            f"Potion [{potion_name}] x{quantity} for {candies} candies."
        )

        view = PotionTradeView(interaction.user, None, potion_name, quantity, candies)
        await interaction.response.send_message(
            content=f"{interaction.user.mention} wants to trade",
            embed=view.build_embed(),
            view=view,
        )
        view.message = await interaction.original_response()

    @app_commands.command(name="upgrade", description="Use cards of the same type to upgrade your card's star rating.")
    @app_commands.describe(upgrade_card_id="The card ID to upgrade")
    async def upgrade(self, interaction: discord.Interaction, upgrade_card_id: str) -> None:
        upgrade_card = iufi.CardPool.get_card(upgrade_card_id)
        if not upgrade_card:
            return await interaction.response.send_message("The card was not found. Please try again.")

        if upgrade_card.owner_id != interaction.user.id:
            return await interaction.response.send_message("You are not the owner of this card.")

        if upgrade_card.stars >= 10:
            return await interaction.response.send_message("Your card has reached the maximum number of stars")

        async def on_ids(modal_interaction: discord.Interaction, card_ids: list[str]):
            converted_cards: list[iufi.Card] = []
            for card_id in card_ids:
                card = iufi.CardPool.get_card(card_id)
                if card and upgrade_card.id != card.id and card.owner_id == modal_interaction.user.id and card.tier[1] == upgrade_card.tier[1]:
                    converted_cards.append(card)

            converted_cards = converted_cards[:(10 - upgrade_card.stars)]
            if not converted_cards:
                return await modal_interaction.response.send_message("There are no card can applied into your card.")

            for card in converted_cards:
                iufi.CardPool.add_available_card(card)

            query = func.update_quest_progress(
                await func.get_user(modal_interaction.user.id),
                "UPGRADE_CARD",
                progress=len(converted_cards),
                query={"$pull": {"cards": {"$in": (converted_ids := [card.id for card in converted_cards])}}}
            )
            await func.update_user(modal_interaction.user.id, query)
            await func.update_card(converted_ids, {"$set": {"owner_id": None, "tag": None, "frame": None, "last_trade_time": 0}})
            upgraded_stars = upgrade_card.stars + len(converted_cards)

            func.logger.info(
                f"User {modal_interaction.user.name} ({modal_interaction.user.id}) upgraded a card [{upgrade_card.id}] from {upgrade_card.stars} to {upgraded_stars}). "
                f"With cards: [{', '.join([card.id for card in converted_cards])}]"
            )

            embed = discord.Embed(title="🆙 Upgraded", color=discord.Color.random())
            embed.description = f"```🆔 {upgrade_card} <- {', '.join([f'{card}' for card in converted_cards])}\n⭐ {upgraded_stars} <- {upgrade_card.stars}```"
            await modal_interaction.response.send_message(embed=embed)

            upgrade_card.change_stars(upgraded_stars)

        modal = MultiIDModal(title="Upgrade Card", label="Card IDs to consume", callback=on_ids)
        await interaction.response.send_modal(modal)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Card(bot))
