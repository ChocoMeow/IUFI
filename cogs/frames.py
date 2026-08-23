import discord, iufi, asyncio
import functions as func

from discord import app_commands
from discord.ext import commands
from views import FrameView

class Frames(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "🖼️"
        self.invisible = False

    @app_commands.command(name="setframe", description="Sets the frame for a photocard. Card can be identified by id or given tag.")
    @app_commands.describe(card_id="The card ID or tag")
    async def setframe(self, interaction: discord.Interaction, card_id: str):
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await interaction.response.send_message("The card was not found. Please try again.")

        if card.owner_id != interaction.user.id:
            return await interaction.response.send_message("You are not the owner of this card.")
        
        if card.tier[1] in ["mystic"]:
            return await interaction.response.send_message("The card does not support the frame!")
        
        if card.stars < 5:
            return await interaction.response.send_message("Only cards with 5 stars or above can apply for the frame")
        
        view = FrameView(interaction.user, card)
        embed, file = await view.build()
        await interaction.response.send_message(file=file, embed=embed, view=view)
        view.response = await interaction.original_response()

    @app_commands.command(name="setframelast", description="Sets the frame for your last obtained photocard.")
    async def setframelast(self, interaction: discord.Interaction):
        user = await func.get_user(interaction.user.id)
        if not user["cards"]:
            return await interaction.response.send_message(f"**{interaction.user.mention} you have no photocards.**", ephemeral=True)
        
        card_id = user["cards"][-1]
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await interaction.response.send_message("The card was not found. Please try again.")

        if card.owner_id != interaction.user.id:
            return await interaction.response.send_message("You are not the owner of this card.")
        
        if card.tier[1] in ["mystic"]:
            return await interaction.response.send_message("The card does not support the frame!")
        
        if card.stars < 5:
            return await interaction.response.send_message("Only cards with 5 stars or above can apply for the frame")
        
        view = FrameView(interaction.user, card)
        embed, file = await view.build()
        await interaction.response.send_message(file=file, embed=embed, view=view)
        view.response = await interaction.original_response()

    @app_commands.command(name="removeframe", description="Removes the frame from a photocard. Card can be identified by its ID or given tag.")
    @app_commands.describe(card_id="The card ID or tag")
    async def removeframe(self, interaction: discord.Interaction, card_id: str):
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await interaction.response.send_message("The card was not found. Please try again.")

        if card.owner_id != interaction.user.id:
            return await interaction.response.send_message("You are not the owner of this card.")
        
        card.change_frame()
        await func.update_card(card.id, {"$set": {"frame": None}})

        func.logger.info(f"User {interaction.user.name}({interaction.user.id}) removed frame from card [{card.id}].")

        embed = discord.Embed(title="🖼️  Set Frame", color=discord.Color.random())
        embed.description = f"```🆔 {card.tier[0]} {card.id}\n{card.display_frame}```"
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Frames(bot))