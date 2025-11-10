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


# RPS faction helpers
# Group rarities into three factions for a rock-paper-scissors style bonus:
#  A (Low): Common, Rare
#  B (Mid): Epic, Legendary
#  C (High): Mystic, Celestial
# A beats B, B beats C, C beats A -> winner gets +25% power bonus
RPS_FACTIONS = {
    'A': ('common', 'rare'),
    'B': ('epic', 'legendary'),
    'C': ('mystic', 'celestial')
}


def faction_for_tier(tier: str) -> Optional[str]:
    if not tier:
        return None
    t = tier.lower()
    for f, tiers in RPS_FACTIONS.items():
        if t in tiers:
            return f
    return None


def rps_bonus_pct(attacker_tier: str, defender_tier: str) -> float:
    """Return the RPS bonus percentage (0.25 for +25% when attacker beats defender, else 0.0)."""
    a = faction_for_tier(attacker_tier)
    b = faction_for_tier(defender_tier)
    if a is None or b is None:
        return 0.0
    # A beats B, B beats C, C beats A
    if (a == 'A' and b == 'B') or (a == 'B' and b == 'C') or (a == 'C' and b == 'A'):
        return 0.25
    return 0.0


# Small helper to produce a human-friendly label for a member when mentions aren't desired
def player_label(member: discord.Member | str) -> str:
    try:
        if isinstance(member, discord.Member):
            return getattr(member, 'display_name', str(member))
    except Exception:
        pass
    return str(member)


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


