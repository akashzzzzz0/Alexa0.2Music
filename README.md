# ALEXA 0.2 Music

Free Telegram group voice-chat music bot. No paid plans or payment system.

## Setup
Set BOT_TOKEN, API_ID, API_HASH, SESSION_STRING and OWNER_ID as environment variables. Never commit credentials.
Install FFmpeg and Python 3.11, then run: python -m bot

Commands: /play, /vplay, /pause, /resume, /skip, /stop, /queue, /start, /help, /ping, /settings. Owner commands: /stats and /broadcast.

A Pyrogram user session is required for voice chat playback. Run on a persistent worker, not a short-lived GitHub Actions job. Video streaming depends on the host, FFmpeg, PyTgCalls version and Telegram voice-chat support. This initial version needs real-host testing before being considered production-ready.
