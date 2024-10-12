import asyncio, time, discord, random, math
import functions as func

from discord.ext import commands

from typing import (
    Optional,
    Union,
    List,
    Dict,
    Any
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
    def __init__(self, player) -> None:
        super().__init__(timeout=player.current.duration // 2)

        self.player: Player = player
        self.current: Track = self.player.current
        self.likes = set()

        self.response: Message = None

    def update_btn(self, btn_name: str, disabled: bool) -> None:
        for child in self.children:
            if child.label == btn_name:
                child.disabled = disabled
                return

    async def on_timeout(self) -> None:
        for child in self.children:
            child.TextStyle = discord.ButtonStyle.grey
            child.disabled = True
        
        try:
            await self.response.edit(view=self)
        except:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.player.current != self.current:
            return await interaction.response.defer()
        
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
        if self.player._is_skipping:
            return

        if (time.time() - self.player.start_guess_time) < 10:
            return await interaction.response.send_message("The music just started, so we can't skip it right now!", ephemeral=True)
        
        if interaction.user in self.player.skip_votes:
            return await interaction.response.send_message("You have voted!", ephemeral=True)
        
        self.player.skip_votes.add(interaction.user)
        if len(self.player.skip_votes) < (required := self.player.required()):
            return await interaction.response.send_message(f"{interaction.user} has voted to skip the song. [{len(self.player.skip_votes)}/{required}]")

        await interaction.response.defer()
        await self.player.stop()

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
        self._max_history_size: int = int(len(MusicPool._questions) * .7)
        self._is_skipping: bool = False

        self.start_guess_time: float = 0
        self.track_start_time: float = 0
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
            self.track_start_time = random.uniform(track.duration * 0.2, track.duration * 0.6)

            # Set the current track and play it
            self._current = track
            self.voice_client.play(await track.source(self.track_start_time), after=lambda e: self.bot.loop.create_task(self.skip_song()))
            
            # Update guesser, history and track usage time
            self.guesser = None
            self.start_guess_time = time.time()
            self.add_to_history(track)
            
            self.skip_votes.clear()
            self._is_skipping = False

            view = InteractionView(self)
            view.response = await self._text_channel.send(embed=self.build_embed(), view=view)

            func.logger.info(f"Music Quiz is now playing: {track.title}")

        except Exception as e:
            func.logger.error("Error in do_next", exc_info=e)
    
    async def check_answer(self, message: Message) -> None:
        async with self._lock:
            if not self.current or self.guesser:
                return 
            
            time_used = time.time() - self.start_guess_time
            result = self.current.check_answer(message.content)
            self.current.update_state(message.author, time_used, result)

            if result:
                self.guesser = message.author
                await self.calculate_reward(message, time_used)
                await self._text_channel.send(embed=self.build_embed(True))

                if not self._is_skipping and (self.current.duration - self.track_start_time - time_used) > (func.settings.MUSIC_GAME_SETTINGS["next_song_interval"] + 5):
                    self._is_skipping = True
                    asyncio.create_task(self.stop(func.settings.MUSIC_GAME_SETTINGS["next_song_interval"]))

    async def calculate_reward(self, message: Message, time_used: float) -> None:
        at = self.current.average_time
        points = 2 + (0 if at * (1 - .3) < time_used < at * (1 + .3) else 1 if time_used < at else -1)

        user = await func.get_user(message.author.id)
        last_points: int = user.get("game_state", {}).get("music_game", {}).get("points", 0)

        # Prepare the query for updating points and rewards
        query: Dict[str, Any] = {"$inc": {"game_state.music_game.points": points}}
        rewards: Dict[str, Dict[str, Union[str, int]]] = {}

        # Calculate milestones and rewards
        for game_reward in func.settings.MUSIC_GAME_SETTINGS["GAME_REWARDS"]:
            last_milestone = last_points // game_reward["amount"]
            current_milestone = (last_points + points) // game_reward["amount"]

            # Check if the user has reached a new milestone
            if current_milestone > last_milestone:
                for reward in game_reward["rewards"]:
                    if isinstance(reward[0], list):
                        reward = random.choice(reward)
                    r_emoji, r_name, r_amount = reward

                    # Update the query for rewards
                    query["$inc"][r_name] = query["$inc"].get(r_name, 0) + r_amount

                    # Update rewards with emoji and amount
                    rewards[r_name] = rewards.setdefault(r_name, {"emoji": r_emoji, "amount": 0})
                    rewards[r_name]["amount"] += r_amount

        # Prepare reward message
        reward_message = ""
        for reward_name, reward_data in rewards.items():
            r_display_name = reward_name.split(".")
            r_emoji, r_amount = reward_data["emoji"], reward_data["amount"]

            if len(r_display_name) == 1:
                reward_message += f"{r_emoji} {r_display_name[0].title():<18} x{reward_data["amount"]}\n"
            else:
                reward_parts = r_display_name[1].split("_")
                format_name = f"{reward_parts[0].title()}" if len(reward_parts) == 1 else f"{reward_parts[0].title()} {reward_parts[1].upper()}"
                reward_message += f"{r_emoji} {f'{format_name} {r_display_name[0].title()}':<18} x{r_amount}\n"

        # Update user data in the database
        await func.update_user(message.author.id, query)
        func.logger.info(f"User {message.author.name}({message.author.id}) earned {points} points in the music quiz by answering in {time_used:.2f} seconds.")

        # Create and send the response embed
        embed = Embed(title="Music Quiz Reward", description=f"```{reward_message}```", color=Color.random()) if reward_message else None
        await message.reply(
            random.choice(MESSAGES).format(time=func.convert_seconds(time_used), points=points),
            embed=embed
        )

    async def connect(self, *, reconnect: bool, timeout: float, self_deaf: bool = False, self_mute: bool = False) -> None:
        await self.channel.connect(reconnect=reconnect, timeout=timeout, self_deaf=self_deaf, self_mute=self_mute)

    async def skip_song(self) -> None:
        if not self.guesser:
            await self._text_channel.send(embed=self.build_embed(True))

        await self.do_next()

    async def stop(self, after_seconds: int = None) -> None:
        if not self.voice_client:
            return
        
        if after_seconds:
            await asyncio.sleep(after_seconds)
        return self.voice_client.stop()
    
    async def teardown(self) -> None:
        if self.voice_client:
            await self.voice_client.disconnect()
    
    def build_embed(self, show_answer: bool = False) -> Embed:
        current: Track = self._current
        if not current:
            return
        
        if not show_answer:
            title = "What song do you think is on right now?"
            description = "```📀 Song Title: ???\n🎤 Singer: ??\n🖼️ Album: ??\n✅ Correct: ??%\n⏱ Avg Time: ??s\n🏅 Record: ??:??s (????)```"
            thumbnail = "https://cdn.discordapp.com/attachments/1183364758175498250/1202590915093467208/74961f7708c7871fed5c7bee00e76418.png"
        
        else:
            member_id, best_time = current.best_record
            member_name = member.display_name if member_id and (member := self.guild.get_member(member_id)) else "???"
            title = f"{self.guesser.display_name}, You guessed it right!" if self.guesser else "No one seems to have the answer just yet"
            description = f"**To hear more: [Click Me]({current.url})**\n```📀 Song Title: {current.title}\n\n🎤 Singer: {', '.join(current.artists)}\n🖼️ Album: {current.album}\n✅ Correct: {current.correct_rate:.1f}%\n🕓 Avg Time: {func.convert_seconds(current.average_time)}\n🏅 Record: {member_name} ({func.convert_seconds(best_time)})```"
            thumbnail = current.thumbnail

        embed = Embed(title=title, description=description, color=Color.random())
        embed.set_thumbnail(url=thumbnail)

        return embed
    
    def add_to_history(self, track: Track):
        """Add a track ID to the history, removing the oldest entry if the history exceeds half the size of the MusicPool's questions."""
        if len(self._history) >= self._max_history_size:
            self._history.pop(0)  # Remove the oldest element
        self._history.append(track.id)  # Add the new track id

    def required(self):
        return math.ceil((len(self.channel.members) - 1) / 2.5)
    
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
        if not self.voice_client:
            return False
        return self.voice_client.is_playing()
    
    @property
    def is_paused(self) -> bool:
        if not self.voice_client:
            return False
        return self.voice_client.is_paused()
    
    @property
    def is_connected(self) -> bool:
        if not self.voice_client:
            return False
        return self.voice_client.is_connected()
    
    @property
    def voice_client(self) -> Optional[VoiceClient]:
        return self._guild.voice_client
    
    @property
    def channel(self) -> Optional[VoiceChannel]:
        return self._channel
        
    def __repr__(self):
        return (f"<IUFI.player bot={self.bot} guildId={self.guild.id}")