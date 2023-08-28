import discord, iufi, time
import functions as func

from discord.ext import commands
from PIL import Image
from io import BytesIO
from views import RollView, PhotoCardView, ShopView

MAX_CARDS = 100

def gen_cards_view(cards: list[iufi.Card]) -> BytesIO:
    # Create a new image for output
    padding = 10
    card_width = cards[0].image.width
    output_image = Image.new('RGBA', ((card_width * len(cards)) + (padding * (len(cards) - 1)), cards[0].image.height), (0, 0, 0, 0))

    # # Paste images into the output image with 10 pixels padding
    space = 0
    for card in cards:
        output_image.paste(card.image, (space, 0))
        space += card.image.width + padding

    resized_image_bytes = BytesIO()
    output_image.save(resized_image_bytes, format='PNG')
    resized_image_bytes.seek(0)

    return resized_image_bytes

class Basic(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(aliases=["r"])
    async def roll(self, ctx: commands.Context):
        retry = func.check_user_cooldown(ctx.author.id)
        if retry:
            return await ctx.reply(f"{ctx.author.mention} your next roll is in {retry}", delete_after=5)
        
        if ctx.author.id in func.USERS_LOCK:
            return
        func.USERS_LOCK.append(ctx.author.id)

        cards = iufi.CardPool.roll()
        resized_image_bytes = gen_cards_view(cards)

        view = RollView(ctx.author, cards)
        view.message = await ctx.send(
            content=f"**{ctx.author.mention} This is your roll!**",
            file=discord.File(resized_image_bytes, filename='image.png'),
            view=view
        )
        func.update_user(ctx.author.id, {"$set": {"cooldown.roll": time.time() + func.COOLDOWN_BASE["roll"]}})
        await view.timeout_count()
        await view.wait()

        if ctx.author.id in func.USERS_LOCK:
            func.USERS_LOCK.remove(ctx.author.id)

    @commands.command(aliases=["rr"])
    async def rareroll(self, ctx: commands.Context):
        if ctx.author.id in func.USERS_LOCK:
            return
        func.USERS_LOCK.append(ctx.author.id)
        
        user = func.get_user(ctx.author.id)
        if user["roll"]["rare"] <= 0:
            return await ctx.reply("You’ve used up all your rare rolls for now.")

        cards = iufi.CardPool.roll(included="rare")
        resized_image_bytes = gen_cards_view(cards)

        view = RollView(ctx.author, cards)
        view.message = await ctx.send(
            content=f"**{ctx.author.mention} This is your roll!**",
            file=discord.File(resized_image_bytes, filename='image.png'),
            view=view
        )

        func.update_user(ctx.author.id, {"$inc": {"roll.rare": -1}})
        await view.timeout_count()
        await view.wait()

        if ctx.author.id in func.USERS_LOCK:
            func.USERS_LOCK.remove(ctx.author.id)

    @commands.command(aliases=["er"])
    async def epicroll(self, ctx: commands.Context):
        if ctx.author.id in func.USERS_LOCK:
            return
        func.USERS_LOCK.append(ctx.author.id)
        
        user = func.get_user(ctx.author.id)
        if user["roll"]["epic"] <= 0:
            return await ctx.reply("You’ve used up all your epic rolls for now.")

        cards = iufi.CardPool.roll(included="epic")
        resized_image_bytes = gen_cards_view(cards)

        view = RollView(ctx.author, cards)
        view.message = await ctx.send(
            content=f"**{ctx.author.mention} This is your roll!**",
            file=discord.File(resized_image_bytes, filename='image.png'),
            view=view
        )
        func.update_user(ctx.author.id, {"$inc": {"roll.epic": -1}})
        await view.timeout_count()
        await view.wait()

        if ctx.author.id in func.USERS_LOCK:
            func.USERS_LOCK.remove(ctx.author.id)
        
    @commands.command(aliases=["lr"])
    async def legendroll(self, ctx: commands.Context):
        if ctx.author.id in func.USERS_LOCK:
            return
        func.USERS_LOCK.append(ctx.author.id)
        
        user = func.get_user(ctx.author.id)
        if user["roll"]["legendary"] <= 0:
            return await ctx.reply("You’ve used up all your epic rolls for now.")

        cards = iufi.CardPool.roll(included="legendary")
        resized_image_bytes = gen_cards_view(cards)

        view = RollView(ctx.author, cards)
        view.message = await ctx.send(
            content=f"**{ctx.author.mention} This is your roll!**",
            file=discord.File(resized_image_bytes, filename='image.png'),
            view=view
        )
        func.update_user(ctx.author.id, {"$inc": {"roll.legendary": -1}})
        await view.timeout_count()
        await view.wait()

        if ctx.author.id in func.USERS_LOCK:
            func.USERS_LOCK.remove(ctx.author.id)

    @commands.command(aliases=["v"])
    async def view(self, ctx: commands.Context):
        user = func.get_user(ctx.author.id)

        if not user["cards"]:
            return await ctx.reply(f"**{ctx.author.mention} you have no photocards.**", delete_after=5)

        view = PhotoCardView(ctx.author, user['cards'])
        view.message = await ctx.reply(content="", embed=view.build_embed(), view=view)

    @commands.command(aliases=["in"])
    async def inventory(self, ctx: commands.Context):
        user = func.get_user(ctx.author.id)

        embed = discord.Embed(title=f"🎒 {ctx.author.display_name}'s Inventory", color=0x5cb045)
        embed.description = f"```🍬 Starcandies        x{user['candies']}\n" \
                            f"🌸 Rare rolls         x{user['roll']['rare']}\n" \
                            f"💎 Epic rolls         x{user['roll']['epic']}\n" \
                            f"👑 Legend rolls       x{user['roll']['legendary']}\n" \
                            f"🛠️ Upgrades           Coming Soon\n\n" \
                            f"🖼️ Frames\nComing Soon```"
        embed.set_thumbnail(url=ctx.author.avatar.url)
        await ctx.reply(content="", embed=embed)

    @commands.command(aliases=["cd"])
    async def cooldown(self, ctx: commands.Context):
        user = func.get_user(ctx.author.id)

        embed = discord.Embed(title=f"⏰ {ctx.author.display_name}'s Cooldowns", color=0x59b0c0)
        embed.description = f"```🎲 Roll : {func.cal_retry_time(user['cooldown']['roll'], 'Ready')}\n" \
                            f"🎮 Claim: {func.cal_retry_time(user['cooldown']['claim'], 'Ready')}\n" \
                            f"📅 Daily: {func.cal_retry_time(user['cooldown']['daily'], 'Ready')}```"
        
        embed.set_thumbnail(url=ctx.author.avatar.url)
        await ctx.reply(content="", embed=embed)

    @commands.command(aliases=["i"])
    async def info(self, ctx: commands.Context, card_id: str):
        card: iufi.Card = iufi.CardPool.get_card(card_id)
        if not card:
            return await ctx.reply("The card was not found. Please try again.")
        
        embed = discord.Embed(title=f"ℹ️ Card Info", color=0x949fb8)
        embed.description = f"```🆔 {card.id.zfill(5)}\n" \
                            f"🏷️ {card.tag}\n" \
                            f"{card.tier[0]} {card.tier[1].capitalize()}\n" \
                            f"⭐ {card.stars}```\n" \
                            "Owned by: " + (f"<@{card.owner_id}>" if card.owner_id else "None")
        
        resized_image_bytes = BytesIO()
        card.image.save(resized_image_bytes, format='PNG')
        resized_image_bytes.seek(0)

        embed.set_image(url="attachment://image.png")
        await ctx.reply(content="", file=discord.File(resized_image_bytes, filename="image.png"), embed=embed)

    @commands.command(aliases=["il"])
    async def info_last(self, ctx: commands.Context):
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
                            f"{card.tier[0]} {card.tier[1].capitalize()}\n" \
                            f"⭐ {card.stars}```\n" \
                            "Owned by: " + (f"<@{card.owner_id}>" if card.owner_id else "None")
        
        resized_image_bytes = BytesIO()
        card.image.save(resized_image_bytes, format='PNG')
        resized_image_bytes.seek(0)

        embed.set_image(url="attachment://image.png")
        await ctx.reply(content="", file=discord.File(resized_image_bytes, filename="image.png"), embed=embed)

    @commands.command(aliases=["c"])
    async def convert(self, ctx: commands.Context, *, card_ids: str):
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
        func.update_card(card.id, {"$set": {"owner_id": None, "tag": None}})

        embed = discord.Embed(title="✨ Convert", color=discord.Color.random())
        embed.description = f"```🆔 {', '.join(card_ids)} \n🍬 + {candies}```"
        await ctx.reply(content="", embed=embed)

    @commands.command(aliases=["cl"])
    async def convertlast(self, ctx: commands.Context):
        user = func.get_user(ctx.author.id)

        if not user["cards"]:
            return await ctx.reply(f"**{ctx.author.mention} you have no photocards.**", delete_after=5)
        
        card_id = user["cards"][-1]
        card = iufi.CardPool.get_card(card_id)
        if card:
            card.change_owner()
            iufi.CardPool.add_available_card(card)

        func.update_user(ctx.author.id, {
            "$pull": {"cards": card.id},
            "$inc": {"candies": card.cost}
        })
        func.update_card(card.id, {"$set": {"owner_id": None, "tag": None}})

        embed = discord.Embed(title="✨ Convert", color=discord.Color.random())
        embed.description = f"```🆔 {card.id} \n🍬 + {card.cost}```"
        await ctx.reply(content="", embed=embed)

    @commands.command(aliases=["ca"])
    async def convertall(self, ctx: commands.Context):
        user = func.get_user(ctx.author.id)

        if not user["cards"]:
            return await ctx.reply(f"**{ctx.author.mention} you have no photocards.**", delete_after=5)
        
        converted_cards: list[iufi.Card] = []

        for card_id in user["cards"]:
            card = iufi.CardPool.get_card(card_id)
            if card:
                card.change_owner()
                iufi.CardPool.add_available_card(card)
                converted_cards.append(card)

        func.update_user(ctx.author.id, {
            "$pull": {"cards": {"$in": ( card_ids := [card.id for card in converted_cards])}},
            "$inc": {"candies": ( candies := sum([card.cost for card in converted_cards]))}
        })
        func.update_card(card_ids, {"$set": {"owner_id": None, "tag": None}})

        embed = discord.Embed(title="✨ Convert", color=discord.Color.random())
        embed.description = f"```🆔 {', '.join(card_ids)} \n🍬 + {candies}```"
        await ctx.reply(content="", embed=embed)
    
    @commands.command(aliases=["st"])
    async def settag(self, ctx: commands.Context, card_id: str, tag: str):
        if tag and len(tag) >= 10:
            return await ctx.reply(content="Please shorten the tag name as it is too long.")

        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await ctx.reply("The card was not found. Please try again.")

        if card.owner_id != ctx.author.id:
            return await ctx.reply("You are not the owner of this card.")
        
        if card.tag:
            iufi.CardPool.change_tag(card, tag)
        else:
            iufi.CardPool.add_tag(card, tag)
        
        embed = discord.Embed(title="🏷️ Set Tag", color=discord.Color.random())
        embed.description = f"```🆔 {card.id}\n🏷️ {tag}```"
        await ctx.reply(content="", embed=embed)

    @commands.command(aliases=["stl"])
    async def settaglast(self, ctx: commands.Context, tag: str):
        if tag and len(tag) >= 10:
            return await ctx.reply(content="Please shorten the tag name as it is too long.")
        
        user = func.get_user(ctx.author.id)
        if not user["cards"]:
            return await ctx.reply(f"**{ctx.author.mention} you have no photocards.**", delete_after=5)
        
        card_id = user["cards"][-1]
        card = iufi.CardPool.get_card(card_id)
        if card:
            if card.tag:
                iufi.CardPool.change_tag(card, tag)
            else:
                iufi.CardPool.add_tag(card, tag)
        
            embed = discord.Embed(title="🏷️ Set Tag", color=discord.Color.random())
            embed.description = f"```🆔 {card.id}\n🏷️ {tag}```"
            await ctx.reply(content="", embed=embed)

    @commands.command(aliases=["rt"])
    async def removetag(self, ctx: commands.Context, card_id: str):
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await ctx.reply("The card was not found. Please try again.")

        if card.owner_id != ctx.author.id:
            return await ctx.reply("You are not the owner of this card.")
        
        iufi.CardPool.remove_tag(card)

        embed = discord.Embed(title="🏷️ Set Tag", color=discord.Color.random())
        embed.description = f"```🆔 {card.id}\n🏷️ {card.tag}```"
        await ctx.reply(content="", embed=embed)

    @commands.command(aliases=["p"])
    async def profile(self, ctx: commands.Context):
        user = func.get_user(ctx.author.id)

        level = 0
        exp = user.get("exp", 0)
        default_exp = 100

        while exp >= default_exp:
            exp -= default_exp
            level += 1

        embed = discord.Embed(title=f"👤 {ctx.author.display_name}'s Profile", color=discord.Color.random())
        embed.description = f"```📙 Photocards: {len(user.get('cards', []))}/{func.MAX_CARDS}\n⚔️ Level: {level} ({(exp/default_exp)*100:.1f}%)```"

        await ctx.reply(content="", embed=embed)

    @commands.command()
    async def shop(self, ctx: commands.Context):
        view = ShopView(ctx.author)
        view.message = await ctx.reply(content="", embed=view.build_embed(), view=view)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Basic(bot))