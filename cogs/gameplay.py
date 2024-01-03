import discord, iufi, time, asyncio
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
    async def roll(self, ctx: commands.Context, *, tier: str = None):
        """Rolls a set of photocards for claiming."""
        user = await func.get_user(ctx.author.id)
        actived_potions = {} if tier else func.get_potions(user.get("actived_potions", {}), iufi.POTIONS_BASE)

        query = {}
        if not tier:
            query["$set"] = {"cooldown.roll": time.time() + (func.COOLDOWN_BASE["roll"] * (1 - actived_potions.get("speed", 0)))}

        else:
            tier = tier.lower()
            tier = func.match_string(tier, iufi.TIERS_BASE.keys())
            if not tier:
                return await ctx.reply(f"Tier was not found. Please select a valid tier: `{', '.join(user.get('roll').keys())}`")
 
            if user.get("roll", {}).get(tier, 0) <= 0:
                return await ctx.reply(f"You’ve used up all your `{tier}` rolls for now.")
            
            query["$inc"] = {f"roll.{tier}": -1}

        if user["exp"] == 0:
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label='Beginner Guide', emoji='📗', url='https://docs.google.com/document/d/1VAD20wZQ56S_wDeMJlwIKn_jImIPuxh2lgy1fn17z0c/edit'))
            await ctx.reply(f"**Welcome to IUFI! Please have a look at the guide or use `qhelp` to begin.**", view=view)

        if not tier and (retry := user["cooldown"]["roll"]) > time.time():
            return await ctx.reply(f"{ctx.author.mention} your next roll is <t:{round(retry)}:R>", delete_after=10)

        if len(user["cards"]) >= func.MAX_CARDS:
            return await ctx.reply(f"**{ctx.author.mention} your inventory is full.**", delete_after=5)

        cards = iufi.CardPool.roll(included=[tier] if tier else None, luck_rates=None if tier else actived_potions.get("luck", None))
        image_bytes, image_format = await asyncio.to_thread(iufi.gen_cards_view, cards)

        view = RollView(ctx.author, cards)
        view.message = await ctx.send(
            content=f"**{ctx.author.mention} This is your roll!** (Ends: <t:{round(time.time()) + 71}:R>)",
            file=discord.File(image_bytes, filename=f'image.{image_format}'),
            view=view
        )
        
        await func.update_user(ctx.author.id, query)
        await view.timeout_count()

    @commands.command(aliases=["mg"])
    async def game(self, ctx: commands.Context, level: str):
        """Matching game."""
        if level not in (levels := GAME_SETTINGS.keys()):
            return await ctx.reply(f"Invalid level selection! Please select a valid level: `{', '.join(levels)}`")

        user = await func.get_user(ctx.author.id)
        if (retry := user.get("cooldown", {}).setdefault("match_game", 0)) > time.time():
            return await ctx.reply(f"{ctx.author.mention} your game is <t:{round(retry)}:R>", delete_after=10)

        view = MatchGame(ctx.author, level)
        actived_potions = func.get_potions(user.get("actived_potions", {}), iufi.POTIONS_BASE)
        await func.update_user(ctx.author.id, {"$set": {"cooldown.match_game": time.time() + (view._data.get("cooldown", 0) * (1 - actived_potions.get("speed", 0)))}})
        
        embed, file = await view.build()
        view.response = await ctx.reply(
            content=f"**This game ends** <t:{round(view._start_time + view._data.get('timeout', 0))}:R>",
            embed=embed, file=file, view=view
        )
        await asyncio.sleep(view._data.get("timeout", 280))
        await view.end_game()
        await view.response.edit(view=view)

    @commands.command(aliases=["cd"])
    async def cooldown(self, ctx: commands.Context):
        """Shows all your cooldowns."""
        user = await func.get_user(ctx.author.id)

        cooldown: dict[str, float] = user.get("cooldown", {})
        embed = discord.Embed(title=f"⏰ {ctx.author.display_name}'s Cooldowns", color=0x59b0c0)
        embed.description = f"```🎲 Roll : {func.cal_retry_time(cooldown.get('roll', 0), 'Ready')}\n" \
                            f"🎮 Claim: {func.cal_retry_time(cooldown.get('claim', 0), 'Ready')}\n" \
                            f"📅 Daily: {func.cal_retry_time(cooldown.get('daily', 0), 'Ready')}\n" \
                            f"🃏 Game : {func.cal_retry_time(cooldown.get('match_game', 0), 'Ready')}\n" \
                            f"🔔 Reminder: {'On' if user.get('reminder', False) else 'Off'}\n\n" \
                            f"Potion Time Left:\n"

        potion_status = "\n".join(
            [f"{data['emoji']} {potion.title():<5} {data['level'].upper():<3}: {func.cal_retry_time(data['expiration'])}"
            for potion, data in func.get_potions(user.get("actived_potions", {}), iufi.POTIONS_BASE, details=True).items()]
        )

        embed.description += (potion_status if potion_status else "No potions are activated.") + "```"
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

    @commands.command(aliases=["s"])
    async def shop(self, ctx: commands.Context):
        """Brings up the IUFI shop."""
        view = ShopView(ctx.author)
        view.message = await ctx.reply(embed=await view.build_embed(), view=view)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Gameplay(bot))