# IUFI Startup Checklist

Date checked: 2026-05-24

## 1) Python and dependencies
- [x] Python 3.11+ available (detected: 3.11.15)
- [x] Virtual environment available
- [x] Python packages installed from requirements.txt

## 2) Required environment variables (.env)
- [x] TOKEN is set
- [x] MONGODB_URL is set
- [x] MONGODB_NAME is set

Notes:
- Values were validated as present without printing secrets.

## 3) MongoDB connectivity and schema readiness
- [ ] MongoDB reachable from runtime environment
- [ ] Database named by MONGODB_NAME is accessible
- [ ] Required collections exist:
  - [ ] cards
  - [ ] users
  - [ ] questions
  - [ ] musics

Observed result:
- Connection test failed with ServerSelectionTimeoutError.

What to do next:
- Verify your MongoDB server is running and reachable from this machine.
- Re-check MONGODB_URL in .env (hostname, port, credentials, replica params, TLS settings).
- If using Atlas, ensure current IP is allowed in Network Access and user permissions are valid.
- Create missing collections if needed after connectivity is fixed.

## 4) Discord bot prerequisites
- [ ] Bot token belongs to the intended application and is active
- [ ] Privileged intents enabled in Discord Developer Portal:
  - [ ] Server Members Intent
  - [ ] Message Content Intent
- [ ] Bot invited to target server with required permissions (send messages, manage messages/pins, connect/speak in voice)

## 5) settings.json server wiring
- [ ] MAIN_GUILD updated to your server ID
- [ ] Channel IDs updated to your server:
  - [ ] MAIN_CHAT_CHANNEL
  - [ ] GALLERY_CHANNEL
  - [ ] MARKET_CHANNEL
  - [ ] MUSIC_TEXT_CHANNEL
  - [ ] MUSIC_VOICE_CHANNEL
  - [ ] GAME_CHANNEL_IDS
- [ ] Category filters verified:
  - [ ] ALLOWED_CATEGORY_IDS
  - [ ] IGNORE_CHANNEL_IDS
- [ ] Admin access IDs reviewed:
  - [ ] ADMIN_IDS
- [ ] BUG_REPORT_CHANNEL_ID reviewed

Current status:
- File still contains original project IDs and likely needs replacement for your server.

## 6) Asset readiness
- [x] cover images present (level1.webp, level2.webp, level3.webp)
- [ ] cards available under images/<tier>/
  - Current check found 0 tier folders and 0 .webp card files.
- [ ] frames folder populated if frame features are needed

What to do next:
- Create tier folders under images using names from TIERS_BASE in settings.json:
  common, rare, epic, legendary, mystic, celestial
- Add card images as .webp files into the matching tier folders.
- Optional: add files to newImages using the naming convention for auto-processing.

## 7) Music subsystem
- [ ] ffmpeg binary installed on system PATH
- [ ] OPUS_PATH set in settings.json only if auto-detect fails
- [ ] musics collection has quiz tracks with valid URLs and answer metadata

Current status:
- ffmpeg not found on PATH.

## 8) First-run command
- [ ] Run: python main.py
- [ ] Confirm startup logs show:
  - MongoDB connected
  - cogs loaded
  - card/question/music pools loaded

## 9) Recommended launch order
1. Fix MongoDB connectivity.
2. Replace server-specific IDs in settings.json.
3. Add initial image assets and optional frames.
4. Install ffmpeg.
5. Start bot with python main.py and validate logs.
