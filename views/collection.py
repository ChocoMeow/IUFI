
import discord, iufi, asyncio

from discord.ext import commands

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
    def __init__(self,
                 ctx: commands.Context,
                 member: discord.Member,
                 collections: dict[str, list[str]],
                 timeout: float | None = 60
            ):
        super().__init__(timeout=timeout)
        
        self.ctx: commands.Context = ctx
        self.member: discord.Member = member
        self.collections: dict[str, list[str | None]] = collections
        self.sel_collection: str = list(self.collections.keys())[0]

        if len(self.collections) > 1:
            self.add_item(CollectionDropdown(list(self.collections.keys())))

        self.message: discord.Message = None

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        
        await self.message.edit(view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return self.ctx.author == interaction.user
    
    async def send_msg(self) -> None:
        cards: list[iufi.Card | None] = []

        embed = discord.Embed(title=f"❤️  {self.member.display_name}'s {self.sel_collection.title()} Collection", color=discord.Color.random())
        embed.description = "```"

        for card_id in self.collections[self.sel_collection]:
            card = iufi.CardPool.get_card(card_id)
            if card and card.owner_id == self.member.id:
                embed.description += f"{card.display_id} {card.display_tag} {card.display_frame} {card.display_stars} {card.tier[0]}\n"
                cards.append(card)
                continue

            embed.description += "\u200b\n"
            cards.append(None)
            
        embed.description += "```"
        image_bytes, image_format = await asyncio.to_thread(iufi.gen_cards_view, cards)
        embed.set_image(url=f"attachment://image.{image_format}")
        file=discord.File(image_bytes, filename=f'image.{image_format}')

        if self.message:
            return await self.message.edit(attachments=[file], embed=embed, view=self)
        self.message = await self.ctx.reply(file=file, embed=embed, view=self)