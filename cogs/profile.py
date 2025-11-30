import discord, iufi, time, copy
import functions as func

from discord.ext import commands
from views import (
    CollectionView,
    PhotoCardView,
    WishListView
)
from typing import (
    Dict,
    Any,
    Optional,
)

DAILY_ROWS: list[str] = ["🟥", "🟧", "🟨", "🟩", "🟦", "🟪"]
WEEKLY_REWARDS: list[tuple[str, str, int]] = [
    ("🍬", "candies", 50),
    (func.settings.TIERS_BASE.get("rare")[0], "roll.rare", 1),
    ("🍬", "candies", 100),
    (func.settings.TIERS_BASE.get("epic")[0], "roll.epic", 1),
    ("🍬", "candies", 500),
    (func.settings.TIERS_BASE.get("legendary")[0], "roll.legendary", 1),
]

def generate_progress_bar(total, progress_percentage, filled='█', in_progress='▓', empty='░'):
    """Generate a simple progress bar without ANSI codes"""
    progress = int(total * progress_percentage / 100)
    filled_length = progress
    in_progress_length = 1 if (progress_percentage % (100 / total)) > 0 and progress < total else 0
    empty_length = total - filled_length - in_progress_length

    progress_bar = filled * filled_length + in_progress * in_progress_length + empty * empty_length

    return progress_bar

