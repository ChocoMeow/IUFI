import discord, asyncio, time
import functions as func

from iufi import (
    Card,
    TempCard,
    CardPool,
    gen_cards_view,
    POTIONS_BASE
)
from discord.ext import commands
from random import shuffle, choice
from typing import Any
from collections import Counter
from . import ButtonOnCooldown

GAME_SETTINGS: dict[str, dict[str, Any]] = {
    "1": {
        "exp": 10,
        "cooldown": 3_000,
        "timeout": 120,
        "cards": 3,
        "elem_per_row": 3,
        "max_clicks": 8,
        "rewards": {
            2: ("candies",  5),
            3: [("potions.speed_i", 1), ("potions.luck_i", 1)]
        },
    },
    "2": {
        "exp": 15,
        "cooldown": 5_400,
        "timeout": 240,
        "cards": 6,
        "elem_per_row": 4,
        "max_clicks": 16,
        "rewards": {
            2: ("candies",  5),
            4: ("candies",  10),
            5: [("potions.speed_ii", 1), ("potions.luck_ii", 1)],
            6: ("candies",  15),
        },
    },
    "3": {
        "exp": 20,
        "cooldown": 7_200,
        "timeout": 480,
        "cards": 10,
        "elem_per_row": 5,
        "max_clicks": 26,
        "rewards": {
            2: ("candies",  10),
            4: ("candies",  15),
            6: [("potions.speed_ii", 1), ("potions.luck_ii", 1)],
            8: ("candies",  20),
            9: [("potions.speed_iii", 1), ("potions.luck_iii", 1)],
            10: ("candies",  100)
        },
    }
}

def key(interaction: discord.Interaction):
    return interaction.user

class GuessButton(discord.ui.Button):
    def __init__(self, card: Card, *args, **kwargs) -> None:
        self.view: MatchGame

        self.card: Card = card
        super().__init__(*args, **kwargs)
    
    async def callback(self, interaction: discord.Interaction) -> None:
        if self.disabled:
            return await interaction.response.defer()
        
        if self.view._need_wait:
            return await interaction.response.send_message("Too fast. Please slower!", ephemeral=True)
        
        await interaction.response.defer()
        await self.handle_matching()
        
    async def handle_matching(self):
        if self.view._is_matching:
            await self.matching_process()
        else:
            self.view.guessed[self.custom_id] = self.card
            self.disabled = True

        self.view._is_matching = not self.view._is_matching
        self.view._last_clicked = self
        self.view.clicked += 1
        
        if self.view.click_left <= 0:
            await self.view.end_game()
            
        elif self.view.matched() >= self.view._cards:
            await self.view.end_game()
        
        embed, file = await self.view.build()
        if self.view._is_ended:
            await self.view.response.edit(content="This game has expired.", embed=embed, attachments=[file], view=self.view)
        else:
            await self.view.response.edit(embed=embed, attachments=[file], view=self.view)

    async def matching_process(self):
        for card in self.view.guessed.values():
            if card == self.card:
                self.view.guessed[self.custom_id] = self.card
                self.disabled = True
                break
        else:
            self.disabled = True
            self.view.guessed[self.custom_id] = self.card

            embed, file = await self.view.build()
            await self.view.response.edit(embed=embed, attachments=[file], view=self.view)
            self.view._need_wait = True
            
            await asyncio.sleep(5)
            self.reset_cards()

    def reset_cards(self):
        # Reset the last clicked card and current card to covered state
        self.view._last_clicked.disabled = False
        self.view.guessed[self.view._last_clicked.custom_id] = self.view.covered_card
        self.view.guessed[self.custom_id] = self.view.covered_card

        # Allow the next click
        self.view._need_wait = False
        # Enable the current button again for the next round of guessing
        self.disabled = False

