import asyncio, time, discord, random, math
import functions as func

from discord.ext import commands

from typing import (
    Optional,
    List,
)

from discord import (
    VoiceClient,
    VoiceProtocol,
    VoiceChannel,
    TextChannel,
    Message,
    Guild,
    Embed,
    Member,
    Color
)

from .objects import Track

from .pool import MusicPool

MESSAGES = [
    "Yay! You got it in `{time}`! 🎉 You've gained `{points}` points! 🎶",
    "Wow, you nailed it in just `{time}`! 🎊 That's amazing! You've earned `{points}` points! 🎤",
    "You’re so good at this! 🌟 You guessed it in `{time}` and gained `{points}` points! 🎵",
    "Awesome! You did it in `{time}`! This song is truly a classic! You've earned `{points}` points! 👏",
    "Yes! You guessed the song in `{time}`! Keep shining! You've gained `{points}` points! 🙌",
    "Spot on! You really know your stuff—guessed it in `{time}` and earned `{points}` points! 🎧",
    "You’re on fire! 🚀 You got it in `{time}` and gained `{points}` points! 🔥",
    "Well done! You have such a great ear for music—guessed it in `{time}` and earned `{points}` points! 🎉",
    "Oh wow, you got it right in `{time}`! 🎶 You're really impressive! You've gained `{points}` points! 🥳",
    "Fantastic! You guessed it in `{time}`! You're totally in sync with the music and gained `{points}` points! 🌈"
]

class InteractionView(discord.ui.View):
    def __init__(self, player, timeout: float = None) -> None:
        super().__init__(timeout=timeout)

        self.player: Player = player
        self.likes = set()

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
        await interaction.response.defer()

        current = self.player.current
        if interaction.user in self.likes or not current:
            return
        
        self.likes.add(interaction.user)
        if current:
            current.data["likes"] += 1

    @discord.ui.button(label="Skip", emoji="⏭️")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if (time.time() - self.player.time_used) < 10:
            return await interaction.response.send_message("The music just started, so we can't skip it right now!", ephemeral=True)
        
        if interaction.user in self.player.skip_votes:
            return await interaction.response.send_message("You have voted!", ephemeral=True)
        
        self.player.skip_votes.add(interaction.user)
        if len(self.player.skip_votes) < (required := self.player.required()):
            return await interaction.response.send_message(f"{interaction.user} has voted to skip the song. [{len(self.player.skip_votes)}/{required}]")

        await interaction.response.defer()
        self.player.stop()