class StatsView(discord.ui.View):
    def __init__(self, ctx: commands.Context, member: discord.Member):
        super().__init__(timeout=180.0)  # 3 minutes timeout
        self.ctx = ctx
        self.member = member
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the command invoker and the profile owner to use buttons"""
        if interaction.user.id not in (self.ctx.author.id, self.member.id):
            await interaction.response.send_message(
                "❌ You cannot use these buttons. Only the command invoker or profile owner can interact.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        """Disable buttons when view times out"""
        if self.message:
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True
            try:
                await self.message.edit(view=self)
            except:
                pass  # Message might be deleted

    @discord.ui.button(label="📊 Game Stats", style=discord.ButtonStyle.primary, emoji="🎮")
    async def show_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Sends the full game stats when the button is clicked."""
        # Rebuild latest user data to ensure stats are fresh
        user = await func.get_user(self.member.id)

        level, exp = func.calculate_level(user.get('exp', 0))
        quiz_stats = user.get("game_state", {}).get("quiz_game", {
            "points": 0,
            "correct": 0,
            "wrong": 0,
            "timeout": 0,
            "average_time": 0
        })

        card_match_stats = user.get("game_state", {}).get("match_game", {})
        total_questions = quiz_stats["correct"] + quiz_stats["wrong"] + quiz_stats["timeout"]
        total_wrong = quiz_stats["wrong"] + quiz_stats["timeout"]
        rank_name, rank_emoji = iufi.QuestionPool.get_rank(quiz_stats["points"])
        accuracy = round((quiz_stats['correct'] / total_questions * 100), 1) if total_questions > 0 else 0

        pvp_stats = user.get("pvp", {
            "wins": 0,
            "losses": 0,
            "total_matches": 0
        })

        # Calculate PVP win rate safely
        wins = pvp_stats.get('wins', 0)
        losses = pvp_stats.get('losses', 0)
        total_matches = pvp_stats.get('total_matches', wins + losses)
        win_rate = round((wins / total_matches) * 100, 1) if total_matches > 0 else 0

        stats_embed = discord.Embed(
            title=f"🎮 {self.member.display_name}'s Detailed Stats",
            color=discord.Color.from_rgb(138, 43, 226)  # Blue Violet
        )
        stats_embed.set_thumbnail(url=self.member.display_avatar.url)

        # Quiz Stats with better formatting
        stats_embed.add_field(
            name="╔══════ 🧠 Quiz Performance ══════╗",
            value=(
                f"```yaml\n"
                f"Rank:         {rank_name.title()}\n"
                f"Points:       {quiz_stats['points']:,}\n"
                f"Accuracy:     {accuracy}%\n"
                f"Correct:      {quiz_stats['correct']:,}\n"
                f"Wrong:        {total_wrong:,}\n"
                f"Avg Time:     {func.convert_seconds(quiz_stats['average_time'])}\n"
                f"```"
            ),
            inline=False
        )

        # Card Match Stats with better presentation
        try:
            cms_lines = []
            for level in func.settings.MATCH_GAME_SETTINGS.keys():
                stats = card_match_stats.get(str(level))
                if stats:
                    cms_lines.append(
                        f"{DAILY_ROWS[int(level) - 4]} Lvl {level}: {stats.get('matched', 0):>2} cards | {func.convert_seconds(stats.get('finished_time'))}"
                    )
                else:
                    cms_lines.append(f"⬜ Lvl {level}: Not attempted")
            cms_value = "```\n" + "\n".join(cms_lines) + "\n```"
        except Exception:
            cms_value = "```No card match stats available.```"

        stats_embed.add_field(
            name="╔══════ 🃏 Card Match Records ══════╗",
            value=cms_value,
            inline=False
        )

        # PVP Stats with win/loss ratio visualization
        wl_ratio = f"{round(wins/losses, 2)}" if losses > 0 else "∞"
        pvp_bar = ""
        if total_matches > 0:
            win_blocks = int((wins / total_matches) * 10)
            loss_blocks = 10 - win_blocks
            pvp_bar = f"{'🟩' * win_blocks}{'🟥' * loss_blocks}"

        stats_embed.add_field(
            name="╔══════ ⚔️ PVP Statistics ══════╗",
            value=(
                f"```yaml\n"
                f"Total Matches:  {total_matches}\n"
                f"Wins:           {wins}\n"
                f"Losses:         {losses}\n"
                f"Win Rate:       {win_rate}%\n"
                f"W/L Ratio:      {wl_ratio}\n"
                f"```"
                + (f"{pvp_bar} `{win_rate}%`\n" if total_matches > 0 else "")
            ),
            inline=False
        )

        stats_embed.set_footer(text="Keep playing to improve your stats! 🌟")

        await interaction.response.send_message(embed=stats_embed, ephemeral=True)

    @discord.ui.button(label="💕 Collections", style=discord.ButtonStyle.primary, emoji="🖼️")
    async def show_collections(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Shows the member's collections using the existing CollectionView."""
        user = await func.get_user(self.member.id)
        collections = user.get("collections", {})
        if not collections:
            # No collections — inform the clicker ephemerally
            return await interaction.response.send_message(f"**{self.member.display_name}** has no collections yet.", ephemeral=True)

        # Defer the interaction then send the full collection view via the original ctx
        await interaction.response.defer()
        view = CollectionView(self.ctx, self.member, collections)
        await view.send_msg()

class Profile(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "👤"
        self.invisible = False

    @commands.command(aliases=["p"])
    async def profile(self, ctx: commands.Context, member: discord.Member = None):
        """Shows the profile of a member. If called without a member, shows your own profile.

        **Examples:**
        @prefix@profile
        @prefix@p IU
        """
        if not member:
            member = ctx.author

        user = await func.get_user(member.id)
        bio = user.get('profile', {}).get('bio', 'Empty Bio')

        # Calculate level and experience
        level, exp_in_current_level = func.calculate_level(user.get('exp', 0))

        # The exp needed for each level is DEFAULT_EXP
        exp_for_next = func.settings.DEFAULT_EXP
        exp_progress = exp_in_current_level
        exp_percentage = min((exp_progress / exp_for_next * 100) if exp_for_next > 0 else 0, 100)

        # Get quiz rank
        quiz_stats = user.get("game_state", {}).get("quiz_game", {"points": 0})
        rank_name, rank_emoji = iufi.QuestionPool.get_rank(quiz_stats.get("points", 0))

        # Get pvp stats
        pvp_stats = user.get("pvp", {})
        wins = pvp_stats.get('wins', 0)
        losses = pvp_stats.get('losses', 0)
        total_matches = pvp_stats.get('total_matches', wins + losses)
        win_rate = round((wins / total_matches) * 100, 1) if total_matches > 0 else 0

        # Build a beautiful profile embed
        embed = discord.Embed(color=discord.Color.from_rgb(255, 182, 193))  # Soft pink color
        embed.set_author(name=f"{member.display_name}'s Profile", icon_url=member.display_avatar.url)

        # Bio section with better formatting
        if bio and bio != 'Empty Bio':
            embed.description = f"╭─────────────────╮\n📝 *\"{bio}\"*\n╰─────────────────╯\n"
        else:
            embed.description = ""

        # Level & Experience bar
        exp_bar = generate_progress_bar(20, exp_percentage, filled='█', in_progress='▓', empty='░')
        embed.description += f"\n**╔═══ Level & Experience ═══╗**\n"
        embed.description += f"```\n"
        embed.description += f"⭐ Level {level}\n"
        embed.description += f"➤ {exp_bar} {int(exp_percentage)}%\n"
        embed.description += f"➤ {exp_progress:,} / {exp_for_next:,} XP\n"
        embed.description += f"```\n"

        # Stats Overview
        card_count = len(user.get('cards', []))
        card_limit = func.get_user_card_limit(user)
        candies = user.get('candies', 0)
        collections_count = len(user.get('collections', {}))

        embed.add_field(
            name="📊 Overview",
            value=(
                f"```yaml\n"
                f"Cards:       {card_count}/{card_limit}\n"
                f"Candies:     {candies:,} 🍬\n"
                f"Collections: {collections_count}/5\n"
                f"```"
            ),
            inline=True
        )

        # Game Performance
        embed.add_field(
            name="🎮 Performance",
            value=(
                f"```yaml\n"
                f"Quiz Rank:   {rank_name.title()}\n"
                f"Quiz Points: {quiz_stats.get('points', 0):,}\n"
                f"PVP Matches: {total_matches}\n"
                f"Win Rate:    {win_rate}%\n"
                f"```"
            ),
            inline=True
        )

        # Achievements/Badges (placeholder for future expansion)
        # Check if member has IUFI Master role
        has_iufi_master_role = any(role.id == func.settings.MONTHLY_LEADERBOARD_ROLE for role in member.roles) if func.settings.MONTHLY_LEADERBOARD_ROLE else False
        
        embed.add_field(
            name="🏆 Achievements",
            value=(
                f"```\n"
                f"{'🌟' if card_count >= 100 else '⭐'} Card Collector {'✓' if card_count >= 100 else '🔒 Locked'}\n"
                f"{'👑' if has_iufi_master_role else '💎'} IUFI Master {'✓' if has_iufi_master_role else '🔒 Locked'}\n"
                f"{'⚔️' if wins >= 10 else '🗡️'} PVP Champion {'✓' if wins >= 10 else '🔒 Locked'}\n"
                f"```"
            ),
            inline=False
        )

        # Use member's avatar as thumbnail
        embed.set_thumbnail(url=member.display_avatar.url)

        # If the user has a main card that they own, attach it as the large image (show off)
        file = None
        main_card_id = user.get('profile', {}).get('main')
        card = iufi.CardPool.get_card(main_card_id) if main_card_id else None
        if card and card.owner_id == user.get('_id'):
            file = discord.File(await card.image_bytes(), filename=f"image.{card.format}")
            embed.set_image(url=f"attachment://image.{card.format}")
            embed.add_field(
                name="✨ Showcase Card",
                value=f"```{card.tier[0]} {card.display_id}```",
                inline=False
            )

        # Footer with join date or other info
        embed.set_footer(text=f"Member since {member.joined_at.strftime('%B %d, %Y') if member.joined_at else 'Unknown'}")

        # Add interactive buttons
        view = StatsView(ctx, member)

        if file:
            view.message = await ctx.reply(file=file, embed=embed, view=view)
        else:
            view.message = await ctx.reply(embed=embed, view=view)

    @commands.command(aliases=["sb"])
    async def setbio(self, ctx: commands.Context, *, bio: str = None):
        """Sets your profile bio

        **Examples:**
        @prefix@setbio IU is the best
        @prefix@sb IU is the best
        """
        bio = func.clean_text(bio)
        if bio and len(bio) > 30:
            return await ctx.reply(content="Please shorten the bio as it is too long. (No more than 30 chars)")
        
        await func.update_user(ctx.author.id, {"$set": {"profile.bio": bio}})

        func.logger.info(f"User {ctx.author.name}({ctx.author.id}) changed the bio to [{bio}].")

        embed = discord.Embed(description=f"Bio has been set to\n```{bio}```", color=discord.Color.random())
        await ctx.reply(embed=embed)
    
    @commands.command(aliases=["m"])
    async def main(self, ctx: commands.Context, card_id: str = None):
        """Sets the photocard as your profile display. Card can be identified by its ID or given tag.

        **Examples:**
        @prefix@main 01
        @prefix@m 01
        """
        card = None
        if card_id:
            card = iufi.CardPool.get_card(card_id)
            if not card:
                return await ctx.reply("The card was not found. Please try again.")

            if card.owner_id != ctx.author.id:
                return await ctx.reply("You are not the owner of this card.")

        await func.update_user(ctx.author.id, {"$set": {"profile.main": card_id}})
        embed = discord.Embed(title="👤 Set Main", color=discord.Color.random())
        embed.description = (f"```{card.tier[0]} {card.id} has been set as profile card.```" if card_id and card else "```Your profile card has been cleared```")
        await ctx.reply(embed=embed)

    @commands.command(aliases=["ml"])
    async def mainlast(self, ctx: commands.Context):
        """Sets the last photocard in your collection as your profile display.

        **Examples:**
        @prefix@mainlast
        @prefix@ml
        """
        user = await func.get_user(ctx.author.id)
        if not user["cards"]:
            return await ctx.reply(f"**{ctx.author.mention} you have no photocards.**", delete_after=5)
        
        card_id = user["cards"][-1]
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await ctx.reply("The card was not found. Please try again.")

        if card.owner_id != ctx.author.id:
            return await ctx.reply("You are not the owner of this card.")

        await func.update_user(ctx.author.id, {"$set": {"profile.main": card_id}})
        embed = discord.Embed(title="👤 Set Main", color=discord.Color.random())
        embed.description = f"```{card.tier[0]} {card.id} has been set as profile card.```" if card_id else "```Your profile card has been cleared```"
        await ctx.reply(embed=embed)

    @commands.command(aliases=["cc"])
    async def createcollection(self, ctx: commands.Context, name: str):
        """Creates a collection.

        **Examples:**
        @prefix@createcollection IU
        @prefix@cc IU
        """
        name = func.clean_text(name, allow_spaces=False, convert_to_lower=True)
        if len(name) > 10:
            return await ctx.reply(content="Please shorten the collection name as it is too long. (No more than 10 chars)")

        user = await func.get_user(ctx.author.id)
        if user.get("collections", {}).get(name):
            return await ctx.reply(content=f"{ctx.author.mention} a collection with the name `{name.title()}` already exists.")

        if len(user.get("collections")) >= 5:
            return await ctx.reply(content=f"{ctx.author.mention} you have reached the maximum limit of 5 collections.")
        
        func.logger.info(f"User {ctx.author.name}({ctx.author.id}) created a collection named as [{name}].")

        await func.update_user(ctx.author.id, {"$set": {f"collections.{name}": [None] * 6}})
        await ctx.reply(content=f"{ctx.author.mention} collection successfully created with the name `{name.title()}`. You can now use qsetcollection to edit your collection.")
    
    @commands.command(aliases=["sc"])
    async def setcollection(self, ctx: commands.Context, name:str, slot: int, card_id: str = None):
        """Sets a photocard in the given slot [1 to 6] as your collection. Card can be identified by its ID or given tag.
        
        **Examples:**
        @prefix@setcollection IU 1 01
        @prefix@sc IU 2 04
        """
        if not (1 <= slot <= 6):
            return await ctx.reply(content=f"{ctx.author.mention} the slot must be within `the range of 1 to 6`.")
        
        name = name.lower()
        user = await func.get_user(ctx.author.id)
        if not user.get("collections", {}).get(name):
            return await ctx.reply(content=f"{ctx.author.mention} no collection with the name `{name}` was found.")
        
        card = None
        if card_id:
            card = iufi.CardPool.get_card(card_id)
            if not card:
                return await ctx.reply("The card was not found. Please try again.")

            if card.owner_id != ctx.author.id:
                return await ctx.reply("You are not the owner of this card.")

        await func.update_user(ctx.author.id, {"$set": {f"collections.{name}.{slot - 1}": card.id if card_id else None}})

        func.logger.info(f"User {ctx.author.name}({ctx.author.id}) added card [{card.id if card else None}] to [{name}] collection in slot [{slot}].")

        embed = discord.Embed(title="💕 Collection Set", color=discord.Color.random())
        embed.description = f"```📮 {name.title()}\n🆔 {card.id.zfill(5) if card else None}\n🎰 {slot}\n```"
        await ctx.reply(embed=embed)

    @commands.command(aliases=["scl"])
    async def setcollectionlast(self, ctx: commands.Context, name:str, slot: int):
        """Sets your last photocard as a collection in the given slot [1 to 6].

        **Examples:**
        @prefix@setcollectionlast IU 1
        @prefix@scl IU 2
        """
        if not (1 <= slot <= 6):
            return await ctx.reply(content=f"{ctx.author.mention} the slot must be within `the range of 1 to 6`.")
        
        name = name.lower()
        user = await func.get_user(ctx.author.id)
        if not user.get("collections", {}).get(name):
            return await ctx.reply(content=f"{ctx.author.mention} no collection with the name `{name}` was found.")
        
        if not user["cards"]:
            return await ctx.reply(f"**{ctx.author.mention} you have no photocards.**", delete_after=5)
        
        card_id = user["cards"][-1]
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await ctx.reply("The card was not found. Please try again.")

        if card.owner_id != ctx.author.id:
            return await ctx.reply("You are not the owner of this card.")

        await func.update_user(ctx.author.id, {"$set": {f"collections.{name}.{slot - 1}": card.id}})

        func.logger.info(f"User {ctx.author.name}({ctx.author.id}) added card [{card.id}] to [{name}] collection in slot [{slot}].")

        embed = discord.Embed(title="💕 Collection Set", color=discord.Color.random())
        embed.description = f"```📮 {name.title()}\n{card.display_id}\n🎰 {slot}\n```"
        await ctx.reply(embed=embed)

    @commands.command(aliases=["rc"])
    async def removecollection(self, ctx: commands.Context, name: str):
        """Removes the collection.

        **Examples:**
        @prefix@removecollection IU
        @prefix@rc IU
        """
        user = await func.get_user(ctx.author.id)

        name = name.lower()
        if not user.get("collections", {}).get(name):
            return await ctx.reply(content=f"{ctx.author.mention} no collection with the name `{name}` was found.")
        
        await func.update_user(ctx.author.id, {"$unset": {f"collections.{name}": ""}})

        func.logger.info(f"User {ctx.author.name}({ctx.author.id}) removed [{name}] collection.")

        await ctx.reply(content=f"{ctx.author.mention}, the collection with the name `{name}` has been successfully removed.")

    @commands.command(aliases=["f"])
    async def showcollection(self, ctx: commands.Context, member: discord.Member = None):
        """Shows the given member's collection photocards. If not specified, shows your own.

        **Examples:**
        @prefix@showcollection
        @prefix@f IU
        """
        if not member:
            member = ctx.author

        user = await func.get_user(member.id)
        if len(user.get("collections", {})) == 0:
            return await ctx.reply(content=f"{member.mention} don't have any collections.", allowed_mentions=discord.AllowedMentions.none())

        view = CollectionView(ctx, member, user.get("collections"))
        await view.send_msg()

    @commands.command(aliases=["d"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def daily(self, ctx: commands.Context):
        """Claims your daily reward.

        **Examples:**
        @prefix@daily
        @prefix@d
        """
        user = await func.get_user(ctx.author.id)

        end_time: Optional[float] = user.get("cooldown", {}).get("daily", None)
        retry = func.cal_retry_time(end_time)
        if retry:
            return await ctx.reply(f"{ctx.author.mention} your next daily is in {retry}", delete_after=5)

        claimed = user.get("claimed", 0) + 1
        if (time.time() - end_time) >= 72000 or claimed > 30:
            claimed = 1
        
        reward = {"candies": 5} if claimed % 5 else {WEEKLY_REWARDS[(claimed//5) - 1][1]: WEEKLY_REWARDS[(claimed//5) - 1][2]}
        await func.update_user(ctx.author.id, {
            "$set": {"claimed": claimed, "cooldown.daily": time.time() + func.settings.COOLDOWN_BASE["daily"][1]},
            "$inc": reward
        })

        func.logger.info(f"User {ctx.author.name}({ctx.author.id}) claimed their daily reward. Strike: [{claimed}]")

        embed = discord.Embed(title="📅   Daily Reward", color=discord.Color.random())
        embed.description = f"Daily reward claimed! + {'🍬 5' if claimed % 5 else f'{WEEKLY_REWARDS[(claimed//5) - 1][0]} {WEEKLY_REWARDS[(claimed//5) - 1][2]}'}"
        embed.set_thumbnail(url=ctx.author.display_avatar.url)

        value = "```"
        for index, reward in enumerate(WEEKLY_REWARDS):
            for _ in range(5):
                if claimed > 0:
                    value += DAILY_ROWS[index]
                else:
                    value += "⬜"
                claimed -= 1
            value += f"  {reward[2]:>4} {reward[0]} " + ("✅" if claimed >= 0 else "⬛") + "\n"
        embed.add_field(name="Streak Rewards", value=value + "```")
        await ctx.reply(embed=embed)

    @commands.command(aliases=["v"])
    async def view(self, ctx: commands.Context):
        """View your photocard collection.

        **Examples:**
        @prefix@view
        @prefix@v
        """
        user = await func.get_user(ctx.author.id)

        if not user["cards"]:
            return await ctx.reply(f"**{ctx.author.mention} you have no photocards.**", delete_after=5)

        view = PhotoCardView(ctx.author, user)
        embed, _ = await view.build_embed()
        view.message = await ctx.reply(embed=embed, view=view)

    @commands.command(aliases=["in"])
    async def inventory(self, ctx: commands.Context):
        """Shows the items that you own.
        
        **Examples:**
        @prefix@inventory
        @prefix@in
        """
        user = await func.get_user(ctx.author.id)
        embed = discord.Embed(title=f"🎒 {ctx.author.display_name}'s Inventory", color=0x5cb045)
        embed.description = f"```{'🍬 Starcandies':<20} x{user['candies']}\n"

        for tier, count in user.get("roll").items():
            if count > 0 and tier in func.settings.TIERS_BASE.keys():
                emoji, _ = func.settings.TIERS_BASE.get(tier)
                embed.description += f"{emoji} {tier.title() + ' Rolls':<18} x{count}\n"

        embed.description += f"\n\n"

        potions_data: dict[str, int] = user.get("potions", {})
        potions = ("\n".join(
            [f"{potion.split('_')[0].title() + ' ' + potion.split('_')[1].upper() + ' Potion':21} x{amount}"
            for potion, amount in potions_data.items() if amount]
        ) if sum(potions_data.values()) else "Potion not found!")

        embed.description += f"🍶 Potions:\n{potions}```"
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

    @commands.command(aliases=["qu"])
    async def quests(self, ctx: commands.Context):
        """Shows the daily quests

        **Examples:**
        @prefix@quests
        @prefix@qu
        """
        user = await func.get_user(ctx.author.id)

        embed = discord.Embed(color=discord.Color.random())
        query = func.update_quest_progress(user, "", progress=0, query={})
        if query:
            await func.update_user(ctx.author.id, query)
        
        for quest_type in func.settings.USER_BASE["quests"].keys():    
            user_quest: Dict[str, Any] = user.copy().get("quests", {}).get(quest_type, copy.deepcopy(func.settings.USER_BASE["quests"][quest_type]))

            if quest_type.lower() == 'daily':
                QUESTS_BASE: Dict[str, Any] = func.settings.DAILY_QUESTS
            elif quest_type.lower() == 'weekly':
                QUESTS_BASE: Dict[str, Any] = func.settings.WEEKLY_QUESTS
            else:
                QUESTS_BASE: Dict[str, Any] = {}
            if not QUESTS_BASE:
                continue

            reset_time = round(user_quest.get("next_update", 0))
            details = ""
            for quest_name, progress in user_quest.get("progresses", {}).items():
                quest = QUESTS_BASE.get(quest_name)
                if quest:
                    progress_percentage = (progress / quest['amount']) * 100
                    progress_bar = generate_progress_bar(15, progress_percentage)
                    details += f"{'✅' if progress >= quest['amount'] else '❌'} {quest['title']}\n"
                    details += f"```ansi\n➢ Reward: " + " | ".join(f"{r[0]} {f'{r[2][0]} ~ {r[2][1]}' if isinstance(r[2], list) else r[2]}" for r in quest["rewards"]) + f"\n➢ {progress_bar} {int(progress_percentage)}% ({progress}/{quest['amount']})```\n"
            
            embed.add_field(name=f"{quest_type.title()} Quests", value=f"Resets at <t:{reset_time}:t> (<t:{reset_time}:R>)\n\n{details}", inline=False)

        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

    @commands.command(aliases=["wl"])
    async def wishlist(self, ctx: commands.Context):
        """Add cards into your wishlist when the card got trade of roll by player you will got a dm from IUFIAdd cards to your wishlist! When a card is traded or rolled by a player, you'll receive a DM from IUFI. After that, the card will be automatically removed from your wishlist.

        **Examples:**
        @prefix@wishlist
        @prefix@wl
        """
        user = await func.get_user(ctx.author.id)
        view = WishListView(ctx, user)
        view.message = await ctx.send(embed=view.build_embed(), view=view)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Profile(bot))