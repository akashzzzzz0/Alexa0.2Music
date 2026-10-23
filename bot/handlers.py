import asyncio, os, re, time
from pathlib import Path
import yt_dlp
from pyrogram import filters
from pyrogram.enums import ChatMembersFilter
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
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
            db.execute("CREATE TABLE IF NOT EXISTS logging_settings (group_id INTEGER PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0, changed_by INTEGER, changed_at INTEGER)")
            db.execute("CREATE TABLE IF NOT EXISTS authorized_users (group_id INTEGER NOT NULL, user_id INTEGER NOT NULL, authorized_by INTEGER, authorized_at INTEGER, PRIMARY KEY(group_id, user_id))")
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
                setting = db.execute("SELECT enabled FROM logging_settings WHERE group_id=?", (group_id,)).fetchone()
                if message_text and setting and setting[0] == 1:
                    db.execute("INSERT INTO group_messages(group_id,user_id,username,display_name,message_text,sent_at) VALUES(?,?,?,?,?,?)",
                               (group_id, user.id, user.username or "", display_name, message_text, now))
            if group_id not in state["groups"]:
                state["groups"].append(group_id)
            if user.id not in state["users"]:
                state["users"].append(user.id)
        except Exception:
            logging.exception("Failed to record group activity")

    async def change_group_logging(m, enabled):
        if m.chat.type not in ("group", "supergroup") or not m.from_user:
            return await reply(m, "Use this command in the group.")
        try:
            member = await bot.get_chat_member(m.chat.id, m.from_user.id)
            if member.status not in ("administrator", "owner"):
                return await reply(m, "Only a group admin can change message logging.")
            with sqlite3.connect(DB_PATH) as db:
                db.execute("INSERT INTO logging_settings(group_id,enabled,changed_by,changed_at) VALUES(?,?,?,?) ON CONFLICT(group_id) DO UPDATE SET enabled=excluded.enabled, changed_by=excluded.changed_by, changed_at=excluded.changed_at",
                           (m.chat.id, int(enabled), m.from_user.id, int(time.time())))
            if enabled:
                await reply(m, "📝 Message search logging is ON. Alexa stores messages it receives from now on so the bot owner can search them. Member IDs are recorded for group management. Use /disablelogs to turn message storage off.")
            else:
                await reply(m, "🛑 Message search logging is OFF. New messages won't be stored for search; saved records remain in the database.")
        except Exception as e:
            await reply(m, "Could not change logging setting: " + str(e)[:160])

    @bot.on_message(filters.command("enablelogs") & filters.group)
    async def enable_group_logs(_, m):
        await change_group_logging(m, True)

    @bot.on_message(filters.command("disablelogs") & filters.group)
    async def disable_group_logs(_, m):
        await change_group_logging(m, False)

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

    async def manage_auth(m, authorize):
        if m.chat.type not in ("group", "supergroup") or not m.from_user:
            return await reply(m, "Use /auth or /unauth in the group.")
        try:
            member = await bot.get_chat_member(m.chat.id, m.from_user.id)
            status = str(member.status).lower()
            if m.from_user.id != state["owner_id"] and not (status.endswith("administrator") or status.endswith("owner")):
                return await reply(m, "Only this group's admins/owner or the bot owner can manage authorized users.")
            target = m.reply_to_message.from_user if m.reply_to_message and m.reply_to_message.from_user else None
            if not target and len(m.command) > 1:
                raw = m.command[1].lstrip("@")
                if raw.isdigit():
                    target = await bot.get_users(int(raw))
                else:
                    target = await bot.get_users(raw)
            if not target:
                return await reply(m, "Reply to a user's message with /auth or /unauth, or use /auth USER_ID.")
            if target.is_bot:
                return await reply(m, "Bot accounts cannot be authorized for music controls.")
            import sqlite3
            with sqlite3.connect(DB_PATH) as db:
                if authorize:
                    db.execute("INSERT OR REPLACE INTO authorized_users(group_id,user_id,authorized_by,authorized_at) VALUES(?,?,?,?)", (m.chat.id, target.id, m.from_user.id, int(time.time())))
                else:
                    db.execute("DELETE FROM authorized_users WHERE group_id=? AND user_id=?", (m.chat.id, target.id))
            await reply(m, f"{'✅ Authorized' if authorize else '🚫 Authorization removed'}: {target.first_name} (ID {target.id}) in this group.")
        except Exception as e:
            await reply(m, "Could not update authorization: " + str(e)[:160])

    @bot.on_message(filters.command("auth") & filters.group)
    async def auth_user(_, m):
        await manage_auth(m, True)

    @bot.on_message(filters.command("unauth") & filters.group)
    async def unauth_user(_, m):
        await manage_auth(m, False)

    async def music_admin_only(m):
        # The configured bot owner has global access; otherwise only this group's
        # owner/admins can control playback.
        if m.from_user and m.from_user.id == state["owner_id"]:
            return True
        if m.chat.type not in ("group", "supergroup") or not m.from_user:
            await reply(m, "Use this command in a group.")
            return False
        try:
            member = await bot.get_chat_member(m.chat.id, m.from_user.id)
            status = str(member.status).lower()
            if status.endswith("administrator") or status.endswith("owner"):
                return True
            import sqlite3
            with sqlite3.connect(DB_PATH) as db:
                row = db.execute("SELECT 1 FROM authorized_users WHERE group_id=? AND user_id=?", (m.chat.id, m.from_user.id)).fetchone()
            if row:
                return True
            await reply(m, "🎵 Music controls are for group admins/owner and users authorized with /auth.")
            return False
        except Exception:
            await reply(m, "I couldn't verify your group admin status. Please try again.")
            return False

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
        if await music_admin_only(m):
            await request(m, False)

    @bot.on_message(filters.command("vplay") & filters.group)
    async def vplay(_, m):
        if await music_admin_only(m):
            await request(m, True)

    @bot.on_message(filters.command("queue"))
    async def queue(_, m):
        if not await music_admin_only(m):
            return
        items = QUEUES.get(m.chat.id, [])
        current = CURRENT.get(m.chat.id)
        lines = ["🎶 Now: " + current["title"] if current else "Nothing is playing."]
        lines += [str(i) + ". " + x["title"] for i, x in enumerate(items, 1)]
        await reply(m, "\n".join(lines[:25]))

    @bot.on_message(filters.command("pause") & filters.group)
    async def pause(_, m):
        if not await music_admin_only(m):
            return
        try:
            await calls.pause_stream(m.chat.id)
            await reply(m, "⏸ Paused.")
        except Exception as e:
            await reply(m, "Pause failed: " + str(e)[:140])

    @bot.on_message(filters.command("resume") & filters.group)
    async def resume(_, m):
        if not await music_admin_only(m):
            return
        try:
            await calls.resume_stream(m.chat.id)
            await reply(m, "▶️ Resumed.")
        except Exception as e:
            await reply(m, "Resume failed: " + str(e)[:140])

    # Group members can vote to skip; each user gets one vote per track.
    VOTES = {}

    @bot.on_message(filters.command("voteskip") & filters.group)
    async def vote_skip(_, m):
        cid = m.chat.id
        if cid not in CURRENT:
            return await reply(m, "Nothing is playing right now.")
        VOTES[cid] = {"voters": set(), "message_id": None}
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Vote to skip (0/3)", callback_data=f"musicvote:{cid}")]])
        msg = await reply(m, "🗳️ **Vote to skip this track**\\nThree different group members are needed. Group admins can use /skip directly.", reply_markup=kb)
        VOTES[cid]["message_id"] = msg.id

    @bot.on_callback_query(filters.regex(r"^musicvote:-?\\d+$"))
    async def vote_skip_callback(_, q):
        if not q.from_user:
            return await q.answer("Cannot identify voter.", show_alert=True)
        try:
            cid = int(q.data.split(":", 1)[1])
            vote = VOTES.get(cid)
            if not vote or cid not in CURRENT:
                return await q.answer("This vote is no longer active.", show_alert=True)
            if q.from_user.id in vote["voters"]:
                return await q.answer("You already voted.")
            vote["voters"].add(q.from_user.id)
            count = len(vote["voters"])
            if count >= 3:
                try:
                    await calls.leave_call(cid)
                    CURRENT.pop(cid, None)
                    queue_items = QUEUES.get(cid, [])
                    if queue_items:
                        await start_item(cid, queue_items.pop(0))
                    VOTES.pop(cid, None)
                    await q.message.edit_text("⏭️ Vote passed! Track skipped.")
                except Exception as e:
                    await q.message.edit_text("Vote passed, but skipping failed: " + str(e)[:120])
                return await q.answer("Vote passed!", show_alert=True)
            await q.message.edit_reply_markup(InlineKeyboardMarkup([[InlineKeyboardButton(f"⏭ Vote to skip ({count}/3)", callback_data=f"musicvote:{cid}")]]))
            await q.answer("Vote counted.")
        except Exception as e:
            await q.answer("Vote failed: " + str(e)[:100], show_alert=True)

    @bot.on_message(filters.command("skip") & filters.group)
    async def skip(_, m):
        if not await music_admin_only(m):
            return
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
        if not await music_admin_only(m):
            return
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

    @bot.on_message(filters.command("banuser") & owner)
    async def owner_ban_user(_, m):
        args = m.command[1:]
        if len(args) != 2:
            return await reply(m, "Usage: /banuser GROUP_ID USER_ID")
        try:
            group_id, user_id = int(args[0]), int(args[1])
            await bot.ban_chat_member(group_id, user_id)
            await reply(m, f"User {user_id} banned from group {group_id}.")
        except Exception as e:
            await reply(m, "Ban failed. Check IDs and Alexa's ban-users permission. " + str(e)[:180])

    @bot.on_message(filters.command("unbanuser") & owner)
    async def owner_unban_user(_, m):
        args = m.command[1:]
        if len(args) != 2:
            return await reply(m, "Usage: /unbanuser GROUP_ID USER_ID")
        try:
            group_id, user_id = int(args[0]), int(args[1])
            await bot.unban_chat_member(group_id, user_id, only_if_banned=True)
            await reply(m, f"Ban removed for user {user_id} in group {group_id}. This does not automatically add them back.")
        except Exception as e:
            await reply(m, "Unban failed. Check IDs and Alexa's group access. " + str(e)[:180])

    # Global moderation commands are restricted to the configured bot owner.
    @bot.on_message(filters.command("kick") & owner)
    async def owner_kick(_, m):
        args = m.command[1:]
        if len(args) != 2:
            return await reply(m, "Usage: /kick GROUP_ID USER_ID")
        try:
            group_id, user_id = int(args[0]), int(args[1])
            await bot.ban_chat_member(group_id, user_id)
            await bot.unban_chat_member(group_id, user_id, only_if_banned=True)
            await reply(m, f"User {user_id} kicked from group {group_id}.")
        except Exception as e:
            await reply(m, "Kick failed. Check group ID and Alexa's ban permission. " + str(e)[:160])

    @bot.on_message(filters.command("mute") & owner)
    async def owner_mute(_, m):
        args = m.command[1:]
        if len(args) not in (2, 3):
            return await reply(m, "Usage: /mute GROUP_ID USER_ID [minutes]")
        try:
            group_id, user_id = int(args[0]), int(args[1])
            minutes = max(1, min(int(args[2]), 10080)) if len(args) == 3 else 60
            until = int(time.time()) + minutes * 60
            await bot.restrict_chat_member(group_id, user_id, ChatPermissions(), until_date=until)
            await reply(m, f"User {user_id} muted in group {group_id} for {minutes} minute(s).")
        except Exception as e:
            await reply(m, "Mute failed. Check IDs and Alexa's restrict-members permission. " + str(e)[:160])

    @bot.on_message(filters.command("unmute") & owner)
    async def owner_unmute(_, m):
        args = m.command[1:]
        if len(args) != 2:
            return await reply(m, "Usage: /unmute GROUP_ID USER_ID")
        try:
            group_id, user_id = int(args[0]), int(args[1])
            await bot.restrict_chat_member(group_id, user_id, ChatPermissions(can_send_messages=True, can_send_audios=True, can_send_documents=True, can_send_photos=True, can_send_videos=True, can_send_video_notes=True, can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True, can_add_web_page_previews=True))
            await reply(m, f"Messaging restrictions lifted for user {user_id} in group {group_id}.")
        except Exception as e:
            await reply(m, "Unmute failed. Check IDs and Alexa's restrict-members permission. " + str(e)[:160])

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
            import sqlite3
            try:
                with sqlite3.connect(DB_PATH) as db:
                    stored = db.execute("SELECT group_id, title FROM known_groups ORDER BY seen_at DESC LIMIT 20").fetchall()
                lines = ["💬 **GROUPS**"]
                for gid, title in stored:
                    try:
                        chat = await bot.get_chat(gid)
                        link = chat.invite_link
                        if not link:
                            try:
                                link = (await bot.create_chat_invite_link(gid, name="Alexa Owner Panel")).invite_link
                            except Exception:
                                link = "Invite link unavailable; check Alexa's admin permissions."
                        lines.append(f"{title} | ID: {gid}\\n{link}")
                    except Exception:
                        lines.append(f"{title} | ID: {gid} | inaccessible")
                text = "\\n\\n".join(lines) if stored else "No groups recorded yet."
            except Exception as e:
                text = "Could not load groups: " + str(e)[:160]
        elif action == "broadcast":
            text = "📢 **BROADCAST**\\nSend /broadcast your message in this chat to broadcast to recorded users and groups."
        else:
            text = "Unknown panel section."
        await query.answer()
        try:
            await query.message.edit_text(text, reply_markup=owner_keyboard(), disable_web_page_preview=True)
        except Exception:
            await query.message.reply_text(text, reply_markup=owner_keyboard(), disable_web_page_preview=True)
