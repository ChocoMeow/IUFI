import discord, iufi
import functions as func

from discord.ext import commands

class Listeners(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.emoji = ""
        self.invisible = True

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, member: discord.Member) -> None:
        if guild.id not in [214199357170253834] or member.bot:
            return
        
        user = await func.get_user(member.id, insert=False)
        converted_cards: list[iufi.Card] = []
        for card_id in user["cards"]:
            card = iufi.CardPool.get_card(card_id)
            if card and card.owner_id == member.id:
                iufi.CardPool.add_available_card(card)
                converted_cards.append(card)
                
        await func.update_user(member.id, {
            "$pull": {"cards": {"$in": (card_ids := [card.id for card in converted_cards])}}
        })
        await func.update_card(card_ids, {"$set": {"owner_id": None, "tag": None, "frame": None}})

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Listeners(bot))