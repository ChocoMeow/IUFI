import discord
import functinos as func

from iufi import CardPool, Card
from math import ceil
from io import BytesIO

class Dropdown(discord.ui.Select):
    def __init__(self, cards: dict[str, Card]):
        super().__init__(
            placeholder="Select a card to view...",
            min_values=1, max_values=1
        )
        self.options = []
        self._cards = cards

    async def callback(self, interaction: discord.Interaction) -> None:
        card_id = int(self.values[0])
        card = self._cards.get(str(card_id))

        embed = discord.Embed(title=f"ℹ️ Card Info", color=0x949fb8)
        embed.description = f"```🆔 {card.id.zfill(5)}\n" \
                            f"🏷️ {card.tag}\n" \
                            f"{card.tier[0]} {card.tier[1].capitalize()}\n" \
                            f"⭐ {card.stars}```\n" \
                            "Owned by: " + (f"<@{card.owner_id}>" if card.owner_id else "None")
        embed.set_image(url="attachment://image.png")

        resized_image_bytes = BytesIO()
        card.image.save(resized_image_bytes, format='PNG')
        resized_image_bytes.seek(0)

        await interaction.response.send_message(file=discord.File(resized_image_bytes, filename="image.png"), embed=embed)

class PhotoCardView(discord.ui.View):
    def __init__(self, author: discord.Member, cards: list[int], *, timeout: float | None = 100):
        super().__init__(timeout=timeout)

        self.author: discord.Member = author
        self.cards: dict[str, Card | None] = {card: None for card in cards}

        self.page: int = ceil(len(self.cards) / 10)
        self.current_page: int = 1

        self._dropdown_view: Dropdown = Dropdown(self.cards)
        self.add_item(self._dropdown_view)

        self.message: discord.Message = None

    def build_embed(self) -> discord.Embed:
        offset = self.current_page * 10
        cards = list(self.cards.keys())[(offset-10):offset]

        desc = f"\n**📙 Collection size: `{len(self.cards)}/{func.MAX_CARDS}`**\n```"
        for card_id in cards:
            card = self.cards.get(card_id)
            if not card:
                card = self.cards[card_id] = CardPool.get_card(card_id)

            desc += f"🆔{card.id.zfill(5)} 🏷️{card.tag if card.tag else '-':<12} ⭐{card.stars} {card.tier[0]}\n" if card else f"🆔 {card_id.zfill(5)} {'-' * 20}"
            self._dropdown_view.options.append(discord.SelectOption(label=f"{card.id}", emoji=card.tier[0]))
        embed = discord.Embed(title=f"📖 {self.author.display_name}'s Photocards", description=desc + "```", color=discord.Color.random())
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
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
    
    @discord.ui.button(label='Back', style=discord.ButtonStyle.blurple)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 1:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
    
    @discord.ui.button(label='Next', style=discord.ButtonStyle.blurple)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.page:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label='>>', style=discord.ButtonStyle.grey)
    async def fast_next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page != self.page:
            self.current_page = self.page
            await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(emoji='🗑️', style=discord.ButtonStyle.red)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.message.delete()
        self.stop()