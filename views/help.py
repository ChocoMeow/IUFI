import discord
from discord.ext import commands

class HelpView(discord.ui.View):
    def __init__(
        self, bot: commands.Bot,
        author: discord.Member
    ) -> None:
        super().__init__(timeout=60)

        self.author: discord.Member = author
        self.bot: commands.Bot = bot

        self.add_item(discord.ui.Button(label='Github', emoji=':github:1098265017268322406', url='https://github.com/ChocoMeow/IUFI'))
        self.add_item(discord.ui.Button(label='Beginner Guide', emoji='📗', url='https://docs.google.com/document/d/1VAD20wZQ56S_wDeMJlwIKn_jImIPuxh2lgy1fn17z0c/edit'))
        self.add_item(discord.ui.Button(label='Donate', emoji='🎁', url='https://ko-fi.com/chocoo'))
        self.add_item(discord.ui.Button(label='Card Archive', emoji='🗂️', url='https://d1w5gpixxno4sl.cloudfront.net'))
        
    async def on_error(self, error, item, interaction) -> None:
        return

    async def interaction_check(self, interaction: discord.Interaction) -> None:
        return interaction.user == self.author

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title="🌼 Welcome to IUFI!", color=discord.Color.random())
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        for name, cog in self.bot.cogs.items():
            if cog.invisible:
                continue

            cmds = cog.get_app_commands()
            if not cmds:
                continue

            embed.add_field(
                name=f"{cog.emoji} {name.title()}: [{len(cmds)}]",
                value="```{}```".format(", ".join(f"/{command.qualified_name}" for command in cmds)),
                inline=False
            )

        return embed