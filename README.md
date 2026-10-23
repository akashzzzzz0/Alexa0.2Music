# ALEXA 0.2 Music

Free Telegram group voice-chat music bot. No paid plans or payment system.

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
