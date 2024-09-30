import discord, iufi
import functions as func

from discord.ext import commands

class Listeners(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.emoji: str = ""
        self.invisible: bool = True

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, member: discord.Member) -> None:
        if guild.id != func.settings.MAIN_GUILD or member.bot:
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
        
        func.logger.info(f"User {member.name}({member.id}) has been banned from {guild.name}({guild.id}). All their cards will be returned to the card pool.")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        if member.bot:
            return
        
        joined_voice_channel: bool = (not before.channel and after.channel) or (before.channel != after.channel)
        player: iufi.Player | None = member.guild.voice_client

        if joined_voice_channel and after.channel and after.channel.id == func.settings.MUSIC_VOICE_CHANNEL:
            if not player:
                check = after.channel.permissions_for(member.guild.get_member(self.bot.user.id))
                if check.connect == False or check.speak == False:
                    return

                player: iufi.Player = await after.channel.connect(cls=iufi.Player(self.bot, after.channel), self_deaf=True)

            if not player.is_playing:
                await player.do_next()

        elif before.channel and before.channel.id == func.settings.MUSIC_VOICE_CHANNEL:
            if not player:
                return
            
            members = player.channel.members
            if not any(False if member.bot or member.voice.self_deaf else True for member in members):
                await player.teardown()

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Listeners(bot))