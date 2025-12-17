import discord, asyncio, time
import functions as func

from iufi import (
    Card,
    TempCard,
    CardPool,
    gen_cards_view
)

from random import shuffle, choice
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

        matched_raw = self.matched()
        
        # Feature flag: Use reward card system or traditional rewards
        use_reward_card = func.settings.GIVE_REWARD_CARD

        if not use_reward_card:
            # Traditional reward system
            embed = discord.Embed(title="Game Ended (Rewards)", color=discord.Color.random())
            final_rewards: dict[str, int] = {}
            
            rewards = f"{'Pairs':>9}{'Rewards':>9}\n"
            for matched, reward in self._data.get("rewards").items():
                if isinstance(reward[0], list):
                    reward = choice(reward)
                
                if is_matched := (int(matched) <= matched_raw):
                    if reward[0] not in final_rewards:
                        final_rewards[reward[0]] = 0
                    final_rewards[reward[0]] += reward[1]

                reward_name, amount = reward
                reward_name = reward_name.split(".")

                rewards += ("✅" if is_matched else "⬛") + f"  {matched:<3}"
                if reward_name[0] == "candies":
                    rewards += f"    {'🍬 Candies':<18} x{amount}\n"
                
                elif reward_name[0] == "exp":
                    rewards += f"    {'⚔️ Exp':<19} x{amount}\n"

                else:
                    reward_name = reward_name[1].split("_")
                    potion_data = func.settings.POTIONS_BASE.get(reward_name[0])
                    rewards += f"    {potion_data.get('emoji') + ' ' + reward_name[0].title() + ' ' + reward_name[1].upper() + ' Potion':<18} x{amount}\n"
                
            embed.description = f"```{'🕔 Time Used:':<15} {func.convert_seconds(self.used_time)}\n{'🃏 Matched:':<15} {matched_raw}```\n```{rewards}```"

            update_data = {"$inc": final_rewards}
        else:
            # Reward card system - no traditional rewards
            embed = discord.Embed(title="Game Ended", color=discord.Color.random())
            embed.description = f"```{'🕔 Time Used:':<15} {func.convert_seconds(self.used_time)}\n{'🃏 Matched:':<15} {matched_raw}```"
            update_data = {}
        
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
            if "$set" not in update_data:
                update_data["$set"] = {}
            update_data["$set"].update({
                f"{prefix}.matched": matched_raw,
                f"{prefix}.finished_time": self.used_time,
                f"{prefix}.click_left": self.click_left
            })

            # Determine user's monthly best for this level and update if current run is better
            # Ensure update_data contains monthly fields to reflect monthly leaderboards
            monthly_best_matched = best_state.get('monthly_matched', 0) if best_state else 0
            monthly_best_finished = best_state.get('monthly_finished_time', float('inf')) if best_state else float('inf')
            monthly_best_click_left = best_state.get('monthly_click_left', 0) if best_state else 0

            # If current run is better than monthly best, update monthly fields
            now_ts = time.time()
            should_update_monthly = False
            if matched_raw > monthly_best_matched:
                should_update_monthly = True
            elif matched_raw == monthly_best_matched:
                if self.used_time < monthly_best_finished:
                    should_update_monthly = True
                elif self.used_time == monthly_best_finished and self.click_left > monthly_best_click_left:
                    should_update_monthly = True

            if should_update_monthly:
                if "$set" not in update_data:
                    update_data["$set"] = {}
                update_data["$set"].update({
                    f"{prefix}.monthly_matched": matched_raw,
                    f"{prefix}.monthly_finished_time": self.used_time,
                    f"{prefix}.monthly_click_left": self.click_left,
                    f"{prefix}.last_update": now_ts
                })

        await func.update_user(self.author.id, update_data)

        func.logger.info(
            f"User {self.author.name}({self.author.id}) completed a match game. "
            f"Start time: {self._start_time}, End time: {self._ended_time}. "
            f"Time Used: {func.convert_seconds(self.used_time)} "
            f"Card Matched: {matched_raw}, "
            f"Click Lefts: {self.click_left}"
        )

        await self.response.channel.send(content=f"<@{self.author.id}>", embed=embed)
        
        # Feature flag: Give reward card based on matches
        if use_reward_card and matched_raw > 0:
            try:
                from .reward_card import RewardCardView
                
                # Get probabilities for this level and match count
                probs_config = func.settings.REWARD_CARD_PROBABILITIES or {}
                level_probs = probs_config.get("MATCH_GAME", {}).get(self._level, {})
                selected_probs = level_probs.get(str(matched_raw))
                
                if selected_probs:
                    # Create and send reward card view
                    reward_view = RewardCardView(None, self.author, selected_probs, initial_cost=10, cost_currency_field="candies", timeout=120)
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
                    
                    reward_content = f"**{self.author.mention} This reward ends <t:{reward_view.expires_at}:R>**\n🎁 Card reward for matching {matched_raw} pairs!"
                    reward_msg = await self.response.channel.send(
                        content=reward_content,
                        embed=reward_embed,
                        file=file,
                        view=reward_view
                    )
                    reward_view.message = reward_msg
            except Exception:
                # Fail silently but log
                try:
                    func.logger.exception("Failed to present match game reward card view")
                except:
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