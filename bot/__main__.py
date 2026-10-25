import asyncio, logging, os, shutil, glob
from pathlib import Path

# Keep free-host disk usage low: remove the obsolete Deno runtime left by
# older deployments (it is no longer a requirement) and pip's downloaded cache.
def cleanup_obsolete_runtime():
    base = Path(__file__).resolve().parent.parent
    for pattern in (
        str(base / ".local" / "lib" / "python*" / "site-packages" / "deno"),
        str(base / ".local" / "lib" / "python*" / "site-packages" / "deno-*.dist-info"),
    ):
        for target in glob.glob(pattern):
            shutil.rmtree(target, ignore_errors=True)
    deno_bin = base / ".local" / "bin" / "deno"
    try:
        deno_bin.unlink(missing_ok=True)
    except OSError:
        pass
    shutil.rmtree(Path.home() / ".cache" / "pip", ignore_errors=True)

cleanup_obsolete_runtime()

# Bootstrap a temporary Node.js runtime for yt-dlp's supported YouTube EJS
# challenge solver. Keep the runtime under /tmp so it does not consume the
# host's small persistent disk quota. If the download is unavailable, Alexa
# continues to start and existing non-YouTube sources remain usable.
def ensure_temporary_node_runtime():
    existing = shutil.which("node")
    if existing:
        logging.info("JavaScript runtime already available: node at %s", existing)
        return
    if os.uname().machine.lower() not in ("x86_64", "amd64"):
        logging.warning("Temporary Node.js bootstrap skipped: unsupported architecture")
        return

    version = "v24.22.1"
    archive_name = f"node-{version}-linux-x64.tar.xz"
    archive_url = f"https://nodejs.org/dist/{version}/{archive_name}"
    sums_url = f"https://nodejs.org/dist/{version}/SHASUMS256.txt"
    runtime_root = Path("/tmp/alexa-node-runtime")
    node_bin = runtime_root / "bin" / "node"
    archive_path = Path("/tmp") / archive_name
    sums_path = Path("/tmp") / f"node-{version}-SHASUMS256.txt"

    try:
        if not (node_bin.is_file() and os.access(node_bin, os.X_OK)):
            runtime_root.mkdir(parents=True, exist_ok=True)
            request = urllib.request.Request(archive_url, headers={"User-Agent": "AlexaMusic-runtime-bootstrap/1.0"})
            with urllib.request.urlopen(request, timeout=30) as response, archive_path.open("wb") as out:
                shutil.copyfileobj(response, out)

            request = urllib.request.Request(sums_url, headers={"User-Agent": "AlexaMusic-runtime-bootstrap/1.0"})
            with urllib.request.urlopen(request, timeout=15) as response:
                sums_text = response.read(100_000).decode("ascii", "strict")
            expected = None
            for line in sums_text.splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[-1].lstrip("*") == archive_name:
                    expected = parts[0].lower()
                    break
            if not expected:
                raise RuntimeError("Node.js archive checksum was not found")
            digest = __import__("hashlib").sha256()
            with archive_path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != expected:
                raise RuntimeError("Node.js archive checksum mismatch")

            # Python's tarfile/lzma support extracts just the Node executable;
            # the host does not need the external xz command.
            member_name = f"node-{version}-linux-x64/bin/node"
            with tarfile.open(archive_path, mode="r:xz") as archive:
                member = archive.getmember(member_name)
                source = archive.extractfile(member)
                if source is None:
                    raise RuntimeError("Node.js executable missing from archive")
                node_bin.parent.mkdir(parents=True, exist_ok=True)
                with source, node_bin.open("wb") as target:
                    shutil.copyfileobj(source, target)
            node_bin.chmod(0o755)

        os.environ["PATH"] = str(node_bin.parent) + os.pathsep + os.environ.get("PATH", "")
        logging.info("Temporary Node.js runtime ready: %s", node_bin)
    except Exception as exc:
        logging.warning("Could not prepare temporary Node.js runtime; continuing without it: %s", str(exc)[:240])
    finally:
        archive_path.unlink(missing_ok=True)
        sums_path.unlink(missing_ok=True)

ensure_temporary_node_runtime()

from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.types import (BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats, BotCommandScopeAllChatAdministrators, BotCommandScopeChat)
from pytgcalls import PyTgCalls
from bot.handlers import register_handlers
from bot.version import VERSION, RELEASE_NAME
import time

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
        BotCommand("start", "Open Alexa Music welcome menu"),
        BotCommand("help", "Show all available commands"),
        BotCommand("version", "Show Alexa Music version"),
        BotCommand("health", "Check runtime status"),
        BotCommand("play", "Search and play music in a group"),
        BotCommand("playforce", "Replace the current track"),
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
        BotCommand("start", "Open Alexa Music welcome menu"),
        BotCommand("help", "Show member commands"),
        BotCommand("version", "Show bot version"),
        BotCommand("health", "Check runtime status"),
        BotCommand("voteskip", "Vote to skip a track"),
        BotCommand("ping", "Check bot status"),
        BotCommand("settings", "View music settings"),
    ]
    admin_commands = [
        BotCommand("start", "Open Alexa Music welcome menu"),
        BotCommand("help", "Show admin commands"),
        BotCommand("version", "Show bot version"),
        BotCommand("health", "Check runtime status"),
        BotCommand("play", "Search and play music"),
        BotCommand("playforce", "Force replace current track"),
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
             "users": [], "groups": [], "plays": 0, "started_at": time.time()}
    register_handlers(bot, calls, state, user)
    await bot.start()
    try:
        await configure_command_menus(bot, state["owner_id"])
    except Exception:
        logging.exception("Could not configure Telegram command menus; /help remains available")
    await user.start()
    await calls.start()
    logging.info("ALEXA MUSIC V%s (%s) started", VERSION, RELEASE_NAME)
    try:
        await bot.send_message(
            state["owner_id"],
            "✅ **ALEXA MUSIC V%s IS ACTIVE**\n\n🎧 %s\n🎵 Music engine initialized.\n🩺 Use /health for runtime diagnostics.\n🟢 Ready to receive commands." % (VERSION, RELEASE_NAME)
        )
        logging.info("Owner startup notification sent")
    except Exception:
        logging.exception("Could not send owner startup notification; check OWNER_ID and that the owner has started the bot in DM")
    try:
        await asyncio.Event().wait()
    finally:
        # PyTgCalls 2.2.11 does not expose calls.stop() in every build.
        # Guard cleanup so a shutdown signal does not raise a second exception.
        stop_calls = getattr(calls, "stop", None)
        if callable(stop_calls):
            try:
                result = stop_calls()
                if hasattr(result, "__await__"):
                    await result
            except Exception:
                logging.exception("PyTgCalls cleanup failed")
        else:
            logging.info("PyTgCalls has no stop() method in this installed version; skipping that cleanup step")
        try:
            await user.stop()
        except Exception:
            logging.exception("Could not stop the user client cleanly")
        try:
            await bot.stop()
        except Exception:
            logging.exception("Could not stop the bot client cleanly")

if __name__ == "__main__":
    asyncio.run(main())
