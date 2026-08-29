# IUFI — agent and contributor context

Read this file before changing code. It describes what IUFI is, how the repo is laid out, how the bot boots, and the invariants that commonly break if ignored.

Public install notes live in `README.md`. Operational first-run checks live in `STARTUP_CHECKLIST.md`. A shorter overview also exists in `PROJECT_SUMMARY.md`; prefer this file when they disagree.

## What this project is

IUFI is a **Python Discord bot** for the IU (Lee Ji-eun) fandom. Players collect photocards, trade and convert them, play minigames, and progress through quests, a shop, potions, frames, and a seasonal battle pass.

It is **not** a web app. There is no HTTP API, frontend, or test suite. Runtime is Discord + MongoDB + local image/audio files.

Upstream origin: [ChocoMeow/IUFI](https://github.com/ChocoMeow/IUFI). This workspace is a live deployment fork with server-specific `settings.json` IDs.

## Stack

| Piece | Choice |
| --- | --- |
| Language | Python 3.11+ |
| Discord | `discord.py[voice]==2.7.1` (slash commands + custom legacy prefix) |
| Database | MongoDB via `motor` (async) |
| Images | Pillow; cards are usually `.webp` |
| Music quiz | `yt-dlp`, system `ffmpeg`, Discord Opus |
| Config | `.env` for secrets, `settings.json` for behavior |

Start with `python main.py` after `pip install -r requirements.txt`.

## How to think about the architecture

```
Discord event
    → main.py (IUFI bot: message prefix router, slash error handler, startup)
        → cogs/*.py (commands, listeners, background tasks)
            → views/*.py (buttons, selects, modals, game UIs)
                → functions.py (users, cards, quests, pity, battle pass, settings)
                → iufi/ (Card, pools, Player, exceptions)
                    → MongoDB collections + images/ + musicTracks/
```

**Shared state is in-memory.** `CardPool`, `QuestionPool`, and `MusicPool` are class-level registries loaded at startup. `functions.USERS_BUFFER` caches user documents. If you change a card or user, update **both** MongoDB and the in-memory object, or the next command will see stale data.

## Directory map

```
IUFI/
├── main.py                 # Bot process: DB connect, pool load, cog load, slash sync, prefix router
├── functions.py            # Settings, env tokens, Mongo handles, user/card/quest/pity/BP helpers
├── settings.json           # Loaded at startup (the live config). Not settings.local.json.
├── settings.local.json     # Local copy; NOT auto-loaded. Do not assume it is in effect.
├── .env                    # TOKEN, MONGODB_URL, MONGODB_NAME (+ optional yt-dlp vars)
├── requirements.txt
├── cogs/                   # discord.ext extensions; every *.py is loaded automatically
├── views/                  # discord.ui Views/Modals used by cogs
├── iufi/                   # Domain package (cards, quizzes, music player)
├── images/<tier>/          # Card art; folder name IS the tier. Gitignored.
├── newImages/              # Drop new cards here; processed on startup. Gitignored.
├── frames/                 # Optional frame overlays (<name>.webp). Gitignored.
├── cover/                  # Hidden-card covers: level1.webp … level3.webp
├── musicTracks/            # yt-dlp downloads. Gitignored.
├── update.py               # Self-update from upstream zip (destructive; inspect before use)
├── sync_card_tiers.py      # Offline sync of images/ folder → cards.tier in MongoDB
├── STARTUP_CHECKLIST.md
├── README.md
└── AGENTS.md               # This file
```

Do not commit `.env`, `yt-cookies.txt`, `images/`, `newImages/`, `musicTracks/`, `frames/`, or `logs/`.

## Startup sequence (`main.py`)

1. `func.settings.load()` reads **root `settings.json` only**.
2. Logging from `LOGGING` (optional rotating file under `./logs`).
3. Bot constructed with members + message-content intents.
4. `setup_hook`:
   - Connect MongoDB; require DB name to already exist.
   - Bind collections: `cards`, `users`, `questions`, `musics`.
   - `CardPool.fetch_data()` then `CardPool.process_new_cards()`.
   - `QuestionPool.fetch_data()`, `MusicPool.fetch_data()`.
   - Load Opus (`OPUS_PATH` or autodetection).
   - `load_extension` for every `cogs/*.py`.
   - `tree.sync()` globally.
5. `on_ready` logs pool sizes.

Failed MongoDB, missing DB name, or duplicate slash command names abort startup.

## Dual command surface

Primary UX is **global slash commands** (`/roll`, `/quiz`, …).

`on_message` also implements a **legacy compact prefix** (`q` / `Q` from `BOT_PREFIX`). Commands are glued, not spaced: `qroll` works, `q roll` does not. Aliases such as `r` → `roll` live in `legacy_aliases` in `main.py`. Message invocations fake a slash `Interaction`; some modal-only flows need extra args.

When adding a command:

1. Register it once as `@app_commands.command` in a cog.
2. Add a prefix alias in `main.py` if players still use `q…`.
3. **Names and aliases must be globally unique** across all cogs or the bot will not start.

Developer tools sit under the `dev` slash group in `cogs/developer.py` plus `/debug`. Admin checks use `ADMIN_IDS` in settings (`func.is_admin_interaction`).

## Cog responsibilities

| File | Role |
| --- | --- |
| `cogs/gameplay.py` | Roll, match game, quiz, emoji quiz, shop, battle pass, PvP, cooldown, pity |
| `cogs/card.py` | Card info, convert, tags, trade (cards + potions), upgrade |
| `cogs/profile.py` | Profile, bio, main card, collections, daily, view, inventory, quests, wishlist |
| `cogs/frames.py` | Set/remove frames |
| `cogs/potion.py` | Use potions |
| `cogs/info.py` | `/help`, `/leaderboard` group |
| `cogs/settings.py` | Reminder toggle, reset |
| `cogs/developer.py` | Admin give/remove candies/cards/rolls, quit/wipe, debug |
| `cogs/listeners.py` | Ban → return cards to pool; join music VC → start quiz player; gallery pin at 15 📌 |
| `cogs/tasks.py` | Periodic card drops, cache clear, cooldown DM reminders, monthly quiz role rewards |

`views/` holds the interactive UIs. `views/__init__.py` re-exports the common ones (`RollView`, `MatchGame`, `QuizView`, `ShopView`, `TradeView`, …). Some views (PvP, emoji quiz, reward card, profile status) are imported directly from their modules.

## Domain package (`iufi/`)

- **`objects.py`**: `Card` (image compose, frames, GIF), quiz `Question`, music `Track` / yt-dlp options. Card canvas is 1080×1920, scaled for Discord.
- **`pool.py`**: `CardPool`, `QuestionPool`, `MusicPool`. Drop rates, available-card lists, match-game card subset, music player registry.
- **`music.py`**: `Player` voice client for the music quiz.
- **`utils.py`**, **`exceptions.py`**: helpers and `IUFIException` hierarchy (slash errors surface `IUFIException` messages to the user).
- **`deepsearch.py`**: experimental image search; currently unused (imports commented in `pool.py` and related deps commented in `requirements.txt`).

`CardPool.fetch_data` scans `images/<tier>/`, uses the **folder name as tier**, seeds missing MongoDB docs, and constructs `Card` with only `owner_id`, `stars`, `tag`, `frame`, `last_trade_time`. Extra DB fields such as `tier` / `tier_source` (written by `sync_card_tiers.py`) are **not** applied to the live `Card` object.

When mutating pool membership, keep these in sync: `_cards`, `_tag_cards`, `_available_cards`, `_match_game_cards`.

## Database

| Collection | Typical `_id` | Purpose |
| --- | --- | --- |
| `users` | Discord user id | Candies, exp, owned card ids, potions, pity, cooldowns, quests, PvP, battle pass, `game_state`, wishlist |
| `cards` | Card image stem (e.g. `common12`) | Ownership, stars, tag, frame, last trade time |
| `questions` | quiz question docs | Trivia pool |
| `musics` | track docs | Music quiz URLs + answers |

New users are created from `USER_BASE` in `settings.json` via `get_user(..., insert=True)`. Always go through `get_user` / `update_user` / `update_card` rather than raw collection writes unless you have a reason; `update_user` also refreshes `USERS_BUFFER`.

## Configuration that actually controls gameplay

`settings.json` is **game design**, not just Discord wiring. Important keys:

- **Server IDs**: `MAIN_GUILD`, chat/gallery/market/music channels, `GAME_CHANNEL_IDS` (drops + reminder links), `ADMIN_IDS`, `BUG_REPORT_CHANNEL_ID`, rank Discord roles in `RANK_BASE`.
- **Economy**: `TIERS_BASE` (emoji + convert value), `MAX_CARDS`, `PITY_SETTINGS`, `POTIONS_BASE`, `FRAMES_BASE`, shop-related sections, `REWARD_CARD_PROBABILITIES`.
- **Quests**: `DAILY_QUESTS`, `WEEKLY_QUESTS`. `settings.load()` assumes these sections exist.
- **Games**: `MATCH_GAME_SETTINGS`, `MUSIC_GAME_SETTINGS`, `PVP_SETTINGS`, `COOLDOWN_BASE`.
- **Season**: `BATTLEPASS_SETTINGS` (must stay aligned with `USER_BASE.battlepass.season_id`).
- **Flags**: `PVP_REWARDS_ENABLED`, `GIVE_REWARD_CARD`.

`ALLOWED_CATEGORY_IDS` and `IGNORE_CHANNEL_IDS` are loaded but **not currently used to gate commands** in `main.py`. `GAME_CHANNEL_IDS` is used by drop/reminder tasks. `in_market_channel` / `in_music_channel` exist in `functions.py` but are unused at present.

Wrong channel/guild IDs look like “the bot is broken” even when handlers are fine. Music quiz answers are only consumed in `MUSIC_TEXT_CHANNEL`; the player starts when someone joins `MUSIC_VOICE_CHANNEL`.

## Cards and assets

Tiers (current `TIERS_BASE`): `common`, `rare`, `epic`, `legendary`, `mystic`, `celestial`.

- Live art: `images/<tier>/<id>.webp` (png/jpg/gif also appear in the sync script).
- New art: put files in `newImages/` named so the filename **starts with a tier** (e.g. `common1.webp`). Startup assigns numeric ids and moves files into `images/<tier>/`.
- Covers for unrevealed cards: `cover/level1.webp`–`level3.webp`.
- Frames: `frames/<frame>.webp` matching keys in `FRAMES_BASE`.

`sync_card_tiers.py` is a **maintenance CLI** (dry-run, conflict handling). It writes tier metadata into MongoDB; it does not replace `CardPool` folder-based tiering at runtime.

## Player-facing systems (where to edit them)

| System | Start here |
| --- | --- |
| Rolling / claiming / pity | `cogs/gameplay.py`, `views/roll.py`, `functions.calculate_soft_pity_boost` / `check_pity_guarantee` / `update_pity_from_cards`, `DROP_RATES` in `iufi/pool.py` |
| Collection / convert / trade / tags / upgrade | `cogs/card.py`, `views/trade.py`, `views/photocard.py` |
| Profile, collections, daily, inventory, wishlist | `cogs/profile.py`, `views/collection.py`, `views/wishlist.py` |
| Trivia quiz + monthly ranks | `cogs/gameplay.py`, `views/quiz.py`, `QuestionPool`, `RANK_BASE`, `tasks.distribute_monthly_quiz_rewards` |
| Music quiz | `cogs/listeners.py`, `iufi/music.py`, `iufi/objects.py` Track/yt-dlp, `MUSIC_DB` |
| Match game | `views/matchgame.py`, `MATCH_GAME_SETTINGS` |
| PvP | `cogs/gameplay.py`, `views/pvp.py`, `PVP_SETTINGS` |
| Shop / potions / frames | `views/shop.py`, `cogs/potion.py`, `cogs/frames.py` |
| Quests | `functions.update_quest_progress`, quest dicts in settings |
| Battle pass | `functions.get_battlepass_*` / `add_battlepass_xp`, `BATTLEPASS_SETTINGS`, `/battlepass` |
| Random world drops | `cogs/tasks.py` + `views/drop.py` |

Quiz reward cards: `REWARD_CARD_PROBABILITIES.NORMAL_QUIZ` and logic in `views/quiz.py`. If monthly quiz points are positive but below the first threshold, they must still map to the lowest configured tier or no card is granted.

## Environment variables

Required:

- `TOKEN` — Discord bot token
- `MONGODB_URL`, `MONGODB_NAME`

Optional (music / YouTube):

- `YTDLP_COOKIE_FILE`, `YTDLP_COOKIES_FROM_BROWSER`
- `YTDLP_JS_RUNTIMES`, `YTDLP_REMOTE_COMPONENTS`
- `OPUS_PATH` in settings if Opus autodetection fails

Never print or commit secrets. `yt-cookies.txt` and `.env` are local credentials.

## Conventions for changes

- Match existing style: `import discord, iufi` / `import functions as func`, type hints where already used, `setup(bot)` at the bottom of each cog.
- Persist through `func.update_user` / `func.update_card` and then the matching pool method.
- Preserve `settings.json` key structure; `load()` does not tolerate missing quest/game sections.
- Do not add a second settings loader unless you also change `Settings.load()`.
- There are no automated tests. After logic changes, at least: syntax-check the module, reason through buffer + Mongo + pool, and if possible run the bot and hit the affected slash command. UI changes should be checked in Discord, not only by reading code.
- Do not treat `STARTUP_CHECKLIST.md` as live status; it is a dated ops snapshot.

## Privileged Discord intents

Developer Portal must enable **Server Members** and **Message Content**. The bot needs send/manage messages (and pin in gallery), plus connect/speak in the music voice channel.
