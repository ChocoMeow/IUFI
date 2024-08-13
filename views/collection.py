
import discord, iufi, asyncio, time
import functions as func

from discord.ext import commands

class CaptionModal(discord.ui.Modal, title="Add Caption"):
    def __init__(self, cards: list[iufi.Card]) -> None:
        self.cards = cards
        caption = discord.ui.TextInput(label='Caption')

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        image_bytes, image_format = await asyncio.to_thread(iufi.gen_cards_view, self.cards, size_rate=1)
        if self.cards and (gallery_channel := interaction.guild.get_channel(func.settings.GALLERY_CHANNEL_ID)):
            await gallery_channel.send(
                content=f"Sent by {interaction.user.mention}! {self.caption}",
                file=discord.File(image_bytes, filename=f'image.{image_format}')
            )

class EditBtn(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(emoji="✏️", label="Edit")
    
    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(EditModal(self.view))

class HDBtn(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(emoji="⚡", label="HD Image")
    
    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        await self.view.send_msg(1)

class GalleryBtn(discord.ui.Button):
    def __init__(self) -> None:
        self.view: CollectionView
        super().__init__(emoji="🎨", label="Send To Gallery")
        self.last_send_time: float = 0

    async def callback(self, interaction: discord.Interaction) -> None:
        if all(item is None for item in self.view.cards):
            return await interaction.response.send_message("You can't send this collection without any cards in it.", ephemeral=True)
        
        if time.time() < (self.last_send_time + 30):
            return await interaction.response.send_message("Whoa, that was too fast! Could you please try again later?", ephemeral=True)
        self.last_send_time = time.time()
        await interaction.response.send_modal(CaptionModal(self.view.cards))

class EditModal(discord.ui.Modal):
    def __init__(self, view: discord.ui.View) -> None:
        super().__init__(title="Edit Collection")
        self.view: CollectionView = view
        
        self.add_item(discord.ui.TextInput(
            label="Slot",
            min_length=1,
            max_length=1,
            placeholder="Enter 1 - 6"
        ))
        
        self.add_item(discord.ui.TextInput(
            label="Card",
            min_length=1,
            max_length=15,
            placeholder="Enter card id or tag",
            required=False
        ))
    
    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        slot, card_id = self.children[0].value, self.children[1].value
        if not slot.isdigit():
            return await interaction.followup.send(content=f"{interaction.user.mention} Please enter a integer in slot field.", ephemeral=True)
        
        slot = int(slot)
        if not (1 <= slot <= 6):
            return await interaction.followup.send(content=f"{interaction.user.mention} the slot must be within `the range of 1 to 6`.", ephemeral=True)
        
        name = self.view.sel_collection.lower()
        user = await func.get_user(interaction.user.id)
        if not user.get("collections", {}).get(name):
            return await interaction.followup.send(content=f"{interaction.user.mention} no collection with the name `{name}` was found.")
        
        if card_id:
            card = iufi.CardPool.get_card(card_id)
            if not card:
                return await interaction.followup.send("The card was not found. Please try again.")

            if card.owner_id != interaction.user.id:
                return await interaction.followup.send("You are not the owner of this card.")

        self.view.collections[self.view.sel_collection][slot - 1] = card_id
        await func.update_user(interaction.user.id, {"$set": {f"collections.{name}.{slot - 1}": card.id if card_id else None}})
        await self.view.send_msg()

class CollectionDropdown(discord.ui.Select):
    def __init__(self, options: list[str]):
        self.view: CollectionView
        
        super().__init__(
            placeholder="Select a collection to view...",
            min_values=1, max_values=1,
        )

        self.options = [discord.SelectOption(label=option.title()) for option in options]

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        self.view.sel_collection = self.values[0].lower()
        await self.view.send_msg()

class CollectionView(discord.ui.View):
    def __init__(
            self,
            ctx: commands.Context,
            member: discord.Member,
            collections: dict[str, list[str]],
            timeout: float | None = 60
        ):
        super().__init__(timeout=timeout)
        
        self.ctx: commands.Context = ctx
        self.member: discord.Member = member
        self.is_author: bool = ctx.author == member
        self.collections: dict[str, list[str | None]] = collections
        self.sel_collection: str = list(self.collections.keys())[0]
        self.cards: list[iufi.Card | None] = []

        if self.is_author:
            self.add_item(EditBtn())
            self.add_item(GalleryBtn())
        self.add_item(HDBtn())
        if len(self.collections) > 1:
            self.add_item(CollectionDropdown(list(self.collections.keys())))

        self.message: discord.Message = None

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        
        await self.message.edit(view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return self.ctx.author == interaction.user
    
    async def send_msg(self, size_rate: float = iufi.objects.SIZE_RATE) -> None:
        self.cards.clear()

        embed = discord.Embed(title=f"❤️  {self.member.display_name}'s {self.sel_collection.title()} Collection", color=discord.Color.random())
        embed.description = "```"

        for card_id in self.collections[self.sel_collection]:
            card = iufi.CardPool.get_card(card_id)
            if card and card.owner_id == self.member.id:
                embed.description += f"{card.display_id} {card.display_tag} {card.display_frame} {card.display_stars} {card.tier[0]}\n"
                self.cards.append(card)
                continue

            embed.description += "\u200b\n"
            self.cards.append(None)
            
        embed.description += "```"
        image_bytes, image_format = await asyncio.to_thread(iufi.gen_cards_view, self.cards, size_rate=size_rate)
        embed.set_image(url=f"attachment://image.{image_format}")
        image_file = discord.File(image_bytes, filename=f'image.{image_format}')

        if self.message:
            return await self.message.edit(attachments=[image_file], embed=embed, view=self)
        self.message = await self.ctx.reply(file=image_file, embed=embed, view=self)