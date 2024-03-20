import discord
import functions as func

SHOP_BASE: list[tuple[str, str, int]] = [
    (func.settings.TIERS_BASE.get("rare")[0], "roll.rare", 30),
    (func.settings.TIERS_BASE.get("epic")[0], "roll.epic", 100),
    (func.settings.TIERS_BASE.get("legendary")[0], "roll.legendary", 250)
]

class QuantityModal(discord.ui.Modal):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(title="Enter your quantity", *args, **kwargs)

        self.quantity = 0

        self.add_item(
            discord.ui.TextInput(
                label="Quantity",
                placeholder="Enter a number E.g. 10",
                style=discord.TextStyle.short,
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        self.quantity = self.children[0].value
        try:
            self.quantity = int(self.quantity)
            if self.quantity <= 0:
                self.quantity = 0
            await interaction.response.defer()
        except Exception as _:
            await interaction.response.send_message("Please enter a number!", ephemeral=True)
            self.quantity = 0
        self.stop()

class Dropdown(discord.ui.Select):
    def __init__(self) -> None:
        options = [
            discord.SelectOption(label=f"{item[1].split('.')[1].title()} {item[1].split('.')[0].title()}", emoji=item[0])
            for item in SHOP_BASE
        ]

        super().__init__(
            placeholder="Select a item to buy...",
            min_values=1, max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        selected_item = self.values[0].split(" ")[0]
        for item in SHOP_BASE:
            if item[1].split(".")[1] == selected_item.lower():
                modal = QuantityModal()
                await interaction.response.send_modal(modal)
                await modal.wait()

                if modal.quantity:
                    user = await func.get_user(interaction.user.id)
                    price = modal.quantity * item[2]
                    if user["candies"] < price:
                        return await interaction.followup.send(f"You don't have enough candies! You only have `{user['candies']}` candies", ephemeral=True)
                    
                    query = func.update_quest_progress(user, "BUY_ITEM", progress=modal.quantity, query={
                        "$inc": {"candies": -price, item[1]: modal.quantity}
                    })
                    await func.update_user(interaction.user.id, query)

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

    async def build_embed(self) -> discord.Embed:
        user = await func.get_user(self.author.id)

        embed = discord.Embed(title="🛒 IUFI Shop", color=discord.Color.random())
        embed.description = f"🍬 Starcandies: `{user.get('candies', 0)}`\n```"
        
        for item in SHOP_BASE:
            embed.description += f"{item[0]} {(item[1].split('.')[1].title() + ' ' + item[1].split('.')[0].title()).upper():<20} {item[2]:>3} 🍬\n"
        embed.description += "```"
        
        embed.set_thumbnail(url=self.author.display_avatar.url)

        return embed
