import discord, iufi, time
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
        player: iufi.Player | None = iufi.MusicPool.get_player(member.guild.id)

        if joined_voice_channel and after.channel and after.channel.id == func.settings.MUSIC_VOICE_CHANNEL:
            if not player:
                check = after.channel.permissions_for(member.guild.get_member(self.bot.user.id))
                if check.connect == False or check.speak == False:
                    return

                player = iufi.Player(self.bot, after.channel)
                await iufi.MusicPool.add_player(member.guild.id, player)
                await player.connect(reconnect=True, timeout=30, self_deaf=True)

            player.last_answer_time = time.time()
            if not player.is_playing:
                await player.do_next()

        elif before.channel and before.channel.id == func.settings.MUSIC_VOICE_CHANNEL:
            if not player:
                return
            
            members = player.channel.members
            if not any(False if member.bot or member.voice.self_deaf else True for member in members):
                await player.teardown()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.member.bot or payload.channel_id!= func.settings.GALLERY_CHANNEL:
            return
        
        if payload.message_author_id != self.bot.user.id:
            return
        
        if payload.emoji.name != "📌":
            return
        
        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        reaction = discord.utils.get(message.reactions, emoji=payload.emoji.name)
        if reaction and reaction.count >= 15 and not message.pinned:
            await message.pin(reason="Player has cast more than 15 votes to pin this collection.")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Listeners(bot))