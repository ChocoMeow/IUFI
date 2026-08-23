import discord, iufi, time, asyncio
import functions as func
import random
import io, os
from PIL import Image, ImageFilter

from discord import app_commands
from discord.ext import commands
from iufi.pool import QuestionPool as QP
from views import (
    RollView,
    ShopView,
    MatchGame,
    QuizView,
    ResetAttemptView,
    QUIZ_SETTINGS,
)
from views.emoji_quiz import EmojiQuizView, EmojiResetAttemptView, EMOJI_QUIZ_SETTINGS
from views.pvp import ChallengeView, get_pvp_settings, PvPMatch

class Gameplay(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "🎮"
        self.invisible = False

    @app_commands.command(name="roll", description="Rolls a set of photocards for claiming.")
    @app_commands.describe(tier="Optional tier to use a purchased roll on")
    @app_commands.checks.cooldown(1, 5, key=lambda i: i.user.id)
    async def roll(self, interaction: discord.Interaction, tier: str = None):
        user = await func.get_user(interaction.user.id)
        if not tier and (retry := user["cooldown"]["roll"]) > time.time():
            return await interaction.response.send_message(f"{interaction.user.mention} your next roll is <t:{round(retry)}:R>", ephemeral=True)

        if len(user["cards"]) >= func.get_user_card_limit(user):
            return await interaction.response.send_message(f"**{interaction.user.mention} your inventory is full.**", ephemeral=True)

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
                return await interaction.response.send_message(f"Tier was not found. Please select a valid tier: `{', '.join(user.get('roll').keys())}`")

            if user.get("roll", {}).get(tier, 0) <= 0:
                return await interaction.response.send_message(f"You've used up all your `{tier}` rolls for now.")

            query["$inc"] = {f"roll.{tier}": -1}
            soft_pity_boosts = None

        if not tier:
            query = func.update_quest_progress(user, "ROLL", query=query)
            query = func.add_battlepass_xp(user, func.get_battlepass_xp_for_action("roll"), query=query)
        await func.update_user(interaction.user.id, query)

        if user["exp"] == 0:
            guide_view = discord.ui.View()
            guide_view.add_item(discord.ui.Button(label='Beginner Guide', emoji='📗', url='https://docs.google.com/document/d/1VAD20wZQ56S_wDeMJlwIKn_jImIPuxh2lgy1fn17z0c/edit'))
            await interaction.followup.send(f"**Welcome to IUFI! Please have a look at the guide or use `/help` to begin.**", view=guide_view) if interaction.response.is_done() else await interaction.response.send_message(f"**Welcome to IUFI! Please have a look at the guide or use `/help` to begin.**", view=guide_view)

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
            await func.update_user(interaction.user.id, pity_query)

        image_bytes, image_format = await iufi.gen_cards_view(cards)

        view = RollView(interaction.user, cards)
        message_content = f"**{interaction.user.mention} This is your roll!** (Ends: <t:{round(time.time()) + 71}:R>)"
        file = discord.File(image_bytes, filename=f'image.{image_format}')
        if interaction.response.is_done():
            view.message = await interaction.followup.send(content=message_content, file=file, view=view)
        else:
            await interaction.response.send_message(content=message_content, file=file, view=view)
            view.message = await interaction.original_response()

        await view.timeout_count()
        await func.check_wishlist(view.message, [card.id for card in cards])

    @app_commands.command(name="game", description="IUFI Matching game.")
    @app_commands.describe(level="The match game level")
    async def game(self, interaction: discord.Interaction, level: str):
        if level not in (levels := func.settings.MATCH_GAME_SETTINGS.keys()):
            return await interaction.response.send_message(f"Invalid level selection! Please select a valid level: `{', '.join(levels)}`")

        user = await func.get_user(interaction.user.id)
        if (retry := user.get("cooldown", {}).setdefault("match_game", 0)) > time.time():
            return await interaction.response.send_message(f"{interaction.user.mention} your game is <t:{round(retry)}:R>", ephemeral=True)

        view = MatchGame(interaction.user, level)
        actived_potions = func.get_potions(user.get("actived_potions", {}), func.settings.POTIONS_BASE)

        query = func.update_quest_progress(user, f"PLAY_MATCH_GAME_LVL_{level}", query={"$set": {"cooldown.match_game": time.time() + (view._data.get("cooldown", 0) * (1 - actived_potions.get("speed", 0)))}})
        await func.update_user(interaction.user.id, query)

        embed, file = await view.build()
        await interaction.response.send_message(
            content=f"**This game ends** <t:{round(view._start_time + view._data.get('timeout', 0))}:R>",
            embed=embed, file=file, view=view
        )
        view.response = await interaction.original_response()
        await asyncio.sleep(view._data.get("timeout", 280))
        await view.end_game()
        await view.response.edit(view=view)

    @app_commands.command(name="quiz", description="IUFI Quiz")
    async def quiz(self, interaction: discord.Interaction):
        # Fetch the user data
        user = await func.get_user(interaction.user.id)

        # If the cooldown is still in effect, inform the user and exit
        if (retry := user.get("cooldown", {}).setdefault("quiz_game", 0)) > time.time():
            price = max(5, int(QUIZ_SETTINGS['reset_price'] * ((retry - time.time()) / func.settings.COOLDOWN_BASE["quiz_game"][1])))
            view = ResetAttemptView(interaction, user, price)
            content = f"{interaction.user.mention} your quiz is <t:{round(retry)}:R>. If you\u2019d like to bypass this cooldown, you can do so by paying `🍬 {price}` candies."
            if interaction.response.is_done():
                view.response = await interaction.followup.send(content, view=view)
            else:
                await interaction.response.send_message(content, view=view)
                view.response = await interaction.original_response()
            return

        # Get the rank and questions for the user
        rank = QP.get_question_distribution_by_rank(QP.get_rank(user.get("game_state", {}).get("quiz_game", {}).get("points", 0))[0])
        questions = QP.get_question_by_rank(rank)

        # If there are no questions, inform the user and exit
        if not questions:
            return await interaction.response.send_message("There are no questions for you right now! Please try again later.")

        # Update the user's cooldown time
        query = func.update_quest_progress(user, "PLAY_QUIZ_GAME", query={"$set": {"cooldown.quiz_game": time.time() + func.settings.COOLDOWN_BASE["quiz_game"][1]}})
        await func.update_user(interaction.user.id, query)

        # Create the quiz view and send the initial message
        view = QuizView(interaction.user, questions)
        if interaction.response.is_done():
            view.response = await interaction.followup.send(
                content=f"**This game ends** <t:{round(view._start_time + view.total_time)}:R>",
                embed=view.build_embed(),
                view=view
            )
        else:
            await interaction.response.send_message(
                content=f"**This game ends** <t:{round(view._start_time + view.total_time)}:R>",
                embed=view.build_embed(),
                view=view
            )
            view.response = await interaction.original_response()

        # Wait for the game to end
        await asyncio.sleep(view.total_time)
        await view.end_game()

    @app_commands.command(name="cooldown", description="Shows all your cooldowns.")
    async def cooldown(self, interaction: discord.Interaction):
        user = await func.get_user(interaction.user.id)

        cooldown: dict[str, float] = user.get("cooldown", {})
        embed = discord.Embed(title=f"⏰ {interaction.user.display_name}'s Cooldowns", color=0x59b0c0)
        embed.description = "```" + "".join(f"{emoji} {name.split('_')[0].title():<5}: {func.cal_retry_time(cooldown.get(name, 0), 'Ready')}\n" for name, (emoji, cd) in func.settings.COOLDOWN_BASE.items())

        embed.description += f"🔔 Reminder: {'On' if user.get('reminder', False) else 'Off'}\n\n" \
                             f"Potion Time Left:\n"

        potion_status = "\n".join(
            [f"{data['emoji']} {potion.title():<5} {data['level'].upper():<3}: {func.cal_retry_time(data['expiration'])}"
            for potion, data in func.get_potions(user.get("actived_potions", {}), func.settings.POTIONS_BASE, details=True).items()]
        )

        embed.description += (potion_status if potion_status else "No potions are activated.") + "```"
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="shop", description="Brings up the IUFI shop.")
    async def shop(self, interaction: discord.Interaction):
        view = ShopView(interaction.user)
        await interaction.response.send_message(embed=await view.build_embed(), view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="battlepass", description="Shows your Battle Pass status, progress, and reward outline.")
    async def battlepass(self, interaction: discord.Interaction):
        if not func.battlepass_enabled():
            return await interaction.response.send_message("Battle Pass is currently disabled.")

        user = await func.get_user(interaction.user.id)
        state, sync_query = func.with_battlepass_state_synced(user)
        if sync_query:
            await func.update_user(interaction.user.id, sync_query)

        bp_settings = func.get_battlepass_settings()
        max_level = max(1, int(bp_settings.get("max_level", 100)))
        xp_per_level = max(1, int(bp_settings.get("xp_per_level", 150)))
        price = int(bp_settings.get("shop_price_candies", 0))

        level, in_level_xp, xp_to_next = func.calculate_battlepass_level(state.get("xp", 0))
        progress_pct = 100 if level >= max_level else int((in_level_xp / xp_per_level) * 100)

        def build_progress_bar(current: int, total: int, size: int = 20) -> str:
            if total <= 0:
                return "█" * size
            ratio = max(0.0, min(1.0, current / total))
            filled = int(size * ratio)
            return "█" * filled + "░" * (size - filled)

        progress_bar = build_progress_bar(in_level_xp if level < max_level else xp_per_level, xp_per_level)
        status = "Active" if state.get("is_active") else "Inactive"

        summary = discord.Embed(title=f"🎫 {interaction.user.display_name}'s Battle Pass", color=discord.Color.random())
        summary.description = (
            f"Season: `{state.get('season_id')}`\n"
            f"Status: **{status}**\n"
            f"Price: `🍬 {price}`\n"
            f"```\n"
            f"Level:       {level}/{max_level}\n"
            f"Progress:    {progress_bar} {progress_pct}%\n"
            f"XP in Level: {in_level_xp if level < max_level else xp_per_level}/{xp_per_level}\n"
            f"XP to Next:  {xp_to_next if level < max_level else 0}\n"
            f"```"
        )

        if not state.get("is_active"):
            summary.description += "\nBuy Battle Pass from the shop to start earning Battle Pass XP."

        await interaction.response.send_message(embed=summary)

        lines = []
        for reward_level in range(1, max_level + 1):
            rewards = func.get_battlepass_rewards_for_level(reward_level)
            reward_text = ", ".join(func.format_battlepass_reward(item) for item in rewards) if rewards else "No reward"

            if reward_level <= level:
                marker = "✅"
            elif reward_level == level + 1:
                marker = "👉"
            else:
                marker = "⬜"

            lines.append(f"{marker} L{reward_level:>3}: {reward_text}")

        page_size = 15
        for start in range(0, len(lines), page_size):
            page = lines[start:start + page_size]
            page_embed = discord.Embed(
                title=f"Battle Pass Rewards ({start + 1}-{min(start + page_size, len(lines))})",
                description="```\n" + "\n".join(page) + "\n```",
                color=discord.Color.random()
            )
            await interaction.followup.send(embed=page_embed)

    @app_commands.command(name="emojiquiz", description="Guess IU song or drama by emoji(s).")
    @app_commands.describe(category="Restrict questions to 'song' or 'drama'")
    async def emojiquiz(self, interaction: discord.Interaction, category: str = None):
        user = await func.get_user(interaction.user.id)
        # reuse the quiz cooldown logic
        if (retry := user.get("cooldown", {}).setdefault("quiz_game", 0)) > time.time():
            quiz_cd = func.settings.COOLDOWN_BASE["quiz_game"][1]
            price = max(5, int(EMOJI_QUIZ_SETTINGS['reset_price'] * ((retry - time.time()) / max(1, quiz_cd))))
            view = EmojiResetAttemptView(interaction, user, price)
            content = f"{interaction.user.mention} your emoji quiz is <t:{round(retry)}:R>. If you\u2019d like to bypass this cooldown, you can do so by paying `🍬 {price}` candies."
            if interaction.response.is_done():
                view.response = await interaction.followup.send(content, view=view)
            else:
                await interaction.response.send_message(content, view=view)
                view.response = await interaction.original_response()
            return

        # load emoji entries from JSON file
        try:
            import json
            with open(os.path.join(func.ROOT_DIR, "data", "song_emojis.json"), encoding="utf8") as f:
                entries = json.load(f)
        except Exception:
            entries = []

        if not entries:
            return await interaction.response.send_message("There are no emoji entries available right now.")

        # Normalize category param and filter entries if provided
        category = category.lower() if category else None
        if category and category not in ("song", "drama"):
            return await interaction.response.send_message("Invalid category. Please use `song` or `drama`.")

        filtered = [e for e in entries if (not category) or (e.get("type", "song").lower() == category)]
        if not filtered:
            return await interaction.response.send_message(f"No entries found for category: {category}")

        num_q = min(5, len(filtered))
        # Weighted sampling without replacement based on 'popularity' (1..10). Default popularity=5.
        try:
            items = filtered.copy()
            sampled = []
            for _ in range(num_q):
                weights = [max(1, min(10, int(e.get("popularity", 5)))) for e in items]
                chosen = random.choices(items, weights=weights, k=1)[0]
                sampled.append(chosen)
                # remove the chosen item for subsequent picks
                items.remove(chosen)
        except Exception:
            # fallback to uniform sampling
            sampled = random.sample(filtered, k=num_q)
        # sampled is list of question dicts

        # set cooldown
        quiz_cooldown = func.settings.COOLDOWN_BASE["quiz_game"][1]
        query = func.update_quest_progress(
            user,
            "PLAY_QUIZ_GAME",
            query={"$set": {"cooldown.quiz_game": time.time() + quiz_cooldown}},
        )
        await func.update_user(interaction.user.id, query)

        view = EmojiQuizView(interaction.user, sampled, timeout_per_question=40)
        if interaction.response.is_done():
            view.response = await interaction.followup.send(
                content=f"**This game ends** <t:{round(time.time() + view.total_time)}:R>",
                embed=view.build_embed(),
                view=view
            )
        else:
            await interaction.response.send_message(
                content=f"**This game ends** <t:{round(time.time() + view.total_time)}:R>",
                embed=view.build_embed(),
                view=view
            )
            view.response = await interaction.original_response()

        # start the view runner to manage per-question timeouts
        asyncio.create_task(view.run())

        await asyncio.sleep(view.total_time)
        await view.end_game()

    @app_commands.command(name="pvp", description="Issue a PvP challenge. If opponent is omitted, the challenge is open for anyone to accept.")
    @app_commands.describe(opponent="The member to challenge (omit for an open challenge)")
    async def pvp(self, interaction: discord.Interaction, opponent: discord.Member = None):
        # create challenge view and message
        view = ChallengeView(interaction, interaction.user, opponent, timeout=get_pvp_settings().get("challenge_timeout", 300))
        await interaction.response.send_message(f"{interaction.user.mention} issued a PvP challenge{' to ' + opponent.mention if opponent else ''}. Expires in <t:{round(time.time() + get_pvp_settings().get('challenge_timeout', 300))}:R>", view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="pvp_test", description="[Admin] Auto-start a PvP match using random cards for testing.")
    @app_commands.check(func.is_admin_interaction)
    async def pvp_test(self, interaction: discord.Interaction):
        try:
            # pick random cards for each side
            cards_a = iufi.CardPool.get_random_cards_for_match_game(3)
            cards_b = iufi.CardPool.get_random_cards_for_match_game(3)
        except Exception as e:
            return await interaction.response.send_message(f"Failed to pick random cards for test: {e}")

        opponent = interaction.guild.me
        settings = get_pvp_settings()
        match = PvPMatch(interaction, interaction.user, opponent, settings)

        # send a starter message to attach match outputs to
        await interaction.response.send_message(f"Starting automated PvP test: {interaction.user.mention} vs {opponent.mention}")
        match.message = await interaction.original_response()

        # assign teams directly (bypass modal/ownership checks for testing)
        match.teams[interaction.user.id] = cards_a
        match.teams[opponent.id] = cards_b

        # run the match and wait for it to complete
        await match.run()
        await interaction.followup.send("Automated PvP test finished.")

    @app_commands.command(name="pity", description="[Admin] Shows pity progress for each tier.")
    @app_commands.describe(member="The member to inspect (defaults to yourself)")
    @app_commands.check(func.is_admin_interaction)
    async def pity(self, interaction: discord.Interaction, member: discord.Member = None):
        if not member:
            member = interaction.user

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
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Gameplay(bot))
