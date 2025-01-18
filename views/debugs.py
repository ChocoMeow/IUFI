import discord
import io
import contextlib
import textwrap
import traceback
import iufi
import functions as func
from discord.ext import commands

DAILY_ROWS: list[str] = ["🟥", "🟧", "🟨", "🟩", "🟦", "🟪"]

class InputModal(discord.ui.Modal):
    def __init__(self, items: list[discord.ui.TextInput], *args, **kwargs):
        self.results: list[str | int | float] = []

        super().__init__(*args, **kwargs)

        for item in items:
            self.add_item(item)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        for c in self.children:
            self.results.append(c.value)
        self.stop()

class CogsDropdown(discord.ui.Select):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot

        super().__init__(
            placeholder="Select a cog to reload...",
            min_values=1, max_values=1,
            options=[discord.SelectOption(label="All", description="All the cogs")] +
            [
                discord.SelectOption(label=name.capitalize(), description=cog.description[:50])
                for name, cog in bot.cogs.items()
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        selected = self.values[0].lower()
        try:
            if selected == "all":
                for name in self.bot.cogs.keys():
                    await self.bot.reload_extension(f"cogs.{name.lower()}")
            else:
                await self.bot.reload_extension(f"cogs.{selected}")
        except Exception as e:
            return await interaction.response.send_message(f"Unable to reload `{selected}`! Reason: {e}", ephemeral=True)

        await interaction.response.send_message(f"Reloaded `{selected}` sucessfully!", ephemeral=True)

class ExceutePanel(discord.ui.View):
    def __init__(self, bot: commands.Bot, *, timeout = 180):
        self.bot: commands.Bot = bot

        self.message: discord.WebhookMessage = None
        self.code: str = None
        self._error: Exception = None

        super().__init__(timeout=timeout)
    
    def toggle_button(self, name: str, status: bool):
        child: discord.ui.Button
        for child in self.children:
            if child.label == name:
                child.disabled = status
                break

    def clear_code(self, content: str):
        """Automatically removes code blocks from the code."""
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])

        return content.strip('` \n')
    
    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message:
            await self.message.edit(view=self)

    async def execute(self, interaction: discord.Interaction):
        input_fields = [discord.ui.TextInput(
            label="Code Runner",
            placeholder="Input Your Code",
            style=discord.TextStyle.long,
            default=self.code
        )]
        modal = InputModal(input_fields, title="Enter Your Code")
        await interaction.response.send_modal(modal)
        await modal.wait()

        if not (code := modal.results[0]):
            return
        
        self._error = None
        text = ""

        local_variables = {
            "discord": discord,
            "bot": self.bot,
            "interaction": interaction,
            "input": None
        }

        self.code = self.clear_code(code)
        str_obj = io.StringIO() #Retrieves a stream of data
        try:
            with contextlib.redirect_stdout(str_obj):
                exec(f"async def func():\n{textwrap.indent(self.code, '  ')}", local_variables)
                obj = await local_variables["func"]()
                result = f"{str_obj.getvalue()}\n-- {obj}\n"
        except Exception as e:
            text = f"{e.__class__.__name__}: {e}"
            self._error = e

        if not self._error:
            text = "\n".join([f"{'%03d' % index} | {i}" for index, i in enumerate(result.split("\n"), start=1)])

        self.toggle_button("Error", True if self._error is None else False)

        if not self.message:
            self.message = await interaction.followup.send(f"```{text}```", view=self, ephemeral=True)
        else:
            await self.message.edit(content=f"```{text}```", view=self)

    @discord.ui.button(label="End", emoji="🗑️", custom_id="end")
    async def end(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.message:
            await self.message.delete()
        self.stop()

    @discord.ui.button(label="Rerun", emoji="🔄", custom_id="rerun")
    async def rerun(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.execute(interaction)

    @discord.ui.button(label="Error", emoji="👾", custom_id="Error")
    async def error(self, interaction: discord.Interaction, button: discord.ui.Button):
        result = ''.join(traceback.format_exception(self._error, self._error, self._error.__traceback__))
        await self.message.edit(content=f"```py\n{result}```")

class CogsView(discord.ui.View):
    def __init__(self, bot, *, timeout: float | None = 180):
        super().__init__(timeout=timeout)

        self.add_item(CogsDropdown(bot))

class UserDebugView(discord.ui.View):
    def __init__(self, bot: commands.Bot, member: discord.Member, *, timeout: float = 180):
        self.bot: commands.Bot = bot
        self.member: discord.Member = member

        super().__init__(timeout=timeout)

    async def build_embed(self) -> discord.Embed:
        user_data = await func.get_user(self.member.id)
        
        embed = discord.Embed(title=f"👤 {self.member.display_name}'s Debug Profile", color=self.member.top_role.color)

        # User's Profile Info
        level, exp = func.calculate_level(user_data['exp'])
        bio = user_data.get('profile', {}).get('bio', 'Empty Bio')
        embed.description = f"```{bio}```" if bio else ""
        embed.description += f"```📙 Photocards: {len(user_data.get('cards', []))}/{func.settings.MAX_CARDS}\n⚔️ Level: {level} ({(exp / func.settings.DEFAULT_EXP) * 100:.1f}%)```\u200b"

        # User's Inventory
        inventory_desc = f"{'🍬 Starcandies':<20} x{user_data['candies']}\n"
        for tier, count in user_data.get("roll").items():
            if count > 0 and tier in func.settings.TIERS_BASE.keys():
                emoji, _ = func.settings.TIERS_BASE.get(tier)
                inventory_desc += f"{emoji} {tier.title() + ' Rolls':<18} x{count}\n"

        potions_data: dict[str, int] = user_data.get("potions", {})
        inventory_desc += ("\n".join(
            [f"{potion.split('_')[0].title() + ' ' + potion.split('_')[1].upper() + ' Potion':21} x{amount}"
            for potion, amount in potions_data.items() if amount]
        ) if sum(potions_data.values()) else "Potion not found!")

        embed.add_field(name="Inventory:", value=f"```{inventory_desc}```", inline=False)

        # User's cooldown
        potion_status = "\n".join(
            [f"{data['emoji']} {potion.title():<5} {data['level'].upper():<3}: {func.cal_retry_time(data['expiration'])}"
            for potion, data in func.get_potions(user_data.get("actived_potions", {}), func.settings.POTIONS_BASE, details=True).items()]
        )

        cooldown_desc = "".join(f"{emoji} {name.split('_')[0].title():<5}: {func.cal_retry_time(user_data.get("cooldown", {}).get(name, 0), 'Ready')}\n" for name, (emoji, cd) in func.settings.COOLDOWN_BASE.items())
        cooldown_desc += f"🔔 Reminder: {'On' if user_data.get('reminder', False) else 'Off'}"
        potions_desc = (potion_status if potion_status else "No potions are activated.")
        embed.add_field(name="Cooldown Detail:", value=f"```{cooldown_desc}```", inline=True)
        embed.add_field(name="Potions Detail:", value=f"```{potions_desc}```", inline=True)

        # Empty Field
        embed.add_field(name="", value="", inline=False)

        # User's Game Stats
        quiz_stats = user_data.get("game_state", {}).get("quiz_game", {
            "points": 0,
            "correct": 0,
            "wrong": 0,
            "timeout": 0,
            "average_time": 0
        })

        card_match_stats = user_data.get("game_state", {}).get("match_game", {})
        total_questions = quiz_stats["wrong"] + quiz_stats["timeout"]
        rank_name, rank_emoji = iufi.QuestionPool.get_rank(quiz_stats["points"])
        embed.add_field(name="Ranked Stats:", value=f"> <:{rank_name}:{rank_emoji}> {rank_name.title()} (`{quiz_stats['points']}`)\n> 🎯 K/DA: `{round(quiz_stats['correct'] / total_questions, 1) if total_questions else 0}` (C: `{quiz_stats['correct']}` | W: `{quiz_stats['wrong'] + quiz_stats['timeout']}`)\n> 🕒 Average Time: `{func.convert_seconds(quiz_stats['average_time'])}`", inline=True)
        embed.add_field(name="Card Match Stats:", value="\n".join(f"> {DAILY_ROWS[int(level) - 4]} **Level {level}**: " + (f"🃏 `{stats.get('matched', 0)}` 🕒 `{func.convert_seconds(stats.get('finished_time'))}`" if (stats := card_match_stats.get(level)) else "Not attempted yet") for level in func.settings.MATCH_GAME_SETTINGS.keys()), inline=True)
        embed.add_field(name="Music Stats:", value=f"> 𝄞 Points (```{points}```)" if (points := user_data.get("game_state", {}).get("music_game", {}).get("points")) else "> Not attempted yet", inline=False)

        embed.set_thumbnail(url=self.member.display_avatar.url)
        return embed
    
    @discord.ui.button(label="Modify Candy", emoji="🍬")
    async def modify_candy(self, interaction: discord.Interaction, button: discord.ui.Button):
        ...
    
    @discord.ui.button(label="Modify Exp", emoji="⚔️")
    async def modify_exp(self, interaction: discord.Interaction, button: discord.ui.Button):
        ...

    @discord.ui.button(label="Modify Inventory", emoji="🎒")
    async def modify_inventory(self, interaction: discord.Interaction, button: discord.ui.Button):
        ...
    
    @discord.ui.button(label="Modify Cooldown", emoji="⏳")
    async def modify_cooldown(self, interaction: discord.Interaction, button: discord.ui.Button):
        ...

    @discord.ui.button(label="Modify Game Stats", emoji="🎮")
    async def modify_game_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        ...

    @discord.ui.button(label="Modify Quests", emoji="📜")
    async def modify_quests(self, interaction: discord.Interaction, button: discord.ui.Button):
        ...

class DebugView(discord.ui.View):
    def __init__(self, bot: commands.Bot, author: discord.Member, *, timeout: float | None = 180):
        self.bot: commands.Bot = bot
        self.author: discord.Member = author
        self.panel: ExceutePanel = ExceutePanel(bot)

        super().__init__(timeout=timeout)

    async def interaction_check(self, interaction: discord.Interaction) -> None:
        return interaction.user == self.author

    @discord.ui.button(label='Command', emoji="▶️", style=discord.ButtonStyle.green)
    async def run_command(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.panel.execute(interaction)
    
    @discord.ui.button(label='Cogs', emoji="🔃")
    async def reload_cog(self, interaction: discord.Interaction, button: discord.ui.Button):
        return await interaction.response.send_message("Reload Cogs", view=CogsView(self.bot), ephemeral=True)
    
    @discord.ui.button(label="User Panel", emoji="👤", row=1)
    async def user(self, interaction: discord.Interaction, button: discord.ui.Button):
        input_fields = [discord.ui.TextInput(
            label="User ID",
            placeholder="Input Targeted User ID",
            style=discord.TextStyle.short
        )]
        modal = InputModal(input_fields, title="Enter User ID")
        await interaction.response.send_modal(modal)
        await modal.wait()

        if not (user_id := int(modal.results[0])):
            return
        
        member = interaction.guild.get_member(user_id)
        if not member:
            return await interaction.followup.send("Member not found!", ephemeral=True)
        
        view = UserDebugView(self.bot, member)
        return await interaction.followup.send(embed= await view.build_embed(), view=view, ephemeral=False)

    @discord.ui.button(label="Card Panel", emoji="🃏", row=1)
    async def card(self, interaction: discord.Interaction, button: discord.ui.Button):
        input_fields = [discord.ui.TextInput(
            label="Card ID",
            placeholder="Input Targeted Card ID",
            style=discord.TextStyle.short
        )]
        modal = InputModal(input_fields, title="Enter Card ID")
        await interaction.response.send_modal(modal)
        await modal.wait()