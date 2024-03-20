from __future__ import annotations

import asyncio, os, re, aiohttp, copy
import functions as func

from discord.ext import commands
from urllib.parse import quote
from .objects import Playlist, Track, TRACK_BASE
from .utils import ExponentialBackoff, NodeStats
from collections import Counter

from typing import (
    Dict,
    Optional,
    TYPE_CHECKING,
    Union
)

if TYPE_CHECKING:
    from .player import Player

from random import (
    choice,
    choices,
    sample,
    shuffle
)

from .objects import (
    Card,
    Question,
    QUIZ_LEVEL_BASE,
    RANK_BASE
)

from .exceptions import IUFIException, DuplicatedCardError, DuplicatedTagError
# from .deepsearch import (
#     Load_Data,
#     Search_Setup
# )

DROP_RATES = {
    'common': .93,
    'rare': .05,
    'epic': .003,
    'legendary': .0008,
    'mystic': .0001,
    "celestial": .00005
}

URL_REGEX = re.compile(
    r"https?://(?:www\.)?.+"
)

NODE_VERSION = "v4"
CALL_METHOD = ["PATCH", "DELETE"]


class CardPool:
    _cards: dict[str, Card] = {}
    _tag_cards: dict[str, Card] = {}
    _available_cards: dict[str, list[Card]] = {
        category: [] for category in DROP_RATES
    }

    #DeepSearch
    # search_image: Search_Setup | None = None

    # @classmethod
    # def load_search_metadata(cls) -> None:
    #     image_list = Load_Data().from_folder(["/metadata-files"])
    #     cls.search_image = Search_Setup(image_list=image_list)
    #     cls.search_image.run_index()

    @classmethod
    def add_available_card(cls, card: Card) -> None:
        card.change_owner()
        cls._available_cards[card.tier[1]].append(card)

    @classmethod
    def remove_available_card(cls, card: Card) -> None:
        cls._available_cards[card.tier[1]].remove(card)

    @classmethod
    def add_tag(cls, card: Card, tag: str) -> None:
        if tag.lower() in cls._tag_cards:
            raise DuplicatedTagError(f"Tag {tag} already added into the pool.")
        
        card.change_tag(tag)
        cls._tag_cards[tag.lower()] = card
    
    @classmethod
    def change_tag(cls, card: Card, tag: str) -> None:
        if tag.lower() in cls._tag_cards:
            raise DuplicatedTagError(f"Tag {tag} already added into the pool.")
        
        if card.tag and card.tag.lower() in cls._tag_cards:
            card = cls._tag_cards.pop(card.tag.lower())
            card.change_tag(tag)
            cls._tag_cards[tag.lower()] = card

    @classmethod
    def remove_tag(cls, card: Card) -> None:
        try:
            card = cls._tag_cards.pop(card.tag.lower())
            card.change_tag(None)
        except KeyError as _:
            return
        
    @classmethod
    def add_card(cls, _id: str, tier: str, **kwargs) -> Card:
        card = Card(cls, _id, tier, **kwargs)
        if card.id in cls._cards:
            raise DuplicatedCardError(f"Card {card.id} in {tier} already added into the pool.")
        
        cls._cards[card.id] = card
        if not card.owner_id:
            cls.add_available_card(card)
        
        if card.tag:
            cls.add_tag(card, card.tag)

        return card
    
    @classmethod
    def get_card(cls, card_id: str) -> Card | None:
        if not card_id:
            return
        card_id = card_id.lstrip("0")
        card = cls._cards.get(card_id)
        if not card:
            card = cls._tag_cards.get(card_id.lower())
        return card
    
    @classmethod
    def roll(cls, amount: int = 3, *, included: list[str] = None, avoid: list[str] = None, luck_rates: float = None) -> list[Card]:
        results = included if included else []

        drop_rates = DROP_RATES.copy()
        if luck_rates:
            drop_rates = {k: v if k == 'common' else v * (1 + luck_rates) for k, v in DROP_RATES.items()}
            total = sum(drop_rates.values())
            drop_rates['common'] = 1 - (total - drop_rates['common'])
        
        if avoid:
            drop_rates = {k: v for k, v in drop_rates.items() if k not in avoid}

        results.extend(choices(list(drop_rates.keys()), weights=drop_rates.values(), k=amount - len(results)))
        cards = [
            card
            for cat, amt in Counter(results).items()
            for card in sample(cls._available_cards[cat], k=amt)
        ]
        shuffle(cards)
        return cards

