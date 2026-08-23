import discord, iufi, time, copy
import functions as func

from discord import app_commands
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

class Profile(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji = "👤"
        self.invisible = False

    @app_commands.command(name="profile", description="Shows the profile of a member. If not specified, shows your own profile.")
    @app_commands.describe(member="The member to view (defaults to yourself)")
    async def profile(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        user = await func.get_user(member.id)
        profile = user.get("profile", {})
        bio =  profile.get("bio")
        level, exp_current = func.calculate_level(user.get("exp", 0))

        exp_next = func.settings.DEFAULT_EXP
        exp_pct = min((exp_current / exp_next * 100), 100) if exp_next > 0 else 0

        pvp = user.get("pvp", {})
        wins = pvp.get("wins", 0)

        embed = discord.Embed(color=discord.Color.from_rgb(255, 182, 193))
        embed.set_author(name=f"{member.display_name}'s Profile", icon_url=member.display_avatar.url)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Member was last online {func.cal_last_online_time(user.get('last_active_time'))} ago")

        embed.description = f"╭─────────────────╮\n📝 *\"{bio}\"*\n╰─────────────────╯\n" if bio else ""

        # Level / XP
        exp_bar = generate_progress_bar(20, exp_pct, filled="█", in_progress="▓", empty="░")
        embed.description += func.framed_title("Levels") + "\n"
        embed.description += (
            "```\n"
            f"⭐ Level {level}\n"
            f"➤ {exp_bar} {int(exp_pct)}%\n"
            f"➤ {exp_current:,} / {exp_next:,} XP\n"
            "```\n"
        )

        # Overview
        cards = user.get("cards", [])
        card_count = len(cards)
        card_limit = func.get_user_card_limit(user)
        candies = user.get("candies", 0)
        collections_count = len(user.get("collections", {}))
        streak = user.get("claimed", 0)
        streak_multiplier = ((streak - 1) // 30) + 1 if streak > 0 else 1

        embed.add_field(
            name=func.framed_title("Overview"),
            value=(
                "```yaml\n"
                f"Cards:       {card_count}/{card_limit}\n"
                f"Candies:     {candies:,} 🍬\n"
                f"Collections: {collections_count}/5\n"
                f"Streak:      {streak}\n"
                f"Streak Mult: x{streak_multiplier}\n"
                "```"
            ),
            inline=True,
        )

        # Unlocks / Achievements
        has_iufi_role = bool(func.settings.MONTHLY_LEADERBOARD_ROLE and any(role.id == func.settings.MONTHLY_LEADERBOARD_ROLE for role in member.roles))
        embed.add_field(
            name=func.framed_title("Unlocks"),
            value=(
                "```"
                f"{'🌟' if card_count >= 100 else '⭐'} {'Card Collector':<16} {'✅' if card_count >= 100 else '🔒'}\n"
                f"{'👑' if has_iufi_role else '💎'} {'IUFI Master':<16} {'✅' if has_iufi_role else '🔒'}\n"
                f"{'⚔️' if wins >= 10 else '🗡️'} {'PVP Champion':<16} {'✅' if wins >= 10 else '🔒'}\n"
                "```"
            ),
            inline=False,
        )

        # Showcase main card if owned
        file = discord.utils.MISSING
        main_id = profile.get("main")
        card = iufi.CardPool.get_card(main_id) if main_id else None
        if card and card.owner_id == member.id:
            image_name = f"image.{card.format}"
            file = discord.File(await card.image_bytes(), filename=image_name)
            embed.set_image(url=f"attachment://{image_name}")
            embed.add_field(name=func.framed_title("Showcase"), value=f"```{card}```", inline=False)

        await interaction.response.send_message(embed=embed, file=file)

    @app_commands.command(name="setbio", description="Sets your profile bio.")
    @app_commands.describe(bio="The bio text (max 30 chars)")
    async def setbio(self, interaction: discord.Interaction, bio: str = None):
        bio = func.clean_text(bio)
        if bio and len(bio) > 30:
            return await interaction.response.send_message(content="Please shorten the bio as it is too long. (No more than 30 chars)")
        
        await func.update_user(interaction.user.id, {"$set": {"profile.bio": bio}})

        func.logger.info(f"User {interaction.user.name}({interaction.user.id}) changed the bio to [{bio}].")

        embed = discord.Embed(description=f"Bio has been set to\n```{bio}```", color=discord.Color.random())
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="main", description="Sets a photocard as your profile display. Card can be identified by its ID or given tag.")
    @app_commands.describe(card_id="The card ID or tag (omit to clear your profile card)")
    async def main(self, interaction: discord.Interaction, card_id: str = None):
        card = None
        if card_id:
            card = iufi.CardPool.get_card(card_id)
            if not card:
                return await interaction.response.send_message("The card was not found. Please try again.")

            if card.owner_id != interaction.user.id:
                return await interaction.response.send_message("You are not the owner of this card.")

        await func.update_user(interaction.user.id, {"$set": {"profile.main": card_id}})
        embed = discord.Embed(title="👤 Set Main", color=discord.Color.random())
        embed.description = (f"```{card.tier[0]} {card.id} has been set as profile card.```" if card_id and card else "```Your profile card has been cleared```")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="mainlast", description="Sets the last photocard in your collection as your profile display.")
    async def mainlast(self, interaction: discord.Interaction):
        user = await func.get_user(interaction.user.id)
        if not user["cards"]:
            return await interaction.response.send_message(f"**{interaction.user.mention} you have no photocards.**", ephemeral=True)
        
        card_id = user["cards"][-1]
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await interaction.response.send_message("The card was not found. Please try again.")

        if card.owner_id != interaction.user.id:
            return await interaction.response.send_message("You are not the owner of this card.")

        await func.update_user(interaction.user.id, {"$set": {"profile.main": card_id}})
        embed = discord.Embed(title="👤 Set Main", color=discord.Color.random())
        embed.description = f"```{card.tier[0]} {card.id} has been set as profile card.```" if card_id else "```Your profile card has been cleared```"
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="createcollection", description="Creates a collection.")
    @app_commands.describe(name="The collection name (max 10 chars)")
    async def createcollection(self, interaction: discord.Interaction, name: str):
        name = func.clean_text(name, allow_spaces=False, convert_to_lower=True)
        if len(name) > 10:
            return await interaction.response.send_message(content="Please shorten the collection name as it is too long. (No more than 10 chars)")

        user = await func.get_user(interaction.user.id)
        if user.get("collections", {}).get(name):
            return await interaction.response.send_message(content=f"{interaction.user.mention} a collection with the name `{name.title()}` already exists.")

        if len(user.get("collections")) >= 5:
            return await interaction.response.send_message(content=f"{interaction.user.mention} you have reached the maximum limit of 5 collections.")
        
        func.logger.info(f"User {interaction.user.name}({interaction.user.id}) created a collection named as [{name}].")

        await func.update_user(interaction.user.id, {"$set": {f"collections.{name}": [None] * 6}})
        await interaction.response.send_message(content=f"{interaction.user.mention} collection successfully created with the name `{name.title()}`. You can now use /setcollection to edit your collection.")

    @app_commands.command(name="setcollection", description="Sets a photocard in a collection slot [1-6]. Card can be ID or tag.")
    @app_commands.describe(name="The collection name", slot="The slot number (1-6)", card_id="The card ID or tag (omit to clear the slot)")
    async def setcollection(self, interaction: discord.Interaction, name: str, slot: int, card_id: str = None):
        if not (1 <= slot <= 6):
            return await interaction.response.send_message(content=f"{interaction.user.mention} the slot must be within `the range of 1 to 6`.")
        
        name = name.lower()
        user = await func.get_user(interaction.user.id)
        if not user.get("collections", {}).get(name):
            return await interaction.response.send_message(content=f"{interaction.user.mention} no collection with the name `{name}` was found.")
        
        card = None
        if card_id:
            card = iufi.CardPool.get_card(card_id)
            if not card:
                return await interaction.response.send_message("The card was not found. Please try again.")

            if card.owner_id != interaction.user.id:
                return await interaction.response.send_message("You are not the owner of this card.")

        await func.update_user(interaction.user.id, {"$set": {f"collections.{name}.{slot - 1}": card.id if card_id else None}})

        func.logger.info(f"User {interaction.user.name}({interaction.user.id}) added card [{card.id if card else None}] to [{name}] collection in slot [{slot}].")

        embed = discord.Embed(title="💕 Collection Set", color=discord.Color.random())
        embed.description = f"```📮 {name.title()}\n🆔 {card.id.zfill(5) if card else None}\n🎰 {slot}\n```"
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setcollectionlast", description="Sets your last photocard as a collection in the given slot [1 to 6].")
    @app_commands.describe(name="The collection name", slot="The slot number (1-6)")
    async def setcollectionlast(self, interaction: discord.Interaction, name: str, slot: int):
        if not (1 <= slot <= 6):
            return await interaction.response.send_message(content=f"{interaction.user.mention} the slot must be within `the range of 1 to 6`.")
        
        name = name.lower()
        user = await func.get_user(interaction.user.id)
        if not user.get("collections", {}).get(name):
            return await interaction.response.send_message(content=f"{interaction.user.mention} no collection with the name `{name}` was found.")
        
        if not user["cards"]:
            return await interaction.response.send_message(f"**{interaction.user.mention} you have no photocards.**", ephemeral=True)
        
        card_id = user["cards"][-1]
        card = iufi.CardPool.get_card(card_id)
        if not card:
            return await interaction.response.send_message("The card was not found. Please try again.")

        if card.owner_id != interaction.user.id:
            return await interaction.response.send_message("You are not the owner of this card.")

        await func.update_user(interaction.user.id, {"$set": {f"collections.{name}.{slot - 1}": card.id}})

        func.logger.info(f"User {interaction.user.name}({interaction.user.id}) added card [{card.id}] to [{name}] collection in slot [{slot}].")

        embed = discord.Embed(title="💕 Collection Set", color=discord.Color.random())
        embed.description = f"```📮 {name.title()}\n{card.display_id}\n🎰 {slot}\n```"
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="removecollection", description="Removes a collection.")
    @app_commands.describe(name="The collection name")
    async def removecollection(self, interaction: discord.Interaction, name: str):
        user = await func.get_user(interaction.user.id)

        name = name.lower()
        if not user.get("collections", {}).get(name):
            return await interaction.response.send_message(content=f"{interaction.user.mention} no collection with the name `{name}` was found.")
        
        await func.update_user(interaction.user.id, {"$unset": {f"collections.{name}": ""}})

        func.logger.info(f"User {interaction.user.name}({interaction.user.id}) removed [{name}] collection.")

        await interaction.response.send_message(content=f"{interaction.user.mention}, the collection with the name `{name}` has been successfully removed.")

    @app_commands.command(name="showcollection", description="Shows the given member's collection photocards. If not specified, shows your own.")
    @app_commands.describe(member="The member to view (defaults to yourself)")
    async def showcollection(self, interaction: discord.Interaction, member: discord.Member = None):
        if not member:
            member = interaction.user

        user = await func.get_user(member.id)
        if len(user.get("collections", {})) == 0:
            return await interaction.response.send_message(content=f"{member.mention} don't have any collections.", allowed_mentions=discord.AllowedMentions.none())

        view = CollectionView(interaction, member, user.get("collections"))
        await view.send_msg()

    @app_commands.command(name="daily", description="Claims your daily reward.")
    @app_commands.checks.cooldown(1, 5, key=lambda i: i.user.id)
    async def daily(self, interaction: discord.Interaction):
        user = await func.get_user(interaction.user.id)

        end_time: Optional[float] = user.get("cooldown", {}).get("daily", None)
        retry = func.cal_retry_time(end_time)
        if retry:
            return await interaction.response.send_message(f"{interaction.user.mention} your next daily is in {retry}", ephemeral=True)

        current_time = time.time()
        claimed = user.get("claimed", 0) + 1
        if (current_time - end_time) >= 72000:
            claimed = 1

        cycle_index = (claimed - 1) // 30
        cycle_multiplier = cycle_index + 1
        day_in_cycle = ((claimed - 1) % 30) + 1

        if day_in_cycle % 5:
            reward_emoji, reward_key, base_amount = "🍬", "candies", 5
        else:
            reward_emoji, reward_key, base_amount = WEEKLY_REWARDS[(day_in_cycle // 5) - 1]

        reward_amount = base_amount * cycle_multiplier
        reward = {reward_key: reward_amount}

        await func.update_user(interaction.user.id, {
            "$set": {"claimed": claimed, "cooldown.daily": current_time + func.settings.COOLDOWN_BASE["daily"][1]},
            "$inc": reward
        })

        func.logger.info(
            f"User {interaction.user.name}({interaction.user.id}) claimed their daily reward. "
            f"Strike: [{claimed}] Cycle: [{cycle_index + 1}] Multiplier: [x{cycle_multiplier}]"
        )

        embed = discord.Embed(title="📅   Daily Reward", color=discord.Color.random())
        streak_status = f"Streak: **{claimed}** | Day: **{day_in_cycle}/30**"
        if cycle_multiplier > 1:
            streak_status += f" | Multiplier: **x{cycle_multiplier}**"

        embed.description = (
            f"Daily reward claimed! + {reward_emoji} {reward_amount}\n"
            f"{streak_status}"
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        value = "```"
        progress_in_cycle = day_in_cycle
        for index, reward in enumerate(WEEKLY_REWARDS):
            for _ in range(5):
                if progress_in_cycle > 0:
                    value += DAILY_ROWS[index]
                else:
                    value += "⬜"
                progress_in_cycle -= 1
            value += f"  {(reward[2] * cycle_multiplier):>4} {reward[0]} " + ("✅" if day_in_cycle >= ((index + 1) * 5) else "⬛") + "\n"
        embed.add_field(name="Streak Rewards", value=value + "```")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="view", description="View your photocard collection.")
    @app_commands.checks.cooldown(1, 5, key=lambda i: i.user.id)
    async def view(self, interaction: discord.Interaction):
        user = await func.get_user(interaction.user.id)

        if not user["cards"]:
            return await interaction.response.send_message(f"**{interaction.user.mention} you have no photocards.**", ephemeral=True)

        view = PhotoCardView(interaction.user, user)
        embed, _ = await view.build_embed()
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @app_commands.command(name="inventory", description="Shows the items that you own.")
    async def inventory(self, interaction: discord.Interaction):
        user = await func.get_user(interaction.user.id)
        embed = discord.Embed(title=f"🎒 {interaction.user.display_name}'s Inventory", color=0x5cb045)
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
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="quests", description="Shows your daily/weekly quest progress.")
    async def quests(self, interaction: discord.Interaction):
        user = await func.get_user(interaction.user.id)

        embed = discord.Embed(color=discord.Color.random())
        query = func.update_quest_progress(user, "", progress=0, query={})
        if query:
            await func.update_user(interaction.user.id, query)

        def format_quest_reward(reward: list[Any]) -> str:
            emoji, reward_key, reward_amount = reward
            if isinstance(reward_key, str) and reward_key.startswith("potions."):
                potion_suffix = reward_key.split(".", 1)[1]
                potion_level = potion_suffix.split("_")[-1]
                level_map = {"i": "1", "ii": "2", "iii": "3"}
                level_text = level_map.get(potion_level.lower(), potion_level.upper())

                if isinstance(reward_amount, list):
                    min_qty, max_qty = reward_amount
                    qty_text = f"x{min_qty}" if min_qty == max_qty else f"x{min_qty}~{max_qty}"
                else:
                    qty_text = f"x{reward_amount}"
                return f"{emoji} Lvl {level_text} {qty_text}"

            if isinstance(reward_amount, list):
                return f"{emoji} {reward_amount[0]} ~ {reward_amount[1]}"
            return f"{emoji} {reward_amount}"
        
        for quest_type in func.settings.USER_BASE["quests"].keys():    
            user_quest: Dict[str, Any] = user.copy().get("quests", {}).get(quest_type, copy.deepcopy(func.settings.USER_BASE["quests"][quest_type]))

            QUESTS_BASE: Dict[str, Any] = getattr(func.settings, f"{quest_type.upper()}_QUESTS", None)
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
                    details += f"```ansi\n➢ Reward: " + " | ".join(format_quest_reward(r) for r in quest["rewards"]) + f"\n➢ {progress_bar} {int(progress_percentage)}% ({progress}/{quest['amount']})```\n"
            
            embed.add_field(name=f"{quest_type.title()} Quests", value=f"Resets at <t:{reset_time}:t> (<t:{reset_time}:R>)\n\n{details}", inline=False)

        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="wishlist", description="Manage your wishlist. You'll get a DM when a wishlisted card is traded or rolled.")
    async def wishlist(self, interaction: discord.Interaction):
        user = await func.get_user(interaction.user.id)
        view = WishListView(interaction, user)
        await interaction.response.send_message(embed=view.build_embed(), view=view)
        view.message = await interaction.original_response()

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Profile(bot))