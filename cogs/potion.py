import time, discord
import functions as func

from discord import app_commands
from discord.ext import commands

class Potion(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "🧪"
        self.invisible = False

    @app_commands.command(name="usepotion", description="Use a potion on yourself.")
    @app_commands.describe(potion_name="The potion to use", level="The potion's level")
    @app_commands.checks.cooldown(1, 5, key=lambda i: i.user.id)
    async def usepotion(self, interaction: discord.Interaction, potion_name: str, level: str):
        potion_name, level = potion_name.lower(), level.lower()

        if potion_name not in (potions := func.settings.POTIONS_BASE.keys()):
            return await interaction.response.send_message(f"The potion was not found. Please select a valid potion: `{', '.join(potions)}`")

        potion_data = func.settings.POTIONS_BASE.get(potion_name)

        if level not in (levels := potion_data.get("levels")):
            return await interaction.response.send_message(f"The `{potion_name.title()}` potion level provided is invalid. Please choose a valid level: `{', '.join(levels)}`")
        
        user = await func.get_user(interaction.user.id)

        if user.get("potions", {}).get(f"{potion_name}_{level}", 0) <= 0:
            return await interaction.response.send_message("You don't have this potion.")

        actived_potions = func.get_potions(user.get("actived_potions", {}), func.settings.POTIONS_BASE, details=True)
        active = actived_potions.get(potion_name)
        extending = False
        if active:
            if active["level"] != level:
                return await interaction.response.send_message(
                    f"You already have a `{potion_name.title()} {active['level'].upper()}` potion active. "
                    "You can only add time with the same type and level."
                )
            extending = True

        data: dict[str, dict[str, float]] = {"$set": {}, "$inc": {}}
        if potion_name == "speed" and not extending:
            time_reduce = func.settings.POTIONS_BASE.get("speed").get("levels").get(level)
            for cooldown in user.get("cooldown", []):
                if cooldown in ["daily", "match_game"] or not func.settings.COOLDOWN_BASE.get(cooldown):
                    continue
                
                data["$set"][f"cooldown.{cooldown}"] = user.get("cooldown").get(cooldown, time.time()) - (func.settings.COOLDOWN_BASE.get(cooldown)[1] * time_reduce)

        duration = potion_data.get("expiration")
        expire = (active["expiration"] if extending else time.time()) + duration
        data["$inc"][f"potions.{potion_name}_{level}"] = -1
        data["$set"][f"actived_potions.{potion_name}_{level}"] = expire
        data = func.update_quest_progress(user, "USE_ANY_POTION", query=data)
        await func.update_user(interaction.user.id, data)

        action = "extended" if extending else "used"
        func.logger.info(f"User {interaction.user.name}({interaction.user.id}) {action} a {potion_name}({level}) potion, which will expire in {expire}.")

        await interaction.response.send_message(
            f"You have {'extended' if extending else 'used'} a {potion_name} potion. It will expire in <t:{round(expire)}:R>"
        )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Potion(bot))