class QuestionPool:
    _questions: list[Question] = []

    @classmethod
    def add_question(cls, question: Question) -> None:
        cls._questions.append(question)

    @classmethod
    def remove_question(cls, question: Question) -> None:
        cls._questions.remove(question)
    
    @classmethod
    def get_rank(cls, points: int) -> tuple[str, int]:
        sorted_ranks = sorted(RANK_BASE.items(), key=lambda item: item[1]["points"], reverse=True)
        for rank, details in sorted_ranks:
            if points >= details["points"]:
                return (rank, details["emoji_id"])
        return None

    @classmethod
    def get_question_distribution_by_rank(cls, rank: str) -> list[tuple[str, int]]:
        rank_details = RANK_BASE.get(rank)
        if not rank_details:
            raise IUFIException(f"Rank '{rank}' not found!")
        
        return rank_details["questions"]

    @classmethod
    def get_question(cls, rank: str, number: int) -> list[Question]:
        if rank not in QUIZ_LEVEL_BASE.keys():
            raise IUFIException(f"{rank} is not found in the quiz!")
        
        questions: dict[str, list[Question]] = {
            level: [q for q in cls._questions if q.level == level]
            for level in QUIZ_LEVEL_BASE.keys()
        }

        num_available = len(questions[rank])
        num_to_return = min(number, num_available)

        return sample(questions[rank], k=num_to_return)
    
    @classmethod
    def get_question_by_rank(cls, ranks: list[tuple[str, int]]) -> list[Question]:
        questions: list[Question] = []
        
        for (rank_name, return_num) in ranks:
            if rank_name not in QUIZ_LEVEL_BASE.keys():
                raise IUFIException(f"{rank_name} is not found in the quiz!")
            
            for question in cls.get_question(rank_name, return_num):
                questions.append(question)
        
        return questions

