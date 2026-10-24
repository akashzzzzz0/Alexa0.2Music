# ALEXA MUSIC V3.0.0 — Ultimate Music Edition

Free Telegram group voice-chat music bot. No paid plans or payment system.

Current release: **V3.0.0**. Use `/version` to see the release and `/health` to check runtime diagnostics. V3 adds visible version metadata, health reporting (FFmpeg, active chats, queue, autoplay and uptime), and versioned startup notifications. These diagnostics do not replace real-host playback testing.

## Setup
Set BOT_TOKEN, API_ID, API_HASH, SESSION_STRING and OWNER_ID as environment variables. Never commit credentials.
Install FFmpeg and Python 3.11, then run: python -m bot

Commands: /play, /vplay, /pause, /resume, /skip, /stop, /queue, /start, /help, /ping, /settings. Owner commands: /stats and /broadcast.

A Pyrogram user session is required for voice chat playback. Run on a persistent worker, not a short-lived GitHub Actions job. Video streaming depends on the host, FFmpeg, PyTgCalls version and Telegram voice-chat support. This initial version needs real-host testing before being considered production-ready.


## Owner moderation and group records

Set `OWNER_ID` to the owner's numeric Telegram ID. Owner-only commands:

- `/owner` — inline owner dashboard.
- `/banuser GROUP_ID USER_ID` and `/unbanuser GROUP_ID USER_ID` — moderate one member in one group.
- `/banall GROUP_ID` — prompts the owner for confirmation before attempting to ban non-admin human members of that group; administrators and bot accounts are skipped. Telegram permissions and API limits apply.
- `/chatsearch GROUP_ID search words` — search messages stored for that group.
- `/stats` and `/broadcast message`.

Group member IDs are recorded when Alexa receives group messages. Message text is stored for search only after a group administrator runs `/enablelogs`; `/disablelogs` stops new message storage. Group admins should inform members before enabling logging. The bot can only record messages Telegram delivers to it and cannot retrieve old or hidden chats. Search results are private to the configured owner through the bot's private chat.

SQLite data is stored in `alexa_music.sqlite3` by default. Use `ALEXA_DB_PATH` to choose a persistent disk location on your host. Keep that file private and back it up securely.


## Deploy on Botkeep

Botkeep supports importing a Python project from GitHub. The repository root contains `requirements.txt`, and the intended startup command is:

```bash
python -m bot
```

1. Open [Botkeep](https://botkeep.cloud/) and create a Python workload.
2. In the GitHub tab, connect GitHub and select `akashzzzzz0/Alexa0.2Music`, then select the branch you want to deploy.
3. Set the project root to the repository root (the folder containing `requirements.txt`).
4. Choose Python 3.11 if it is available and set the start command to `python -m bot`.
5. In the workload's Environment settings, add the variables below. Enter your real values privately in Botkeep; do not commit them to GitHub.
6. Start/deploy the workload and inspect Console logs. A successful deploy/build alone does not prove that Telegram voice playback works.

Required environment variables:

- `BOT_TOKEN` — token from BotFather.
- `API_ID` and `API_HASH` — Telegram application credentials.
- `SESSION_STRING` — Pyrogram user session string required by the current voice-chat implementation. Treat it like a password and never share it.
- `OWNER_ID` — bot owner's numeric Telegram ID.

Optional variables:

- `DURATION_LIMIT` — maximum track duration in seconds (default `3600`).
- `UPDATES_URL`, `DISCUSSION_URL` — links shown in the start menu.
- `START_IMAGE_URL` — publicly reachable image URL for the start screen; leave blank for text-only.
- `ALEXA_DB_PATH` — path to the SQLite database. Use a path on storage that Botkeep explicitly keeps persistent, if available.
- `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` — optional Spotify Developer app credentials for reading playlist/album track lists. Spotify track links can be identified without these in most cases. Alexa searches for a playable version on supported sources; it does not stream Spotify audio directly.

### Important Botkeep compatibility checks

The music bot needs FFmpeg and PyTgCalls' native/runtime requirements. The current repository includes a Dockerfile that installs FFmpeg, but do not assume Botkeep's standard Python runtime runs that Dockerfile automatically. Before relying on voice playback, confirm the selected Botkeep runtime supports FFmpeg and PyTgCalls, or choose a supported container/Docker deployment if Botkeep offers it for your account. The free workload has limited shared resources, so memory/CPU limits may affect downloads and playback.

SQLite files, downloaded media, and in-memory queues may not survive replacement/redeployment unless their storage location is persistent. Configure persistent storage if available and back up the database. Never run two copies of this bot with the same Telegram credentials at the same time.

For Botkeep's current workflow, see its [GitHub deployment guide](https://botkeep.cloud/docs/github) and [hosting guide](https://botkeep.cloud/docs/hosting). The panel's available runtime versions and capabilities are authoritative. Test `/start`, `/help`, `/reload`, and a short `/play` request in a test group before using it in a live group.
