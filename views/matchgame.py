import discord, asyncio, time
import functions as func

from iufi import (
    Card,
    TempCard,
    CardPool,
    gen_cards_view
)

from random import shuffle
from typing import Any
from collections import Counter

class GuessButton(discord.ui.Button):
    def __init__(self, card: Card, *args, **kwargs) -> None:
        self.view: MatchGame

        self.card: Card = card
        super().__init__(*args, **kwargs)
    
    async def callback(self, interaction: discord.Interaction) -> None:
        if self.disabled:
            return await interaction.response.defer()
        
        if self.view._need_wait:
            return await interaction.response.send_message("Too fast! Pwease slow down, pwetty pwease!", ephemeral=True)
        
        await interaction.response.defer()
        await self.handle_matching()
        
    async def handle_matching(self):
        try:
            self.view._need_wait = True
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
            if self.view._ended_time:
                await self.view.response.edit(content="This game has expired.", embed=embed, attachments=[file], view=self.view)
            else:
                await self.view.response.edit(embed=embed, attachments=[file], view=self.view)
        
        finally:
            self.view._need_wait = False

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
            
            await asyncio.sleep(5)
            self.reset_cards()

    def reset_cards(self):
        # Reset the last clicked card and current card to covered state
        self.view._last_clicked.disabled = False
        self.view.guessed[self.view._last_clicked.custom_id] = self.view.covered_card
        self.view.guessed[self.custom_id] = self.view.covered_card

        # Enable the current button again for the next round of guessing
        self.disabled = False

class MatchGame(discord.ui.View):
    def __init__(self, author: discord.Member, level: str = "1", timeout: float = None):
        super().__init__(timeout=timeout)

        self.author: discord.Member = author
        self._level: str = level
        self._data: dict[str, Any] = func.settings.MATCH_GAME_SETTINGS.get(level)
        self._cards: int = self._data.get("cards")
        self._max_click: int = self._data.get("max_clicks")
        self._start_time: float = time.time()
        self._ended_time: float = None

        self._is_matching: bool = False
        self._need_wait: bool = False
        self.clicked: int = 0
        self._last_clicked: discord.ui.Button = None
        self.covered_card: TempCard = TempCard(f"cover/level{self._level}.webp")

        cards: list[Card] = CardPool.get_random_cards_for_match_game(self._cards)
        cards.extend(cards)
        self.cards: list[Card] = cards
        shuffle(self.cards)

        self.guessed: dict[str, Card] = {}
        self.embed_color = discord.Color.random()
        self.response: discord.Message = None

        for index, card in enumerate(self.cards, start=1):
            index = str(index)

            self.guessed.setdefault(index, self.covered_card)
            self.add_item(GuessButton(card, label=index, custom_id=index, row=(int(index) -1) // self._data.get("elem_per_row")))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            return False
        
        if self._ended_time:
            return False
        
        return True
    
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        pass

    async def end_game(self) -> None:
        if self._ended_time:
            return

        self._ended_time = time.time()
        for child in self.children:
            child.disabled = True

        embed = discord.Embed(title="Game Ended", color=discord.Color.random())
        matched_raw = self.matched()
        embed.description = (
            f"```{'🕔 Time Used:':<15} {func.convert_seconds(self.used_time)}\n"
            f"{'🃏 Matched:':<15} {matched_raw}```\n"
            "Reward type: claimable card drop (probability-based)."
        )

        update_data: dict[str, Any] = {}
        user = await func.get_user(self.author.id)

        best_state = user.get("game_state", {}).get("match_game", {}).get(self._level, {
            "finished_time": 0,
            "matched": 0,
            "click_left": 0
        })

        prefix = f"game_state.match_game.{self._level}"
        if matched_raw > best_state["matched"] or (
                matched_raw == best_state["matched"] and (
                    self.used_time < best_state["finished_time"] or self.click_left > best_state["click_left"]
                )
        ):
            update_data["$set"] = {
                f"{prefix}.matched": matched_raw,
                f"{prefix}.finished_time": self.used_time,
                f"{prefix}.click_left": self.click_left
            }

        await func.update_user(self.author.id, update_data)

        func.logger.info(
            f"User {self.author.name}({self.author.id}) completed a match game. "
            f"Start time: {self._start_time}, End time: {self._ended_time}. "
            f"Time Used: {func.convert_seconds(self.used_time)} "
            f"Card Matched: {matched_raw}, "
            f"Click Lefts: {self.click_left}"
        )

        await self.response.channel.send(content=f"<@{self.author.id}>", embed=embed)

        # Present probability-based reward card for match game performance.
        if matched_raw > 0:
            try:
                from .reward_card import RewardCardView

                probs_config = func.settings.REWARD_CARD_PROBABILITIES or {}
                level_probs = probs_config.get("MATCH_GAME", {}).get(str(self._level), {})

                probs = level_probs.get(str(matched_raw))
                if not probs and level_probs:
                    # Fallback to the highest configured threshold <= matched pairs.
                    eligible = [(int(k), v) for k, v in level_probs.items() if str(k).isdigit() and int(k) <= matched_raw]
                    if eligible:
                        probs = max(eligible, key=lambda item: item[0])[1]

                if probs:
                    reward_view = RewardCardView(None, self.author, probs, initial_cost=10, cost_currency_field="candies", timeout=120)
                    await reward_view._roll_card()

                    reward_embed = reward_view.build_embed()
                    file = None
                    if reward_view.current_card:
                        try:
                            img_bytes = await reward_view.current_card.image_bytes()
                            filename = f"{reward_view.current_card.id}.webp"
                            file = discord.File(img_bytes, filename=filename)
                            reward_embed.set_image(url=f"attachment://{filename}")
                        except Exception:
                            file = None

                    reward_content = (
                        f"**{self.author.mention} This reward ends <t:{reward_view.expires_at}:R>**\n"
                        f"🎁 Card reward for matching {matched_raw} pair{'s' if matched_raw != 1 else ''} on level {self._level}!"
                    )
                    reward_msg = await self.response.channel.send(
                        content=reward_content,
                        embed=reward_embed,
                        file=file,
                        view=reward_view
                    )
                    reward_view.message = reward_msg
            except Exception:
                try:
                    func.logger.exception("Failed to present match game reward card view")
                except Exception:
                    pass

        self.stop()
        
    async def build(self) -> tuple[discord.Embed, discord.File]:
        embed = discord.Embed(
            description=f"```{'⚔️ Level:':<17}  {self._level}\n" \
                        f"{'👆 Click left:':<17} {self.click_left}\n" \
                        f"{'🃏 Card Matched:':<17} {self.matched()}```",
            color=self.embed_color
        )   

        bytes, image_format = await gen_cards_view([card for card in self.guessed.values()], cards_per_row=self._data.get("elem_per_row"))
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