class Node:
    """The base class for a node. 
       This node object represents a Lavalink node. 
    """

    def __init__(
        self,
        *,
        pool,
        bot: commands.Bot,
        host: str,
        port: int,
        password: str,
        identifier: str,
        secure: bool = False,
        heartbeat: int = 30,
        session: Optional[aiohttp.ClientSession] = None,
        resume_key: Optional[str] = None

    ):
        self._bot: commands.Bot = bot
        self._host: str = host
        self._port: int = port
        self._pool: NodePool = pool
        self._password: str = password
        self._identifier: str = identifier
        self._heartbeat: int = heartbeat
        self._secure: bool = secure
       
        self._websocket_uri: str = f"{'wss' if self._secure else 'ws'}://{self._host}:{self._port}/" + NODE_VERSION + "/websocket"
        self._rest_uri: str = f"{'https' if self._secure else 'http'}://{self._host}:{self._port}"

        self._session: aiohttp.ClientSession = session or aiohttp.ClientSession()
        self._websocket: aiohttp.ClientWebSocketResponse = None
        self._task: asyncio.Task = None

        self.resume_key: str = resume_key or str(os.urandom(8).hex())

        self._session_id: str = None
        self._available: bool = None

        self._headers = {
            "Authorization": self._password,
            "User-Id": str(bot.user.id),
            "Client-Name": f"IUFI/1.0",
            'Resume-Key': self.resume_key
        }

        self._players: Dict[int, Player] = {}
        self._bot.add_listener(self._update_handler, "on_socket_response")

    def __repr__(self) -> str:
        return (
            f"<IUFI.node ws_uri={self._websocket_uri} rest_uri={self._rest_uri} "
            f"player_count={len(self._players)}>"
        )

    @property
    def is_connected(self) -> bool:
        """"Property which returns whether this node is connected or not"""
        return self._websocket is not None and not self._websocket.closed


    @property
    def stats(self) -> NodeStats:
        """Property which returns the node stats."""
        return self._stats

    @property
    def players(self) -> Dict[int, Player]:
        """Property which returns a dict containing the guild ID and the player object."""
        return self._players

    @property
    def bot(self) -> commands.Bot:
        """Property which returns the discord.py client linked to this node"""
        return self._bot

    @property
    def player_count(self) -> int:
        """Property which returns how many players are connected to this node"""
        return len(self.players)

    @property
    def pool(self) -> NodePool:
        """Property which returns the pool this node is apart of"""
        return self._pool

    async def _update_handler(self, data: dict) -> None:
        await self._bot.wait_until_ready()

        if not data:
            return

        if data["t"] == "VOICE_SERVER_UPDATE":
            guild_id = int(data["d"]["guild_id"])
            try:
                player = self._players[guild_id]
                await player.on_voice_server_update(data["d"])
            except KeyError:
                return

        elif data["t"] == "VOICE_STATE_UPDATE":
            if int(data["d"]["user_id"]) != self._bot.user.id:
                return

            guild_id = int(data["d"]["guild_id"])
            try:
                player = self._players[guild_id]
                await player.on_voice_state_update(data["d"])
            except KeyError:
                return

    async def _listen(self) -> None:
        backoff = ExponentialBackoff(base=7)    

        while True:
            try:
                msg = await self._websocket.receive()
            except:
                break
            if msg.type == aiohttp.WSMsgType.CLOSED:
                self._available = False

                retry = backoff.delay()
                print(f"Trying to reconnect {self._identifier} with {round(retry)}s")
                await asyncio.sleep(retry)
                if not self.is_connected:
                    try:
                        await self.connect()
                    except:
                        pass
            else:
                self._bot.loop.create_task(self._handle_payload(msg.json()))

    async def _handle_payload(self, data: dict) -> None:
        op = data.get("op", None)
        if not op:
            return

        if op == "ready":
            self._session_id = data.get("sessionId")

        if op == "stats":
            self._stats = NodeStats(data)
            return

        if "guildId" in data:
            if not (player := self._players.get(int(data["guildId"]))):
                return

        if op == "event":
            await player._dispatch_event(data)
        elif op == "playerUpdate":
            await player._update_state(data)

    async def send(
        self, method: int, 
        guild_id: Union[str, int] = None, 
        query: str = None, 
        data: Union[dict, str] = None
    ) -> dict:
        if not self._available:
            raise IUFIException(
                f"The node '{self._identifier}' is unavailable."
            )
        
        uri: str = f"{self._rest_uri}/{NODE_VERSION}" \
                   f"/sessions/{self._session_id}/players" \
                   f"/{guild_id}" if guild_id else "" \
                   f"?{query}" if query else ""
        
        async with self._session.request(
            method=CALL_METHOD[method],
            url=uri,
            headers={"Authorization": self._password},
            json=data if data else {}
        ) as resp:
            if resp.status >= 300:
                raise IUFIException(f"Getting errors from Lavalink REST api")
            
            if method == CALL_METHOD[1]:
                return await resp.json(content_type=None)

            return await resp.json()
        
    def get_player(self, guild_id: int) -> Optional[Player]:
        """Takes a guild ID as a parameter. Returns a IUFI Player object."""
        return self._players.get(guild_id, None)

    async def connect(self) -> None:
        """Initiates a connection with a Lavalink node and adds it to the node pool."""
        try:
            self._websocket = await self._session.ws_connect(
                self._websocket_uri, headers=self._headers, heartbeat=self._heartbeat
            )

            self._task = self._bot.loop.create_task(self._listen())
            self._available = True

            print(f"{self._identifier} is connected!")
        
        except aiohttp.ClientConnectorError:
            raise IUFIException(
                f"The connection to node '{self._identifier}' failed."
            )
        except aiohttp.WSServerHandshakeError:
            raise IUFIException(
                f"The password for node '{self._identifier}' is invalid."
            )
        except aiohttp.InvalidURL:
            raise IUFIException(
                f"The URI for node '{self._identifier}' is invalid."
            )
        
        if self.players:
            await self.reconnect()

        return self
              
    async def disconnect(self) -> None:
        """Disconnects a connected Lavalink node and removes it from the node pool.
           This also destroys any players connected to the node.
        """
        for player in self.players.copy().values():
            await player.teardown()

        await self._websocket.close()
        del self._pool._nodes[self._identifier]
        self._available = False
        self._task.cancel()

    async def reconnect(self) -> None:
        await asyncio.sleep(10)
        for player in self.players.copy().values():
            try:
                if player._voice_state:
                    await player._dispatch_voice_update(player._voice_state)

                if player.current:
                    await player.play(track=player.current, start=min(player._last_position, player.current.length))

                    if player.is_paused:
                        await player.set_pause(True)
            except:
                await player.teardown()
            await asyncio.sleep(2)

    async def get_tracks(
        self,
        query: str,
        *,
        search_type: str = "ytsearch"
    ) -> Optional[Union[Playlist, Track]]:
        """Fetches tracks from the node's REST api to parse into Lavalink.

           You can also pass in a discord.py Context object to get a
           Context object on any track you search.
        """

        if not URL_REGEX.match(query) and not re.match(r"(?:ytm?|sc)search:.", query):
            query = f"{search_type}:{query}"

        async with self._session.get(
            url=f"{self._rest_uri}/" + NODE_VERSION + f"/loadtracks?identifier={quote(query)}",
            headers={"Authorization": self._password}
        ) as response:
            data = await response.json()

        load_type = data.get("loadType")

        if not load_type:
            raise IUFIException("There was an error while trying to load this track.")

        elif load_type == "error":
            exception = data["data"]
            raise IUFIException(f"{exception['message']} [{exception['severity']}]")

        elif load_type == "empty":
            return None

        elif load_type == "playlist":
            data = data.get("data")
            
            return Playlist(
                playlist_info=data["info"],
                tracks=data["tracks"]
            )

        elif load_type == "search":
            return [
                Track(
                    track_id=track["encoded"],
                    info=track["info"]
                )
                for track in data["data"]
            ]

        elif load_type == "track":
            track = data["data"]
            return [
                Track(
                    track_id=track["encoded"],
                    info=track["info"],
                )
            ]

