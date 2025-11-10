import discord
import functions as func

SHOP_BASE: list[tuple[str, str, int]] = [
    (func.settings.TIERS_BASE.get("rare")[0], "roll.rare", 30),
    (func.settings.TIERS_BASE.get("epic")[0], "roll.epic", 100),
    (func.settings.TIERS_BASE.get("legendary")[0], "roll.legendary", 250),
    ("📦", "inventory.slots", 100)  # 10 extra card slots per purchase; base price is 100
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

                    # Handle inventory slots (10 slots per "item") differently because price is exponential
                    if item[1] == "inventory.slots":
                        # number of previous 10-slot purchases made by the user
                        prev_purchases = user.get("extra_props", {}).get("slot_purchases", 0)
                        qty = modal.quantity
                        base_price = item[2] if isinstance(item[2], int) else 100

                        # compute total cost: sum of base * 2^(prev_purchases + i)
                        total_price = 0
                        for i in range(qty):
                            total_price += base_price * (2 ** (prev_purchases + i))

                        if user["candies"] < total_price:
                            return await interaction.followup.send(f"You don't have enough candies! You only have `{user['candies']}` candies", ephemeral=True)

                        # apply update: decrement candies, increment extra_card_slots by qty*10, increment slot_purchases by qty
                        query = func.update_quest_progress(user, "BUY_ITEM", progress=modal.quantity, query={
                            "$inc": {"candies": -total_price, "extra_props.extra_card_slots": modal.quantity * 10, "extra_props.slot_purchases": modal.quantity}
                        })

                        await func.update_user(interaction.user.id, query)

                        func.logger.info(f"User {interaction.user.name}({interaction.user.id}) purchased {modal.quantity * 10} extra slots (batches={modal.quantity}) for {total_price} candies.")

                        embed = discord.Embed(title="🛒 Shop Purchase", color=discord.Color.random())
                        embed.description = f"```{item[0]} + {modal.quantity * 10} slots\n🍬 - {total_price}```"

                        return await interaction.followup.send(content="", embed=embed)

                    # default behavior for other items
                    price = modal.quantity * item[2]
                    if user["candies"] < price:
                        return await interaction.followup.send(f"You don't have enough candies! You only have `{user['candies']}` candies", ephemeral=True)
                    
                    query = func.update_quest_progress(user, "BUY_ITEM", progress=modal.quantity, query={
                        "$inc": {"candies": -price, item[1]: modal.quantity}
                    })
                    await func.update_user(interaction.user.id, query)

                    func.logger.info(f"User {interaction.user.name}({interaction.user.id}) purchased {modal.quantity} {selected_item.lower()} for {price} candies.")

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
            # For inventory slots, show the next price per 10 slots based on user's purchases
            if item[1] == "inventory.slots":
                prev_purchases = user.get("extra_props", {}).get("slot_purchases", 0)
                next_price = item[2] * (2 ** prev_purchases)
                display_price = f"{next_price} (per 10 slots)"
                embed.description += f"{item[0]} {(item[1].split('.')[1].title() + ' ' + item[1].split('.')[0].title()).upper():<20} {display_price:>10} 🍬\n"
            else:
                embed.description += f"{item[0]} {(item[1].split('.')[1].title() + ' ' + item[1].split('.')[0].title()).upper():<20} {item[2]:>3} 🍬\n"
        embed.description += "```"
        
        embed.set_thumbnail(url=self.author.display_avatar.url)

        return embed
