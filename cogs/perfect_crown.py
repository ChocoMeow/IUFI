import os

import discord
import time
import functions as func

from discord.ext import commands

from iufi.perfect_crown import (
    apply_contract_cooldown,
    ROYAL_CONTRACT_TEAMS,
    ROYAL_TREASURY_TIERS,
    ROYAL_TREASURY_TOKEN_COSTS,
    is_royal_treasury_open,
    get_user_perfect_crown_tokens,
    get_treasury_cards_for_tier,
)


class TreasuryTierDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=f"{item['label']} Tier",
                emoji=str(item["emoji"]),
                value=key,
            )
            for key, item in ROYAL_TREASURY_TIERS.items()
        ]
        super().__init__(
            placeholder="Select a treasury section...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        view: RoyalTreasuryView = self.view
        view.selected_tier = self.values[0]
        await interaction.response.edit_message(embed=await view.build_embed(), view=view)


class TreasuryBuyModal(discord.ui.Modal):
    def __init__(self, view: "RoyalTreasuryView"):
        super().__init__(title="Buy Card From Treasury")
        self.view_ref = view
        self.card_index = discord.ui.TextInput(
            label="Card Number (treasury order)",
            placeholder="Enter index (e.g. 1, 2, 3...)",
            style=discord.TextStyle.short,
            required=True,
            max_length=5,
        )
        self.add_item(self.card_index)

    async def on_submit(self, interaction: discord.Interaction):
        view = self.view_ref
        tier = view.selected_tier
        bot_user_id = interaction.client.user.id if interaction.client.user else None
        if not bot_user_id:
            return await interaction.response.send_message("Bot state not ready yet. Try again.", ephemeral=True)

        try:
            index = int(str(self.card_index.value).strip())
            if index <= 0:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message("Please enter a valid positive number.", ephemeral=True)

        cards = get_treasury_cards_for_tier(tier)
        if index > len(cards):
            return await interaction.response.send_message(
                f"Invalid card number. `{tier}` section has `{len(cards)}` entries.",
                ephemeral=True,
            )

        card = cards[index - 1]
        if not card:
            return await interaction.response.send_message("This treasury slot has no configured card.", ephemeral=True)

        if card.owner_id != bot_user_id:
            return await interaction.response.send_message(
                "This card is sold out already.", ephemeral=True
            )

        user = await func.get_user(interaction.user.id)
        if len(user.get("cards", [])) >= func.get_user_card_limit(user):
            return await interaction.response.send_message("Your inventory is full.", ephemeral=True)

        owned_tokens = sorted(get_user_perfect_crown_tokens(user))
        token_cost = ROYAL_TREASURY_TOKEN_COSTS[tier]
        if len(owned_tokens) < token_cost:
            return await interaction.response.send_message(
                f"You need `{token_cost}` tokens, but only have `{len(owned_tokens)}`.",
                ephemeral=True,
            )

        consumed_tokens = owned_tokens[:token_cost]
        actived_potions = func.get_potions(user.get("actived_potions", {}), func.settings.POTIONS_BASE)
        user_query = func.update_quest_progress(
            user,
            ["COLLECT_ANY_CARD", f"COLLECT_{card._tier.upper()}_CARD"],
            query={
                "$push": {"cards": card.id},
                "$set": {
                    "cooldown.claim": time.time() + (
                        apply_contract_cooldown(
                            func.settings.COOLDOWN_BASE["claim"][1] * (1 - actived_potions.get("speed", 0)),
                            user,
                        )
                    )
                },
                "$inc": {"exp": 10, "event_tokens.perfect_crown_count": -token_cost},
                "$unset": {f"event_tokens.perfect_crown.{token_id}": "" for token_id in consumed_tokens},
            }
        )

        card.change_owner(interaction.user.id)
        await func.update_user(interaction.user.id, user_query)
        await func.update_card(card.id, {"$set": {"owner_id": interaction.user.id}})

        await interaction.response.send_message(
            f"Purchased treasury card `#{index}` ({card.display_id}) for `{token_cost}` tokens.",
            ephemeral=True,
        )
        await view.message.edit(embed=await view.build_embed(), view=view)


class TreasuryBuyButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Buy Card", emoji="🛒", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        view: RoyalTreasuryView = self.view
        await interaction.response.send_modal(TreasuryBuyModal(view))


class RoyalTreasuryView(discord.ui.View):
    def __init__(self, author: discord.Member, bot_user_id: int):
        super().__init__(timeout=60)
        self.author = author
        self.bot_user_id = bot_user_id
        self.selected_tier = "mystic"
        self.message: discord.Message | None = None
        self.add_item(TreasuryTierDropdown())
        self.add_item(TreasuryBuyButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.author

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message:
            await self.message.edit(view=self)

    async def build_embed(self) -> discord.Embed:
        user = await func.get_user(self.author.id)
        token_count = len(get_user_perfect_crown_tokens(user))
        tier = self.selected_tier
        tier_meta = ROYAL_TREASURY_TIERS[tier]
        token_cost = ROYAL_TREASURY_TOKEN_COSTS[tier]

        embed = discord.Embed(title="🏰 Royal Treasury", color=discord.Color.gold())
        embed.description = (
            f"Perfect Crown tokens: `{token_count}`\n"
            f"Current section: `{tier_meta['emoji']} {tier_meta['label']}` "
            f"(cost per card: `{token_cost}` tokens)\n```"
        )

        cards = get_treasury_cards_for_tier(tier)
        if not cards:
            embed.description += "No cards configured for this section.\n"
        else:
            for idx, card in enumerate(cards, start=1):
                if not card:
                    embed.description += f"{idx:>2}. [UNCONFIGURED]\n"
                    continue

                is_available = card.owner_id == self.bot_user_id
                status = "AVAILABLE" if is_available else "SOLD OUT"
                embed.description += f"{idx:>2}. {card.id.zfill(5)}  {card.tier[0]}  {status}\n"

        embed.description += "```"
        embed.set_footer(text="Use 'Buy Card' and enter the treasury card number.")
        embed.set_thumbnail(url=self.author.display_avatar.url)
        return embed


class ContractTeamSelectionView(discord.ui.View):
    def __init__(self, author: discord.Member):
        super().__init__(timeout=60)
        self.author = author
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("Only the command author can choose a team here.", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message:
            await self.message.edit(view=self)

    async def _sign_contract(self, interaction: discord.Interaction, team_key: str) -> None:
        user = await func.get_user(self.author.id)
        if user.get("event_team"):
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(
                content="Your contract is already signed. No turning back now!",
                embed=None,
                attachments=[],
                view=self,
            )
            self.stop()
            return

        team_data = ROYAL_CONTRACT_TEAMS[team_key]
        await func.update_user(self.author.id, {"$set": {"event_team": team_key}})

        embed = discord.Embed(
            title=f"🤝 Contract Signed: {team_data['label']}",
            description=str(team_data["flavor_text"]),
            color=discord.Color.gold() if team_key == "royal" else discord.Color.green(),
        )
        embed.add_field(name="Active Buff", value=str(team_data["buff_description"]), inline=False)

        gif_name = str(team_data["success_gif_file"])
        gif_path = os.path.join(func.ROOT_DIR, "perfect_crown", gif_name)
        embed.set_image(url=f"attachment://{gif_name}")
        file = discord.File(gif_path, filename=gif_name)

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=None, embed=embed, attachments=[file], view=self)
        self.stop()

    @discord.ui.button(label="Team Royal", emoji="👑", style=discord.ButtonStyle.blurple)
    async def choose_royal(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._sign_contract(interaction, "royal")

    @discord.ui.button(label="Team Chaebol", emoji="💸", style=discord.ButtonStyle.green)
    async def choose_chaebol(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._sign_contract(interaction, "chaebol")


class PerfectCrown(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.emoji = "👑"
        self.invisible = False

    @commands.command(aliases=["treasury"])
    async def royaltreasury(self, ctx: commands.Context):
        """Buy treasury cards using Perfect Crown tokens on May 16 KST.

        **Examples:**
        @prefix@royaltreasury
        @prefix@treasury
        """
        if not is_royal_treasury_open():
            return await ctx.reply("🏰 The Royal Treasury only opens on **May 16 (KST)**.")

        view = RoyalTreasuryView(ctx.author, ctx.me.id)
        view.message = await ctx.reply(embed=await view.build_embed(), view=view)

    @commands.command(aliases=["ct"])
    async def contract(self, ctx: commands.Context):
        """Sign a Royal Contract with one event team.

        **Examples:**
        @prefix@contract
        @prefix@ct
        """
        user = await func.get_user(ctx.author.id)
        if user.get("event_team"):
            return await ctx.reply("Your contract is already signed. No turning back now!")

        embed = discord.Embed(
            title="🤝 Royal Contract",
            description=(
                "Choose your side for the event. **This cannot be changed later.**\n\n"
                "👑 **Team Royal** — Halves your cooldowns until May 16th.\n"
                "💸 **Team Chaebol** — 2× Star Candies from converting cards until May 16th."
            ),
            color=discord.Color.random(),
        )
        view = ContractTeamSelectionView(ctx.author)
        view.message = await ctx.reply(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PerfectCrown(bot))