class Player(VoiceProtocol):
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
        self._channel: Optional[VoiceChannel] = channel
        self._guild: Optional[Guild] = channel.guild if channel else None
        self._lock: asyncio.Lock = asyncio.Lock()

        self._text_channel: Optional[TextChannel] = self.bot.get_channel(func.settings.MUSIC_TEXT_CHANNEL)
        self._message: Optional[Message] = None
        self._current: Track = None
        self._history: List[str] = []
        self._is_updating: bool = False

        self.time_used: float = 0
        self.guesser: Member = None

        self.skip_votes = set()

    async def do_next(self) -> None:
        try:
            # Check if the bot is connected and ready to play
            if not self.is_connected or self.is_playing or not self.channel:
                return

            # Fetch a random track, checking history
            track = await MusicPool.get_random_question(self._history)
            if not track:
                return await self.teardown()

            if not track.is_loaded:
                await track.load_data()

            # Determine a random start time within the track's duration
            start_time = random.uniform(track.duration * 0.2, track.duration * 0.6)

            # Set the current track and play it
            self._current = track
            self.voice_client.play(await track.source(start_time), after=lambda e: self.bot.loop.create_task(self.do_next()))
            
            # Update guesser, history and track usage time
            self.guesser = None
            self.time_used = time.time()
            self.add_to_history(track)
            
            self.skip_votes.clear()

            await self.invoke_controller()

            func.logger.info(f"Music Quiz is now playing: {track.title}")

        except Exception as e:
            func.logger.error("Error in do_next", exc_info=e)

    async def is_position_fresh(self):
        try:
            async for message in self._text_channel.history(limit=5):
                if message.id == self._message.id:
                    return True
        except:
            pass

        return False
    
    async def invoke_controller(self) -> None:
        if self._is_updating or not self.channel or not self._text_channel:
            return
        
        self._is_updating = True

        embed = self.build_embed()
        view = InteractionView(self)
        view.update_btn("Skip", self.guesser is not None)
        
        if not self._message:
            self._message = await self._text_channel.send(embed=embed, view=view)

        elif not await self.is_position_fresh():
            await self._message.delete()
            self._message = await self._text_channel.send(embed=embed, view=view)

        else:
            await self._message.edit(embed=embed, view=view)

        self._is_updating = False

    async def check_answer(self, message: Message) -> None:
        async with self._lock:
            if self.guesser and self.current:
                return
            
            time_used = time.time() - self.time_used
            result = self.current.check_answer(message.content)
            self.current.update_state(message.author, time_used, result)

            if result:
                self.guesser = message.author
                at = self.current.average_time
                points = 2 + (0 if at * (1 - .3) < time_used < at * (1 + .3) else 1 if time_used < at else -1)
                query = func.update_quest_progress(
                    await func.get_user(message.author.id),
                    "PLAY_MUSIC_QUIZ_GAME",
                    progress=points,
                    query={"$inc": {"game_state.music_game.points": points}}
                )
                await func.update_user(message.author.id, query)

                func.logger.info(f"User {message.author.name}({message.author.id}) earned {points} points in the music quiz by answering in {time_used:.2f} seconds.")

                await message.reply(random.choice(MESSAGES).format(time=func.convert_seconds(time_used), points=points))
                await self.invoke_controller()

                await asyncio.sleep(10)
                self.stop()

    async def connect(self, *, reconnect: bool, timeout: float, self_deaf: bool = False, self_mute: bool = False) -> None:
        await self.channel.connect(reconnect=reconnect, timeout=timeout, self_deaf=self_deaf, self_mute=self_mute)

    async def teardown(self) -> None:
        try:
            await self._message.delete()
        except:
            pass
        await self.voice_client.disconnect()
    
    def build_embed(self) -> Embed:
        current: Track = self._current
        if not current:
            return
        
        if not self.guesser:
            title = "What song do you think is on right now?"
            description = "```📀 Song Title: ???\n🎤 Singer: ??\n🖼️ Album: ??\n✅ Correct: ??%\n⏱ Avg Time: ??s\n🏅 Record: ??:??s (????)```"
            thumbnail = "https://cdn.discordapp.com/attachments/1183364758175498250/1202590915093467208/74961f7708c7871fed5c7bee00e76418.png"
        
        else:
            member_id, best_time = current.best_record
            member_name = member.display_name if (member := self.guild.get_member(member_id)) else "???"
            title = f"{self.guesser.display_name}, You guessed it right!"
            description = f"**To hear more: [Click Me]({current.url})**\n```📀 Song Title: {current.title}\n\n🎤 Singer: {', '.join(current.artists)}\n🖼️ Album: {current.album}\n✅ Correct: {current.correct_rate:.1f}%\n🕓 Avg Time: {func.convert_seconds(current.average_time)}\n🏅 Record: {member_name} ({func.convert_seconds(best_time)})```"
            thumbnail = current.thumbnail

        embed = Embed(title=title, description=description, color=Color.random())
        embed.set_thumbnail(url=thumbnail)

        return embed
    
    def add_to_history(self, track: Track):
        """Check if the history exceeds 10 elements"""
        if len(self._history) >= 1:
            self._history.pop(0)  # Remove the oldest element
        self._history.append(track.id)  # Add the new track id

    def required(self, leave=False):
        return math.ceil((len(self.channel.members) - 1) / 2.5)
    
    def stop(self) -> None:
        return self.voice_client.stop()
    
    @property
    def bot(self) -> Optional[commands.Bot]:
        return self._bot
    
    @property
    def guild(self) -> Optional[Guild]:
        return self._guild
    
    @property
    def current(self) -> Optional[Track]:
        return self._current
    
    @property
    def is_playing(self) -> bool:
        return self.voice_client.is_playing()
    
    @property
    def is_paused(self) -> bool:
        return self.voice_client.is_paused()
    
    @property
    def is_connected(self) -> None:
        return self.voice_client.is_connected()
    
    @property
    def voice_client(self) -> Optional[VoiceClient]:
        return self._guild.voice_client
    
    @property
    def channel(self) -> Optional[VoiceChannel]:
        return self._channel
        
    def __repr__(self):
        return (f"<IUFI.player bot={self.bot} guildId={self.guild.id}")