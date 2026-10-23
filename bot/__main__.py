import asyncio, logging, os, shutil
from dotenv import load_dotenv
from pyrogram import Client
from pytgcalls import PyTgCalls
from bot.handlers import register_handlers

load_dotenv()
logging.basicConfig(level=logging.INFO)

def need(key):
    value = os.getenv(key, "").strip()
    if not value:
        raise RuntimeError("Missing environment variable: " + key)
    return value

async def main():
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg is missing. Use the repository Dockerfile or a host runtime that installs FFmpeg.")
    logging.info("FFmpeg available: %s", shutil.which("ffmpeg"))
    api_id = int(need("API_ID"))
    api_hash = need("API_HASH")
    bot = Client("alexa_music_bot", api_id=api_id, api_hash=api_hash,
                 bot_token=need("BOT_TOKEN"), in_memory=True)
    user = Client("alexa_music_user", api_id=api_id, api_hash=api_hash,
                  session_string=need("SESSION_STRING"), in_memory=True)
    calls = PyTgCalls(user)
    state = {"owner_id": int(need("OWNER_ID")), "duration_limit": int(os.getenv("DURATION_LIMIT", "3600")),
             "users": [], "groups": [], "plays": 0}
    register_handlers(bot, calls, state)
    await bot.start()
    await user.start()
    await calls.start()
    logging.info("ALEXA 0.2 Music started")
    try:
        await asyncio.Event().wait()
    finally:
        await calls.stop()
        await user.stop()
        await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
