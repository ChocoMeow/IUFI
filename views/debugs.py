import discord
import io
import contextlib
import textwrap
import traceback

from discord.ext import commands

class ExceuteModal(discord.ui.Modal):
    def __init__(self, code: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.code: str = code

        self.add_item(
            discord.ui.TextInput(
                label="Code Runner",
                placeholder="Input Your Code",
                style=discord.TextStyle.long,
                default=self.code
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.code = self.children[0].value
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
    def __init__(self, bot: commands.Bot, author: discord.Member, *, timeout = 180):
        self.bot: commands.Bot = bot
        self.author: discord.Member = author

        self.message: discord.WebhookMessage = None
        self.code: str = None
        self._error: Exception = None

        super().__init__(timeout=timeout)

    def interaction_check(self, interaction: discord.Interaction) -> None:
        return interaction.user == self.author
    
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
        modal = ExceuteModal(self.code, title="Enter Your Code")
        await interaction.response.send_modal(modal)
        await modal.wait()

        if not (code := modal.code):
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

class DebugView(discord.ui.View):
    def __init__(self, bot, *, timeout: float | None = 180):
        self.bot: commands.Bot = bot
        self.panel: ExceutePanel = ExceutePanel(bot)

        super().__init__(timeout=timeout)

    @discord.ui.button(label='Command', emoji="▶️", style=discord.ButtonStyle.green)
    async def run_command(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.panel.execute(interaction)
    
    @discord.ui.button(label='Cogs', emoji="🔃")
    async def reload_cog(self, interaction: discord.Interaction, button: discord.ui.Button):
        return await interaction.response.send_message("Reload Cogs", view=CogsView(self.bot), ephemeral=True)
