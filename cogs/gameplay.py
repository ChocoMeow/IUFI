import discord, iufi, time
import functions as func

from discord.ext import commands

from views import RollView, ShopView, MatchGame, GAME_SETTINGS

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

        if user["exp"] == 0:
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label='Beginner Guide', emoji='📗', url='https://docs.google.com/document/d/1clS-HmpKX8MJOv9K383jq7TijJqCi5y5yn68kHPTTpk/edit?usp=drivesdk'))
            await ctx.reply(f"**Welcome to IUFI! Please have a look at the guide or use `qhelp` to begin.**", view=view)


        if (retry := user["cooldown"]["roll"]) > time.time():
            return await ctx.reply(f"{ctx.author.mention} your next roll is <t:{round(retry)}:R>", delete_after=10)

        if len(user["cards"]) >= func.MAX_CARDS:
            return await ctx.reply(f"**{ctx.author.mention} your inventory is full.**", delete_after=5)
        
        actived_potions = func.get_potions(user.get("actived_potions", {}), iufi.POTIONS_BASE)
        cards = iufi.CardPool.roll(luck_rates=actived_potions.get("luck", None))
        image_bytes, image_format = iufi.gen_cards_view(cards)

        view = RollView(ctx.author, cards)
        view.message = await ctx.send(
            content=f"**{ctx.author.mention} This is your roll!** (Ends: <t:{round(time.time()) + 71}:R>)",
            file=discord.File(image_bytes, filename=f'image.{image_format}'),
            view=view
        )
        await func.update_user(ctx.author.id, {"$set": {"cooldown.roll": time.time() + (func.COOLDOWN_BASE["roll"] * (1 - actived_potions.get("speed", 0)))}})
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

    @commands.command(aliases=["mg"])
    async def game(self, ctx: commands.Context, level: str):
        """Matching game."""
        if level not in (levels := GAME_SETTINGS.keys()):
            return await ctx.reply(f"Invalid level selection! Please select a valid level: `{', '.join(levels)}`")
        
        user = await func.get_user(ctx.author.id)
        if (retry := user.get("cooldown", {}).setdefault("match_game", 0)) > time.time():
            return await ctx.reply(f"{ctx.author.mention} your game is <t:{round(retry)}:R>", delete_after=10)

        await func.update_user(ctx.author.id, {"$set": {"cooldown.match_game": time.time() + GAME_SETTINGS.get(level, {}).get("cooldown", 0)}})
        view = MatchGame(ctx.author, level)
        embed, file = view.build()
        view.response = await ctx.reply(embed=embed, file=file, view=view)
        await view.timeout_count()

    @commands.command(aliases=["cd"])
    async def cooldown(self, ctx: commands.Context):
        """Shows all your cooldowns."""
        user = await func.get_user(ctx.author.id)

        cooldown: dict[str, float] = user.get("cooldown", {})
        embed = discord.Embed(title=f"⏰ {ctx.author.display_name}'s Cooldowns", color=0x59b0c0)
        embed.description = f"```🎲 Roll : {func.cal_retry_time(cooldown.get('roll', 0), 'Ready')}\n" \
                            f"🎮 Claim: {func.cal_retry_time(cooldown.get('claim', 0), 'Ready')}\n" \
                            f"📅 Daily: {func.cal_retry_time(cooldown.get('daily', 0), 'Ready')}\n" \
                            f"🃏 Game : {func.cal_retry_time(cooldown.get('match_game', 0), 'Ready')}\n\n" \
                            f"Potion Time Left:\n" 

        potion_status = "\n".join(
            [f"{data['emoji']} {potion.title():<5} {data['level'].upper():<3}: {func.cal_retry_time(data['expiration'])}"
            for potion, data in func.get_potions(user.get("actived_potions", {}), iufi.POTIONS_BASE, details=True).items()]
        )
        
        embed.description += (potion_status if potion_status else "No potions are activated.") + "```"
        embed.set_thumbnail(url=ctx.author.avatar.url)
        await ctx.reply(embed=embed)

    @commands.command(aliases=["s"])
    async def shop(self, ctx: commands.Context):
        """Brings up the IUFI shop."""
        view = ShopView(ctx.author)
        view.message = await ctx.reply(embed=await view.build_embed(), view=view)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Gameplay(bot))