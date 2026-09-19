import iufi
import discord
import functions as func

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
            "$pull": {
                "wishlist": {"$in": self.values},
                "wishlist_boosts": {"$in": self.values}
            }
        })
        await self.view.update_data()

class BoostDropDown(discord.ui.Select):
    def __init__(self, cards: List[iufi.Card], boosts: List[str]):
        self.view: WishListView

        super().__init__(
            placeholder="Select a card to boost its roll chance.",
            min_values=1, max_values=1,
            options=self._generate_options(cards, boosts)
        )

    @staticmethod
    def _generate_options(cards: List[iufi.Card], boosts: List[str]) -> List[discord.SelectOption]:
        return [
            discord.SelectOption(
                value=card.id,
                label=f"{'⚡ ' if card.id in boosts else ''}{card.display_id}",
                description=f"{card.tier[1].capitalize()}" + (" (boosted)" if card.id in boosts else ""),
                emoji=card.tier[0]
            ) for card in cards
        ]

    async def callback(self, interaction: discord.Interaction):
        card = iufi.CardPool.get_card(self.values[0])
        if not card:
            return await interaction.response.send_message("This card no longer exists.", ephemeral=True)

        tier = card.tier[1]
        boosts = [card_id for card_id in self.view.boosts if card_id != card.id]

        if card.id in self.view.boosts:
            message = f"`{card.display_id}` is no longer boosted."

        elif card.owner_id:
            return await interaction.response.send_message(
                f"`{card.display_id}` is already owned, so you cannot put a boost on it.",
                ephemeral=True
            )

        else:
            # Only one boosted card per tier, so the previous pick is dropped.
            replaced = None
            for boosted_id in boosts:
                boosted_card = iufi.CardPool.get_card(boosted_id)
                if boosted_card and boosted_card.tier[1] == tier:
                    replaced = boosted_card
                    break

            if replaced:
                boosts.remove(replaced.id)

            boosts.append(card.id)
            message = f"`{card.display_id}` is now your boosted `{tier}` wish card."
            if replaced:
                message += f" It replaced `{replaced.display_id}`."

        await func.update_user(interaction.user.id, {"$set": {"wishlist_boosts": boosts}})
        await interaction.response.send_message(message, ephemeral=True)
        await self.view.update_data()

class WishListView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, user: Dict[str, Any], timeout: float | None = 180):
        super().__init__(timeout=timeout)

        self.interaction: discord.Interaction = interaction
        self.wishlist = user.get("wishlist", [])
        self.boosts = user.get("wishlist_boosts", [])
        self.cards = iufi.CardPool.search_valid_cards(self.wishlist)
        self.select_dropdown = None
        self.boost_dropdown = None

        if self.wishlist:
            self.select_dropdown = RemoveDropDown(self.cards)
            self.boost_dropdown = BoostDropDown(self.cards, self.boosts)
            self.add_item(self.select_dropdown)
            self.add_item(self.boost_dropdown)

        self.page: int = ceil(len(self.cards) / 13)
        self.current_page: int = 1
        self.message: discord.Message = None

    def build_embed(self) -> discord.Embed:
        offset = self.current_page * 13
        cards = self.cards[(offset - 13):offset]

        if not cards:
            desc = "Your wishlist is currently empty."
        else:
            desc = f"Here are the cards in your wishlist: [{len(self.cards)}/25]\n" \
                   "⚡ marks the boosted card of a tier. You can boost one card per tier.\n```"
            for card in cards:
                member = self.interaction.guild.get_member(card.owner_id)
                desc += f"{'⚡' if card.id in self.boosts else '  '} {card.display_id} {card.display_frame} {card.display_stars} {card.tier[0]} 👤 {member.display_name if member else 'None':5}\n"
            desc += "```"

        embed = discord.Embed(title="Your Wishlist", description=desc, color=discord.Color.random())

        if self.page > 0:
            embed.set_footer(text="Pages: {}/{}".format(self.current_page, self.page))
            
        return embed

    async def update_data(self) -> None:
        user = await func.get_user(self.interaction.user.id)
        self.wishlist = user.get("wishlist", [])
        self.boosts = user.get("wishlist_boosts", [])
        self.cards = iufi.CardPool.search_valid_cards(self.wishlist)
        self.page: int = ceil(len(self.cards) / 13)
        self.current_page: int = 1
        
        if self.select_dropdown:
            self.select_dropdown.options = self.select_dropdown._generate_options(self.cards)
            self.select_dropdown.max_values = len(self.cards)
        elif self.cards:
            self.select_dropdown = RemoveDropDown(self.cards)
            self.add_item(self.select_dropdown)

        if self.boost_dropdown:
            self.boost_dropdown.options = self.boost_dropdown._generate_options(self.cards, self.boosts)
        elif self.cards:
            self.boost_dropdown = BoostDropDown(self.cards, self.boosts)
            self.add_item(self.boost_dropdown)
        
        if not self.cards:
            self.remove_item(self.select_dropdown)
            self.remove_item(self.boost_dropdown)
            self.select_dropdown = self.boost_dropdown = None

        await self.message.edit(embed=self.build_embed(), view=self)

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        
        await self.message.edit(view=self)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return self.interaction.user == interaction.user
    
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
        await func.update_user(interaction.user.id, {"$unset": {"wishlist": [], "wishlist_boosts": []}})
        await interaction.response.send_message("You have successfully removed all cards from your wishlist.", ephemeral=True)
        await self.update_data()