async def compose_three_image(cards: list[Card], *, size_rate: float = 0.28, use_cover: bool = False) -> BytesIO:
    """Stitch three images horizontally and return a BytesIO WEBP file.

    If use_cover is True, use images from the cover folder (level1.webp..level3.webp)
    rather than the actual card images. This is used to hide the real cards during reward selection.
    """
    import os

    imgs = []
    if use_cover:
        # preferred cover filenames in order
        cover_dir = os.path.join(func.ROOT_DIR, 'cover')
        preferred = ['level1.webp', 'level2.webp', 'level3.webp']
        available_pref = [os.path.join(cover_dir, n) for n in preferred if os.path.exists(os.path.join(cover_dir, n))]

        if available_pref:
            # Use the preferred set (or subset) and shuffle to randomize positions
            covers = available_pref[:]
            random.shuffle(covers)
            # If fewer covers than cards, repeat the list
            while len(covers) < len(cards):
                covers.extend(available_pref)
            covers = covers[:len(cards)]
        else:
            # fallback: any webp in the cover folder
            cover_paths = [os.path.join(func.ROOT_DIR, 'cover', f) for f in os.listdir(os.path.join(func.ROOT_DIR, 'cover')) if f.lower().endswith('.webp')]
            if not cover_paths:
                raise RuntimeError('No cover images found in cover/ folder')
            covers = random.sample(cover_paths, k=min(len(cover_paths), len(cards)))
            while len(covers) < len(cards):
                covers.append(random.choice(cover_paths))

        # Load the cover images in the order of covers list
        for path in covers:
            try:
                with Image.open(path) as im:
                    img = im.convert('RGBA')
                    target_size = (int(img.width * size_rate), int(img.height * size_rate))
                    img = img.resize(target_size, Image.LANCZOS)
                    imgs.append(img)
            except Exception:
                continue
    else:
        for c in cards:
            try:
                img = await c.image(size_rate=size_rate)
                if isinstance(img, list):
                    img = img[0]
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                imgs.append(img)
            except Exception:
                # fallback to the first card's image if individual fails
                try:
                    tmp = await CardPool.get_card(cards[0].id).image(size_rate=size_rate) if cards else None
                    if tmp:
                        if isinstance(tmp, list):
                            tmp = tmp[0]
                        imgs.append(tmp)
                except Exception:
                    continue

    if not imgs:
        raise RuntimeError("No images available to compose three-image")

    # If fewer than requested (shouldn't normally happen), duplicate last to fill the row
    while len(imgs) < len(cards):
        imgs.append(imgs[-1])

    padding = 10
    widths = [im.width for im in imgs]
    heights = [im.height for im in imgs]
    total_w = sum(widths) + padding * (len(imgs) - 1)
    max_h = max(heights)

    out = Image.new('RGBA', (total_w, max_h), (0, 0, 0, 0))
    x = 0
    for im in imgs:
        y = (max_h - im.height) // 2
        out.paste(im, (x, y), im)
        x += im.width + padding

    bio = BytesIO()
    out.save(bio, format='WEBP')
    bio.seek(0)
    return bio


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
        embed.description = f"{player_label(self.challenger)} vs {player_label(self.opponent)}\nStarting match..."
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

            # Determine RPS bonus percentages for preview (attacker perspective)
            a_bonus_pct = rps_bonus_pct(a_tier, b_tier)
            b_bonus_pct = rps_bonus_pct(b_tier, a_tier)

            # Send range embed (secret: we show range but not rolled values)
            range_embed = discord.Embed(title=f"Round {i+1} — Power Ranges", color=discord.Color.random())
            a_field = f"🎲 {a_card._tier.capitalize()}: {int(a_rng[0])} - {int(a_rng[1])}"
            if a_bonus_pct > 0:
                a_field += f"\n🔺 +{int(a_bonus_pct*100)}% (RPS bonus)"
            b_field = f"🎲 {b_card._tier.capitalize()}: {int(b_rng[0])} - {int(b_rng[1])}"
            if b_bonus_pct > 0:
                b_field += f"\n🔺 +{int(b_bonus_pct*100)}% (RPS bonus)"

            range_embed.add_field(name=f"{self.challenger.display_name}", value=a_field, inline=True)
            range_embed.add_field(name=f"{self.opponent.display_name}", value=b_field, inline=True)
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
            # We'll compute raw roll, include stars, then apply RPS bonus to that subtotal.
            a_raw = random.randint(int(a_rng[0]), int(a_rng[1]))
            b_raw = random.randint(int(b_rng[0]), int(b_rng[1]))
            a_stars = getattr(a_card, "stars", 0)
            b_stars = getattr(b_card, "stars", 0)

            a_base = a_raw + a_stars
            b_base = b_raw + b_stars

            a_bonus_amt = int(a_base * a_bonus_pct)
            b_bonus_amt = int(b_base * b_bonus_pct)

            a_total = a_base + a_bonus_amt
            b_total = b_base + b_bonus_amt

            # resolve ties with rerolls (reroll raw values and recompute totals)
            attempts = 0
            while a_total == b_total and attempts < self.settings.get("max_reroll_attempts", 20):
                a_raw = random.randint(int(a_rng[0]), int(a_rng[1]))
                b_raw = random.randint(int(b_rng[0]), int(b_rng[1]))
                a_base = a_raw + a_stars
                b_base = b_raw + b_stars
                a_bonus_amt = int(a_base * a_bonus_pct)
                b_bonus_amt = int(b_base * b_bonus_pct)
                a_total = a_base + a_bonus_amt
                b_total = b_base + b_bonus_amt
                attempts += 1

            # determine round winner and highlight side
            if a_total > b_total:
                winner = self.challenger
                self.wins[self.challenger.id] += 1
                result_str = f"{player_label(self.challenger)} wins Round {i+1}! ({a_total} vs {b_total})"
                highlight = "left"
            elif b_total > a_total:
                winner = self.opponent
                self.wins[self.opponent.id] += 1
                result_str = f"{player_label(self.opponent)} wins Round {i+1}! ({b_total} vs {a_total})"
                highlight = "right"
            else:
                winner = None
                result_str = f"Round {i+1} is a tie after {attempts} rerolls. ({a_total} vs {b_total})"
                highlight = None

            # Build the reveal embed showing rolled powers and winner
            reveal_embed = discord.Embed(title=f"Round {i+1} — Result", color=discord.Color.random())

            # Helper to build the value string with breakdown (returns list of lines)
            def build_breakdown(tier_name, rng, raw, stars, bonus_amt, bonus_pct):
                lines = []
                lines.append(f"🎲 {tier_name.capitalize()}: {int(rng[0])}-{int(rng[1])}")
                lines.append(f"🎲 Roll: {raw}")
                if stars:
                    lines.append(f"⭐ Stars: {stars}")
                rolled = (raw + (stars or 0))
                # Show Bonus line only when > 0; Total is basic when no bonus
                if bonus_amt > 0:
                    lines.append(f"➕ Bonus: {bonus_amt} (+{int(bonus_pct*100)}%)")
                    lines.append(f"🧮 Total: { (rolled + bonus_amt) } ({rolled} + {bonus_amt} power)")
                else:
                    lines.append(f"🧮 Total: { rolled }")
                return lines

            # Build breakdowns for both players
            a_lines = build_breakdown(a_card._tier, a_rng, a_raw, a_stars, a_bonus_amt, a_bonus_pct)
            b_lines = build_breakdown(b_card._tier, b_rng, b_raw, b_stars, b_bonus_amt, b_bonus_pct)

            # If one side has a Bonus line and the other doesn't, insert an explicit zero-bonus line into the other
            a_has_bonus = any(l.startswith('➕ Bonus') for l in a_lines)
            b_has_bonus = any(l.startswith('➕ Bonus') for l in b_lines)
            if a_has_bonus and not b_has_bonus:
                # insert zero bonus before the total and replace the Total line with breakdown form
                b_lines.insert(-1, f"➕ Bonus: 0 (+0%)")
                b_rolled = b_raw + b_stars
                b_lines[-1] = f"🧮 Total: {b_rolled} ({b_rolled} + 0 power)"
            elif b_has_bonus and not a_has_bonus:
                a_lines.insert(-1, f"➕ Bonus: 0 (+0%)")
                a_rolled = a_raw + a_stars
                a_lines[-1] = f"🧮 Total: {a_rolled} ({a_rolled} + 0 power)"

            # Ensure both sides have the same number of lines by padding with invisible lines if needed
            max_len = max(len(a_lines), len(b_lines))
            pad_token = '\u200b'  # zero-width space — invisible but keeps vertical spacing
            if len(a_lines) < max_len:
                a_lines += [pad_token] * (max_len - len(a_lines))
            if len(b_lines) < max_len:
                b_lines += [pad_token] * (max_len - len(b_lines))

            reveal_embed.add_field(name=f"{self.challenger.display_name}", value="\n".join(a_lines), inline=True)
            reveal_embed.add_field(name=f"{self.opponent.display_name}", value="\n".join(b_lines), inline=True)
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

        # === REWARD FLOW: offer three hidden cards from the loser for the winner to pick one ===
        if not func.settings.PVP_REWARDS_ENABLED :
            return 

        try:
            if match_winner is None:
                return

            loser = self.challenger if match_winner.id == self.opponent.id else self.opponent

            # fetch latest user docs
            loser_doc = await func.get_user(loser.id)
            winner_doc = await func.get_user(match_winner.id)

            # get candidate cards (ensure ownership still matches)
            candidate_ids = [c for c in loser_doc.get("cards", []) if (card_obj := CardPool.get_card(str(c))) and card_obj.owner_id == loser.id]

            if not candidate_ids:
                await self.message.channel.send(f"No available cards to be rewarded from {player_label(loser)}.")
                return

            # pick up to three random distinct candidate ids
            sample_size = min(3, len(candidate_ids))
            reward_ids = random.sample(candidate_ids, k=sample_size)
            reward_cards = [CardPool.get_card(str(cid)) for cid in reward_ids]

            # shuffle the offered cards so positions are random
            random.shuffle(reward_cards)

            # Define Reward UI classes
            class RewardButton(discord.ui.Button):
                def __init__(self, card: Card, *, idx: int):
                    # Do NOT show rarity emoji here; keep images hidden from fields and only show stitched cover
                    super().__init__(label=f"Pick {idx}", style=discord.ButtonStyle.green)
                    self.card = card
                    self.idx = idx

                async def callback(self, interaction: discord.Interaction):
                    # Only winner may pick
                    if interaction.user.id != match_winner.id:
                        return await interaction.response.send_message("Only the match winner can pick a reward.", ephemeral=True)

                    async with self.view._lock:
                        # re-check availability
                        if self.card.owner_id != loser.id:
                            return await interaction.response.send_message("This card is no longer available.", ephemeral=True)

                        # check winner inventory limit
                        _winner = await func.get_user(match_winner.id)
                        if (len(_winner.get("cards", [])) + 1) > func.get_user_card_limit(_winner):
                            return await interaction.response.send_message("Your inventory is full. Please free some space before claiming the reward.", ephemeral=True)

                        # perform transfer: in-memory
                        self.card.change_owner(match_winner.id)
                        last_trade_time = time.time()
                        self.card.last_trade_time = last_trade_time

                        # DB updates: remove from loser, add to winner, update card owner
                        await func.update_user(loser.id, {"$pull": {"cards": self.card.id}})

                        winner_query = func.update_quest_progress(_winner, ["COLLECT_ANY_CARD", f"COLLECT_{self.card._tier.upper()}_CARD"], query={
                            "$push": {"cards": self.card.id},
                            "$inc": {"exp": 10}
                        })
                        await func.update_user(match_winner.id, winner_query)

                        await func.update_card(self.card.id, {"$set": {"owner_id": match_winner.id, "last_trade_time": last_trade_time}})

                        func.logger.info(f"PvP reward: User {match_winner.name}({match_winner.id}) took card {self.card.id} from {loser.name}({loser.id})")

                        # disable view and update UI to show selection
                        for ch in self.view.children:
                            ch.disabled = True
                        self.view.stop()

                        # send confirmation and reveal the card image
                        try:
                            image_bytes = await self.card.image_bytes()
                            file = discord.File(image_bytes, filename=f"reward_{self.card.id}.webp")
                            embed = discord.Embed(title="🏆 PvP Reward", color=discord.Color.gold())
                            embed.description = f"{player_label(match_winner)} picked {self.card.display_id} from {player_label(loser)}"
                            await interaction.response.send_message(embed=embed, file=file)
                        except Exception:
                            await interaction.response.send_message(f"{player_label(match_winner)} picked {self.card.display_id} from {player_label(loser)}")

            class RewardView(discord.ui.View):
                def __init__(self, cards: list[Card], timeout: float | None = 60):
                    super().__init__(timeout=timeout)
                    self._lock = asyncio.Lock()
                    for idx, c in enumerate(cards, start=1):
                        self.add_item(RewardButton(c, idx=idx))

                async def on_timeout(self) -> None:
                    for child in self.children:
                        child.disabled = True
                    try:
                        await reward_message.edit(content="*🕟 Reward selection expired.*", view=self)
                    except Exception:
                        pass
                    self.stop()

            # Build and send reward embed with a stitched image of the three cover images
            reward_embed = discord.Embed(title="PvP Reward — Choose one card", color=discord.Color.green())
            reward_embed.description = f"{player_label(match_winner)}, pick one card taken from {player_label(loser)}. Click the button under the image to pick."

            try:
                # Use cover images to hide the real cards (level1.webp / level2.webp / level3.webp)
                stitched = await compose_three_image(reward_cards, size_rate=0.28, use_cover=True)
                file = discord.File(stitched, filename="pvp_reward_three.webp")
                reward_embed.set_image(url=f"attachment://pvp_reward_three.webp")
                view = RewardView(reward_cards, timeout=60)
                reward_message = await self.message.channel.send(embed=reward_embed, file=file, view=view)
            except Exception as e:
                # fallback to non-image embed listing (shouldn't normally happen)
                try:
                    func.logger.exception(f"Failed to compose three-card reward image: {e}")
                except Exception:
                    pass
                view = RewardView(reward_cards, timeout=60)
                reward_message = await self.message.channel.send(embed=reward_embed, view=view)

        except Exception as e:
            try:
                func.logger.exception(f"Error in PvP reward flow: {e}")
            except Exception:
                pass


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
                embed.description = f"{player_label(self.match.challenger)}: {challenger_status}\n{player_label(self.match.opponent)}: {opponent_status}"
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
        embed.description = f"{player_label(challenger)} vs {player_label(opponent)}\nBoth players, please submit your teams (3 unique cards) by clicking your Submit button below. You must own the cards you submit."

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


