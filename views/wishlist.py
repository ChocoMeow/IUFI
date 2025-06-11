import iufi
import discord
import functions as func

from discord.ext import commands
from typing import Dict, List, Any
from math import ceil

class AddModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title="Edit Collection")

        self.view: WishListView = view
        self.add_item(discord.ui.TextInput(
            label="Card IDs",
            placeholder="Enter IDs (e.g., ID1 ID2 ID3 ...)",
            required=True
        ))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        # Split input and filter for valid card IDs
        card_ids = set(self.children[0].value.split())
        validated_cards = iufi.CardPool.search_valid_cards(card_ids)

        if validated_cards:
            if (len(validated_cards) + len(self.view.cards)) > 25:
                return await interaction.followup.send("You can only add up to 25 cards to your wishlist.", ephemeral=True)
            
            if any(card in self.view.cards for card in validated_cards):
                return await interaction.followup.send("You can't add these cards as they are already in your wishlist.", ephemeral=True)
            
            if any(card.owner_id == interaction.user.id for card in validated_cards):
                return await interaction.followup.send("Oops! You can’t add cards that you already own.", ephemeral=True)
            
            await func.update_user(interaction.user.id, {
                "$push": {"wishlist": {"$each": [card.id for card in validated_cards]}}
            })
            await interaction.followup.send("Cards added to your wishlist successfully.", ephemeral=True)
            await self.view.update_data()
        else:
            await interaction.followup.send("No valid card IDs were provided.", ephemeral=True)

class RemoveDropDown(discord.ui.Select):
    def __init__(self, cards: List[iufi.Card]):
        self.view: WishListView

        super().__init__(
            placeholder="Select cards to remove from your wishlist.",
            min_values=1, max_values=len(cards),
            options=[discord.SelectOption(
                value=card.id,
                label=card.display_id,
                description=f"{card.display_stars} {card.display_tag}",
                emoji=card.tier[0]
            ) for card in cards]
        )

    async def callback(self, interaction: discord.Interaction):
        await func.update_user(interaction.user.id, {
            "$pull": {"wishlist": {"$in": self.values}}
        })
        await interaction.response.send_message(f"You have successfully removed {len(self.values)} cards from your wishlist.", ephemeral=True)
        await self.view.update_data()
        
class RemoveDropDown(discord.ui.Select):
    def __init__(self, cards: List[iufi.Card]):
        self.view: WishListView

        super().__init__(
            placeholder="Select cards to remove from your wishlist.",
            min_values=1, max_values=len(cards),
            options=self._generate_options(cards)
        )

    @staticmethod
    def _generate_options(cards: List[iufi.Card]) -> List[discord.SelectOption]:
        return [
            discord.SelectOption(
                value=card.id,
                label=card.display_id,
                description=f"{card.display_stars} {card.display_tag}",
                emoji=card.tier[0]
            ) for card in cards
        ]

    async def callback(self, interaction: discord.Interaction):
        await func.update_user(interaction.user.id, {
            "$pull": {"wishlist": {"$in": self.values}}
        })
        await self.view.update_data()

class WishListView(discord.ui.View):
    def __init__(self, ctx: commands.Context, user: Dict[str, Any], timeout: float | None = 180):
        super().__init__(timeout=timeout)

        self.ctx: commands.Context = ctx
        self.wishlist = user.get("wishlist", [])
        self.cards = iufi.CardPool.search_valid_cards(self.wishlist)
        self.select_dropdown = None

        if self.wishlist:
            self.select_dropdown = RemoveDropDown(self.cards)
            self.add_item(self.select_dropdown)

        self.page: int = ceil(len(self.cards) / 13)
        self.current_page: int = 1
        self.message: discord.Message = None

    def build_embed(self) -> discord.Embed:
        offset = self.current_page * 13
        cards = self.cards[(offset - 13):offset]

        if not cards:
            desc = "Your wishlist is currently empty."
        else:
            desc = f"Here are the cards in your wishlist: [{len(self.cards)}/25]\n```"
            for card in cards:
                member = self.ctx.guild.get_member(card.owner_id)
                desc += f"{card.display_id} {card.display_frame} {card.display_stars} {card.tier[0]} 👤 {member.display_name if member else 'None':5}\n"
            desc += "```"

        embed = discord.Embed(title="Your Wishlist", description=desc, color=discord.Color.random())

        if self.page > 0:
            embed.set_footer(text="Pages: {}/{}".format(self.current_page, self.page))
            
        return embed

    async def update_data(self) -> None:
        user = await func.get_user(self.ctx.author.id)
        self.wishlist = user.get("wishlist", [])
        self.cards = iufi.CardPool.search_valid_cards(self.wishlist)
        self.page: int = ceil(len(self.cards) / 13)
        self.current_page: int = 1
        
        if self.select_dropdown:
            self.select_dropdown.options = self.select_dropdown._generate_options(self.cards)
            self.select_dropdown.max_values = len(self.cards)
        else:
            self.select_dropdown = RemoveDropDown(self.cards)
            self.add_item(self.select_dropdown)
        
        if not self.cards:
            self.remove_item(self.select_dropdown)

        await self.message.edit(embed=self.build_embed(), view=self)

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        
        await self.message.edit(view=self)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return self.ctx.author == interaction.user
    
    @discord.ui.button(label='Back', style=discord.ButtonStyle.blurple)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if self.current_page > 1:
            self.current_page -= 1
            await self.message.edit(embed=self.build_embed())
    
    @discord.ui.button(label='Next', style=discord.ButtonStyle.blurple)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if self.current_page < self.page:
            self.current_page += 1
            await self.message.edit(embed=self.build_embed())

    @discord.ui.button(label="Add Card", style=discord.ButtonStyle.green)
    async def add(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddModal(self))

    @discord.ui.button(label="Clear All", style=discord.ButtonStyle.red)
    async def clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        await func.update_user(interaction.user.id, {"$unset": {"wishlist": []}})
        await interaction.response.send_message("You have successfully removed all cards from your wishlist.", ephemeral=True)
        await self.update_data()