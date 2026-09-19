import discord, iufi

from .hd import HDBtn


class CardInfoView(discord.ui.View):
    def __init__(
        self,
        author: discord.abc.User,
        cards: list[iufi.Card],
        guild: discord.Guild | None = None,
        *,
        timeout: float | None = 60
    ):
        super().__init__(timeout=timeout)

        self.author = author
        self.cards = cards
        self.guild = guild
        self.message: discord.Message | None = None

        self.add_item(HDBtn())

    def is_gif(self) -> bool:
        return any(card.is_gif for card in self.cards if card)

    def hd_blocked_reason(self) -> str | None:
        cards = [card for card in self.cards if card]
        if any(card._tier == "celestial" for card in cards):
            return "Celestial cards cannot be shown in HD."
        if any(card.is_gif for card in cards):
            return "GIF cards cannot be shown in HD."
        return None

    def build_embed(self) -> discord.Embed:
        if len(self.cards) > 1:
            desc = "```"
            for card in self.cards:
                member = self.guild.get_member(card.owner_id) if self.guild else None
                desc += f"{card.display_id} {card.display_tag} {card.display_frame} {card.display_stars} {card.tier[0]} 👤 {member.display_name if member else 'None':5}\n"
            desc += "```"
        else:
            card = self.cards[0]
            desc = f"```{card.display_id}\n" \
                   f"{card.display_tag}\n" \
                   f"{card.display_frame}\n" \
                   f"{card.tier[0]} {card.tier[1].capitalize()}\n" \
                   f"{card.display_stars}```\n" \
                   "**Owned by: **" + (f"<@{card.owner_id}>" if card.owner_id else "None")

        return discord.Embed(title="ℹ️ Card Info", description=desc, color=0x949fb8)

    async def render(self, size_rate: float = iufi.objects.SIZE_RATE) -> tuple[discord.Embed, discord.File]:
        embed = self.build_embed()

        if len(self.cards) > 1:
            image_bytes, image_format = await iufi.gen_cards_view(
                self.cards, 4, size_rate=size_rate, hide_image_if_no_owner=True
            )
        else:
            card = self.cards[0]
            image_bytes, image_format = await card.image_bytes(True, size_rate=size_rate), card.format

        embed.set_image(url=f"attachment://image.{image_format}")
        return embed, discord.File(image_bytes, filename=f"image.{image_format}")

    async def apply_hd(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        embed, file = await self.render(1)
        if self.message:
            await self.message.edit(embed=embed, attachments=[file], view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.author

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True

        if self.message:
            await self.message.edit(view=self)
