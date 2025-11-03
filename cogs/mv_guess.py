import discord, time, asyncio, io, os, random
import functions as func
from discord.ext import commands
from PIL import Image, ImageFilter

# new imports for youtube screenshot
import yt_dlp
import subprocess
import tempfile
import shutil

class MVGuess(commands.Cog):
    """Cog implementing the "Guess the IU MV" game.

    Behaviour:
    - Picks a random entry from `mv_videos.json`.
    - Captures a random frame from the video's YouTube URL using yt_dlp + ffmpeg, blurs it and posts it.
    - Waits for user messages in the channel for `timeout` seconds and accepts partial/fuzzy matches.
    - Reveals the image and awards points on correct guess, or reveals after timeout.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # channel ids where a game is currently running (prevents concurrent games in same channel)
        self._running_channels: set[int] = set()

    async def _screenshot_from_youtube(self, url: str, blur_radius: int = 12) -> tuple[io.BytesIO, io.BytesIO]:
        """Download a short segment of the YouTube video and extract a random frame.

        Returns a tuple (blurred_png_bytesio, original_png_bytesio).
        Raises RuntimeError on failure with a helpful message.
        """
        def _sync_work(u: str, br: int) -> tuple[bytes, bytes]:
            # create temp files
            tmp_dir = tempfile.mkdtemp(prefix="mv_guess_")
            try:
                temp_video = os.path.join(tmp_dir, "temp_video.%(ext)s")

                # Step 1: get info to determine duration
                ydl_opts_info = {"quiet": True, "skip_download": True, "noplaylist": True}
                with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                    info = ydl.extract_info(u, download=False)
                    duration = info.get("duration")

                # Determine a random short segment (start .. start + 2s) to download
                if not duration or duration <= 4:
                    # Very short video: download the whole video
                    seg_start = 0.0
                    seg_end = float(duration) if duration else 2.0
                else:
                    # pick a random start at least 2s in and at least 2s before end
                    low = 2.0
                    high = max(low, duration - 2.0)
                    seg_start = float(random.uniform(low, high))
                    seg_end = seg_start + 2.0

                # midpoint inside the downloaded segment (used for screenshot)
                seg_mid = (seg_start + seg_end) / 2.0

                # Step 2: download only the short section using ffmpeg external downloader
                out_video_template = os.path.join(tmp_dir, "temp_video.%(ext)s")
                # Use ffmpeg as external downloader to seek and limit duration (much faster)
                ydl_opts_download = {
                    "quiet": True,
                    "noplaylist": True,
                    "outtmpl": out_video_template,
                    "format": "bestvideo[ext=mp4]/bestvideo",  # video only, no audio
                    "external_downloader": "ffmpeg",
                    "external_downloader_args": {
                        "ffmpeg_i": ["-ss", str(seg_start), "-t", "2"]  # seek to start, download 2 seconds
                    },
                }
                with yt_dlp.YoutubeDL(ydl_opts_download) as ydl:
                    ydl.download([u])

                # Find the downloaded file (actual extension may vary)
                downloaded_files = [f for f in os.listdir(tmp_dir) if f.startswith("temp_video.") and not f.endswith(".part")]
                if not downloaded_files:
                    raise RuntimeError("Failed to download video segment from YouTube")

                out_video = os.path.join(tmp_dir, downloaded_files[0])

                # --- NEW: copy the downloaded video to a persistent folder for inspection ---
                try:
                    save_dir = os.path.join(func.ROOT_DIR, "mv_guess_downloads")
                    os.makedirs(save_dir, exist_ok=True)
                    video_id = info.get("id") if isinstance(info, dict) else None
                    base_name = downloaded_files[0]
                    _, ext = os.path.splitext(base_name)
                    timestamp = int(time.time())
                    safe_vid = (video_id or "video").replace("/", "_")
                    saved_video_name = f"{safe_vid}_{timestamp}{ext}"
                    saved_video_path = os.path.join(save_dir, saved_video_name)
                    shutil.copy(out_video, saved_video_path)
                    # optional: small log for debugging
                    # print(f"Saved downloaded video to {saved_video_path}")
                except Exception:
                    # Do not fail the whole operation if saving for testing fails
                    pass
                # --- end new code ---

                # Step 3: use ffmpeg CLI to extract a single frame at start_time
                out_image = os.path.join(tmp_dir, "screenshot.jpg")
                try:
                    # Seek inside the downloaded segment. When using download_sections the file starts at t=0,
                    # so compute seek time relative to the segment (midpoint - seg_start).
                    seek_time = max(0.0, seg_mid - seg_start)
                    cmd = [
                        "ffmpeg",
                        "-ss", str(seek_time),
                        "-i", out_video,
                        "-frames:v", "1",
                        out_image,
                        "-y"
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode != 0:
                        raise RuntimeError(result.stderr or result.stdout or "ffmpeg failed")
                except Exception as e:
                    # include the exception message
                    raise RuntimeError(f"ffmpeg failed to extract frame: {e}")

                if not os.path.exists(out_image):
                    raise RuntimeError("Failed to create screenshot image")

                # --- NEW: copy screenshot to same save folder for inspection ---
                try:
                    # reuse save_dir and saved_video_name base
                    screenshot_name = f"{os.path.splitext(saved_video_name)[0]}.jpg"
                    saved_screenshot_path = os.path.join(save_dir, screenshot_name)
                    shutil.copy(out_image, saved_screenshot_path)
                    # print(f"Saved screenshot to {saved_screenshot_path}")
                except Exception:
                    pass
                # --- end new code ---

                # Step 4: open and create both original and blurred bytes
                img = Image.open(out_image).convert("RGBA")

                # original bytes
                orig_bio = io.BytesIO()
                img.save(orig_bio, format="PNG")
                orig_bytes = orig_bio.getvalue()

                # blurred bytes
                if br and br > 0:
                    blurred_img = img.filter(ImageFilter.GaussianBlur(radius=br))
                else:
                    blurred_img = img

                blur_bio = io.BytesIO()
                blurred_img.save(blur_bio, format="PNG")
                blur_bytes = blur_bio.getvalue()

                return blur_bytes, orig_bytes

            finally:
                # Clean up the temp directory
                try:
                    shutil.rmtree(tmp_dir)
                except Exception:
                    pass

        # Run the blocking work in a thread and get bytes
        try:
            blur_bytes, orig_bytes = await asyncio.to_thread(_sync_work, url, blur_radius)
        except Exception as e:
            raise RuntimeError(str(e)) from e

        blur_io = io.BytesIO(blur_bytes)
        blur_io.seek(0)
        orig_io = io.BytesIO(orig_bytes)
        orig_io.seek(0)
        return blur_io, orig_io

    @commands.command()
    async def guess(self, ctx: commands.Context, timeout: int = 30):
        """Start a "Guess the IU MV" game in this channel.

        Usage: `q guess [timeout_seconds]`
        """
        if ctx.channel.id in self._running_channels:
            return await ctx.reply("A Guess the IU MV game is already running in this channel.", delete_after=10)

        self._running_channels.add(ctx.channel.id)
        try:
            # Load MV entries: prefer mv_videos.json
            entries = []
            try:
                import json
                mv_path = os.path.join(func.ROOT_DIR, "mv_videos.json")
                if os.path.exists(mv_path):
                    try:
                        with open(mv_path, encoding="utf8") as f:
                            entries = json.load(f)
                    except json.JSONDecodeError as e:
                        return await ctx.reply(f"Error: Failed to parse mv_videos.json: {e}", delete_after=20)
                else:
                    return await ctx.reply("Error: mv_videos.json not found. Please add the file to the bot root.", delete_after=20)
            except Exception as e:
                return await ctx.reply(f"Error: Could not load MV entries: {e}", delete_after=20)

            if not entries:
                return await ctx.reply("There are no MV entries available right now.")

            # Normalize entry structure: support both {title, youtube_url} and {name, ...}
            def _get_title(e):
                return e.get("title") or e.get("name") or e.get("name", "")

            entry = random.choice(entries)
            title = _get_title(entry) or ""
            youtube = entry.get("youtube_url") or entry.get("url")

            if not youtube:
                return await ctx.reply("Error: Selected MV entry has no YouTube URL.", delete_after=20)

            # Capture a screenshot from the YouTube video and blur it
            try:
                screenshot_buf, original_buf = await self._screenshot_from_youtube(youtube, blur_radius=12)
            except Exception as e:
                return await ctx.reply(f"Error: Failed to capture screenshot from YouTube: {e}", delete_after=30)

            # send the blurred screenshot
            file = discord.File(screenshot_buf, filename="blur.png")
            embed = discord.Embed(title="🎬 Guess the IU MV!", description=f"⏳ You have {timeout} seconds! Type your guess in chat.", color=discord.Color.random())
            embed.set_image(url="attachment://blur.png")
            await ctx.reply(embed=embed, file=file)

            start_time = time.time()
            winner = None
            winner_msg = None

            # Listen for messages until timeout
            while True:
                remaining = timeout - (time.time() - start_time)
                if remaining <= 0:
                    break

                try:
                    msg = await self.bot.wait_for(
                        "message",
                        timeout=remaining,
                        check=lambda m: m.channel == ctx.channel and not m.author.bot
                    )
                except asyncio.TimeoutError:
                    break

                guess_text = func.clean_text(msg.content, allow_spaces=True, convert_to_lower=True)
                answer_text = func.clean_text(title, allow_spaces=True, convert_to_lower=True)

                matched = False
                # direct substring match
                if guess_text and (guess_text in answer_text or answer_text in guess_text):
                    matched = True
                else:
                    # fuzzy checks using normalized similarities
                    if func.lev_similarity(guess_text, answer_text) >= 0.72 or func.jac_similarity(guess_text, answer_text) >= 0.55:
                        matched = True

                if matched:
                    winner = msg.author
                    winner_msg = msg
                    break

            # Reveal outcome
            if winner:
                # We already have the original unblurred buffer from the first capture
                original_buf = original_buf if 'original_buf' in locals() else screenshot_buf

                file2 = discord.File(original_buf, filename="mv.png")

                desc = f"🌟 {winner.mention} got it right! 🎶 It was **{title}**!"
                if youtube:
                    desc += f"\nWatch on YouTube: {youtube}"

                try:
                    await winner_msg.add_reaction("🎉")
                except Exception:
                    pass

                await ctx.reply(desc, file=file2)

                # Award points/exp
                await func.update_user(winner.id, {"$inc": {"game_state.mv_guess.points": 1, "exp": 5}, "$set": {"game_state.mv_guess.last_update": time.time()}})

            else:
                reveal = f"😅 Time’s up! It was **{title}**."
                if youtube:
                    reveal += f"\nWatch on YouTube: {youtube}"
                await ctx.reply(reveal)

        finally:
            self._running_channels.discard(ctx.channel.id)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MVGuess(bot))
