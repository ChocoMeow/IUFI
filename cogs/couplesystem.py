import discord
import functions as func
import time
import random
from discord.ext import commands
from views import ProposeView

class CoupleSystem(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "💞"
        self.invisible = False
        self.COOLDOWN = 24 * 60 * 60

    @commands.command(aliases=["pr"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def propose(self, ctx: commands.Context, user: discord.Member):
        """Propose to a user"""
        if user.bot:
            return await ctx.reply("My love, Bots are not into humans.")
        if user.id == ctx.author.id:
            return await ctx.reply("Sweetie, Self-love is great, but proposal might be pushing it.")

        user_data = await func.get_user(ctx.author.id)
        if user_data.get("couple_id"):
            return await ctx.reply("Cutie, You already got a player-two. No need for love triangles.")
        
        if not user_data.get("event_item") or user_data.get("event_item", {}).get("rose", 0) <= 0:
            return await ctx.reply("You don't have a rose. Don't worry, you can get one from the shop.")

        other_user_data = await func.get_user(user.id)
        if other_user_data.get("couple_id", None) is not None:
            return await ctx.reply("Sorry, Romeo! This Juliet is already taken. Time to find another Juliet.")

        await func.update_user(ctx.author.id, {"$inc": {"event_item.rose": -1}})
        view = ProposeView(ctx.author, user)
        view.message = await ctx.reply(f"{ctx.author.mention} has proposed to {user.mention} with a rose🌹!", view=view)

    @commands.command(aliases=["opr"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def openproposal(self, ctx: commands.Context):
        """Open proposal to anyone"""
        user_data = await func.get_user(ctx.author.id)
        if user_data.get("couple_id"):
            return await ctx.reply("Cutie, You already got a player-two. No need for love triangles.")

        if not user_data.get("event_item") or user_data.get("event_item", {}).get("rose", 0) <= 0:
            return await ctx.reply("You don't have a rose. Don't worry, you can get one from the shop.")

        await func.update_user(ctx.author.id, {"$inc": {"event_item.rose": -1}})
        view = ProposeView(ctx.author, None)
        view.message = await ctx.reply(f"🌹Proposal alert: {ctx.author.mention} is on the lookout for a player-two! Will you be the chosen one?", view=view)

    @commands.command(aliases=["cq"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def couplequest(self, ctx: commands.Context):
        """View your couple quests"""
        user = await func.get_user(ctx.author.id)
        if not user.get("couple_id"):
            return await ctx.reply("You're not in a relationship.")

        couple_data = await func.get_couple_data(user.get("couple_id"))
        quests = couple_data.get("quests", {})
        if not quests or couple_data.get("next_reset_at", 0) < time.time():
            quests = random.sample(func.COUPLE_QUESTS, 3)
            quests = [[int(quests[0]), 0] for quests in quests]  # [[id, progress], [id, progress], [id, progress]]
            await func.update_couple(user.get("couple_id"),
                                     {"$set": {"quests": quests, "next_reset_at": time.time() + self.COOLDOWN}})

        embed = discord.Embed(title="💑 Couple Quests", color=0x949fb8)
        embed.description = f"Quests resets <t:{int(couple_data.get('next_reset_at'))}:R> \n```"
        for i in quests:
            quest_data = func.get_couple_quest_by_id(i[0])

            is_completed = "✅ " if i[1] >= quest_data[5] else "⬛ "
            progress = f"({i[1]}/{quest_data[5]})"
            embed.description += f"{is_completed} {quest_data[1]:<25} {progress:>7} - {quest_data[3]:>2}{quest_data[4]}\n"

        embed.description += "```"
        embed.set_footer(text="Completing each quest will reward you a ❤️ for couple leaderboard")
        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CoupleSystem(bot))
