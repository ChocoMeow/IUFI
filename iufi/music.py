import asyncio, time, discord, youtube_dl
import functions as func

from discord.ext import commands

from typing import (
    Optional,
    List,
    Dict,
)

from discord import (
    PCMVolumeTransformer,
    FFmpegPCMAudio,
    VoiceProtocol,
    VoiceClient,
    VoiceChannel,
    TextChannel,
    Message,
    Guild,
    Embed,
    Color
)

from .pool import MusicPool

YTDL_FORMAT_OPTIONS: Dict[str, str] = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

FFMPEG_OPTIONS: Dict[str, str] = {
    'options': '-vn',
}

YTDL = youtube_dl.YoutubeDL(YTDL_FORMAT_OPTIONS)

class InteractionView(discord.ui.View):
    def __init__(self, player, timeout: float = None) -> None:
        super().__init__(timeout=timeout)

        self.player: Player = player
        self.likes: list[int] = []

    def update_btn(self, btn_name: str, disabled: bool) -> None:
        for child in self.children:
            if child.label == btn_name:
                child.disabled = disabled
                return

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user not in self.player.channel.members:
            await interaction.response.send_message(f"Join {self.player.channel.mention} to play IUFI Music!", ephemeral=True)
            return False
        return True
    
    @discord.ui.button(emoji="❤️")
    async def love(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.likes:
            self.likes.append(interaction.user.id)
            return await interaction.response.send_message("You have already liked this song!", ephemeral=True)
        
        await interaction.response.defer()
        current = self.player.current
        if current:
            current.db_data["likes"] += 1

    @discord.ui.button(label="Skip", emoji="⏭️")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.player.stop()

class Track(PCMVolumeTransformer):
    def __init__(self, source, *, data, db_data, volume=0.5):
        super().__init__(source, volume)

        self.data = data
        self.db_data = db_data
        
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: YTDL.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else YTDL.prepare_filename(data)
        return cls(FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data)
    
class Player(VoiceClient):
    """The base player class for IUFI.
       In order to initiate a player, you must pass it in as a cls when you connect to a channel.
       i.e: ```py
       await ctx.author.voice.channel.connect(cls=iufi.Player)
       ```
    """

    def __call__(self, client: commands.Bot, channel: VoiceChannel):
        self.client: commands.Bot = client
        self.channel: VoiceChannel = channel

        return self

    def __init__(
        self, 
        client: Optional[commands.Bot] = None, 
        channel: Optional[VoiceChannel] = None, 
    ):
        self._bot: commands.Bot = client
        self._guild: Optional[Guild] = channel.guild if channel else None
        self._queue: List[Track] = []

        self.text_channel: Optional[TextChannel] = self.bot.get_channel(func.settings.MUSIC_TEXT_CHANNEL)
        self._message: Optional[Message] = None
        self._current: Track = None
    
    async def do_next(self) -> None:
        track = await MusicPool.get_question()

        self.play(track, after=self.do_next)

    async def seek(self) -> None:
        ...

    async def stop(self) -> None:
        ...

    async def disconnect(self) -> None:
        ...

    async def teardown(self) -> None:
        ...
    
    async def check_answer(self, message: Message) -> None:
        if self.guesser and self.current:
            return
        
        time_used = time.time() - self.time_used
        result = self.current.check_answer(message.content)
        self.current.update_state(message.author, time_used, result)
        
        if result:
            self.guesser = message.author
            await self.invoke_controller()

            at = self.current.average_time
            points = 2 + (0 if at * (1 - .3) < time_used < at * (1 + .3) else 1 if time_used < at else -1)
            await func.update_user(message.author.id, {"$inc": {"game_state.music_game.points": points}})

            await asyncio.sleep(10)
            await self.stop()

    async def invoke_controller(self) -> None:
        if not self.channel or not self.text_channel:
            return
        
        embed = self.build_embed()
        view = InteractionView(self)
        view.update_btn("Skip", self.guesser is not None)
        
        if not self.message:
            self.message = await self.text_channel.send(embed=embed, view=view)

        elif not await self.is_position_fresh():
            await self.message.delete()
            self.message = await self.text_channel.send(embed=embed, view=view)

        else:
            await self.message.edit(embed=embed, view=view)

    def build_embed(self) -> Embed:
        current: Track = self._current
        if not current:
            return
        
        if not self.guesser:
            title = "What song do you think is on right now?"
            description = "```📀 Song Title: ???\n✅ Correct: ??%\n⏱ Avg Time: ??s\n🏅 Record: ??:??s (????)```"
            thumbnail = "https://cdn.discordapp.com/attachments/1183364758175498250/1202590915093467208/74961f7708c7871fed5c7bee00e76418.png"
        
        else:
            member_id, best_time = current.best_record
            member_name = member.display_name if (member := self.guild.get_member(member_id)) else "???"
            title = f"{self.guesser.display_name}, You guessed it right!"
            description = f"**To hear more: [Click Me]({current.uri})**\n```📀 Song Title: {current.title}\n\n✅ Correct: {current.correct_rate:.1f}%\n🕓 Avg Time: {current.average_time:.1f}s\n🏅 Record: {member_name}s ({func.convert_seconds(best_time)})```"
            thumbnail = current.thumbnail

        embed = Embed(title=title, description=description, color=Color.random())
        embed.set_thumbnail(url=thumbnail)

        return embed
    
    @property
    def bot(self) -> Optional[commands.Bot]:
        return self._bot
    
    @property
    def guild(self) -> Optional[Guild]:
        return self._guild
    
    @property
    def current(self) -> Optional[Track]:
        return self._current
    
    def __repr__(self):
        return (
            f"<IUFI.player bot={self.bot} guildId={self.guild.id} "
            f"is_playing={self.is_playing}>"
        )