class NodePool:
    """The base class for the node pool.
       This holds all the nodes that are to be used by the bot.
    """

    _nodes: dict[str, Node] = {}
    _questions: Playlist = None

    def __repr__(self) -> str:
        return f"<IUFI.NodePool node_count={self.node_count}>"

    @property
    def nodes(self) -> Dict[str, Node]:
        """Property which returns a dict with the node identifier and the Node object."""
        return self._nodes

    @property
    def node_count(self) -> int:
        return len(self._nodes.values())

    @classmethod
    async def fetch_question(cls) -> None:
        node = cls.get_node()
        cls._questions = await node.get_tracks("https://www.youtube.com/playlist?list=PLhKSPhxqvGkOuFPbkC7oJjy2ULXmVV-X9")

    @classmethod
    async def get_question(cls) -> Track:
        if not cls._questions:
            await cls.fetch_question()
        
        track: Track = choice(cls._questions.tracks)
        if not track.db_data:
            track_data = await func.MUSIC_DB.find_one({"_id": track.identifier})
            if not track_data:
                await func.MUSIC_DB.insert_one({ "_id": track.identifier, **TRACK_BASE})

            track.db_data = track_data or copy.deepcopy(TRACK_BASE)
            
        return track
    
    @classmethod
    def get_node(cls, *, identifier: str = None) -> Node:
        """Fetches a node from the node pool using it's identifier.
           If no identifier is provided, it will choose a node at random.
        """

        available_nodes = {node for _, node in cls._nodes.items() if node.is_connected}

        if identifier:
            available_nodes = { node for node in available_nodes if node._identifier == identifier }

        if not available_nodes:
            raise IUFIException("There are no nodes available.")

        nodes = {node: len(node.players.keys()) for node in available_nodes}
        return min(nodes, key=nodes.get)

    @classmethod
    async def create_node(
        cls,
        *,
        bot: commands.Bot,
        host: str,
        port: str,
        password: str,
        identifier: str,
        secure: bool = False,
        heartbeat: int = 30,
        session: Optional[aiohttp.ClientSession] = None,
        resume_key: Optional[str] = None,

    ) -> Node:
        """Creates a Node object to be then added into the node pool.
           For Spotify searching capabilites, pass in valid Spotify API credentials.
        """
        if identifier in cls._nodes.keys():
            raise IUFIException(f"A node with identifier '{identifier}' already exists.")

        node = Node(
            pool=cls, bot=bot, host=host, port=port, password=password, identifier=identifier,
            secure=secure, heartbeat=heartbeat, session=session, resume_key=resume_key
        )

        await node.connect()
        cls._nodes[node._identifier] = node
        return node