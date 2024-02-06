import discord
import functions as func

class ProposeView(discord.ui.View):
    def __init__(
        self,
        romeo: discord.Member,
        juliet_not_yet: discord.Member | None,
        timeout: float | None = 43_200,
    ) -> None:

        super().__init__(timeout=timeout)

        self.romeo: discord.Member = romeo
        self.juliet_not_yet: discord.Member | None = juliet_not_yet

        self.message: discord.Message = None

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True

        await self.message.edit(view=self)
        self.stop()

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title="💍 Propose", color=discord.Color.random())
        embed.description = f"{self.romeo.mention} is proposing to " + (f"{self.juliet_not_yet.mention}!" if self.juliet_not_yet else "anyone who is willing to accept!") 
        return embed

    @discord.ui.button(label='Accept', style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        juliet_not_yet = self.juliet_not_yet or interaction.user

        if interaction.user != juliet_not_yet:
            return await interaction.response.send_message(f"This proposal is for {juliet_not_yet.mention}", ephemeral=True)
        
        if interaction.user == self.romeo:
            return await interaction.response.send_message("Self-acceptance is important, but not in this case sweetheart!", ephemeral=True)

        juliet_not_yet_data = await func.get_user(juliet_not_yet.id)
        if juliet_not_yet_data.get("couple_id"):
            return await interaction.response.send_message("Oops! Looks like you've got a commitment buffer overflow. No room for another relationship!", ephemeral=True)

        romeo_data = await func.get_user(self.romeo.id)
        if romeo_data.get("couple_id"):
            await interaction.response.send_message("Sorry, someone else caught the user's attention. Looks like you're not Player 2 this time.", ephemeral=True)
            await self.on_timeout()

        await interaction.response.defer()

        await func.make_couple(self.romeo.id, juliet_not_yet.id)

        embed = discord.Embed(title="✅ Accepted", color=discord.Color.random())
        embed.description = f"{self.romeo.mention} and {juliet_not_yet.mention} are a couple now! 💞"

        await self.on_timeout()
        await interaction.followup.send(content=f"{self.romeo.mention}, {juliet_not_yet.mention} has accepted your proposal!", embed=embed)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if self.juliet_not_yet is None and interaction.user != self.romeo:
            return

        if interaction.user == self.romeo:
            await interaction.followup.send(f"{self.romeo.mention} has cancelled their proposal!")
        elif interaction.user == self.juliet_not_yet:
            await interaction.followup.send(f"{self.romeo.mention}, {self.juliet_not_yet.mention} has rejected your proposal!")
        else:
            return

        await self.on_timeout()
