import discord
import asyncio
import time
import random
from typing import Optional, Dict, List
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

import functions as func
from iufi import CardPool, Card
from discord.ext import commands


# PvP implementation: Challenge -> both players submit 3-card teams (via modal) -> best-of-3 rounds
# Configurable via func.settings.PVP_SETTINGS if present, otherwise fallback defaults.


def get_pvp_settings():
    defaults = {
        "power_ranges": {
            "common": [1, 20],
            "rare": [10, 35],
            "epic": [25, 60],
            "legendary": [45, 100],
            "mystic": [70, 150],
            "celestial": [100, 250]
        },
        "challenge_timeout": 300,
        "round_delay": 4,
        "max_reroll_attempts": 20
    }
    return getattr(func.settings, "PVP_SETTINGS", {}) or defaults


class PvPMatch:
    def __init__(self, ctx: Optional[commands.Context], challenger: discord.Member, opponent: discord.Member, settings: dict):
        self.ctx = ctx
        self.challenger = challenger
        self.opponent = opponent
        self.started_at = time.time()
        self.settings = settings
        self.teams: Dict[int, List[Card]] = {}
        self.wins: Dict[int, int] = {challenger.id: 0, opponent.id: 0}
        self.message: Optional[discord.Message] = None
        self._lock = asyncio.Lock()

    def is_ready(self) -> bool:
        return (self.challenger.id in self.teams) and (self.opponent.id in self.teams)

    async def run(self):
        # resolve best of 3
        if not self.message:
            return

        embed = discord.Embed(title="PvP Match", color=discord.Color.blurple())
        embed.description = f"{self.challenger.mention} vs {self.opponent.mention}\nStarting match..."
        await self.message.edit(embed=embed, view=None)

        # Round by round
        for i in range(3):
            a_card = self.teams[self.challenger.id][i]
            b_card = self.teams[self.opponent.id][i]

            # compute power roll
            a_roll, b_roll = self._power_roll(a_card), self._power_roll(b_card)

            # ensure no perfect tie by rerolling limited times
            attempts = 0
            while a_roll == b_roll and attempts < self.settings.get("max_reroll_attempts", 20):
                a_roll, b_roll = self._power_roll(a_card), self._power_roll(b_card)
                attempts += 1

            # determine round winner
            if a_roll > b_roll:
                winner = self.challenger
                self.wins[self.challenger.id] += 1
                result_str = f"{self.challenger.mention} wins Round {i+1}! ({a_roll} vs {b_roll})"
            elif b_roll > a_roll:
                winner = self.opponent
                self.wins[self.opponent.id] += 1
                result_str = f"{self.opponent.mention} wins Round {i+1}! ({b_roll} vs {a_roll})"
            else:
                winner = None
                result_str = f"Round {i+1} is a tie after {attempts} rerolls. ({a_roll} vs {b_roll})"

            round_embed = discord.Embed(title=f"Round {i+1}", color=discord.Color.random())
            round_embed.add_field(name=f"{self.challenger.display_name}", value=f"{a_card.display_id} ({a_card._tier.capitalize()})\nPower: {a_roll}", inline=True)
            round_embed.add_field(name=f"{self.opponent.display_name}", value=f"{b_card.display_id} ({b_card._tier.capitalize()})\nPower: {b_roll}", inline=True)
            round_embed.set_footer(text=result_str)

            # Attempt to compose a single stitched image (left card vs right card with 'VS' text)
            try:
                a_img = await a_card.image(size_rate=0.28)
                b_img = await b_card.image(size_rate=0.28)
                if isinstance(a_img, list):
                    a_img = a_img[0]
                if isinstance(b_img, list):
                    b_img = b_img[0]

                if a_img.mode != 'RGBA':
                    a_img = a_img.convert('RGBA')
                if b_img.mode != 'RGBA':
                    b_img = b_img.convert('RGBA')

                padding = 12
                middle_w = max(int(a_img.width * 0.35), 80)
                out_w = a_img.width + b_img.width + middle_w + padding * 4
                out_h = max(a_img.height, b_img.height) + padding * 2

                out = Image.new('RGBA', (out_w, out_h), (0, 0, 0, 0))
                left_x = padding
                left_y = (out_h - a_img.height) // 2
                right_x = left_x + a_img.width + middle_w + padding * 2
                right_y = (out_h - b_img.height) // 2

                out.paste(a_img, (left_x, left_y), a_img)
                out.paste(b_img, (right_x, right_y), b_img)

                draw = ImageDraw.Draw(out)
                font_size = max(36, int(out_h * 0.20))
                try:
                    font = ImageFont.truetype("DejaVuSans.ttf", font_size)
                except Exception:
                    font = ImageFont.load_default()

                vs_text = "VS"
                bbox = draw.textbbox((0, 0), vs_text, font=font)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
                text_x = left_x + a_img.width + (middle_w // 2) + padding - (text_w // 2)
                text_y = (out_h - text_h) // 2

                # stroke/shadow then fill
                draw.text((text_x - 2, text_y - 2), vs_text, font=font, fill=(0, 0, 0, 255))
                draw.text((text_x + 2, text_y + 2), vs_text, font=font, fill=(0, 0, 0, 255))
                draw.text((text_x, text_y), vs_text, font=font, fill=(255, 255, 255, 255))

                bytes_io = BytesIO()
                out.save(bytes_io, format='WEBP')
                bytes_io.seek(0)

                fname = f"round_{i+1}.webp"
                file = discord.File(bytes_io, filename=fname)
                round_embed.set_image(url=f"attachment://{fname}")
                await self.message.channel.send(embed=round_embed, file=file)

            except Exception as e:
                # If composition failed, fall back to attaching both files individually (previous behavior)
                try:
                    func.logger.exception(f"Compose failed for round images, falling back to separate attachments: {e}")
                except Exception:
                    pass
                try:
                    a_bytes = await a_card.image_bytes()
                    b_bytes = await b_card.image_bytes()
                    fname_a = f"card_a_{i+1}.webp"
                    fname_b = f"card_b_{i+1}.webp"
                    file_a = discord.File(a_bytes, filename=fname_a)
                    file_b = discord.File(b_bytes, filename=fname_b)
                    round_embed.set_image(url=f"attachment://{fname_a}")
                    round_embed.set_thumbnail(url=f"attachment://{fname_b}")
                    await self.message.channel.send(embed=round_embed, files=[file_a, file_b])
                except Exception:
                    # last-resort: send text-only embed
                    try:
                        func.logger.exception(f"Failed to send fallback round images for match {self.challenger.id} vs {self.opponent.id} (round {i+1}): {e}")
                    except Exception:
                        pass
                    await self.message.channel.send(embed=round_embed)

            # small delay between rounds for dramatic reveal
            await asyncio.sleep(self.settings.get("round_delay", 4))

        # determine match winner
        if self.wins[self.challenger.id] > self.wins[self.opponent.id]:
            match_winner = self.challenger
        elif self.wins[self.opponent.id] > self.wins[self.challenger.id]:
            match_winner = self.opponent
        else:
            match_winner = None

        final_embed = discord.Embed(title="PvP Match Result", color=discord.Color.gold())
        if match_winner:
            final_embed.description = f"Winner: {match_winner.mention}\nScore: {self.wins[self.challenger.id]} - {self.wins[self.opponent.id]}"
        else:
            final_embed.description = f"Match ended in a draw.\nScore: {self.wins[self.challenger.id]} - {self.wins[self.opponent.id]}"

        await self.message.channel.send(embed=final_embed)

    def _power_roll(self, card: Card) -> int:
        # determine tier range from settings
        ranges = self.settings.get("power_ranges", {})
        tier = card._tier if hasattr(card, "_tier") else card.tier[1]
        rng = ranges.get(tier) or ranges.get(card.tier[1])
        if not rng:
            # fallback to a conservative default
            rng = [1, 100]
        lo, hi = int(rng[0]), int(rng[1])

        # If card has stars, it could slightly bias the roll. We'll add small star bonus.
        star_bonus = getattr(card, "stars", 0)
        # compute roll
        return random.randint(lo, hi) + star_bonus


class TeamModal(discord.ui.Modal):
    def __init__(self, match: PvPMatch, for_user_id: int):
        super().__init__(title="Submit your team (3 card IDs)")
        self.match = match
        self.for_user_id = for_user_id

        self.card1 = discord.ui.TextInput(label="Card 1 ID / Tag", placeholder="e.g. 123", required=True, max_length=64)
        self.card2 = discord.ui.TextInput(label="Card 2 ID / Tag", placeholder="e.g. 456", required=True, max_length=64)
        self.card3 = discord.ui.TextInput(label="Card 3 ID / Tag", placeholder="e.g. 789", required=True, max_length=64)

        self.add_item(self.card1)
        self.add_item(self.card2)
        self.add_item(self.card3)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # validate the submission
        user_id = interaction.user.id
        if user_id != self.for_user_id:
            return await interaction.response.send_message("This submission isn't for you.", ephemeral=True)

        entries = [self.card1.value.strip(), self.card2.value.strip(), self.card3.value.strip()]
        # check uniqueness
        if len(set(entries)) != 3:
            return await interaction.response.send_message("Cards must be unique.", ephemeral=True)

        # resolve cards
        resolved = CardPool.search_valid_cards(entries)
        if len(resolved) != 3:
            return await interaction.response.send_message("One or more card IDs/tags are invalid.", ephemeral=True)

        # ownership check
        user_doc = await func.get_user(user_id)
        owned_ids = set(str(x).lstrip("0") for x in user_doc.get("cards", []))
        for c in resolved:
            if str(c.id) not in owned_ids and (not c.owner_id or c.owner_id != user_id):
                return await interaction.response.send_message("You must own all the cards you submit.", ephemeral=True)

        # store the team
        self.match.teams[user_id] = resolved

        # update the match message to show submission status
        try:
            if self.match.message:
                embed = discord.Embed(title="Team Submission", color=discord.Color.blue())
                challenger_status = "✅ Submitted" if self.match.challenger.id in self.match.teams else "⏳ Waiting"
                opponent_status = "✅ Submitted" if self.match.opponent.id in self.match.teams else "⏳ Waiting"
                embed.description = f"{self.match.challenger.mention}: {challenger_status}\n{self.match.opponent.mention}: {opponent_status}"
                await self.match.message.edit(embed=embed, view=self.match_message_view())
        except Exception:
            pass

        await interaction.response.send_message("Team submitted.", ephemeral=True)

        # if both ready, run match
        if self.match.is_ready():
            # run match in background
            asyncio.create_task(self.match.run())

    def match_message_view(self) -> discord.ui.View:
        # keep simple view showing submit buttons for remaining players
        view = SubmissionView(self.match)
        return view


class SubmitButton(discord.ui.Button):
    def __init__(self, match: PvPMatch, target_user_id: int, label: str):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.match = match
        self.target_user_id = target_user_id

    async def callback(self, interaction: discord.Interaction):
        # only allow the intended user to open their modal
        if interaction.user.id != self.target_user_id:
            return await interaction.response.send_message("This button isn't for you.", ephemeral=True)

        # open modal for this user
        modal = TeamModal(self.match, self.target_user_id)
        await interaction.response.send_modal(modal)


class SubmissionView(discord.ui.View):
    def __init__(self, match: PvPMatch, timeout: float = None):
        super().__init__(timeout=timeout)
        self.match = match
        # add two submit buttons targeted to each player
        self.add_item(SubmitButton(match, match.challenger.id, f"Submit: {match.challenger.display_name}"))
        self.add_item(SubmitButton(match, match.opponent.id, f"Submit: {match.opponent.display_name}"))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Only allow the challenger or opponent to interact with submission view
        return interaction.user.id in (self.match.challenger.id, self.match.opponent.id)

    async def on_timeout(self) -> None:
        try:
            if self.match.message:
                await self.match.message.edit(content="Submission period expired.", view=None)
        except Exception:
            pass


class ChallengeView(discord.ui.View):
    def __init__(self, ctx: commands.Context, challenger: discord.Member, opponent: Optional[discord.Member] = None, timeout: float = None):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.challenger = challenger
        self.opponent = opponent
        self.settings = get_pvp_settings()
        self.match: Optional[PvPMatch] = None
        self.message: Optional[discord.Message] = None

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check acceptance rules
        if self.opponent and interaction.user.id != self.opponent.id:
            return await interaction.response.send_message("This challenge is not for you.", ephemeral=True)

        # create PvPMatch
        opponent = interaction.user
        challenger = self.challenger
        self.match = PvPMatch(self.ctx, challenger, opponent, self.settings)

        # send submission message with view containing targeted submit buttons
        embed = discord.Embed(title="PvP Match - Team Submission", color=discord.Color.blurple())
        embed.description = f"{challenger.mention} vs {opponent.mention}\nBoth players, please submit your teams (3 unique cards) by clicking your Submit button below. You must own the cards you submit."

        # replace buttons with submission view
        view = SubmissionView(self.match, timeout=self.settings.get("challenge_timeout", 300))

        try:
            # edit original message to show the submission UI
            await self.message.edit(content=None, embed=embed, view=view)
            self.match.message = self.message
            await interaction.response.send_message("Match accepted. Submit your team using the buttons in the match message.", ephemeral=True)
        except Exception:
            # fallback: send a new message
            sent = await self.ctx.send(embed=embed, view=view)
            self.match.message = sent
            await interaction.response.send_message("Match accepted. Submit your team using the buttons in the match message.", ephemeral=True)

        # stop this view from accepting further accepts
        for child in self.children:
            child.disabled = True
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.challenger.id:
            return await interaction.response.send_message("Only the challenger can cancel this challenge.", ephemeral=True)
        for child in self.children:
            child.disabled = True
        try:
            await self.message.edit(content="Challenge canceled.", view=self)
        except Exception:
            pass
        await interaction.response.send_message("Challenge canceled.", ephemeral=True)
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Allow only challenger or the intended opponent (if set) to interact with initial challenge view
        if interaction.user.id == self.challenger.id:
            return True
        if self.opponent and interaction.user.id == self.opponent.id:
            return True
        if not self.opponent:
            # open challenge — anyone can accept except the challenger
            return interaction.user.id != self.challenger.id
        return False

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        try:
            if self.message:
                await self.message.edit(content="Challenge expired.", view=self)
        except Exception:
            pass
        self.stop()
