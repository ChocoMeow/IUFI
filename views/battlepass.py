import discord, asyncio
import functions as func

from random import choice
from typing import Any


XP_ACTION_LABELS = {
    "roll": "Normal roll (not a purchased tier roll)",
    "quiz": "Quiz that gains points",
    "mg1": "Match Game level 1 (match at least 2 cards)",
    "mg2": "Match Game level 2 (match at least 4 cards)",
    "mg3": "Match Game level 3 (match at least 6 cards)",
    "daily_quest": "Completing a daily quest",
    "weekly_quest": "Completing a weekly quest",
}

DROP_REPLY_MESSAGES = [
    "{0} claimed a Battle Pass XP drop! Keep climbing that pass.",
    "Nice grab, {0}! Battle Pass XP is yours.",
    "{0} snagged the Battle Pass XP drop just in time!",
]


def _build_progress_bar(current: int, total: int, size: int = 20) -> str:
    if total <= 0:
        return "█" * size
    ratio = max(0.0, min(1.0, current / total))
    filled = int(size * ratio)
    return "█" * filled + "░" * (size - filled)


class BattlepassXPDropView(discord.ui.View):
    def __init__(self, xp_amount: int, timeout: float | None = 70) -> None:
        super().__init__(timeout=timeout)
        self.xp_amount = int(xp_amount)
        self.claimed = False
        self._lock = asyncio.Lock()
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message:
            await self.message.edit(content="This drop has expired", view=self)

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title="🎫 Battle Pass XP Drop", color=discord.Color.gold())
        embed.description = f"A random Battle Pass XP drop appeared!\nClaim **`{self.xp_amount} XP`** before it expires."
        return embed

    @discord.ui.button(label="Claim Now", style=discord.ButtonStyle.green)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        async with self._lock:
            if self.claimed:
                await self.on_timeout()
                self.stop()
                return await interaction.followup.send("This Battle Pass XP drop has already been claimed!", ephemeral=True)

            user = await func.get_user(interaction.user.id)
            state = func.get_battlepass_state(user)
            if not state.get("is_active"):
                return await interaction.followup.send(
                    "You need an active Battle Pass to claim this drop. Buy it from the shop first.",
                    ephemeral=True
                )

            query = func.add_battlepass_xp(user, self.xp_amount)
            granted = int(query.get("$inc", {}).get("battlepass.xp", 0) or 0)
            full_set = query.get("$set", {}).get("battlepass")
            if isinstance(full_set, dict):
                granted = max(0, int(full_set.get("xp", 0)) - int(state.get("xp", 0)))

            self.claimed = True
            await func.update_user(interaction.user.id, query)

            func.logger.info(
                f"User {interaction.user.name}({interaction.user.id}) claimed a Battle Pass XP drop of {self.xp_amount} "
                f"(applied {granted})."
            )

            embed = discord.Embed(title="🎊 Battle Pass XP Claimed", color=discord.Color.gold())
            if granted <= 0:
                embed.description = f"{interaction.user.mention} claimed the drop, but is already at the Battle Pass XP cap."
            else:
                embed.description = f"{interaction.user.mention} gained **`{granted} Battle Pass XP`**!"

            await self.on_timeout()
            self.stop()
            await interaction.followup.send(
                content=choice(DROP_REPLY_MESSAGES).format(interaction.user.mention),
                embed=embed
            )


