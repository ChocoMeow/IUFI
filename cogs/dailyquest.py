import discord, iufi
import functions as func
from discord.ext import commands
import time
import random


class DailyQuest(commands.Cog):
    def __init__(self):
        self.emoji = "🍬"
        self.invisible = False
        # id, name, description, reward, reward_emoji, required_progress
        self.DAILY_QUESTS = func.DAILY_QUESTS
        self.COUPLE_QUESTS = func.COUPLE_QUESTS
        self.COOLDOWN = 24 * 60 * 60

    @commands.command(aliases=["dq"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def dailyquest(self, ctx: commands.Context):
        """View your daily quests"""
        user_dq = await func.get_daily_quest(ctx.author.id)
        quests = user_dq.get("quests", {})
        if not quests or user_dq.get("next_reset_at", 0) < time.time():
            quests = random.sample(self.DAILY_QUESTS, 3)
            quests = [[quests[0],0] for quests in quests] # [[id, progress], [id, progress], [id, progress]]
            await func.update_daily_quest(ctx.author.id, {"$set": {"quests": quests, "next_reset_at": time.time() + self.COOLDOWN}})
        embed = discord.Embed(title="🍬 Daily Quests", color=0x949fb8)
        embed.description = "```"
        for i in quests:
            quest_data = func.get_daily_quest_by_id(i[0])
            embed.description += f"{quest_data[1]} - {i[1]}/{quest_data[5]} {quest_data[4]}"
            if i[1] >= quest_data[5]:
                embed.description += " ✅"
            embed.description += "\n"
        embed.description += "```"
        embed.set_footer(text=f"Quests resets in {func.cal_retry_time(user_dq.get('next_reset_at'))}")
        await ctx.reply(embed=embed)

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
            quests = random.sample(self.COUPLE_QUESTS, 3)
            quests = [[quests[0],0] for quests in quests] # [[id, progress], [id, progress], [id, progress]]
            await func.update_couple(user.get("couple_id"), {"$set": {"quests": quests, "next_reset_at": time.time() + self.COOLDOWN}})
        embed = discord.Embed(title="🍬 Couple Quests", color=0x949fb8)
        embed.description = "```"
        for i in quests:
            quest_data = func.get_couple_quest_by_id(i[0])
            embed.description += f"{quest_data[1]} - {i[1]}/{quest_data[5]} {quest_data[4]}"
            if i[1] >= quest_data[5]:
                embed.description += " ✅"
            embed.description += "\n"
        embed.description += "```"
        embed.set_footer(text=f"Quests resets in {func.cal_retry_time(couple_data.get('next_reset_at'))}")
        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DailyQuest())