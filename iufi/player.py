"""MIT License

Copyright (c) 2023 - present Vocard Development

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import time

from math import ceil
from asyncio import sleep

from typing import (
    Any,
    Dict,
    Optional,
    Union
)

from discord import (
    Guild,
    VoiceChannel,
    VoiceProtocol,
    Member,
    ui,
    Message,
    Interaction,
    Embed
)

from discord.ext import commands

from . import musicevents
from .pool import NodePool
from .exceptions import IUFIException
from .objects import Track
from .pool import Node, NodePool
from .musicevents import IUFIMusicEvent, TrackEndEvent, TrackStartEvent

async def connect_channel(ctx: commands.Context, channel: VoiceChannel = None):
    try:
        channel = channel or ctx.author.voice.channel
    except:
        raise IUFIException("No voice channel to connect. Please either provide one or join one.")

    check = channel.permissions_for(ctx.guild.me)
    if check.connect == False or check.speak == False:
        raise IUFIException("Sorry! i don't have permissions to join or speak in your voice channel.")

    player: Player = await channel.connect(cls=Player(ctx.bot, channel, ctx))
    return player

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
        ctx: Union[commands.Context, Interaction] = None,
    ):
        self._bot: commands.Bot = client
        self.context = ctx
        self.channel: VoiceChannel = channel
        self._guild = channel.guild if channel else None

        self._volume: int = 100

        self._node = NodePool.get_node()
        self._current: Track = None
        self._paused: bool = False
        self._is_connected: bool = False
        self._track_is_stuck = False

        self._position: int = 0
        self._last_position: int = 0
        self._last_update: int = 0
        self._ending_track: Optional[Track] = None

        self._voice_state: dict = {}

        self.skip_votes = set()

    def __repr__(self):
        return (
            f"<IUFI.player bot={self.bot} guildId={self.guild.id} "
            f"is_connected={self.is_connected} is_playing={self.is_playing}>"
        )

    @property
    def position(self) -> float:
        """Property which returns the player's position in a track in milliseconds"""
        current = self._current.original

        if not self.is_playing or not self._current:
            return 0

        if self.is_paused:
            return min(self._last_position, current.length)

        difference = (time.time() * 1000) - self._last_update
        position = self._last_position + difference

        if position > current.length:
            return 0

        return min(position, current.length)

    @property
    def is_playing(self) -> bool:
        """Property which returns whether or not the player is actively playing a track."""
        return self._is_connected and self._current is not None

    @property
    def is_connected(self) -> bool:
        """Property which returns whether or not the player is connected"""
        return self._is_connected

    @property
    def is_paused(self) -> bool:
        """Property which returns whether or not the player has a track which is paused or not."""
        return self._is_connected and self._paused

    @property
    def current(self) -> Track:
        """Property which returns the currently playing track"""
        return self._current

    @property
    def node(self) -> Node:
        """Property which returns the node the player is connected to"""
        return self._node

    @property
    def guild(self) -> Guild:
        """Property which returns the guild associated with the player"""
        return self._guild
    
    @property
    def bot(self) -> commands.Bot:
        """Property which returns the bot associated with this player instance"""
        return self._bot

    @property
    def is_dead(self) -> bool:
        """Returns a bool representing whether the player is dead or not.
           A player is considered dead if it has been destroyed and removed from stored players.
        """
        return self.guild.id not in self._node._players

    def required(self, leave = False) -> int:
        required = ceil((len(self.channel.members) - 1) / 2.5)
        if leave:
            if len(self.channel.members) == 3:
                required = 2
        
        return required
    
    def is_user_join(self, user: Member) -> bool:
        if user not in self.channel.members:
            if not user.guild_permissions.manage_guild:
                return False        
        return True
    
    def is_privileged(self, user: Member, check_user_join: bool = True) -> bool:
        manage_perm = user.guild_permissions.manage_guild
        if check_user_join and not self.is_user_join(user):
            raise IUFIException(f"{user.mention}, you must be in {self.channel.mention} to use voice commands. Please rejoin if you are in voice!")
        
        return manage_perm
    
    async def _update_state(self, data: dict) -> None:
        state: dict = data.get("state")
        self._last_update = time.time() * 1000
        self._is_connected = state.get("connected")
        self._last_position = state.get("position")

    async def _dispatch_voice_update(self, voice_data: Dict[str, Any]) -> None:
        if {"sessionId", "event"} != self._voice_state.keys():
            return

        await self._node.send(
            method=0, guild_id=self._guild.id,
            data = {"voice": {
                "token": voice_data['event']['token'],
                "endpoint": voice_data['event']['endpoint'],
                "sessionId": voice_data['sessionId'],
            }}
        )

    async def on_voice_server_update(self, data: dict) -> None:
        self._voice_state.update({"event": data})
        await self._dispatch_voice_update(self._voice_state)

    async def on_voice_state_update(self, data: dict) -> None:
        self._voice_state.update({"sessionId": data.get("session_id")})

        if not (channel_id := data.get("channel_id")):
            await self.teardown()
            self._voice_state.clear()
            return

        self.channel = self.guild.get_channel(int(channel_id))

        if not data.get("token"):
            return

        await self._dispatch_voice_update({**self._voice_state, "event": data})

    async def _dispatch_event(self, data: dict) -> None:
        event_type = data.get("type")
        event: IUFIMusicEvent = getattr(musicevents, event_type)(data, self)

        if isinstance(event, TrackEndEvent) and event.reason != "replaced":
            self._current = None

        event.dispatch(self._bot)

        if isinstance(event, TrackStartEvent):
            self._ending_track = self._current

    async def do_next(self) -> None:
        if self.is_playing or not self.channel:
            return
        
        if self._paused:
            self._paused = False

        if self._track_is_stuck:
            await sleep(10)
            self._track_is_stuck = False

        if not self.guild.me.voice:
            await self.connect(timeout=0.0, reconnect=True)
        
        track: Track = await self._node.pool.get_question()
        print(f"Now is playing: {track.title}")
        await self.play(track, ignore_if_playing=True)

        self.skip_votes.clear()

    async def invoke_controller(self) -> None:
        if not self.channel:
            return
        
        await self.context.channel.send(embed=self.build_embed())

    def build_embed(self) -> Embed:
        current: Track = self._current
        if not current:
            return
        
        embed = Embed(title=current.title, url=current.uri)
        embed.description = "```💽 Album: -----\n✅ Correct: ---\n⏱ Median: ----\n🏅 Record: ----s (------)```"

        if current.thumbnail:
            embed.set_thumbnail(url=current.thumbnail)

        return embed

    
    async def teardown(self):
        try:
            await self.destroy()
        except:
            pass

    async def get_tracks(
        self,
        query: str,
        *,
        requester: Member,
        search_type: str = "ytsearch"
    ):
        """Fetches tracks from the node's REST api to parse into Lavalink.

        If you passed in Spotify API credentials when you created the node,
        you can also pass in a Spotify URL of a playlist, album or track and it will be parsed
        accordingly.

        You can also pass in a discord.py Context object to get a
        Context object on any track you search.
        """
        return await self._node.get_tracks(query, requester=requester, search_type=search_type)

    async def connect(self, *, timeout: float, reconnect: bool, self_deaf: bool = True, self_mute: bool = False):
        await self.guild.change_voice_state(channel=self.channel, self_deaf=True, self_mute=self_mute)
        self._node._players[self.guild.id] = self
        self._is_connected = True

    async def stop(self):
        """Stops the currently playing track."""
        self._current = None
        await self._node.send(method=0, guild_id=self._guild.id, data={'encodedTrack': None})

    async def disconnect(self, *, force: bool = False):
        """Disconnects the player from voice."""
        try:
            await self.guild.change_voice_state(channel=None)
        finally:
            self.cleanup()
            self._is_connected = False
            self.channel = None

    async def destroy(self):
        """Disconnects and destroys the player, and runs internal cleanup."""
        
        try:
            await self.disconnect()
        except:
            # 'NoneType' has no attribute '_get_voice_client_key' raised by self.cleanup() ->
            # assume we're already disconnected and cleaned up
            assert self.channel is None and not self.is_connected
        
        self._node._players.pop(self.guild.id)
        await self._node.send(method=1, guild_id=self._guild.id)
        
    async def play(
        self,
        track: Track,
        *,
        start: int = 0,
        end: int = 0,
        ignore_if_playing: bool = False
    ) -> Track:
        """Plays a track. If a Spotify track is passed in, it will be handled accordingly."""
        if not self._node:
            return track
            
        data = {
            "encodedTrack": track.track_id,
            "position": str(start)
        }

        if end > 0:
            data["endTime"] = str(end)
                  
        await self._node.send(
            method=0, guild_id=self._guild.id,
            data=data,
            query=f"noReplace={ignore_if_playing}"
        )

        self._current = track
        return self._current

    async def set_pause(self, pause: bool, requester: Member = None) -> bool:
        """Sets the pause state of the currently playing track."""
        await self._node.send(method=0, guild_id=self._guild.id, data={"paused": pause})

        self._paused = pause
        return self._paused