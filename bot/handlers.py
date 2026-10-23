import asyncio, os, re, time
from pathlib import Path
import yt_dlp
from pyrogram import filters
from pyrogram.enums import ChatMembersFilter
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

    # Store group message metadata and text for owner-only search.
    import sqlite3
    DB_PATH = Path(os.getenv("ALEXA_DB_PATH", "alexa_music.sqlite3"))

    def init_db():
        with sqlite3.connect(DB_PATH) as db:
            db.execute("CREATE TABLE IF NOT EXISTS members (group_id INTEGER, user_id INTEGER, username TEXT, display_name TEXT, last_seen INTEGER, PRIMARY KEY(group_id, user_id))")
            db.execute("CREATE TABLE IF NOT EXISTS group_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER, user_id INTEGER, username TEXT, display_name TEXT, message_text TEXT, sent_at INTEGER)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_group_messages ON group_messages(group_id, sent_at)")
            db.execute("CREATE TABLE IF NOT EXISTS known_groups (group_id INTEGER PRIMARY KEY, title TEXT, seen_at INTEGER)")
    init_db()

    @bot.on_message(filters.group & ~filters.service, group=5)
    async def record_group_activity(_, m):
        if not m.from_user:
            return
        group_id = m.chat.id
        user = m.from_user
        display_name = " ".join(x for x in [user.first_name, user.last_name] if x)[:128]
        message_text = (m.text or m.caption or "")[:3500]
        now = int(time.time())
        try:
            with sqlite3.connect(DB_PATH) as db:
                db.execute("INSERT INTO members VALUES (?, ?, ?, ?, ?) ON CONFLICT(group_id, user_id) DO UPDATE SET username=excluded.username, display_name=excluded.display_name, last_seen=excluded.last_seen",
                           (group_id, user.id, user.username or "", display_name, now))
                db.execute("INSERT INTO known_groups VALUES (?, ?, ?) ON CONFLICT(group_id) DO UPDATE SET title=excluded.title, seen_at=excluded.seen_at",
                           (group_id, m.chat.title or str(group_id), now))
                if message_text:
                    db.execute("INSERT INTO group_messages(group_id,user_id,username,display_name,message_text,sent_at) VALUES(?,?,?,?,?,?)",
                               (group_id, user.id, user.username or "", display_name, message_text, now))
            if group_id not in state["groups"]:
                state["groups"].append(group_id)
            if user.id not in state["users"]:
                state["users"].append(user.id)
        except Exception:
            logging.exception("Failed to record group activity")

    @bot.on_message(filters.command("chatsearch") & owner)
    async def owner_chat_search(_, m):
        args = m.command[1:]
        if len(args) < 2:
            return await reply(m, "Usage: /chatsearch GROUP_ID search words")
        try:
            group_id = int(args[0])
            term = " ".join(args[1:])[:200]
            with sqlite3.connect(DB_PATH) as db:
                rows = db.execute("SELECT display_name, username, user_id, message_text, sent_at FROM group_messages WHERE group_id=? AND message_text LIKE ? ORDER BY sent_at DESC LIMIT 10",
                                  (group_id, "%" + term.replace("%", "\\%").replace("_", "\\_") + "%")).fetchall()
            if not rows:
                return await reply(m, "No matching stored messages found. Only messages received after recording was enabled can be searched.")
            lines = [f"🔎 Results for group {group_id}:"]
            for name, username, uid, body, sent_at in rows:
                lines.append(f"{name} (@{username or 'none'}, ID {uid}) — {time.strftime('%Y-%m-%d %H:%M', time.localtime(sent_at))}\\n{body[:500]}")
            await reply(m, "\\n\\n".join(lines)[:3900])
        except Exception as e:
            await reply(m, "Search failed: " + str(e)[:180])

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

    # Owner-only Ban All: only the selected group, excludes administrators and bot accounts.
    pending_ban_all = {}

    @bot.on_message(filters.command("banall") & owner)
    async def owner_ban_all(_, m):
        if len(m.command) != 2:
            return await reply(m, "Usage: /banall GROUP_ID\\nThis targets only that group and skips admins and bot accounts.")
        try:
            group_id = int(m.command[1])
            chat = await bot.get_chat(group_id)
            pending_ban_all[m.from_user.id] = group_id
            await reply(m, f"⚠️ **Confirm Ban All**\\nGroup: {chat.title or group_id}\\nID: `{group_id}`\\nAll accessible non-admin human members will be banned. Admins and bot accounts are excluded. This cannot be easily reversed for many users.", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirm Ban All", callback_data=f"own:banallconfirm:{group_id}")],
                [InlineKeyboardButton("❌ Cancel", callback_data="own:banallcancel")]
            ]))
        except Exception as e:
            await reply(m, "Could not load target group. Check its ID and Alexa's admin permissions.\\n" + str(e)[:180])

    @bot.on_callback_query(filters.regex(r"^own:banall"))
    async def owner_ban_all_callback(_, query):
        if not query.from_user or query.from_user.id != state["owner_id"]:
            await query.answer("Owner only.", show_alert=True)
            return
        action = query.data.split(":")
        if action[1] == "banallcancel":
            pending_ban_all.pop(query.from_user.id, None)
            await query.answer("Cancelled.")
            return await query.message.edit_text("Ban All cancelled.")
        try:
            group_id = int(action[2])
            if pending_ban_all.get(query.from_user.id) != group_id:
                await query.answer("No matching pending confirmation.", show_alert=True)
                return
            await query.answer("Starting. This may take time.", show_alert=True)
            admin_ids = set()
            async for member in bot.get_chat_members(group_id, filter=ChatMembersFilter.ADMINISTRATORS):
                admin_ids.add(member.user.id)
            banned = failed = skipped = 0
            async for member in bot.get_chat_members(group_id):
                user = member.user
                if user.id in admin_ids or user.is_bot:
                    skipped += 1
                    continue
                try:
                    await bot.ban_chat_member(group_id, user.id)
                    banned += 1
                except Exception:
                    failed += 1
                await asyncio.sleep(0.08)
            pending_ban_all.pop(query.from_user.id, None)
            await query.message.edit_text(f"🛡️ **Ban All finished**\\nGroup ID: `{group_id}`\\nBanned: {banned}\\nFailed: {failed}\\nSkipped admins/bots: {skipped}")
        except Exception as e:
            await query.message.reply_text("Ban All stopped/failed. Check Alexa's ban-users permission and group access.\\n" + str(e)[:220])

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
