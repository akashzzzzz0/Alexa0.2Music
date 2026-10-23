import asyncio, os, re, time
from pathlib import Path
import yt_dlp
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pytgcalls.types import MediaStream, AudioQuality, VideoQuality

DIR = Path("downloads")
DIR.mkdir(exist_ok=True)
QUEUES = {}
CURRENT = {}

def register_handlers(bot, calls, state):
    owner = filters.user(state["owner_id"])
    async def reply(m, text, **kw):
        await m.reply_text(text, disable_web_page_preview=True, **kw)

    async def fetch(query, video):
        opts = {"outtmpl": str(DIR / "%(id)s.%(ext)s"), "noplaylist": True,
                "quiet": True, "no_warnings": True,
                "format": "best[height<=720][ext=mp4]/best" if video else "bestaudio/best"}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, query, download=True)
            if info.get("entries"):
                info = next((x for x in info["entries"] if x), None)
            if not info:
                raise ValueError("No result found")
            path = ydl.prepare_filename(info)
            if not os.path.exists(path):
                found = list(DIR.glob(str(info.get("id", "")) + ".*"))
                if not found:
                    raise FileNotFoundError("Media download missing")
                path = str(found[0])
            return {"title": info.get("title", "Unknown"), "duration": int(info.get("duration") or 0),
                    "path": path, "video": video}

    async def start_item(chat_id, item):
        CURRENT[chat_id] = item
        if item["video"]:
            media = MediaStream(item["path"], audio_parameters=AudioQuality.HIGH,
                                video_parameters=VideoQuality.HD_720p)
        else:
            media = MediaStream(item["path"], audio_parameters=AudioQuality.HIGH)
        await calls.play(chat_id, media)

    @bot.on_message(filters.command("start"))
    async def start(_, m):
        if m.from_user and m.from_user.id not in state["users"]:
            state["users"].append(m.from_user.id)
        await reply(m, "🎵 **ALEXA 0.2 Music**\nFree group music bot. Add me to a group, start its voice chat, then use /play.\nUse /help for commands.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("➕ Add to Group", url="https://t.me/" + (await bot.get_me()).username + "?startgroup=true")]]))

    @bot.on_message(filters.command("help"))
    async def help_cmd(_, m):
        await reply(m, "**Commands**\n/play song or YouTube URL\n/vplay YouTube URL\n/queue\n/pause\n/resume\n/skip\n/stop\n/ping\n/settings\n\nOwner: /stats and /broadcast message")

    @bot.on_message(filters.command("ping"))
    async def ping(_, m):
        await reply(m, "🏓 ALEXA is online.")

    @bot.on_message(filters.command("settings"))
    async def settings(_, m):
        await reply(m, "⚙️ Duration limit: " + str(state["duration_limit"]) + " seconds. All features are free.")

    async def request(m, video):
        if m.chat.type not in ("group", "supergroup"):
            return await reply(m, "Use this command in a group.")
        if m.chat.id not in state["groups"]:
            state["groups"].append(m.chat.id)
        query = " ".join(m.command[1:]).strip()
        if not query:
            return await reply(m, "Give a song name or URL. Example: /play lo-fi music")
        if not re.match(r"^https?://", query):
            query = "ytsearch1:" + query
        status = await m.reply_text("🔎 Preparing media…")
        try:
            item = await fetch(query, video)
            if item["duration"] > state["duration_limit"]:
                Path(item["path"]).unlink(missing_ok=True)
                return await status.edit_text("This track exceeds the configured duration limit.")
            chat_id = m.chat.id
            if chat_id in CURRENT:
                QUEUES.setdefault(chat_id, []).append(item)
                return await status.edit_text("➕ Queued: **" + item["title"] + "**")
            await start_item(chat_id, item)
            state["plays"] += 1
            await status.edit_text(("📺" if video else "🎵") + " Playing: **" + item["title"] + "**")
        except Exception as e:
            await status.edit_text("❌ Playback failed: " + str(e)[:220] + "\nCheck active voice chat, user session, FFmpeg and host compatibility.")

    @bot.on_message(filters.command("play") & filters.group)
    async def play(_, m):
        await request(m, False)

    @bot.on_message(filters.command("vplay") & filters.group)
    async def vplay(_, m):
        await request(m, True)

    @bot.on_message(filters.command("queue"))
    async def queue(_, m):
        items = QUEUES.get(m.chat.id, [])
        current = CURRENT.get(m.chat.id)
        lines = ["🎶 Now: " + current["title"] if current else "Nothing is playing."]
        lines += [str(i) + ". " + x["title"] for i, x in enumerate(items, 1)]
        await reply(m, "\n".join(lines[:25]))

    @bot.on_message(filters.command("pause") & filters.group)
    async def pause(_, m):
        try:
            await calls.pause_stream(m.chat.id)
            await reply(m, "⏸ Paused.")
        except Exception as e:
            await reply(m, "Pause failed: " + str(e)[:140])

    @bot.on_message(filters.command("resume") & filters.group)
    async def resume(_, m):
        try:
            await calls.resume_stream(m.chat.id)
            await reply(m, "▶️ Resumed.")
        except Exception as e:
            await reply(m, "Resume failed: " + str(e)[:140])

    @bot.on_message(filters.command("skip") & filters.group)
    async def skip(_, m):
        cid = m.chat.id
        try:
            await calls.leave_call(cid)
            CURRENT.pop(cid, None)
            q = QUEUES.get(cid, [])
            if q:
                await start_item(cid, q.pop(0))
                await reply(m, "⏭ Skipped to next track.")
            else:
                await reply(m, "⏭ Skipped. Queue is empty.")
        except Exception as e:
            await reply(m, "Skip failed: " + str(e)[:140])

    @bot.on_message(filters.command("stop") & filters.group)
    async def stop(_, m):
        cid = m.chat.id
        QUEUES.pop(cid, None)
        CURRENT.pop(cid, None)
        try:
            await calls.leave_call(cid)
        except Exception:
            pass
        await reply(m, "⏹ Stopped and cleared the queue.")

    @bot.on_message(filters.command("stats") & owner)
    async def stats(_, m):
        await reply(m, "📊 Users seen: " + str(len(state["users"])) + "\nGroups seen: " + str(len(state["groups"])) + "\nTracks started: " + str(state["plays"]))

    @bot.on_message(filters.command("broadcast") & owner)
    async def broadcast(_, m):
        text = " ".join(m.command[1:]).strip()
        if not text:
            return await reply(m, "Usage: /broadcast your message")
        sent = failed = 0
        for cid in list(dict.fromkeys(state["users"] + state["groups"])):
            try:
                await bot.send_message(cid, text)
                sent += 1
            except Exception:
                failed += 1
            await asyncio.sleep(0.05)
        await reply(m, "Broadcast complete. Sent: " + str(sent) + ", failed: " + str(failed) + ".")

    # Owner dashboard; callbacks are restricted to the configured owner.
    def owner_keyboard():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Statistics", callback_data="own:stats"), InlineKeyboardButton("👥 Users", callback_data="own:users")],
            [InlineKeyboardButton("💬 Groups", callback_data="own:groups"), InlineKeyboardButton("📢 Broadcast help", callback_data="own:broadcast")],
            [InlineKeyboardButton("🔄 Refresh", callback_data="own:home")]
        ])

    @bot.on_message(filters.command("owner") & owner)
    async def owner_panel(_, m):
        await reply(m, "🛡️ **ALEXA 0.2 MUSIC — OWNER PANEL**\\nChoose a section below. Only the configured owner can open this panel.", reply_markup=owner_keyboard())

    @bot.on_callback_query(filters.regex(r"^own:"))
    async def owner_panel_callback(_, query):
        if not query.from_user or query.from_user.id != state["owner_id"]:
            await query.answer("Owner only.", show_alert=True)
            return
        action = query.data.split(":", 1)[1]
        if action in ("home", "stats"):
            text = ("🛡️ **OWNER PANEL**\\n" if action == "home" else "📊 **BOT STATISTICS**\\n")
            text += f"Known users: {len(state['users'])}\\nKnown groups: {len(state['groups'])}\\nTracks started: {state['plays']}\\nDuration limit: {state['duration_limit']} seconds"
        elif action == "users":
            ids = state["users"]
            preview = "\\n".join(str(x) for x in ids[-30:]) if ids else "No users recorded yet."
            text = f"👥 **USERS ({len(ids)})**\\nLatest recorded IDs:\\n{preview}"
        elif action == "groups":
            ids = state["groups"]
            preview = "\\n".join(str(x) for x in ids[-30:]) if ids else "No groups recorded yet."
            text = f"💬 **GROUPS ({len(ids)})**\\nLatest recorded group IDs:\\n{preview}"
        elif action == "broadcast":
            text = "📢 **BROADCAST**\\nSend /broadcast your message in this chat to broadcast to recorded users and groups."
        else:
            text = "Unknown panel section."
        await query.answer()
        try:
            await query.message.edit_text(text, reply_markup=owner_keyboard(), disable_web_page_preview=True)
        except Exception:
            await query.message.reply_text(text, reply_markup=owner_keyboard(), disable_web_page_preview=True)