class MatchGame(discord.ui.View):
    def __init__(self, author: discord.Member, level: str = "1", timeout: float = None):
        super().__init__(timeout=timeout)

        self.author: discord.Member = author
        self._level: str = level
        self._data: dict[str, Any] = GAME_SETTINGS.get(level)
        self._cards: int = self._data.get("cards")
        self._max_click: int = self._data.get("max_clicks")
        self._start_time: float = time.time()
        self._ended_time: float = None

        self._is_matching: bool = False
        self._need_wait: bool = False
        self._is_ended: bool = False
        self.clicked: int = 0
        self._last_clicked: discord.ui.Button = None
        self.covered_card: TempCard = TempCard(f"cover/level{self._level}.jpg")

        cards: list[Card] = CardPool.roll(self._cards, avoid=["celestial"])
        cards.extend(cards)
        self.cards: list[Card] = cards
        shuffle(self.cards)

        self.guessed: dict[str, Card] = {}
        self.embed_color = discord.Color.random()
        self.response: discord.Message = None
        
        self.cooldown = commands.CooldownMapping.from_cooldown(1.0, 3.0, key)

        for index, card in enumerate(self.cards, start=1):
            index = str(index)

            self.guessed.setdefault(index, self.covered_card)
            self.add_item(GuessButton(card, label=index, custom_id=index, row=(int(index) -1) // self._data.get("elem_per_row")))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            return False
        
        if self._is_ended:
            return False

        retry_after = self.cooldown.update_rate_limit(interaction)
        if retry_after:
            raise ButtonOnCooldown(retry_after)
        return True
    
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        if isinstance(error, ButtonOnCooldown):
            sec = int(error.retry_after)
            await interaction.response.send_message(f"You're on cooldown for {sec} second{'' if sec == 1 else 's'}!", ephemeral=True)
        
    async def timeout_count(self) -> None:
        await asyncio.sleep(self._data.get("timeout", 0))
        await self.end_game()
        await self.response.edit(view=self)
        self.stop()

    async def end_game(self) -> None:
        if self._is_ended:
            return
        self._is_ended = True
        self._ended_time = time.time()

        for child in self.children:
            child.disabled = True

        embed = discord.Embed(title="Game Ended (Rewards)", color=discord.Color.random())
        matched_raw = self.matched()
        final_rewards: dict[str, int] = {}
        
        rewards = f"{'Pairs':>9}{'Rewards':>9}\n"
        for matched, reward in self._data.get("rewards").items():
            if isinstance(reward, list):
                reward = choice(reward)
            
            if is_matched := (matched <= matched_raw):
                if reward[0] not in final_rewards:
                    final_rewards[reward[0]] = 0
                final_rewards[reward[0]] += reward[1]

            reward_name, amount = reward
            reward_name = reward_name.split(".")

            rewards += ("✅" if is_matched else "⬛") + f"  {matched:<3}"
            if reward_name[0] == "candies":
                rewards += f"    {'🍬 Candy':<18} x{amount}\n"
            else:
                reward_name = reward_name[1].split("_")
                potion_data = POTIONS_BASE.get(reward_name[0])
                rewards += f"    {potion_data.get('emoji') + ' ' + reward_name[0].title() + ' ' + reward_name[1].upper() + ' Potion':<18} x{amount}\n"
            
        embed.description = f"```{rewards}```"

        update_data = {"$inc": final_rewards | {"exp": self._data["exp"]}}
        user = await func.get_user(self.author.id)

        best_state = user.get("game_state", {}).get("match_game", {}).get(self._level, {
            "finished_time": 0,
            "matched": 0,
            "click_left": 0
        })

        prefix = f"game_state.match_game.{self._level}"
        if matched_raw > best_state["matched"] or (
                matched_raw == best_state["matched"] and (
                    self.used_time > best_state["finished_time"] or self.click_left > best_state["click_left"]
                )
        ):
            update_data["$set"] = {
                f"{prefix}.matched": matched_raw,
                f"{prefix}.finished_time": self.used_time,
                f"{prefix}.click_left": self.click_left
            }

        await func.update_user(self.author.id, update_data)
        await self.response.channel.send(content=f"<@{self.author.id}>", embed=embed)

    async def build(self) -> tuple[discord.Embed, discord.File]:
        embed = discord.Embed(
            description=f"```Level:        {self._level}\n" \
                        f"Click left:   {self.click_left}\n" \
                        f"Card Matched: {self.matched()}```",
            color=self.embed_color
        )   

        bytes, image_format = await asyncio.to_thread(gen_cards_view, [card for card in self.guessed.values()], cards_per_row=self._data.get("elem_per_row"))
        embed.set_image(url=f"attachment://image.{image_format}")

        return embed, discord.File(bytes, filename=f"image.{image_format}")

    def matched(self) -> int:
        counter = Counter([card for card in self.guessed.values() if card != self.covered_card])
        return len([count for count in counter.values() if count == 2])
    
    @property
    def used_time(self) -> float:
        return round(self._ended_time - self._start_time, 2)
    
    @property
    def click_left(self) -> int:
        return self._max_click - self.clicked