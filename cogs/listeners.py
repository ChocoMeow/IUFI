import discord, iufi, asyncio
import functions as func

from discord.ext import commands

class Listeners(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.emoji = ""
        self.invisible = True

        self.iufi = iufi.NodePool()
        bot.loop.create_task(self.start_nodes())

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
        
    async def start_nodes(self) -> None:
        """Connect and intiate nodes."""
        await self.bot.wait_until_ready()
        
        try:
            await self.iufi.create_node(
                bot = self.bot,
                host = "172.18.0.1",
                port = 2332,
                password = "youshallnotpass",
                identifier = "DEFAULT"
            )
            
        except Exception as e:
            print(f'Node DEFAULT is not able to connect! - Reason: {e}')

    @commands.Cog.listener()
    async def on_iufi_track_end(self, player: iufi.Player, track, _):
        await player.do_next()

    @commands.Cog.listener()
    async def on_iufi_track_stuck(self, player: iufi.Player, track, _):
        await asyncio.sleep(10)
        await player.do_next()

    @commands.Cog.listener()
    async def on_iufi_track_exception(self, player: iufi.Player, track, error: dict):
        try:
            player._track_is_stuck = True
            await player.context.send(f"{error['message']}! The next song will begin in the next 5 seconds.", delete_after=10)
        except:
            pass

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Listeners(bot))