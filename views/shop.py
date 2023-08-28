import discord
import functions as func

SHOP_BASE: list[tuple[str, str, int]] = [
    ("🌸", "rare", 30),
    ("💎", "epic", 100),
    ("👑", "legendary", 250)
]

class QuantityModal(discord.ui.Modal):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(title="Enter your quantity", *args, **kwargs)

        self.quantity = 0

        self.add_item(
            discord.ui.TextInput(
                label="Code Runner",
                placeholder="Enter a number E.g. 10",
                style=discord.TextStyle.short,
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        self.quantity = self.children[0].value
        try:
            self.quantity = int(self.quantity)
            await interaction.response.defer()
        except Exception as _:
            await interaction.response.send_message("Please enter a number!", ephemeral=True)
        self.stop()

class Dropdown(discord.ui.Select):
    def __init__(self) -> None:
        options = [
            discord.SelectOption(label=item[1].title(), emoji=item[0])
            for item in SHOP_BASE
        ]

        super().__init__(
            placeholder="Select a item to buy...",
            min_values=1, max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        selected_item = self.values[0]
        for item in SHOP_BASE:
            if item[1] == selected_item.lower():
                modal = QuantityModal()
                await interaction.response.send_modal(modal)
                await modal.wait()

                if modal.quantity:
                    user = func.get_user(interaction.user.id)
                    price = modal.quantity * item[2]
                    if user["candies"] < price:
                        return await interaction.followup.send(f"You don't have enough candies! You only have `{user['candies']}` candies", ephemeral=True)
                    
                    func.update_user(interaction.user.id, {
                        "$inc": {"candies": -price, f"roll.{item[1]}": modal.quantity},
                    })

                    embed = discord.Embed(title="🛒 Shop Purchase", color=discord.Color.random())
                    embed.description = f"```{item[0]} + {modal.quantity}\n🍬 - {price}```"

                    return await interaction.followup.send(content="", embed=embed)

class ShopView(discord.ui.View):
    def __init__(self, author: discord.Member, timeout: float | None = 60):
        super().__init__(timeout=timeout)

        self.add_item(Dropdown())
        self.author: discord.Member = author
        self.message: discord.Member = None

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        await self.message.edit(view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.author

    def build_embed(self) -> discord.Embed:
        user = func.get_user(self.author.id)

        embed = discord.Embed(title="🛒 IUFI Shop", color=discord.Color.random())
        embed.description = f"🍬 Starcandies: `{user.get('candies', 0)}`\n```"
        
        for item in SHOP_BASE:
            embed.description += f"{item[0]} {(item[1] + ' Roll').upper():<20} {item[2]:>3} 🍬\n"
        embed.description += "```"
        
        embed.set_thumbnail(url=self.author.avatar.url)

        return embed

    
