import discord, iufi
import functions as func

from discord.ext import commands
from views import (
    ConfirmView,
    TradeView
)

class Card(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "🎴"
        
    @commands.command(aliases=["i"])
    async def cardinfo(self, ctx: commands.Context, *, card_ids: str):
        """Shows the details of a photocard. Card can be identified by its ID or given tag."""
        cards: list[iufi.Card] = []

        card_ids = card_ids.split(" ")
        for card_id in card_ids:
            card = iufi.CardPool.get_card(card_id)
            if card:
                cards.append(card)

        if not cards:
            return await ctx.reply("The card was not found. Please try again.")
        
        if len(cards) > 1:
            desc = "```"
            for card in cards[:8]:
                member = ctx.guild.get_member(card.owner_id)
                desc += f"🆔{card.id.zfill(5)} 🏷️{card.tag if card.tag else '-':<12} 🖼️ {card.frame[0] if [1] else '-  '} ⭐{card.stars} {card.tier[0]} {member.display_name if member else 'None':5}\n"
            desc += "```"

            image_bytes, is_gif = iufi.gen_cards_view(cards, 4)
            image_format = "gif" if is_gif else "png"

        else:
            desc = f"```🆔 {card.id.zfill(5)}\n" \
                   f"🏷️ {card.tag}\n" \
                   f"🖼️ {card.frame[0]}\n" \
                   f"{card.tier[0]} {card.tier[1].capitalize()}\n" \
                   f"⭐ {card.stars}```\n" \
                   "**Owned by: **" + (f"<@{card.owner_id}>" if card.owner_id else "None")

            image_bytes, image_format = card.image_bytes, card.format

        embed = discord.Embed(title=f"ℹ️ Card Info", description=desc, color=0x949fb8)
        embed.set_image(url=f"attachment://image.{image_format}")
        await ctx.reply(file=discord.File(image_bytes, filename=f"image.{image_format}"), embed=embed)

    @commands.command(aliases=["il"])
    async def info_last(self, ctx: commands.Context):
        """Shows the details of your last photocard."""
        user = func.get_user(ctx.author.id)

        if not user["cards"]:
            return await ctx.reply(f"**{ctx.author.mention} you have no photocards.**", delete_after=5)
        
        card_id = user["cards"][-1]
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await ctx.reply("Card not found! Please try again.")
        
        embed = discord.Embed(title=f"ℹ️ Card Info", color=0x949fb8)
        embed.description = f"```🆔 {card.id.zfill(5)}\n" \
                            f"🏷️ {card.tag}\n" \
                            f"🖼️ {card.frame[0]}\n" \
                            f"{card.tier[0]} {card.tier[1].capitalize()}\n" \
                            f"⭐ {card.stars}```\n" \
                            "**Owned by: **" + (f"<@{card.owner_id}>" if card.owner_id else "None")
        
        embed.set_image(url=f"attachment://image.{card.format}")
        await ctx.reply(file=discord.File(card.image_bytes, filename=f"image.{card.format}"), embed=embed)

    @commands.command(aliases=["c"])
    async def convert(self, ctx: commands.Context, *, card_ids: str):
        """Converts the photocards into starcandies. Card can be identified by its ID or given tag. The amount of starcandies received is dependent on the card's rarity."""
        converted_cards: list[iufi.Card] = []

        card_ids = card_ids.split(" ")
        for card_id in card_ids:
            card = iufi.CardPool.get_card(card_id)
            if card and card.owner_id == ctx.author.id:
                card.change_owner()
                iufi.CardPool.add_available_card(card)
                converted_cards.append(card)
        
        func.update_user(ctx.author.id, {
            "$pull": {"cards": {"$in": (card_ids := [card.id for card in converted_cards])}},
            "$inc": {"candies": (candies := sum([card.cost for card in converted_cards]))}
        })
        func.update_card(card_ids, {"$set": {"owner_id": None, "tag": None, "frame": None}})

        embed = discord.Embed(title="✨ Convert", color=discord.Color.random())
        embed.description = f"```🆔 {', '.join([f'{card.tier[0]} {card.id}' for card in converted_cards])} \n🍬 + {candies}```"
        await ctx.reply(embed=embed)

    @commands.command(aliases=["cl"])
    async def convertlast(self, ctx: commands.Context):
        """Converts the last photocard of your collection."""
        user = func.get_user(ctx.author.id)

        if not user["cards"]:
            return await ctx.reply(f"**{ctx.author.mention} you have no photocards.**", delete_after=5)
        
        if not (card := iufi.CardPool.get_card(user["cards"][-1])):
            return
        
        embed = discord.Embed(color=discord.Color.random())
        embed.description = f"```🆔 {card.tier[0]} {card.id} \n🍬 + {card.cost}```"
        message: discord.Message = None

        if card.tier[1] not in ["common", "rare"]:
            embed.title="✨ Confirm to convert?"

            view = ConfirmView(ctx.author)
            view.message = message = await ctx.reply(embed=embed, view=view)
            await view.wait()

            if not view.is_confirm:
                return
            
        if card.owner_id != ctx.author.id:
            return await ctx.reply(content="Your cards cannot be converted because there has been a change in your inventory.")
        
        card.change_owner()
        iufi.CardPool.add_available_card(card)

        func.update_user(ctx.author.id, {
            "$pull": {"cards": card.id},
            "$inc": {"candies": card.cost}
        })
        func.update_card(card.id, {"$set": {"owner_id": None, "tag": None, "frame": None}})
        embed.title="✨ Converted"
        await message.edit(embed=embed, view=None) if message else await ctx.reply(embed=embed)
        
    @commands.command(aliases=["ca"])
    async def convertall(self, ctx: commands.Context):
        """Converts all photocard of your collection."""
        user = func.get_user(ctx.author.id)

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
        embed.description = f"```🆔 {', '.join([f'{card.tier[0]} {card.id}' for card in converted_cards])} \n🍬 + {candies}```"

        view = ConfirmView(ctx.author)
        view.message = await ctx.reply(embed=embed, view=view)
        await view.wait()

        if view.is_confirm:
            if user["cards"] != card_ids:
                return await ctx.reply(content="Your cards cannot be converted because there has been a change in your inventory.", ephemeral=True)
            
            for card in converted_cards:
                card.change_owner()
                iufi.CardPool.add_available_card(card)

            func.update_user(ctx.author.id, {
                "$pull": {"cards": {"$in": card_ids}},
                "$inc": {"candies": candies}
            })
            func.update_card(card_ids, {"$set": {"owner_id": None, "tag": None, "frame": None}})

            embed.title = "✨ Converted"
            await view.message.edit(embed=embed, view=None)
    
    @commands.command(aliases=["cm"])
    async def convertmass(self, ctx: commands.Context, category: str):
        """Converts photocards that fit the given mode."""
        user = func.get_user(ctx.author.id)
        category = category.lower()

        if not user["cards"]:
            return await ctx.reply(f"**{ctx.author.mention} you have no photocards.**", delete_after=5)
        
        converted_cards: list[iufi.Card] = []
        for card_id in user["cards"]:
            card = iufi.CardPool.get_card(card_id)
            if card:
                if category == "notag" and not card.tag:
                    pass
                elif category != card.tier[1]:
                    continue
                converted_cards.append(card)

        card_ids = [card.id for card in converted_cards]
        candies = sum([card.cost for card in converted_cards])
                       
        embed = discord.Embed(title="✨ Confirm to convert?", color=discord.Color.random())
        embed.description = f"```🆔 {', '.join([f'{card.tier[0]} {card.id}' for card in converted_cards])} \n🍬 + {candies}```"

        view = ConfirmView(ctx.author)
        view.message = await ctx.reply(embed=embed, view=view)
        await view.wait()

        if view.is_confirm:
            if not all(elem in user["cards"] for elem in card_ids):
                return await ctx.reply(content="Your cards cannot be converted because there has been a change in your inventory.", ephemeral=True)
            
            for card in converted_cards:
                card.change_owner()
                iufi.CardPool.add_available_card(card)

            func.update_user(ctx.author.id, {
                "$pull": {"cards": {"$in": card_ids}},
                "$inc": {"candies": candies}
            })
            func.update_card(card_ids, {"$set": {"owner_id": None, "tag": None, "frame": None}})

            embed.title = "✨ Converted"
            await view.message.edit(embed=embed, view=None)

    @commands.command(aliases=["st"])
    async def settag(self, ctx: commands.Context, card_id: str, tag: str):
        """Sets the photocard's tag. Card can be identified by its ID or previous tag."""
        if tag and len(tag) >= 10:
            return await ctx.reply(content="Please shorten the tag name as it is too long. (No more than 10 chars)")

        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await ctx.reply("The card was not found. Please try again.")

        if card.owner_id != ctx.author.id:
            return await ctx.reply("You are not the owner of this card.")
        
        if card.tag:
            await iufi.CardPool.change_tag(card, tag)
        else:
            await iufi.CardPool.add_tag(card, tag)
        
        embed = discord.Embed(title="🏷️ Set Tag", color=discord.Color.random())
        embed.description = f"```🆔 {card.tier[0]} {card.id}\n🏷️ {tag}```"
        await ctx.reply(embed=embed)

    @commands.command(aliases=["stl"])
    async def settaglast(self, ctx: commands.Context, tag: str):
        """Sets the tag of the last photocard in your collection."""
        if tag and len(tag) >= 10:
            return await ctx.reply(content="Please shorten the tag name as it is too long.")
        
        user = func.get_user(ctx.author.id)
        if not user["cards"]:
            return await ctx.reply(f"**{ctx.author.mention} you have no photocards.**", delete_after=5)
        
        card_id = user["cards"][-1]
        card = iufi.CardPool.get_card(card_id)
        if card:
            if card.tag:
                await iufi.CardPool.change_tag(card, tag)
            else:
                await iufi.CardPool.add_tag(card, tag)
        
            embed = discord.Embed(title="🏷️ Set Tag", color=discord.Color.random())
            embed.description = f"```🆔 {card.tier[0]} {card.id}\n🏷️ {tag}```"
            await ctx.reply(embed=embed)

    @commands.command(aliases=["rt"])
    async def removetag(self, ctx: commands.Context, card_id: str):
        """Removes the photocard's tag. Card can be identified by its ID or given tag."""
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await ctx.reply("The card was not found. Please try again.")

        if card.owner_id != ctx.author.id:
            return await ctx.reply("You are not the owner of this card.")
        
        await iufi.CardPool.remove_tag(card)

        embed = discord.Embed(title="🏷️ Set Tag", color=discord.Color.random())
        embed.description = f"```🆔 {card.id}\n🏷️ {card.tag}```"
        await ctx.reply(embed=embed)

    @commands.command(aliases=["t"])
    async def trade(self, ctx: commands.Context, member: discord.Member, card_id: str, candies: int):
        """Trades your card with a member."""
        if candies < 0:
            return await ctx.reply("The candy count cannot be set to a negative value.")
        
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await ctx.reply("The card was not found. Please try again.")

        if card.owner_id != ctx.author.id:
            return await ctx.reply("You are not the owner of this card.")
        
        embed = discord.Embed(title="⤵️ Trade", color=discord.Color.random())
        embed.description = f"```Seller: {ctx.author.display_name}\n" \
                            f"Buyer: {member.display_name}\n" \
                            f"Candies: 🍬 {candies}\n\n" \
                            f"🆔 {card.id.zfill(5)}\n" \
                            f"🏷️ {card.tag}\n" \
                            f"🖼️ {card.frame[0]}\n" \
                            f"{card.tier[0]} {card.tier[1].title()}\n" \
                            f"⭐ {card.stars}```\n" \
        
        embed.set_image(url="attachment://image.png")

        view = TradeView(ctx.author, member, card, candies)
        view.message = await ctx.reply(content=f"{member.mention}, {ctx.author.mention} want to trade with you.", file=discord.File(card.image_bytes, filename=f"image.{card.format}"), embed=embed, view=view)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Card(bot))