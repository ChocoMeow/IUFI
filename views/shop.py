import discord
import functions as func
import events

def _build_shop_base() -> list[tuple[str, str, int]]:
    items = [
        (func.settings.TIERS_BASE.get("rare")[0], "roll.rare", 30),
        (func.settings.TIERS_BASE.get("epic")[0], "roll.epic", 100),
        (func.settings.TIERS_BASE.get("legendary")[0], "roll.legendary", 250),
        ("📦", "inventory.slots", 100),  # 1 extra card slot per purchase; base price is 100
    ]
    bp_settings = func.get_battlepass_settings()
    if bp_settings.get("enabled", False):
        items.append(("🎫", "battlepass.pass", int(bp_settings.get("shop_price_candies", 0))))
    return items

SHOP_BASE: list[tuple[str, str, int]] = _build_shop_base()

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
            discord.SelectOption(
                label="Battle Pass" if item[1] == "battlepass.pass" else f"{item[1].split('.')[1].title()} {item[1].split('.')[0].title()}",
                emoji=item[0],
                value=item[1]
            )
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
            if item[1] == selected_item:
                if item[1] == "battlepass.pass":
                    user = await func.get_user(interaction.user.id)
                    state = func.get_battlepass_state(user)
                    if state.get("is_active") or state.get("is_purchased"):
                        return await interaction.response.send_message("You already own this Battle Pass.", ephemeral=True)

                    price = events.shop_price(item[2], item[1])
                    if user.get("candies", 0) < price:
                        return await interaction.response.send_message(f"You don't have enough candies! You need `{price - user.get('candies', 0)}` more candies.", ephemeral=True)

                    query = func.update_quest_progress(user, "BUY_ITEM", progress=1, query={
                        "$inc": {"candies": -price},
                        "$set": {"battlepass.is_active": True, "battlepass.is_purchased": True}
                    })
                    await func.update_user(interaction.user.id, query)

                    embed = discord.Embed(title="🛒 Shop Purchase", color=discord.Color.random())
                    embed.description = f"```🎫 Battle Pass\n🍬 - {price}```\nYou now earn **full** Battle Pass XP."
                    return await interaction.response.send_message(embed=embed)

                modal = QuantityModal()
                await interaction.response.send_modal(modal)
                await modal.wait()

                if modal.quantity:
                    user = await func.get_user(interaction.user.id)

                    # Handle inventory slots (1 slot per purchase) differently because price increases with purchases
                    if item[1] == "inventory.slots":
                        # number of previous slot purchases made by the user
                        prev_purchases = user.get("extra_props", {}).get("slot_purchases", 0)
                        qty = modal.quantity
                        base_price = item[2] if isinstance(item[2], int) else 100

                        total_price = 0
                        for i in range(qty):
                            total_price += events.shop_price(base_price + (prev_purchases + i) * 10, item[1])

                        if user["candies"] < total_price:
                            needed = total_price - user["candies"]
                            return await interaction.followup.send(f"You don't have enough candies! You need `{needed}` more candies (price goes up as you purchase more slots).", ephemeral=True)

                        # apply update: decrement candies, increment extra_card_slots by qty, increment slot_purchases by qty
                        query = func.update_quest_progress(user, "BUY_ITEM", progress=modal.quantity, query={
                            "$inc": {"candies": -total_price, "extra_props.extra_card_slots": modal.quantity, "extra_props.slot_purchases": modal.quantity}
                        })

                        await func.update_user(interaction.user.id, query)

                        func.logger.info(f"User {interaction.user.name}({interaction.user.id}) purchased {modal.quantity} extra slot(s) for {total_price} candies.")

                        embed = discord.Embed(title="🛒 Shop Purchase", color=discord.Color.random())
                        embed.description = f"```{item[0]} + {modal.quantity} slot{'s' if modal.quantity > 1 else ''}\n🍬 - {total_price}```"

                        return await interaction.followup.send(content="", embed=embed)

                    # default behavior for other items
                    price = modal.quantity * events.shop_price(item[2], item[1])
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
        embed.description = f"🍬 Starcandies: `{user.get('candies', 0)}`\n"
        sale_pct = int(round(events.shop_sale_fraction() * 100))
        if events.is_active() and sale_pct > 0:
            embed.description += f"🎉 **{events.name()}** / community sale: `{sale_pct}%` off shop items"
            if events.milestone_shop_sale_fraction() > 0:
                embed.description += " (excluding battlepass)"
            embed.description += "\n"
        elif events.milestone_shop_sale_fraction() > 0:
            embed.description += f"🎉 Community milestone: `{int(round(events.milestone_shop_sale_fraction() * 100))}%` off shop items (excluding battlepass)\n"
        embed.description += "```"
        
        for item in SHOP_BASE:
            # For inventory slots, show the next price per slot based on user's purchases
            if item[1] == "inventory.slots":
                prev_purchases = user.get("extra_props", {}).get("slot_purchases", 0)
                next_price = events.shop_price(item[2] + prev_purchases * 10, item[1])
                display_price = f"{next_price} (per slot)"
                embed.description += f"{item[0]} {(item[1].split('.')[1].title() + ' ' + item[1].split('.')[0].title()).upper():<20} {display_price:>10} 🍬\n"
            elif item[1] == "battlepass.pass":
                state = func.get_battlepass_state(user)
                status = "OWNED" if state.get("is_active") or state.get("is_purchased") else f"{events.shop_price(item[2], item[1])} 🍬"
                embed.description += f"{item[0]} {'BATTLE PASS':<20} {status:>10}\n"
            else:
                embed.description += f"{item[0]} {(item[1].split('.')[1].title() + ' ' + item[1].split('.')[0].title()).upper():<20} {events.shop_price(item[2], item[1]):>3} 🍬\n"
        embed.description += "```"
        
        embed.set_thumbnail(url=self.author.display_avatar.url)

        return embed