class BattlepassView(discord.ui.View):
    def __init__(self, author: discord.abc.User, user: dict[str, Any], timeout: float = 120):
        super().__init__(timeout=timeout)
        self.author = author
        self.mode = "overview"
        self.pages: list[discord.Embed] = []
        self.current_page = 0
        self.message: discord.Message | None = None
        self.overview_embed: discord.Embed | None = None
        self.xp_embed: discord.Embed | None = None
        self._rebuild(user)
        self._update_buttons()

    def _rebuild(self, user: dict[str, Any]) -> None:
        state = func.get_battlepass_state(user)
        bp_settings = func.get_battlepass_settings()
        max_level = max(1, int(bp_settings.get("max_level", 100)))
        xp_per_level = max(1, int(bp_settings.get("xp_per_level", 150)))
        price = int(bp_settings.get("shop_price_candies", 0))
        claimed = {int(level) for level in state.get("claimed_rewards", []) if str(level).lstrip("-").isdigit()}

        level, in_level_xp, xp_to_next = func.calculate_battlepass_level(state.get("xp", 0))
        progress_pct = 100 if level >= max_level else int((in_level_xp / xp_per_level) * 100)
        progress_bar = _build_progress_bar(in_level_xp if level < max_level else xp_per_level, xp_per_level)
        status = "Active" if state.get("is_active") else "Inactive"

        summary = discord.Embed(title=f"🎫 {self.author.display_name}'s Battle Pass", color=discord.Color.random())
        summary.description = (
            f"Season: `{state.get('season_id')}`\n"
            f"Status: **{status}**\n"
            f"Price: `🍬 {price}`\n"
            f"```\n"
            f"Level:       {level}/{max_level}\n"
            f"Progress:    {progress_bar} {progress_pct}%\n"
            f"XP in Level: {in_level_xp if level < max_level else xp_per_level}/{xp_per_level}\n"
            f"XP to Next:  {xp_to_next if level < max_level else 0}\n"
            f"```"
        )
        if not state.get("is_active"):
            summary.description += "\nBuy Battle Pass from the shop to start earning Battle Pass XP."
        self.overview_embed = summary

        lines = []
        for reward_level in range(1, max_level + 1):
            rewards = func.get_battlepass_rewards_for_level(reward_level)
            reward_text = ", ".join(func.format_battlepass_reward(item) for item in rewards) if rewards else "No reward"

            if reward_level in claimed:
                marker = "✅"
            elif reward_level == level + 1:
                marker = "👉"
            else:
                marker = "⬜"

            lines.append(f"{marker} L{reward_level:>3}: {reward_text}")

        page_size = 15
        pages = []
        for start in range(0, len(lines), page_size):
            page = lines[start:start + page_size]
            pages.append(discord.Embed(
                title=f"Battle Pass Rewards ({start + 1}-{min(start + page_size, len(lines))})",
                description="```\n" + "\n".join(page) + "\n```",
                color=discord.Color.random()
            ))
        self.pages = pages or [discord.Embed(title="Battle Pass Rewards", description="No rewards configured.", color=discord.Color.random())]

        xp_map = bp_settings.get("xp_per_action", {})
        source_lines = []
        for action, amount in xp_map.items():
            label = XP_ACTION_LABELS.get(action, action.replace("_", " ").title())
            source_lines.append(f"{label}: `{amount} XP`")

        drop_amounts = bp_settings.get("drop", {}).get("xp_amounts", [10, 25, 50])
        drop_text = "/".join(str(amount) for amount in drop_amounts)
        source_lines.append(f"Random world drop (claim while the pass is enabled): `{drop_text} XP`")

        xp_embed = discord.Embed(title="Battle Pass XP Sources", color=discord.Color.gold())
        xp_embed.description = (
            "Battle Pass XP is only earned with an **active** Battle Pass.\n\n"
            + "\n".join(f"• {line}" for line in source_lines)
        )
        self.xp_embed = xp_embed

    def current_embed(self) -> discord.Embed:
        if self.mode == "xp":
            return self.xp_embed
        if self.mode == "rewards":
            return self.pages[self.current_page]
        return self.overview_embed

    def _update_buttons(self):
        self.overview_button.disabled = self.mode == "overview"
        self.xp_button.disabled = self.mode == "xp"
        self.previous_button.disabled = self.mode != "rewards"
        last_page = self.mode == "rewards" and self.current_page >= len(self.pages) - 1
        self.next_button.disabled = last_page

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("Only the player who opened this Battle Pass can use these buttons.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            await self.message.edit(view=self)

    @discord.ui.button(label="Overview", style=discord.ButtonStyle.secondary)
    async def overview_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.mode = "overview"
        self._update_buttons()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="XP Sources", style=discord.ButtonStyle.secondary)
    async def xp_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.mode = "xp"
        self._update_buttons()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.mode == "rewards" and self.current_page > 0:
            self.current_page -= 1
        else:
            self.mode = "overview"
        self._update_buttons()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.mode != "rewards":
            self.mode = "rewards"
            self.current_page = 0
        elif self.current_page < len(self.pages) - 1:
            self.current_page += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.current_embed(), view=self)
