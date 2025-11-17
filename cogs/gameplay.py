import discord, iufi, time, asyncio
import functions as func

from discord.ext import commands
from iufi.pool import QuestionPool as QP
from views import (
    RollView,
    ShopView,
    MatchGame,
    QuizView,
    ResetAttemptView,
    QUIZ_SETTINGS
)

class Gameplay(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "🎮"
        self.invisible = False

    @commands.command(aliases=["r"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def roll(self, ctx: commands.Context, *, tier: str = None):
        """Rolls a set of photocards for claiming.

        **Examples:**
        @prefix@roll
        @prefix@r rare
        """
        user = await func.get_user(ctx.author.id)
        if not tier and (retry := user["cooldown"]["roll"]) > time.time():
            return await ctx.reply(f"{ctx.author.mention} your next roll is <t:{round(retry)}:R>", delete_after=10)

        if len(user["cards"]) >= func.get_user_card_limit(user):
            return await ctx.reply(f"**{ctx.author.mention} your inventory is full.**", delete_after=5)
        
        actived_potions = {} if tier else func.get_potions(user.get("actived_potions", {}), func.settings.POTIONS_BASE)
        query = {}
        guaranteed_tier = None

        if not tier:
            # Normal roll - check if pity guarantees a tier
            guaranteed_tier = func.check_pity_guarantee(user)

            # Calculate soft pity boosts for rate increases
            soft_pity_boosts = func.calculate_soft_pity_boost(user)

            query["$set"] = {"cooldown.roll": time.time() + (func.settings.COOLDOWN_BASE["roll"][1] * (1 - actived_potions.get("speed", 0)))}

        else:
            # Purchased roll - don't affect pity
            tier = func.match_string(tier.lower(), func.settings.TIERS_BASE.keys())
            if not tier:
                return await ctx.reply(f"Tier was not found. Please select a valid tier: `{', '.join(user.get('roll').keys())}`")
 
            if user.get("roll", {}).get(tier, 0) <= 0:
                return await ctx.reply(f"You've used up all your `{tier}` rolls for now.")

            query["$inc"] = {f"roll.{tier}": -1}
            soft_pity_boosts = None

        query = func.update_quest_progress(user, "ROLL", query=query)
        await func.update_user(ctx.author.id, query)
        
        if user["exp"] == 0:
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label='Beginner Guide', emoji='📗', url='https://docs.google.com/document/d/1VAD20wZQ56S_wDeMJlwIKn_jImIPuxh2lgy1fn17z0c/edit'))
            await ctx.reply(f"**Welcome to IUFI! Please have a look at the guide or use `qhelp` to begin.**", view=view)

        # Roll cards with guaranteed tier if pity was triggered, otherwise use the purchased tier or normal roll
        roll_tier = guaranteed_tier if guaranteed_tier else tier

        # Apply soft pity boosts for normal rolls (combine with luck potion if present)
        if not tier and not roll_tier:
            # Normal roll without guarantee - apply soft pity boosts
            cards = iufi.CardPool.roll(
                included=[roll_tier] if roll_tier else None,
                luck_rates=actived_potions.get("luck", None),
                soft_pity_boosts=soft_pity_boosts
            )
        else:
            # Guaranteed roll or purchased roll - no soft pity
            cards = iufi.CardPool.roll(
                included=[roll_tier] if roll_tier else None,
                luck_rates=None if roll_tier else actived_potions.get("luck", None)
            )

        # Update pity based on rolled cards (only for normal rolls)
        if not tier:
            pity_query = func.update_pity_from_cards(user, cards)
            await func.update_user(ctx.author.id, pity_query)

        image_bytes, image_format = await iufi.gen_cards_view(cards)

        view = RollView(ctx.author, cards)
        view.message = await ctx.send(
            content=f"**{ctx.author.mention} This is your roll!** (Ends: <t:{round(time.time()) + 71}:R>)",
            file=discord.File(image_bytes, filename=f'image.{image_format}'),
            view=view
        )
        
        await view.timeout_count()
        await func.check_wishlist(view.message, [card.id for card in cards])

    @commands.command(aliases=["mg"])
    async def game(self, ctx: commands.Context, level: str):
        """IUFI Matching game.

        **Examples:**
        @prefix@game 1
        @prefix@mg 2
        """
        if level not in (levels := func.settings.MATCH_GAME_SETTINGS.keys()):
            return await ctx.reply(f"Invalid level selection! Please select a valid level: `{', '.join(levels)}`")

        user = await func.get_user(ctx.author.id)
        if (retry := user.get("cooldown", {}).setdefault("match_game", 0)) > time.time():
            return await ctx.reply(f"{ctx.author.mention} your game is <t:{round(retry)}:R>", delete_after=10)

        view = MatchGame(ctx.author, level)
        actived_potions = func.get_potions(user.get("actived_potions", {}), func.settings.POTIONS_BASE)

        query = func.update_quest_progress(user, f"PLAY_MATCH_GAME_LVL_{level}", query={"$set": {"cooldown.match_game": time.time() + (view._data.get("cooldown", 0) * (1 - actived_potions.get("speed", 0)))}})
        await func.update_user(ctx.author.id, query)
        
        embed, file = await view.build()
        view.response = await ctx.reply(
            content=f"**This game ends** <t:{round(view._start_time + view._data.get('timeout', 0))}:R>",
            embed=embed, file=file, view=view
        )
        await asyncio.sleep(view._data.get("timeout", 280))
        await view.end_game()
        await view.response.edit(view=view)

    @commands.command(aliases=["q"])
    async def quiz(self, ctx: commands.Context):
        """IUFI Quiz
        
        **Examples:**
        @prefix@quiz
        @prefix@q
        """
        # Fetch the user data
        user = await func.get_user(ctx.author.id)

        # If the cooldown is still in effect, inform the user and exit
        if (retry := user.get("cooldown", {}).setdefault("quiz_game", 0)) > time.time():
            price = max(5, int(QUIZ_SETTINGS['reset_price'] * ((retry - time.time()) / func.settings.COOLDOWN_BASE["quiz_game"][1])))
            view = ResetAttemptView(ctx, user, price)
            view.response = await ctx.reply(f"{ctx.author.mention} your quiz is <t:{round(retry)}:R>. If you’d like to bypass this cooldown, you can do so by paying `🍬 {price}` candies.", delete_after=20, view=view)
            return 
        
        # Get the rank and questions for the user
        rank = QP.get_question_distribution_by_rank(QP.get_rank(user.get("game_state", {}).get("quiz_game", {}).get("points", 0))[0])
        questions = QP.get_question_by_rank(rank)

        # If there are no questions, inform the user and exit
        if not questions:
            return await ctx.send("There are no questions for you right now! Please try again later.")

        # Update the user's cooldown time
        query = func.update_quest_progress(user, "PLAY_QUIZ_GAME", query={"$set": {"cooldown.quiz_game": time.time() + func.settings.COOLDOWN_BASE["roll"][1]}})
        await func.update_user(ctx.author.id, query)

        # Create the quiz view and send the initial message
        view = QuizView(ctx.author, questions)
        view.response = await ctx.reply(
            content=f"**This game ends** <t:{round(view._start_time + view.total_time)}:R>",
            embed=view.build_embed(),
            view=view
        )

        # Wait for the game to end
        await asyncio.sleep(view.total_time)
        await view.end_game()

    @commands.command(aliases=["cd"])
    async def cooldown(self, ctx: commands.Context):
        """Shows all your cooldowns.

        **Examples:**
        @prefix@cooldown
        @prefix@cd
        """
        user = await func.get_user(ctx.author.id)

        cooldown: dict[str, float] = user.get("cooldown", {})
        embed = discord.Embed(title=f"⏰ {ctx.author.display_name}'s Cooldowns", color=0x59b0c0)
        embed.description = "```" + "".join(f"{emoji} {name.split('_')[0].title():<5}: {func.cal_retry_time(cooldown.get(name, 0), 'Ready')}\n" for name, (emoji, cd) in func.settings.COOLDOWN_BASE.items())
        
        embed.description += f"🔔 Reminder: {'On' if user.get('reminder', False) else 'Off'}\n\n" \
                             f"Potion Time Left:\n"

        potion_status = "\n".join(
            [f"{data['emoji']} {potion.title():<5} {data['level'].upper():<3}: {func.cal_retry_time(data['expiration'])}"
            for potion, data in func.get_potions(user.get("actived_potions", {}), func.settings.POTIONS_BASE, details=True).items()]
        )

        embed.description += (potion_status if potion_status else "No potions are activated.") + "```"
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

    @commands.command(aliases=["s"])
    async def shop(self, ctx: commands.Context):
        """Brings up the IUFI shop.

        **Examples:**
        @prefix@shop
        @prefix@s
        """
        view = ShopView(ctx.author)
        view.message = await ctx.reply(embed=await view.build_embed(), view=view)

    @commands.command(aliases=["mypity"], hidden=True)
    async def pity(self, ctx: commands.Context, member: discord.Member = None):
        """Shows pity progress for each tier. Admin only command.

        **Examples:**
        @prefix@pity
        @prefix@pity @user
        """
        if ctx.author.id not in func.settings.ADMIN_IDS:
            return await ctx.reply("This command is only available to administrators.", delete_after=5)

        if not member:
            member = ctx.author

        user = await func.get_user(member.id)
        user_pity = user.get("pity", {})
        soft_pity_boosts = func.calculate_soft_pity_boost(user)

        embed = discord.Embed(title=f"🎲 {member.display_name}'s Pity Progress", color=0x59b0c0)

        pity_info = []
        for tier, pity_config in func.settings.PITY_SETTINGS.items():
            soft_pity = pity_config.get('soft_pity', 0)
            hard_pity = pity_config.get('hard_pity', 0)
            max_boost = pity_config.get('soft_pity_boost', 1.0)
            current = user_pity.get(tier, 0)
            current_boost = soft_pity_boosts.get(tier, 1.0)

            # Determine which phase user is in
            if current >= hard_pity:
                phase = "🔥 HARD PITY (Guaranteed!)"
                progress_to_show = hard_pity
                bar_percentage = 1.0
            elif current >= soft_pity:
                phase = f"✨ SOFT PITY (Rates boosted {current_boost:.2f}x)"
                progress_to_show = hard_pity
                bar_percentage = current / hard_pity
            else:
                phase = f"📊 Building (Soft pity at {soft_pity})"
                progress_to_show = soft_pity
                bar_percentage = current / soft_pity if soft_pity > 0 else 0

            # Progress bar
            progress_bar_length = 20
            filled = int(bar_percentage * progress_bar_length)
            bar = "█" * filled + "░" * (progress_bar_length - filled)

            pity_info.append(f"**{tier.capitalize()}**: {current}/{progress_to_show}")
            pity_info.append(f"{bar} {phase}\n")

        embed.description = "\n".join(pity_info)
        embed.set_footer(text="Soft pity: Increased rates | Hard pity: Guaranteed! | Normal rolls only.")
        embed.set_thumbnail(url=member.display_avatar.url)
        await ctx.reply(embed=embed)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Gameplay(bot))