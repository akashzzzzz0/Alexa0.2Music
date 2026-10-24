import asyncio, logging, os, shutil
from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.types import (BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats, BotCommandScopeAllChatAdministrators, BotCommandScopeChat)
from pytgcalls import PyTgCalls
from bot.handlers import register_handlers

load_dotenv()
logging.basicConfig(level=logging.INFO)

def need(key):
    value = os.getenv(key, "").strip()
    if not value:
        raise RuntimeError("Missing environment variable: " + key)
    return value

async def configure_command_menus(bot, owner_id):
    """Install Telegram command menus for private chats, group members/admins, and bot owner."""
    private_commands = [
        BotCommand("help", "Show all available commands"),
        BotCommand("play", "Search and play music in a group"),
        BotCommand("vplay", "Play a video in a group"),
        BotCommand("queue", "Show the music queue"),
        BotCommand("autoplay", "Turn autoplay on or off"),
        BotCommand("pause", "Pause playback"),
        BotCommand("resume", "Resume playback"),
        BotCommand("skip", "Skip the current track"),
        BotCommand("stop", "Stop playback and clear queue"),
        BotCommand("voteskip", "Vote to skip a track"),
        BotCommand("ping", "Check bot status"),
        BotCommand("settings", "View music settings"),
    ]
    member_commands = [
        BotCommand("help", "Show member commands"),
        BotCommand("voteskip", "Vote to skip a track"),
        BotCommand("ping", "Check bot status"),
        BotCommand("settings", "View music settings"),
    ]
    admin_commands = [
        BotCommand("help", "Show admin commands"),
        BotCommand("play", "Search and play music"),
        BotCommand("vplay", "Play a video"),
        BotCommand("queue", "Show the music queue"),
        BotCommand("autoplay", "Turn autoplay on or off"),
        BotCommand("pause", "Pause playback"),
        BotCommand("resume", "Resume playback"),
        BotCommand("skip", "Skip the current track"),
        BotCommand("stop", "Stop playback and clear queue"),
        BotCommand("voteskip", "Open a skip vote"),
        BotCommand("auth", "Authorize a music member"),
        BotCommand("unauth", "Remove music authorization"),
        BotCommand("enablelogs", "Enable group message logging"),
        BotCommand("disablelogs", "Disable group message logging"),
        BotCommand("reload", "Refresh group admin cache/settings"),
        BotCommand("ping", "Check bot status"),
        BotCommand("settings", "View music settings"),
    ]
    owner_commands = private_commands + [
        BotCommand("owner", "Open bot owner panel"),
        BotCommand("stats", "View bot statistics"),
        BotCommand("broadcast", "Broadcast a message"),
        BotCommand("banall", "Ban members in a selected group"),
        BotCommand("banuser", "Ban a user from a group"),
        BotCommand("unbanuser", "Unban a user from a group"),
        BotCommand("kick", "Kick a user from a group"),
        BotCommand("mute", "Mute a user in a group"),
        BotCommand("unmute", "Unmute a user in a group"),
        BotCommand("chatsearch", "Search saved group messages"),
        BotCommand("reload", "Refresh settings/admin cache"),
    ]
    # More specific scopes override general scopes in Telegram.
    await bot.set_bot_commands(private_commands, scope=BotCommandScopeAllPrivateChats())
    await bot.set_bot_commands(member_commands, scope=BotCommandScopeAllGroupChats())
    await bot.set_bot_commands(admin_commands, scope=BotCommandScopeAllChatAdministrators())
    await bot.set_bot_commands(owner_commands, scope=BotCommandScopeChat(chat_id=owner_id))
    logging.info("Role-based Telegram command menus configured")


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
    try:
        await configure_command_menus(bot, state["owner_id"])
    except Exception:
        logging.exception("Could not configure Telegram command menus; /help remains available")
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
