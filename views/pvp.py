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

# Prefer a bundled font inside the repo (fonts/DejaVuSans.ttf). If it's missing, try common system fonts.
FONT_CANDIDATES = [
    'fonts/DejaVuSans.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/Library/Fonts/Arial.ttf',
    '/System/Library/Fonts/Supplemental/Arial.ttf',
]

def load_truetype(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a TrueType font from the bundled fonts/ folder first, then fall back to common system fonts.

    This prefers a local, committed TTF so rendering is consistent across hosts. If no TTF is found,
    it falls back to PIL's default bitmap font (less ideal).
    """
    for candidate in FONT_CANDIDATES:
        try:
            f = ImageFont.truetype(candidate, size)
            # Log which font path was used for easier debugging
            try:
                func.logger.info(f"Loaded font: {candidate} (size={size})")
            except Exception:
                pass
            return f
        except Exception:
            continue

    try:
        func.logger.warning("No TrueType font found in repo or system paths; falling back to bitmap font.")
    except Exception:
        pass
    return ImageFont.load_default()


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
        "post_round_delay": 3,
        "max_reroll_attempts": 20
    }
    return getattr(func.settings, "PVP_SETTINGS", {}) or defaults


async def compose_vs_image(a_card: Card, b_card: Card, *, highlight: Optional[str] = None, size_rate: float = 0.28) -> BytesIO:
    """Create a stitched image: left card vs right card. If highlight is 'left' or 'right', draw a border around the winner."""
    # Load images (may be lists for GIFs)
    a_img = await a_card.image(size_rate=size_rate)
    b_img = await b_card.image(size_rate=size_rate)
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

    # draw highlight border & a bottom ribbon over only the winning card if needed
    if highlight in ('left', 'right'):
        # determine box for winner (card coordinates)
        if highlight == 'left':
            bx, by, bw, bh = left_x, left_y, a_img.width, a_img.height
        else:
            bx, by, bw, bh = right_x, right_y, b_img.width, b_img.height

        # soft glowing border around the winner card
        glow_color = (34, 197, 94, 255)  # green-ish
        for i in range(6, 0, -2):
            rect = [bx - i, by - i, bx + bw + i, by + bh + i]
            draw.rounded_rectangle(rect, radius=12 + i, outline=(glow_color[0], glow_color[1], glow_color[2], int(30 + (i * 30 / 6))))

        # draw a ribbon only across the bottom of the winner card (with slight horizontal padding)
        ribbon_h = max(int(bh * 0.14), 20)
        # position ribbon so it sits at the bottom of the card; allow small horizontal extension
        hor_pad = max(int(bw * 0.06), 8)
        rx = max(0, bx - hor_pad)
        rw = min(out_w - rx, bw + hor_pad * 2)
        ry = by + bh - ribbon_h
        ribbon_color = (16, 185, 129, 255)  # green

        # rounded ribbon rectangle
        radius = max(6, int(ribbon_h * 0.25))
        draw.rounded_rectangle([rx, ry, rx + rw, ry + ribbon_h], radius=radius, fill=ribbon_color)

        # draw WINNER text centered in that ribbon using high-res rendering to avoid pixelation
        text = "WINNER"
        # target font size (relative to ribbon height)
        base_font_size = max(14, int(ribbon_h * 0.6))
        scale = 4  # render at 4x and downscale for smooth edges
        try:
            font_hi = load_truetype(base_font_size * scale)
        except Exception:
            font_hi = ImageFont.load_default()

        # create temporary high-res canvas for text
        tmp_w = max(1, int(rw * scale))
        tmp_h = max(1, int(ribbon_h * scale))
        tmp = Image.new('RGBA', (tmp_w, tmp_h), (0, 0, 0, 0))
        td = ImageDraw.Draw(tmp)

        # measure text in high-res
        tb = td.textbbox((0, 0), text, font=font_hi)
        text_w_hi = tb[2] - tb[0]
        text_h_hi = tb[3] - tb[1]
        tx_hi = (tmp_w - text_w_hi) // 2
        ty_hi = (tmp_h - text_h_hi) // 2

        # draw shadow slightly offset (high-res) then white text
        shadow_color = (0, 0, 0, 200)
        td.text((tx_hi - int(2 * scale), ty_hi - int(2 * scale)), text, font=font_hi, fill=shadow_color)
        td.text((tx_hi + int(2 * scale), ty_hi + int(2 * scale)), text, font=font_hi, fill=shadow_color)
        td.text((tx_hi, ty_hi), text, font=font_hi, fill=(255, 255, 255, 255))

        # downscale to ribbon size using the best available resampling filter and paste with alpha
        resample_filter = getattr(Image, 'LANCZOS', None)
        if resample_filter is None:
            resampling = getattr(Image, 'Resampling', None)
            if resampling and hasattr(resampling, 'LANCZOS'):
                resample_filter = resampling.LANCZOS
            else:
                # try BICUBIC then fallback to NEAREST
                resample_filter = getattr(Image, 'BICUBIC', None)
                if resample_filter is None and resampling and hasattr(resampling, 'BICUBIC'):
                    resample_filter = resampling.BICUBIC
                if resample_filter is None:
                    resample_filter = getattr(Image, 'NEAREST', 0)

        small = tmp.resize((int(tmp_w / scale), int(tmp_h / scale)), resample=resample_filter)
        out.paste(small, (int(rx), int(ry)), small)

    # Draw VS in middle lightly for the preview too
    # Prefer bundled TrueType via load_truetype; fallback to bitmap font if unavailable
    try:
        font = load_truetype(max(28, int(out_h * 0.12)))
    except Exception:
        font = ImageFont.load_default()
    vs_text = "VS"
    vb = draw.textbbox((0, 0), vs_text, font=font)
    v_w = vb[2] - vb[0]
    v_h = vb[3] - vb[1]
    vx = left_x + a_img.width + (middle_w // 2) + padding - (v_w // 2)
    vy = (out_h - v_h) // 2
    draw.text((vx - 1, vy - 1), vs_text, font=font, fill=(0, 0, 0, 255))
    draw.text((vx + 1, vy + 1), vs_text, font=font, fill=(0, 0, 0, 255))
    draw.text((vx, vy), vs_text, font=font, fill=(255, 255, 255, 255))

    bytes_io = BytesIO()
    out.save(bytes_io, format='WEBP')
    bytes_io.seek(0)
    return bytes_io


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

        # Round by round: show power ranges first, then reveal rolls and winner
        for i in range(3):
            a_card = self.teams[self.challenger.id][i]
            b_card = self.teams[self.opponent.id][i]

            # determine configured ranges for each card's tier
            ranges = self.settings.get("power_ranges", {})
            a_tier = a_card._tier if hasattr(a_card, "_tier") else a_card.tier[1]
            b_tier = b_card._tier if hasattr(b_card, "_tier") else b_card.tier[1]
            a_rng = ranges.get(a_tier, [1, 100])
            b_rng = ranges.get(b_tier, [1, 100])

            # Send range embed (secret: we show range but not rolled values)
            range_embed = discord.Embed(title=f"Round {i+1} — Power Ranges", color=discord.Color.random())
            range_embed.add_field(name=f"{self.challenger.display_name}", value=f"🎲 {a_card._tier.capitalize()}: {int(a_rng[0])} - {int(a_rng[1])}", inline=True)
            range_embed.add_field(name=f"{self.opponent.display_name}", value=f"🎲 {b_card._tier.capitalize()}: {int(b_rng[0])} - {int(b_rng[1])}", inline=True)
            range_embed.set_footer(text="A secret roll will be revealed shortly...")

            # Try to show a stitched preview image without highlight
            try:
                range_img = await compose_vs_image(a_card, b_card, highlight=None, size_rate=0.28)
                fname_range = f"round_{i+1}_range.webp"
                file_range = discord.File(range_img, filename=fname_range)
                range_msg = await self.message.channel.send(embed=range_embed, file=file_range)
            except Exception as e:
                try:
                    func.logger.exception(f"Failed to compose/send range image for match {self.challenger.id} vs {self.opponent.id} (round {i+1}): {e}")
                except Exception:
                    pass
                range_msg = await self.message.channel.send(embed=range_embed)

            # wait to reveal the roll
            await asyncio.sleep(self.settings.get("round_delay", 4))

            # perform the secret rolls now
            a_roll = random.randint(int(a_rng[0]), int(a_rng[1])) + getattr(a_card, "stars", 0)
            b_roll = random.randint(int(b_rng[0]), int(b_rng[1])) + getattr(b_card, "stars", 0)

            # resolve ties with rerolls
            attempts = 0
            while a_roll == b_roll and attempts < self.settings.get("max_reroll_attempts", 20):
                a_roll = random.randint(int(a_rng[0]), int(a_rng[1])) + getattr(a_card, "stars", 0)
                b_roll = random.randint(int(b_rng[0]), int(b_rng[1])) + getattr(b_card, "stars", 0)
                attempts += 1

            # determine round winner and highlight side
            if a_roll > b_roll:
                winner = self.challenger
                self.wins[self.challenger.id] += 1
                result_str = f"{self.challenger.mention} wins Round {i+1}! ({a_roll} vs {b_roll})"
                highlight = "left"
            elif b_roll > a_roll:
                winner = self.opponent
                self.wins[self.opponent.id] += 1
                result_str = f"{self.opponent.mention} wins Round {i+1}! ({b_roll} vs {a_roll})"
                highlight = "right"
            else:
                winner = None
                result_str = f"Round {i+1} is a tie after {attempts} rerolls. ({a_roll} vs {b_roll})"
                highlight = None

            # Build the reveal embed showing rolled powers and winner
            reveal_embed = discord.Embed(title=f"Round {i+1} — Result", color=discord.Color.random())
            reveal_embed.add_field(name=f"{self.challenger.display_name}", value=f"🎲 {a_card._tier.capitalize()}: {int(a_rng[0])}-{int(a_rng[1])}\n🎲 Roll: {a_roll}", inline=True)
            reveal_embed.add_field(name=f"{self.opponent.display_name}", value=f"🎲 {b_card._tier.capitalize()}: {int(b_rng[0])}-{int(b_rng[1])}\n🎲 Roll: {b_roll}", inline=True)
            reveal_embed.set_footer(text=result_str)

            # Compose reveal image with highlight and send; then remove the range message
            try:
                reveal_img = await compose_vs_image(a_card, b_card, highlight=highlight, size_rate=0.28)
                fname_reveal = f"round_{i+1}_reveal.webp"
                file_reveal = discord.File(reveal_img, filename=fname_reveal)
                await self.message.channel.send(embed=reveal_embed, file=file_reveal)
            except Exception as e:
                try:
                    func.logger.exception(f"Compose failed for reveal images, falling back to separate attachments: {e}")
                except Exception:
                    pass
                try:
                    a_bytes = await a_card.image_bytes()
                    b_bytes = await b_card.image_bytes()
                    fname_a = f"card_a_{i+1}.webp"
                    fname_b = f"card_b_{i+1}.webp"
                    file_a = discord.File(a_bytes, filename=fname_a)
                    file_b = discord.File(b_bytes, filename=fname_b)
                    reveal_embed.set_image(url=f"attachment://{fname_a}")
                    reveal_embed.set_thumbnail(url=f"attachment://{fname_b}")
                    await self.message.channel.send(embed=reveal_embed, files=[file_a, file_b])
                except Exception:
                    try:
                        func.logger.exception(f"Failed to send fallback reveal images for match {self.challenger.id} vs {self.opponent.id} (round {i+1}): {e}")
                    except Exception:
                        pass
                    await self.message.channel.send(embed=reveal_embed)

            # try to delete the earlier range message to visually replace it with the reveal
            try:
                await range_msg.delete()
            except Exception:
                pass

            # pause briefly after reveal
            await asyncio.sleep(self.settings.get("post_round_delay", 3))

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
