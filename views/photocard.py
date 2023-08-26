import discord
import functinos as func

from iufi import CardPool, Card
from math import ceil

class PhotoCardView(discord.ui.View):
    def __init__(self, author: discord.Member, cards: list[int], *, timeout: float | None = 100):
        super().__init__(timeout=timeout)

        self.author: discord.Member = author
        self.cards: dict[str, Card | None] = {card: None for card in cards}

        self.page: int = ceil(len(self.cards) / 10)
        self.current_page: int = 1

        self.message: discord.Message = None

    def build_embed(self) -> discord.Embed:
        offset = self.current_page * 10
        cards = list(self.cards.keys())[(offset-10):offset]

        desc = f"**📙 Collection size: `{len(self.cards)}/{func.MAX_CARDS}`**\n\n```"
        for card_id in cards:
            card = self.cards.get(card_id)
            if not card:
                card = self.cards[card_id] = CardPool.get_card(card_id)

            desc += f"🆔{card.id.zfill(5)} 🏷️{card.tag if card.tag else '-':<12} ⭐{card.stars} {card.tier[0]}\n" if card else f"🆔 {card_id.zfill(5)} {'-' * 20}"

        embed = discord.Embed(title=f"📖 {self.author.display_name}'s Photocards", description=desc + "```")
        embed.set_thumbnail(url=self.author.avatar.url)
        embed.set_footer(text="Pages: {}/{}".format(self.current_page, self.page))

        return embed

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        
        await self.message.edit(view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.author == interaction.user:
            return True
        return False
    
    @discord.ui.button(label='<<', style=discord.ButtonStyle.grey)
    async def fast_back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page != 1:
            self.current_page = 1
            await interaction.response.edit_message(embed=self.build_embed())
    
    @discord.ui.button(label='Back', style=discord.ButtonStyle.blurple)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 1:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.build_embed())
    
    @discord.ui.button(label='Next', style=discord.ButtonStyle.blurple)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.page:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.build_embed())

    @discord.ui.button(label='>>', style=discord.ButtonStyle.grey)
    async def fast_next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page != self.page:
            self.current_page = self.page
            await interaction.response.edit_message(embed=self.build_embed())

    @discord.ui.button(emoji='🗑️', style=discord.ButtonStyle.red)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.message.delete()
        self.stop()