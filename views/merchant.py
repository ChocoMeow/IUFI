import asyncio
import time

import discord

import debut
import functions as func


class MerchantQuantityModal(discord.ui.Modal):
    def __init__(self, max_qty: int) -> None:
        super().__init__(title="How many to buy?")
        self.quantity = 0
        self.add_item(
            discord.ui.TextInput(
                label=f"Quantity (1–{max_qty})",
                placeholder="1",
                style=discord.TextStyle.short,
            )
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            self.quantity = int(self.children[0].value)
            if self.quantity <= 0:
                self.quantity = 0
                await interaction.response.send_message("Please enter a number greater than 0.", ephemeral=True)
                return
            await interaction.response.defer(ephemeral=True)
        except Exception:
            self.quantity = 0
            await interaction.response.send_message("Please enter a number!", ephemeral=True)
        self.stop()


class MerchantSelect(discord.ui.Select):
    def __init__(self, view: "WanderingMerchantView") -> None:
        self.merchant_view = view
        super().__init__(
            placeholder="Pick an item to buy...",
            min_values=1,
            max_values=1,
            options=view.select_options(),
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.merchant_view.handle_select(interaction, self.values[0])


class WanderingMerchantView(discord.ui.View):
    def __init__(self, listings: list[dict], timeout: float) -> None:
        super().__init__(timeout=timeout)
        self.listings = listings
        self.closes_at = time.time() + timeout
        self.message: discord.Message | None = None
        self.closed = False
        self._lock = asyncio.Lock()
        self._select = MerchantSelect(self)
        self.add_item(self._select)

    def listing_by_id(self, sku: str) -> dict | None:
        for item in self.listings:
            if item.get("id") == sku:
                return item
        return None

    def select_options(self) -> list[discord.SelectOption]:
        options: list[discord.SelectOption] = []
        for item in self.listings:
            left = int(item.get("left", 0) or 0)
            if left <= 0:
                continue
            option_kwargs = {
                "label": str(item.get("name") or item["id"])[:100],
                "value": str(item["id"]),
                "description": f"{item.get('price', 0)} 🍬 · stock {left}"[:100],
            }
            if item.get("emoji"):
                option_kwargs["emoji"] = item["emoji"]
            options.append(discord.SelectOption(**option_kwargs))
        if not options:
            options.append(
                discord.SelectOption(
                    label="Sold out",
                    value="sold_out",
                    description="The truck has nothing left this visit.",
                )
            )
        return options

    def rebuild_select(self) -> None:
        self._select.options = self.select_options()
        sold_out = all(int(item.get("left", 0) or 0) <= 0 for item in self.listings)
        self._select.disabled = sold_out or self.closed
        if sold_out:
            self._select.placeholder = "Sold out this visit"

    def build_embed(self, *, closed: bool = False) -> discord.Embed:
        if closed:
            embed = discord.Embed(
                title="🚚 Wandering Merchant — Shop closed",
                description="The wandering merchant truck has left. Shop closed.",
                color=discord.Color.dark_grey(),
            )
            return embed

        embed = discord.Embed(
            title="🚚 Wandering Merchant Truck",
            color=discord.Color.gold(),
        )
        lines = [
            "A truck rolled into the channel with limited IUFI goods. Buy before it leaves!",
            "One purchase per person this visit.",
            f"Closes <t:{round(self.closes_at)}:R>",
            "```",
        ]
        for item in self.listings:
            left = int(item.get("left", 0) or 0)
            status = "SOLD OUT" if left <= 0 else f"{item.get('price', 0)} 🍬"
            name = f"{item.get('emoji', '')} {item.get('name', item['id'])}"
            lines.append(f"{name:<28} {status:>12}  stock {left}")
        lines.append("```")
        embed.description = "\n".join(lines)
        return embed

    async def close_shop(self) -> None:
        async with self._lock:
            if self.closed:
                return
            self.closed = True
        self.stop()
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(content="Shop closed.", embed=self.build_embed(closed=True), view=self)
            except discord.HTTPException as error:
                func.logger.warning("Failed to close wandering merchant message: %s", error)
        if debut.get_active_view() is self:
            debut.set_active_view(None)

    async def on_timeout(self) -> None:
        await self.close_shop()

    async def refresh_message(self) -> None:
        self.rebuild_select()
        if self.message:
            try:
                await self.message.edit(embed=self.build_embed(), view=self)
            except discord.HTTPException:
                pass

    def _max_quantity(self, listing: dict, user_id: int) -> int:
        if debut.bought_this_visit(user_id):
            return 0
        left = int(listing.get("left", 0) or 0)
        catalog = debut.item_by_id(str(listing["id"]))
        per_person = None if catalog is None else catalog.get("per_person")
        if per_person is not None:
            try:
                cap = int(per_person)
            except (TypeError, ValueError):
                cap = left
            left = min(left, max(0, cap - debut.person_purchased(user_id, str(listing["id"]))))
        remaining = listing.get("stock")
        if remaining is not None:
            left = min(left, int(remaining))
        return max(0, left)

    async def handle_select(self, interaction: discord.Interaction, sku: str) -> None:
        if self.closed:
            return await interaction.response.send_message("The truck already left.", ephemeral=True)
        if sku == "sold_out":
            return await interaction.response.send_message("The truck is sold out this visit.", ephemeral=True)

        listing = self.listing_by_id(sku)
        if not listing or int(listing.get("left", 0) or 0) <= 0:
            return await interaction.response.send_message("That item is gone this visit.", ephemeral=True)

        max_qty = self._max_quantity(listing, interaction.user.id)
        if max_qty <= 0:
            if debut.bought_this_visit(interaction.user.id):
                return await interaction.response.send_message(
                    "You already bought something this visit. Wait for the truck to come back.",
                    ephemeral=True,
                )
            return await interaction.response.send_message("You cannot buy any more of this item.", ephemeral=True)

        quantity = 1
        if int(listing.get("per_appearance", 1) or 1) > 1:
            modal = MerchantQuantityModal(max_qty)
            await interaction.response.send_modal(modal)
            await modal.wait()
            if not modal.quantity:
                return
            quantity = min(modal.quantity, max_qty)
            followup = True
        else:
            await interaction.response.defer(ephemeral=True)
            followup = True

        async with self._lock:
            if self.closed:
                ok = False
                msg = "The truck already left."
            else:
                ok, msg = await debut.purchase(interaction.user.id, listing, quantity)
                if ok:
                    self.rebuild_select()
                    if self.message:
                        try:
                            await self.message.edit(embed=self.build_embed(), view=self)
                        except discord.HTTPException:
                            pass

        if followup:
            await interaction.followup.send(msg, ephemeral=True)


async def spawn_merchant(channel, *, record_appearance: bool = True) -> discord.Message | None:
    listings = debut.build_appearance_stock()
    if not listings:
        func.logger.info("Wandering merchant skipped: no stock left.")
        return None

    duration = debut.appearance_duration()
    debut.reset_visit_buyers()
    view = WanderingMerchantView(listings, duration)
    debut.set_active_view(view)
    try:
        view.message = await channel.send(
            content=f"**The wandering merchant truck is here! Closes <t:{round(view.closes_at)}:R>**",
            embed=view.build_embed(),
            view=view,
        )
    except Exception:
        debut.set_active_view(None)
        raise
    if record_appearance:
        await debut.mark_appearance()
    func.logger.info(
        "Wandering merchant spawned in %s(%s) for %ss with %s item(s)",
        getattr(channel, "name", "unknown"),
        getattr(channel, "id", "?"),
        duration,
        len(listings),
    )
    return view.message
