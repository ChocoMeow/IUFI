import iufi, time
import functions as func

from discord.ext import commands

class Potion(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "🧪"
        self.invisible = False

    @commands.command(aliases=["up"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def usepotion(self, ctx: commands.Context, potion_name: str, level: str):
        """Use a potion on the user

        **Exampls:**
        qusepotion speed i
        qup luck ii
        """
        potion_name, level = potion_name.lower(), level.lower()

        if potion_name not in (potions := func.settings.POTIONS_BASE.keys()):
            return await ctx.reply(f"The potion was not found. Please select a valid potion: `{', '.join(potions)}`")

        potion_data = func.settings.POTIONS_BASE.get(potion_name)

        if level not in (levels := potion_data.get("levels")):
            return await ctx.reply(f"The `{potion_name.title()}` potion level provided is invalid. Please choose a valid level: `{', '.join(levels)}`")
        
        user = await func.get_user(ctx.author.id)

        actived_potions = func.get_potions(user.get("actived_potions", {}), func.settings.POTIONS_BASE)
        if potion_name in actived_potions:
            return await ctx.reply("Wait for the current potion's effect to end before using another potion from the same category.")
    
        if user.get("potions", {}).get(f"{potion_name}_{level}", 0) <= 0:
            return await ctx.reply("You don't have this potion.")

        data: dict[str, dict[str, float]] = {"$set": {}, "$inc": {}}
        if potion_name == "speed":
            time_reduce = func.settings.POTIONS_BASE.get("speed").get("levels").get(level)
            for cooldown in user.get("cooldown", []):
                if cooldown in ["daily", "match_game"]: continue
                data["$set"][f"cooldown.{cooldown}"] = user.get("cooldown").get(cooldown, time.time()) - (func.settings.COOLDOWN_BASE.get(cooldown)[1] * time_reduce)

        data["$inc"][f"potions.{potion_name}_{level}"] = -1
        data["$set"][f"actived_potions.{potion_name}_{level}"] = (expire := time.time() + potion_data.get("expiration"))
        data = func.update_quest_progress(user, "USE_ANY_POTION", query=data)
        await func.update_user(ctx.author.id, data)

        func.logger.info(f"User {ctx.author.name}({ctx.author.id}) used a {potion_name}({level}) potion, which will expire in {expire}.")

        await ctx.reply(f"You have used a {potion_name} potion. It will expire in <t:{round(expire)}:R>")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Potion(bot))