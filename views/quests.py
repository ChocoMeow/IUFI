import copy
import discord
import functions as func

from typing import Any, Dict


def format_quest_reward(reward: list[Any]) -> str:
    emoji, reward_key, reward_amount = reward
    if isinstance(reward_key, str) and reward_key.startswith("potions."):
        potion_suffix = reward_key.split(".", 1)[1]
        potion_level = potion_suffix.split("_")[-1]
        level_map = {"i": "1", "ii": "2", "iii": "3"}
        level_text = level_map.get(potion_level.lower(), potion_level.upper())

        if isinstance(reward_amount, list):
            min_qty, max_qty = reward_amount
            qty_text = f"x{min_qty}" if min_qty == max_qty else f"x{min_qty}~{max_qty}"
        else:
            qty_text = f"x{reward_amount}"
        return f"{emoji} Lvl {level_text} {qty_text}"

    if isinstance(reward_amount, list):
        return f"{emoji} {reward_amount[0]} ~ {reward_amount[1]}"
    return f"{emoji} {reward_amount}"


def generate_progress_bar(total, progress_percentage, filled='█', in_progress='▓', empty='░'):
    progress = int(total * progress_percentage / 100)
    filled_length = progress
    in_progress_length = 1 if (progress_percentage % (100 / total)) > 0 and progress < total else 0
    empty_length = total - filled_length - in_progress_length
    return filled * filled_length + in_progress * in_progress_length + empty * empty_length


class QuestRerollSelect(discord.ui.Select):
    def __init__(self, quest_type: str, options: list[discord.SelectOption], cost: int, *, disabled: bool = False):
        self.quest_type = quest_type
        super().__init__(
            placeholder=f"Reroll a {quest_type} quest ({cost}🍬)",
            min_values=1,
            max_values=1,
            options=options,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.view.reroll_quest(interaction, self.quest_type, self.values[0])


class QuestsView(discord.ui.View):
    def __init__(self, author: discord.Member, user: Dict[str, Any], *, timeout: float | None = 120):
        super().__init__(timeout=timeout)
        self.author = author
        self.user = user
        self.message: discord.Message | None = None
        self._rerolling = False
        self._rebuild_controls()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("This quest menu is not for you.", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    def _rerollable_options(self, quest_type: str) -> list[discord.SelectOption]:
        quests_base = func._quest_pool_for_type(quest_type)
        progresses = (self.user.get("quests", {}).get(quest_type) or {}).get("progresses") or {}
        options: list[discord.SelectOption] = []
        for quest_name, progress in progresses.items():
            quest = quests_base.get(quest_name)
            if not quest or func._is_quest_complete(quest, progress):
                continue
            options.append(discord.SelectOption(
                label=quest["title"][:100],
                value=quest_name,
                description=f"{progress}/{quest['amount']}",
            ))
        return options

    def _rebuild_controls(self) -> None:
        self.clear_items()
        for quest_type, row in (("daily", 0), ("weekly", 1)):
            cost = func.QUESTS_SETTINGS[quest_type].get("reroll_cost", 50 if quest_type == "daily" else 100)
            options = self._rerollable_options(quest_type)
            if not options:
                options = [discord.SelectOption(label="No incomplete quests to reroll", value="none")]
                select = QuestRerollSelect(quest_type, options, cost, disabled=True)
            else:
                select = QuestRerollSelect(quest_type, options, cost)
            select.row = row
            self.add_item(select)

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title=f"📜 {self.author.display_name}'s Quests", color=discord.Color.random())

        for quest_type in func.settings.USER_BASE["quests"].keys():
            user_quest: Dict[str, Any] = self.user.get("quests", {}).get(
                quest_type,
                copy.deepcopy(func.settings.USER_BASE["quests"][quest_type]),
            )

            quests_base: Dict[str, Any] = getattr(func.settings, f"{quest_type.upper()}_QUESTS", None)
            if not quests_base:
                continue

            reset_time = round(user_quest.get("next_update", 0))
            details = ""
            for quest_name, progress in user_quest.get("progresses", {}).items():
                quest = quests_base.get(quest_name)
                if not quest:
                    continue
                progress_percentage = (progress / quest["amount"]) * 100
                progress_bar = generate_progress_bar(15, progress_percentage)
                details += f"{'✅' if progress >= quest['amount'] else '❌'} {quest['title']}\n"
                details += (
                    "```ansi\n➢ Reward: "
                    + " | ".join(format_quest_reward(r) for r in quest["rewards"])
                    + f"\n➢ {progress_bar} {int(progress_percentage)}% ({progress}/{quest['amount']})```\n"
                )

            if not details:
                details = "No active quests.\n"

            reroll_cost = func.QUESTS_SETTINGS.get(quest_type, {}).get("reroll_cost")
            footer = f"Resets at <t:{reset_time}:t> (<t:{reset_time}:R>)"
            if reroll_cost is not None:
                footer += f"\nReroll one quest: 🍬 {reroll_cost}"

            embed.add_field(
                name=f"{quest_type.title()} Quests",
                value=f"{footer}\n\n{details}",
                inline=False,
            )

        embed.set_thumbnail(url=self.author.display_avatar.url)
        embed.set_footer(text=f"Your candies: {self.user.get('candies', 0)}")
        return embed

    async def reroll_quest(self, interaction: discord.Interaction, quest_type: str, quest_name: str) -> None:
        if self._rerolling:
            return await interaction.response.send_message("A reroll is already in progress.", ephemeral=True)

        self._rerolling = True
        try:
            user = await func.get_user(interaction.user.id)
            query, error = func.build_quest_reroll_query(user, quest_type, quest_name)
            if error:
                return await interaction.response.send_message(error, ephemeral=True)

            await func.update_user(interaction.user.id, query)
            self.user = await func.get_user(interaction.user.id)
            self._rebuild_controls()

            cost = func.QUESTS_SETTINGS[quest_type]["reroll_cost"]
            quests_base = func._quest_pool_for_type(quest_type)
            old_title = (quests_base.get(quest_name) or {}).get("title", quest_name)
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
            await interaction.followup.send(
                f"Rerolled **{old_title}** for 🍬 {cost}.",
                ephemeral=True,
            )
            func.logger.info(
                f"User {interaction.user.name}({interaction.user.id}) rerolled {quest_type} quest "
                f"{quest_name} for {cost} candies."
            )
        finally:
            self._rerolling = False
