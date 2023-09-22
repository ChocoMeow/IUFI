import discord, iufi, time
import functions as func

from discord.ext import commands

from views import RollView, ShopView

class Gameplay(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "🎮"
        self.invisible = False

    @commands.command(aliases=["r"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def roll(self, ctx: commands.Context):
        """Rolls a set of photocards for claiming."""
        user = await func.get_user(ctx.author.id)
        if (retry := user["cooldown"]["roll"]) > time.time():
            return await ctx.reply(f"{ctx.author.mention} your next roll is <t:{round(retry)}:R>", delete_after=10)

        if len(user["cards"]) >= func.MAX_CARDS:
            return await ctx.reply(f"**{ctx.author.mention} your inventory is full.**", delete_after=5)
        
        cards = iufi.CardPool.roll(is_lucky=func.is_luck_potion_active(user))
        image_bytes, image_format = iufi.gen_cards_view(cards)

        view = RollView(ctx.author, cards)
        view.message = await ctx.send(
            content=f"**{ctx.author.mention} This is your roll!** (Ends: <t:{round(time.time()) + 71}:R>)",
            file=discord.File(image_bytes, filename=f'image.{image_format}'),
            view=view
        )
        next_roll_cooldown = time.time() + ( func.SPEED_POTION_ROLL_COOLDOWN if func.is_speed_potion_active(user) else func.COOLDOWN_BASE["roll"])
        await func.update_user(ctx.author.id, {"$set": {"cooldown.roll": next_roll_cooldown}})
        await view.timeout_count()

    @commands.command(aliases=["rr"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def rareroll(self, ctx: commands.Context):
        """Starts a roll with at least one rare photocard guaranteed."""
        user = await func.get_user(ctx.author.id)
        if user["roll"]["rare"] <= 0:
            return await ctx.reply("You’ve used up all your `rare` rolls for now.")

        if len(user["cards"]) >= func.MAX_CARDS:
            return await ctx.reply(f"**{ctx.author.mention} your inventory is full.**", delete_after=5)

        cards = iufi.CardPool.roll(included="rare")
        image_bytes, image_format = iufi.gen_cards_view(cards)

        view = RollView(ctx.author, cards)
        view.message = await ctx.send(
            content=f"**{ctx.author.mention} This is your roll!** (Ends: <t:{round(time.time()) + 71}:R>)",
            file=discord.File(image_bytes, filename=f'image.{image_format}'),
            view=view
        )

        await func.update_user(ctx.author.id, {"$inc": {"roll.rare": -1}})
        await view.timeout_count()

    @commands.command(aliases=["er"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def epicroll(self, ctx: commands.Context):
        """Starts a roll with at least one epic photocard guaranteed."""
        user = await func.get_user(ctx.author.id)
        if user["roll"]["epic"] <= 0:
            return await ctx.reply("You’ve used up all your `epic` rolls for now.")

        if len(user["cards"]) >= func.MAX_CARDS:
            return await ctx.reply(f"**{ctx.author.mention} your inventory is full.**", delete_after=5)

        cards = iufi.CardPool.roll(included="epic")
        image_bytes, image_format = iufi.gen_cards_view(cards)

        view = RollView(ctx.author, cards)
        view.message = await ctx.send(
            content=f"**{ctx.author.mention} This is your roll!** (Ends: <t:{round(time.time()) + 71}:R>)",
            file=discord.File(image_bytes, filename=f'image.{image_format}'),
            view=view
        )
        await func.update_user(ctx.author.id, {"$inc": {"roll.epic": -1}})
        await view.timeout_count()

    @commands.command(aliases=["lr"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def legendroll(self, ctx: commands.Context):
        """Starts a roll with at least one legendary photocard guaranteed."""
        user = await func.get_user(ctx.author.id)
        if user["roll"]["legendary"] <= 0:
            return await ctx.reply("You’ve used up all your `legend` rolls for now.")

        if len(user["cards"]) >= func.MAX_CARDS:
            return await ctx.reply(f"**{ctx.author.mention} your inventory is full.**", delete_after=5)

        cards = iufi.CardPool.roll(included="legendary")
        image_bytes, image_format = iufi.gen_cards_view(cards)

        view = RollView(ctx.author, cards)
        view.message = await ctx.send(
            content=f"**{ctx.author.mention} This is your roll!** (Ends: <t:{round(time.time()) + 71}:R>)",
            file=discord.File(image_bytes, filename=f'image.{image_format}'),
            view=view
        )
        await func.update_user(ctx.author.id, {"$inc": {"roll.legendary": -1}})
        await view.timeout_count()

    @commands.command(aliases=["cd"])
    async def cooldown(self, ctx: commands.Context):
        """Shows all your cooldowns."""
        user = await func.get_user(ctx.author.id)

        embed = discord.Embed(title=f"⏰ {ctx.author.display_name}'s Cooldowns", color=0x59b0c0)
        embed.description = f"```🎲 Roll : {func.cal_retry_time(user['cooldown']['roll'], 'Ready')}\n" \
                            f"🎮 Claim: {func.cal_retry_time(user['cooldown']['claim'], 'Ready')}\n" \
                            f"📅 Daily: {func.cal_retry_time(user['cooldown']['daily'], 'Ready')}\n" \
                            f"\nTime Left:\n" \
                            f"🏃 Speed: {func.cal_retry_time(user['cooldown']['speed'], 'Not Active')}\n" \
                            f"🌠 Luck : {func.cal_retry_time(user['cooldown']['luck'], 'Not Active')}```"

        embed.set_thumbnail(url=ctx.author.avatar.url)
        await ctx.reply(embed=embed)

    @commands.command(aliases=["s"])
    async def shop(self, ctx: commands.Context):
        """Brings up the IUFI shop."""
        view = ShopView(ctx.author)
        view.message = await ctx.reply(embed=await view.build_embed(), view=view)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Gameplay(bot))