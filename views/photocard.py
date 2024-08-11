import discord, asyncio
import functions as func

from iufi import (
    CardPool,
    Card,
    gen_cards_view
)

from typing import Tuple, List
from discord.ext import commands
from . import ButtonOnCooldown
from math import ceil

def key(interaction: discord.Interaction):
    return interaction.user

#Sorter
class SorterInterface:
    def __init__(self, name: str, description: str, emoji: str) -> None:
        self.name: str = name
        self.description: str = description
        self.emoji: str = emoji

    def sort(self, cards: dict[str, Card]) -> None:
        pass

class TierSorter(SorterInterface):
    def __init__(self) -> None:
        super().__init__(
            name="Tier Sorter [Ascending]",
            description="Sort your photocards from lowest to highest tier with ease.",
            emoji="😌"
        )
    
    def sort(self, cards: dict[str, Card]) -> dict[str, Card]:
        sorted_dict = {}
        
        for tier in func.settings.TIERS_BASE:
            sorted_dict.update({
                card_id: card 
                for card_id, card in cards.items() if card and card._tier == tier
            })
        
        return sorted_dict
    
class SortDropdown(discord.ui.Select):
    def __init__(self):
        self.view: PhotoCardView
        self._sorters: List[SorterInterface] = [TierSorter()]
        
        super().__init__(
            placeholder="Select a sorter for clearer photocards...",
            min_values=1, max_values=1
        )
        self.options = [discord.SelectOption(label=sorter.name, value=index, description=sorter.description, emoji=sorter.emoji) for index, sorter in enumerate(self._sorters)]

    async def callback(self, interaction: discord.Interaction) -> None:
        sel_sorter: SorterInterface = self._sorters[int(self.values[0])]
        self.view.cards = sel_sorter.sort(self.view.cards.copy())
        await self.view.update_embed(interaction)

class PhotoCardView(discord.ui.View):
    def __init__(self, author: discord.Member, cards: list[int], *, timeout: float | None = 100):
        super().__init__(timeout=timeout)

        self.author: discord.Member = author
        self.cards: dict[str, Card | None] = {card: None for card in cards}

        self.page: int = ceil(len(self.cards) / 8)
        self.current_page: int = 1

        self._dropdown_view: SortDropdown = SortDropdown()
        self.add_item(self._dropdown_view)

        self.toggle_cards_view: bool = False
        self.message: discord.Message = None
        self.cooldown = commands.CooldownMapping.from_cooldown(1.0, 8.0, key)

    async def build_embed(self) -> Tuple[discord.Embed, discord.File]:
        offset = self.current_page * 8
        card_ids, cards = list(self.cards.keys())[(offset-8):offset], []
        desc = f"\n**📙 Collection size: `{len(self.cards)}/{func.settings.MAX_CARDS}`**\n```"

        for card_id in card_ids:
            card = self.cards.get(card_id)
            if not card:
                card = self.cards[card_id] = CardPool.get_card(card_id)
            
            if not card:
                continue
            
            if self.toggle_cards_view:
                cards.append(card)
            
            desc += f"{card.display_id} {card.display_tag} {card.display_frame} {card.display_stars} {card.tier[0]}\n" if card else f"🆔 {card_id.zfill(5)} {'-' * 20}"
            
        embed = discord.Embed(title=f"📖 {self.author.display_name}'s Photocards", description=desc + "```", color=discord.Color.random())
        embed.set_footer(text="Pages: {}/{}".format(self.current_page, self.page))

        if self.toggle_cards_view:
            image_bytes, image_format = await asyncio.to_thread(gen_cards_view, cards, 4)
            embed.set_image(url=f"attachment://image.{image_format}")
            return embed, discord.File(image_bytes, filename=f"image.{image_format}")
        else:
            embed.set_thumbnail(url=self.author.display_avatar.url)
            
        return embed, None

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        
        await self.message.edit(view=self)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        if isinstance(error, ButtonOnCooldown):
            sec = int(error.retry_after)
            await interaction.response.send_message(f"You're on cooldown for {sec} second{'' if sec == 1 else 's'}!", ephemeral=True)
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.toggle_cards_view:
            retry_after = self.cooldown.update_rate_limit(interaction)
            if retry_after:
                raise ButtonOnCooldown(retry_after)
        
        return self.author == interaction.user
    
    async def update_embed(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
            
        embed, file = await self.build_embed()
        await self.message.edit(embed=embed, attachments=[file] if file else [], view=self)
            
    @discord.ui.button(label='<<', style=discord.ButtonStyle.grey)
    async def fast_back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page != 1:
            self.current_page = 1
            await self.update_embed(interaction)
        await interaction.response.defer()
    
    @discord.ui.button(label='Back', style=discord.ButtonStyle.blurple)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 1:
            self.current_page -= 1
            await self.update_embed(interaction)
        await interaction.response.defer()
    
    @discord.ui.button(label='Next', style=discord.ButtonStyle.blurple)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.page:
            self.current_page += 1
            await self.update_embed(interaction)
        await interaction.response.defer()

    @discord.ui.button(label='>>', style=discord.ButtonStyle.grey)
    async def fast_next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page != self.page:
            self.current_page = self.page
            await self.update_embed(interaction)
        await interaction.response.defer()
    
    @discord.ui.button(emoji='👁️', style=discord.ButtonStyle.green)
    async def view_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.toggle_cards_view = not self.toggle_cards_view
        button.style = discord.ButtonStyle.red if self.toggle_cards_view else discord.ButtonStyle.green
        await self.update_embed(interaction)