# IUFI Project Summary

## Purpose
- IUFI is a Python Discord bot for the IU community, centered on collectible photo cards and mini-games.
- Main user systems include card rolls/collections, trading, tagging, frames, quizzes, music quizzes, match games, PvP, profiles, quests, potions, shop, leaderboards, and seasonal/battle-pass features.

## Runtime and startup
- Supported runtime: Python 3.11+.
- Start locally with `python main.py`; dependencies are pinned in `requirements.txt`.
- `main.py` loads `settings.json`, reads `.env` through `functions.py`, configures logging and privileged Discord intents, connects to MongoDB, loads all pools, optionally loads Opus, then dynamically loads every `.py` file in `cogs/` as a Discord extension.
- Required `.env` variables: `TOKEN`, `MONGODB_URL`, `MONGODB_NAME`.
- MongoDB collections used: `cards`, `users`, `questions`, `musics`.
- Music quiz additionally needs system `ffmpeg` and an Opus library; `settings.json` can override autodetection through `OPUS_PATH`. Optional yt-dlp auth/runtime settings are read from `YTDLP_COOKIE_FILE`, `YTDLP_COOKIES_FROM_BROWSER`, `YTDLP_JS_RUNTIMES`, and `YTDLP_REMOTE_COMPONENTS`.

## Architecture
- `functions.py`: global paths, environment tokens, JSON settings loader, MongoDB collection handles, shared user/database helpers, battle-pass helpers, cooldown/time utilities, and common bot functions. Settings are loaded from root `settings.json`; `settings.local.json` is not automatically loaded.
- `iufi/objects.py`: domain objects and rendering/media behavior, especially `Card`, quiz/question objects, tracks, image/frame composition, and YouTube/audio handling.
- `iufi/pool.py`: in-memory registries and database hydration for `CardPool`, `QuestionPool`, and `MusicPool`. Card startup scans `images/<tier>`, seeds missing MongoDB card documents, filters legacy card fields, and processes `newImages/`.
- `iufi/music.py`: voice/music player behavior.
- `iufi/utils.py`, `iufi/exceptions.py`, `iufi/deepsearch.py`: shared utilities, domain exceptions, and currently optional/experimental search support.
- `cogs/`: Discord command/event/task extensions. Key areas: `card.py`, `gameplay.py`, `potion.py`, `profile.py`, `frames.py`, `settings.py`, `developer.py`, `info.py`, `listeners.py`, and `tasks.py`.
- `views/`: Discord UI components and game views, including roll/drop/reward cards, collection/profile, quiz/music quiz, match game, PvP, trade/shop/frame/wishlist, confirmations, help, and leaderboards.
- `update.py` and `sync_card_tiers.py`: maintenance/data synchronization scripts; inspect before changing card data workflows.

## Configuration and assets
- `settings.json` contains server/channel IDs, command prefixes, tier/drop and pity settings, cooldowns, quest definitions, user defaults, reward configuration, game settings, logging, and feature flags. It is the behavioral configuration source, not just deployment metadata.
- Card images live under `images/<tier>/`; supported tier names are configured by `TIERS_BASE` and include common, rare, epic, legendary, mystic, and celestial in the current setup. New uploads in `newImages/` must begin with a tier name and are moved/assigned numeric IDs at startup.
- Optional frame assets are `frames/<frame>.webp`; hidden-card covers are `cover/level1.webp` through `level3.webp`; downloaded music is stored in `musicTracks/`.
- The repository contains server-specific IDs and credentials-related local files. Never print or commit secrets from `.env`, `yt-cookies.txt`, or local settings.

## Important invariants and known pitfalls
- All loaded cog commands and aliases must be globally unique; duplicate registration prevents startup.
- Card documents may contain legacy fields such as `tier` or `tier_source`; `CardPool.fetch_data` intentionally whitelists only `owner_id`, `stars`, `tag`, `frame`, and `last_trade_time` when constructing `Card`.
- Normal quiz reward cards are configured under `REWARD_CARD_PROBABILITIES.NORMAL_QUIZ` and triggered in `views/quiz.py` as monthly quiz points cross thresholds. Positive points below the first configured threshold must fall back to the lowest configured tier, otherwise the reward path can silently produce no card.
- `CardPool` is class-level in-memory state. Refresh/registration changes must account for `_cards`, `_tag_cards`, `_available_cards`, and `_match_game_cards` together.
- `main.py` filters message processing by configured category/channel IDs and treats the music text channel and market channel specially; changing IDs can make commands appear broken even when handlers work.
- `settings.load()` assumes expected configuration keys exist for several quest/game sections, so configuration edits should preserve required structure.

## Verification and current environment notes
- There is no obvious automated test suite in the repository; use focused Python syntax/type checks or a controlled startup check when changing code.
- `STARTUP_CHECKLIST.md` is the operational reference. Its last recorded check found MongoDB unreachable, ffmpeg unavailable on PATH, original project/server IDs still present, and no card tier folders/files at that time; verify the live workspace before relying on those conditions.
- Startup is infrastructure-dependent: a successful bot run requires reachable MongoDB, valid Discord token/intents/permissions, matching server/channel IDs, card assets, and the music prerequisites for music features.
