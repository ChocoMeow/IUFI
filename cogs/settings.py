import discord
import functions as func

from discord.ext import commands

class Settings(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.emoji = "⚙️"
        self.invisible = False

    @commands.command(aliases=["tr"])
    async def togglereminder(self, ctx: commands.Context, target: str = None) -> None:
        """Toggle reminders.

        With no argument, toggles the global reminder flag (legacy behavior).
        With a cooldown name or shorthand (prefix), toggles that specific reminder only.

        Examples:
        @prefix@togglereminder          # toggle all reminders (legacy)
        @prefix@togglereminder d        # toggle daily reminder only
        @prefix@togglereminder r        # toggle roll reminder only
        @prefix@togglereminder mg       # toggle match_game reminder only
        """
        # cooldown keys we care about (exclude claim)
        cooldown_keys = [k for k in func.settings.COOLDOWN_BASE.keys() if k != "claim"]

        # simple alias map for common short flags
        alias_map = {
            "d": "daily",
            "r": "roll",
            "mg": "match_game",
            "q": "quiz_game",
            "quiz": "quiz_game",
        }

        user = await func.get_user(ctx.author.id)

        # No target -> toggle global boolean (legacy behavior)
        if not target:
            toggle = not user.get("reminder", False)
            await func.update_user(ctx.author.id, {"$set": {"reminder": toggle}})

            toggle_text = "On" if toggle else "Off"
            embed = discord.Embed(title=f"🔔 Reminder {toggle_text}", color=discord.Color.random())
            embed.description = f"Reminders have been turned {toggle_text}"
            await ctx.reply(embed=embed)
            return

        # Normalize and resolve target to a cooldown key
        key = target.lower()
        if key in ("all", "*", "a"):
            # treat as global toggle
            toggle = not user.get("reminder", False)
            await func.update_user(ctx.author.id, {"$set": {"reminder": toggle}})
            toggle_text = "On" if toggle else "Off"
            embed = discord.Embed(title=f"🔔 Reminder {toggle_text}", color=discord.Color.random())
            embed.description = f"Reminders have been turned {toggle_text}"
            await ctx.reply(embed=embed)
            return

        if key in alias_map:
            key = alias_map[key]
        else:
            # try prefix matching to the cooldown names
            matched = func.match_string(key, cooldown_keys)
            if matched:
                key = matched

        if key not in cooldown_keys:
            embed = discord.Embed(title="🔔 Reminder - Unknown target", color=discord.Color.red())
            embed.description = (
                "Unknown reminder target. Valid targets:\n"
                + ", ".join(cooldown_keys)
                + "\nYou can also use short flags like `d`, `r`, `mg`, or `q`."
            )
            await ctx.reply(embed=embed)
            return

        # Build base reminder state from current user setting
        current = user.get("reminder", False)

        if isinstance(current, bool):
            # if global boolean True -> start from all True, otherwise all False
            base = {k: current for k in cooldown_keys}
        else:
            # ensure we have entries for all keys
            base = {k: bool(current.get(k, False)) for k in cooldown_keys}

        # toggle the specific key
        base[key] = not base.get(key, False)

        # Save dict-based per-key reminder settings
        await func.update_user(ctx.author.id, {"$set": {"reminder": base}})

        toggle_text = "On" if base[key] else "Off"
        embed = discord.Embed(title=f"🔔 Reminder {key} {toggle_text}", color=discord.Color.random())
        embed.description = f"Reminder for **{key}** is now **{toggle_text}**"
        await ctx.reply(embed=embed)

    @commands.command(hidden=True)
    async def reset(self, ctx: commands.Context) -> None:
        """Reset jk"""
        if ctx.author.id in func.settings.ADMIN_IDS:
            await ctx.reply("**All game data has been wiped.**")

async def setup(bot: commands.Bot):
    await bot.add_cog(Settings(bot))