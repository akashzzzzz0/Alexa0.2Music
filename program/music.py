

import os
import re
import asyncio
import aiohttp
import subprocess
import json
from time import time

import logging

from config import ASSISTANT_NAME, BOT_USERNAME, COOKIES_FILE, IMG_1, IMG_2, MAX_QUEUE_SIZE, PROXY_URL, SPONSORBLOCK_REMOVE
from driver.design.thumbnail import thumb
from driver.design.chatname import CHAT_TITLE
from driver.decorators import errors
from driver.filters import command, other_filters
from driver.queues import QUEUE, add_to_queue, drop_if_live, set_active_thread
from driver.clients import call_py, user
from driver.utils import get_assistant_member, bash, make_progress, control_panel, media_audio, drop_stale_queue
from pyrogram import Client
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserAlreadyParticipant, UserNotParticipant, PeerIdInvalid
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from youtubesearchpython import VideosSearch


log = logging.getLogger(__name__)

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


def _ytdl_site_flags():
    """Build extra yt-dlp flags for non-YouTube sites (cookies, user-agent, proxy)."""
    flags = ["--socket-timeout", "60"]
    if COOKIES_FILE:
        flags += ["--cookies", COOKIES_FILE]
    flags += ["--user-agent", _DEFAULT_USER_AGENT]
    if PROXY_URL:
        flags += ["--proxy", PROXY_URL]
    return flags


def _youtube_search_results(query: str, limit: int = 8):
    """Run the blocking YouTube search client outside the asyncio event loop."""
    return VideosSearch(query, limit=limit).result().get("result", [])


def ytsearch(query: str):
    try:
        q = query.strip()
        is_yt = bool(re.match(r"https?://(www\.|m\.)?(youtube\.com|youtu\.be)/", q))
        if re.match(r"https?://", q):
            # any direct URL — use yt-dlp for metadata (handles YouTube, Rutube, Vimeo, …)
            cmd = ["yt-dlp", "--no-warnings", "--skip-download",
                   "--print", "%(title)s\x1f%(duration_string)s\x1f%(id)s\x1f%(thumbnail)s"]
            if not is_yt:
                cmd += _ytdl_site_flags()
            cmd.append(q)
            out = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=90,
            ).stdout.strip().split("\x1f")
            title = out[0] if out and out[0] else q
            duration = out[1] if len(out) > 1 else ""
            vid = out[2] if len(out) > 2 and out[2] else ""
            raw_thumb = out[3] if len(out) > 3 else ""
            # prefer the well-known HQ thumbnail URL for YouTube
            thumbnail = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if is_yt and vid else raw_thumb
            return [title, q, duration, thumbnail]
        # Search several YouTube candidates and prefer the closest title match.
        # This improves auto-play accuracy without silently selecting a loosely
        # related result when YouTube's ranking is imperfect.
        results = _youtube_search_results(query, limit=10)
        if not results:
            # YouTube search itself can be unavailable; try a public SoundCloud
            # result so /play still has a supported source to attempt.
            return _soundcloud_search_pick(query) or 0

        ranked = sorted(
            results,
            key=lambda item: _music_match_score(
                query, item.get("title", ""), item.get("channel", "")
            ),
            reverse=True,
        )
        data = ranked[0]
        if _music_match_score(query, data.get("title", ""), data.get("channel", "")) < 0.28:
            return _soundcloud_search_pick(query) or 0

        songname = data["title"]
        url = data["link"]
        duration = data.get("duration") or ""
        thumbnail = f"https://i.ytimg.com/vi/{data['id']}/hqdefault.jpg"
        return [songname, url, duration, thumbnail]
    except Exception as e:
        log.warning("ytsearch failed: %s", e)
        if "q" in locals() and _YT_RE.match(q):
            video_id = re.search(r"(?:youtu\.be/|[?&]v=)([A-Za-z0-9_-]{11})", q)
            thumbnail = (
                f"https://i.ytimg.com/vi/{video_id.group(1)}/hqdefault.jpg"
                if video_id else ""
            )
            return [q, q, "", thumbnail]
        if "q" in locals() and not re.match(r"^https?://", q, re.I):
            return _soundcloud_search_pick(q) or 0
        return 0


_YT_RE = re.compile(r"https?://(www\.|m\.)?(youtube\.com|youtu\.be)/")


async def ytdl(format: str, link: str, status_msg=None):
    # For non-YouTube sites (e.g. Rutube) the formats are HLS-only muxed streams
    # that would require downloading gigabytes before playback.  Instead, extract
    # the direct stream URL and hand it to ffmpeg live (same as radio).
    # YouTube must still be downloaded first because its URLs 403 ffmpeg directly.
    if not _YT_RE.match(link):
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp", "--no-warnings", "--no-playlist",
            *_ytdl_site_flags(),
            "-f", "worstaudio/worst",
            "--print", "%(url)s",
            link,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            url = stdout.decode(errors="ignore").strip()
            if url:
                return 1, url
        err = stderr.decode(errors="ignore")[-400:]
        return 0, (err or "stream URL extraction failed")

    proc = await asyncio.create_subprocess_exec(
        "yt-dlp",
        "--no-warnings",
        "--no-playlist",
        # Retry transient extractor/network/fragment failures. These do not
        # bypass YouTube verification; they only recover temporary transport errors.
        "--retries", "3",
        "--fragment-retries", "3",
        "--concurrent-fragments", "4",
        "--extractor-retries", "3",
        "--file-access-retries", "3",
        "--socket-timeout", "30",
        *(["--sponsorblock-remove", SPONSORBLOCK_REMOVE] if SPONSORBLOCK_REMOVE else []),
        "--no-simulate",
        "--newline",
        "--progress-template",
        "download:PROG|%(progress._percent_str)s|%(progress._speed_str)s|%(progress._eta_str)s",
        "--print",
        "after_move:filepath",
        "-f",
        "bestaudio[ext=m4a]/bestaudio/best",
        "-o",
        "downloads/%(id)s.%(ext)s",
        f"{link}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stderr_buf = []

    async def _drain_stderr():
        while True:
            chunk = await proc.stderr.readline()
            if not chunk:
                break
            stderr_buf.append(chunk.decode(errors="ignore"))

    stderr_task = asyncio.ensure_future(_drain_stderr())

    path = ""
    last_edit = 0.0
    while True:
        raw = await proc.stdout.readline()
        if not raw:
            break
        line = raw.decode(errors="ignore").strip()
        if not line:
            continue
        if line.startswith("PROG|"):
            if status_msg is not None and time() - last_edit >= 3:
                last_edit = time()
                parts = line.split("|")
                pct = parts[1].strip() if len(parts) > 1 else ""
                spd = parts[2].strip() if len(parts) > 2 else ""
                eta = parts[3].strip() if len(parts) > 3 else ""
                try:
                    await status_msg.edit(
                        f"📥 **Downloading from YouTube…** `{pct}`\n({spd}, ETA {eta})"
                    )
                except Exception:
                    pass
        else:
            path = line  # --print after_move:filepath is the last line on success
    await proc.wait()
    await stderr_task
    if proc.returncode == 0 and path:
        return 1, path
    return 0, ("".join(stderr_buf)[-500:] or "download failed")


def _music_tokens(value: str):
    """Normalize a search phrase/title for conservative same-track matching."""
    value = re.sub(r"\([^)]*\)|\[[^]]*\]", " ", str(value or "").lower())
    value = re.sub(
        r"\b(official|music|video|audio|lyrics?|visualizer|hd|4k|full|"
        r"lyrical|remastered|slowed|reverb)\b",
        " ",
        value,
    )
    return {
        token for token in re.findall(r"[a-z0-9]+", value)
        if len(token) > 1
    }


def _music_match_score(query: str, title: str, artist: str = "") -> float:
    """Score title + artist relevance while rewarding exact title matches."""
    query_tokens = _music_tokens(query)
    title_tokens = _music_tokens(title)
    artist_tokens = _music_tokens(artist)
    candidate_tokens = title_tokens | artist_tokens
    if not query_tokens or not candidate_tokens:
        return 0.0
    matched = query_tokens & candidate_tokens
    coverage = len(matched) / len(query_tokens)
    title_coverage = len(query_tokens & title_tokens) / len(query_tokens)
    precision = len(matched) / len(candidate_tokens)
    return (0.65 * coverage) + (0.25 * title_coverage) + (0.10 * precision)


def _same_song_query(query: str, title: str, artist: str = "") -> bool:
    # Conservative threshold: don't substitute a vaguely related track.
    return _music_match_score(query, title, artist) >= 0.48


def _soundcloud_search_results(query: str, limit: int = 8):
    """Search public SoundCloud tracks with yt-dlp's maintained extractor."""
    if not query or not query.strip():
        return []
    cmd = [
        "yt-dlp", "--no-warnings", "--flat-playlist", "--dump-single-json",
        "--playlist-end", str(limit), "--socket-timeout", "20",
        *_ytdl_site_flags(), f"scsearch{limit}:{query.strip()}",
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=35,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            log.info("SoundCloud search unavailable: %s", proc.stderr[-300:])
            return []
        payload = json.loads(proc.stdout)
        entries = payload.get("entries", []) if isinstance(payload, dict) else []
        return [entry for entry in entries if isinstance(entry, dict)]
    except Exception as exc:
        log.warning("SoundCloud search failed: %s", exc)
        return []


def _soundcloud_search_pick(query: str):
    """Return the closest public SoundCloud result in /play's search tuple."""
    entries = _soundcloud_search_results(query, limit=8)
    ranked = sorted(
        entries,
        key=lambda item: _music_match_score(
            query,
            item.get("title", ""),
            item.get("uploader") or item.get("artist") or item.get("channel") or "",
        ),
        reverse=True,
    )
    for item in ranked:
        title = str(item.get("title") or "").strip()
        link = str(
            item.get("webpage_url") or item.get("original_url") or item.get("url") or ""
        ).strip()
        artist = str(
            item.get("uploader") or item.get("artist") or item.get("channel") or ""
        ).strip()
        if (
            title
            and link.startswith("https://")
            and "soundcloud.com" in link
            and _same_song_query(query, title, artist)
        ):
            duration = item.get("duration_string") or ""
            if not duration and item.get("duration"):
                try:
                    seconds = int(float(item["duration"]))
                    duration = f"{seconds // 60}:{seconds % 60:02d}"
                except (TypeError, ValueError):
                    duration = ""
            return [title, link, duration, item.get("thumbnail") or IMG_1]
    return []


async def soundcloud_fallback(query: str):
    """Resolve a matching public SoundCloud track to a direct live stream URL."""
    entries = await asyncio.to_thread(_soundcloud_search_results, query, 8)
    ranked = sorted(
        entries,
        key=lambda item: _music_match_score(
            query,
            item.get("title", ""),
            item.get("uploader") or item.get("artist") or item.get("channel") or "",
        ),
        reverse=True,
    )
    for item in ranked[:4]:
        title = str(item.get("title") or "").strip()
        artist = str(
            item.get("uploader") or item.get("artist") or item.get("channel") or ""
        ).strip()
        link = str(
            item.get("webpage_url") or item.get("original_url") or item.get("url") or ""
        ).strip()
        if not title or not link.startswith("https://") or "soundcloud.com" not in link:
            continue
        if not _same_song_query(query, title, artist):
            continue
        try:
            ok, stream_url = await ytdl("bestaudio", link)
        except Exception as exc:
            log.warning("SoundCloud stream resolution failed for %s: %s", link, exc)
            continue
        if not ok:
            continue
        duration = item.get("duration_string") or ""
        if not duration and item.get("duration"):
            try:
                seconds = int(float(item["duration"]))
                duration = f"{seconds // 60}:{seconds % 60:02d}"
            except (TypeError, ValueError):
                duration = ""
        log.info("SoundCloud fallback selected: %s - %s", artist, title)
        return 1, stream_url, title, duration, link
    return 0, None, None, None, None


async def alternative_audio_fallback(query: str, status_msg=None):
    """Try public Audius first, then public SoundCloud; never depend on YouTube auth."""
    if status_msg is not None:
        try:
            await status_msg.edit(
                "⚠️ YouTube audio unavailable. Checking Audius and SoundCloud…"
            )
        except Exception:
            pass
    result = await audius_fallback(query)
    if result[0]:
        return result
    return await soundcloud_fallback(query)


async def ytdl_with_fallback(query: str, first_link: str, status_msg=None):
    """Try the chosen YouTube result, then a few close title matches.

    This does not bypass YouTube verification. It only tries alternate
    matching search results when one particular video is unavailable.
    """
    candidates = [first_link]
    if not re.match(r"^https?://", (query or "").strip(), re.I):
        try:
            results = await asyncio.to_thread(_youtube_search_results, query, 6)
            for item in results:
                link = item.get("link")
                title = item.get("title", "")
                if (
                    link
                    and link not in candidates
                    and _same_song_query(query, title)
                ):
                    candidates.append(link)
        except Exception as exc:
            log.warning("YouTube fallback search failed: %s", exc)

    last_error = "No matching YouTube result could be played."
    for index, candidate in enumerate(candidates[:3]):
        if index and status_msg is not None:
            try:
                await status_msg.edit(
                    "⚠️ First result unavailable. Trying another matching YouTube result..."
                )
            except Exception:
                pass
        ok, value = await ytdl("bestaudio[ext=m4a]", candidate, status_msg if index == 0 else None)
        if ok:
            return 1, value, candidate
        last_error = value or last_error

    return 0, last_error, first_link


async def audius_fallback(query: str):
    """Search Audius' official read/stream API after YouTube extraction fails."""
    if not query or not query.strip():
        return 0, None, None, None, None

    endpoint = "https://api.audius.co/v1"
    timeout = aiohttp.ClientTimeout(total=18, connect=7)
    try:
        async with aiohttp.ClientSession(
            timeout=timeout,
            headers={"User-Agent": "AlexaMusicBot/1.0"},
        ) as session:
            async with session.get(
                f"{endpoint}/tracks/search",
                params={"query": query.strip(), "limit": 10, "sort_method": "relevant"},
            ) as response:
                if response.status != 200:
                    log.warning("Audius search returned HTTP %s", response.status)
                    return 0, None, None, None, None
                payload = await response.json(content_type=None)

        tracks = payload.get("data", []) if isinstance(payload, dict) else []
        for track in tracks:
            if not isinstance(track, dict):
                continue
            if track.get("is_stream_gated") is True or track.get("is_scheduled_release") is True:
                continue
            track_id = track.get("id")
            title = str(track.get("title") or "").strip()
            artist_data = track.get("user") or {}
            artist = str(artist_data.get("name") or "").strip() if isinstance(artist_data, dict) else ""
            if not track_id or not title or not _same_song_query(query, f"{title} {artist}"):
                continue

            stream_url = f"{endpoint}/tracks/{track_id}/stream"
            permalink = str(track.get("permalink") or "").strip()
            if not permalink:
                handle = str(artist_data.get("handle") or "").strip() if isinstance(artist_data, dict) else ""
                permalink = f"https://audius.co/{handle}/{track_id}" if handle else "https://audius.co"

            seconds = track.get("duration")
            try:
                seconds = int(seconds)
                duration = f"{seconds // 60}:{seconds % 60:02d}" if seconds > 0 else ""
            except (TypeError, ValueError):
                duration = ""
            log.info("Audius fallback selected: %s - %s", artist, title)
            return 1, stream_url, title, duration, permalink

        log.info("Audius had no close public match for query: %s", query)
    except Exception as exc:
        log.warning("Audius fallback failed: %s", exc)
    return 0, None, None, None, None


@Client.on_message(command(["play", f"play@{BOT_USERNAME}"]) & other_filters)
@errors
async def play(c: Client, m: Message):
    # snapshot before any await: pyrogram's message-cache can mutate .command
    # back to None on a cached Message once another handler's filter check
    # runs against it concurrently, which happens easily once we start
    # awaiting below (a bare `m.command` read later crashed with
    # "TypeError: object of type 'NoneType' has no len()")
    cmd_args = m.command
    await m.delete()
    replied = m.reply_to_message
    chat_id = m.chat.id
    thread_id = m.message_thread_id if getattr(m, "topic_message", False) else None
    keyboard = control_panel
    if m.sender_chat:
        return await m.reply_text("you're an __Anonymous__ Admin !\n\n» revert back to user account from admin rights.")
    try:
        aing = await c.get_me()
    except Exception as e:
        return await m.reply_text(f"error:\n\n{e}")
    a = await c.get_chat_member(chat_id, aing.id)
    if a.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
        await m.reply_text(
            f"💡 To use me, I need to be an **Administrator** with the following **permissions**:\n\n» ❌ __Delete messages__\n» ❌ __Add users__\n» ❌ __Manage video chat__\n\nData is **updated** automatically after you **promote me**"
        )
        return
    priv = a.privileges
    if not (priv and priv.can_manage_video_chats):
        await m.reply_text(
            "missing required permission:" + "\n\n» ❌ __Manage video chat__"
        )
        return
    if not (priv and priv.can_delete_messages):
        await m.reply_text(
            "missing required permission:" + "\n\n» ❌ __Delete messages__"
        )
        return
    if not (priv and priv.can_invite_users):
        await m.reply_text("missing required permission:" + "\n\n» ❌ __Add users__")
        return
    try:
        ubot = (await user.get_me()).id
        b = await get_assistant_member(c, chat_id, ubot)
        if b.status == ChatMemberStatus.BANNED:
            await m.reply_text(
                f"@{ASSISTANT_NAME} **is banned in group** {m.chat.title}\n\n» **unban the userbot first if you want to use this bot.**"
            )
            return
    except (UserNotParticipant, PeerIdInvalid):
        if m.chat.username:
            try:
                await user.join_chat(m.chat.username)
            except UserAlreadyParticipant:
                pass
            except Exception as e:
                await m.reply_text(f"❌ **userbot failed to join**\n\n**reason**: `{e}`")
                return
        else:
            try:
                invitelink = await c.export_chat_invite_link(
                    m.chat.id
                )
                if invitelink.startswith("https://t.me/+"):
                    invitelink = invitelink.replace(
                        "https://t.me/+", "https://t.me/joinchat/"
                    )
                await user.join_chat(invitelink)
            except UserAlreadyParticipant:
                pass
            except Exception as e:
                return await m.reply_text(
                    f"❌ **userbot failed to join**\n\n**reason**: `{e}`"
                )
    # if a previous stream died silently, clear the stale queue so we rejoin
    await drop_stale_queue(chat_id)
    # radio/IPTV never hold a real queue slot — a new /play takes over now
    drop_if_live(chat_id)
    # set after the drop_*() calls above, which may clear_queue() (and with it
    # any stale ACTIVE_THREAD entry) before this session's is recorded
    set_active_thread(chat_id, thread_id)
    if replied:
        # audio sent as a generic file/document (e.g. a bare .mp3) counts too
        audio_doc = (
            replied.document
            if replied.document and (replied.document.mime_type or "").startswith("audio/")
            else None
        )
        if replied.audio or replied.voice or audio_doc:
            media = replied.audio or replied.voice or audio_doc
            ext = os.path.splitext(getattr(media, "file_name", None) or "")[1] or ".m4a"
            cached = os.path.join(os.getcwd(), "downloads", f"{media.file_unique_id}{ext}")
            if os.path.exists(cached) and os.path.getsize(cached) == media.file_size:
                # same Telegram file already fully downloaded — reuse it
                os.utime(cached, None)  # mark fresh for the LRU cache pruner
                suhu = await replied.reply("📦 **already downloaded — starting...**")
                dl = cached
            else:
                suhu = await replied.reply("📥 **downloading audio...**")
                dl = await replied.download(
                    file_name=cached,
                    progress=make_progress(suhu, "📥 Downloading audio"),
                )
            link = replied.link
            # Title preference: audio metadata title > caption > file name > generic
            if replied.audio and replied.audio.title:
                songname = replied.audio.title[:70]
            elif replied.caption:
                songname = str(replied.caption).splitlines()[0][:70]
            elif getattr(media, "file_name", None):
                songname = media.file_name[:70]
            elif replied.voice:
                songname = "Voice Note"
            else:
                songname = "Audio"
            if chat_id in QUEUE:
                pos = add_to_queue(chat_id, songname, dl, link, "Audio", 0)
                if pos == -1:
                    return await suhu.edit(f"🚫 queue is full (max {MAX_QUEUE_SIZE}).")
                await suhu.delete()
                await m.reply_photo(
                    photo=f"{IMG_1}",
                    caption=f"💡 **Track added to queue »** `{pos}`\n\n🏷 **Name:** [{songname}]({link}) | `music`\n💭 **Chat:** `{chat_id}`\n🎧 **Request by:** {m.from_user.mention()}",
                    reply_markup=keyboard,
                )
            else:
             try:
                await suhu.edit("🔄 **Joining vc...**")
                await call_py.play(chat_id, media_audio(dl))
                add_to_queue(chat_id, songname, dl, link, "Audio", 0)
                await suhu.delete()
                requester = f"[{m.from_user.first_name}](tg://user?id={m.from_user.id})"
                await m.reply_photo(
                    photo=f"{IMG_2}",
                    caption=f"🏷 **Name:** [{songname}]({link})\n💭 **Chat:** `{chat_id}`\n💡 **Status:** `Playing`\n🎧 **Request by:** {requester}\n📹 **Stream type:** `Music`",
                    reply_markup=keyboard,
                )
             except Exception as e:
                await suhu.delete()
                await m.reply_text(f"🚫 error:\n\n» {e}")
        else:
            if len(cmd_args) < 2:
                await m.reply(
                    "» reply to an **audio file** or **give something to search.**"
                )
            else:
                suhu = await c.send_message(chat_id, "🔍 **Searching...**", message_thread_id=thread_id)
                query = m.text.split(None, 1)[1]
                search = await asyncio.to_thread(ytsearch, query)
                if search == 0:
                    await suhu.edit("❌ **no results found.**")
                else:
                    songname = search[0]
                    title = search[0]
                    url = search[1]
                    duration = search[2]
                    thumbnail = search[3]
                    userid = m.from_user.id
                    gcname = m.chat.title
                    try:
                        ctitle = await CHAT_TITLE(gcname)
                        image = await thumb(thumbnail, title, userid, ctitle)
                    except Exception as e:
                        return await suhu.edit(f"🚫 couldn't build the thumbnail: `{e}`")
                    format = "bestaudio[ext=m4a]"
                    ok, ytlink, playback_url = await ytdl_with_fallback(query, url, suhu)
                    if ok:
                        url = playback_url
                    if ok == 0:
                        audius_query = title if _YT_RE.match(query) else query
                        alt_ok, alt_stream, alt_title, alt_duration, alt_url = await alternative_audio_fallback(audius_query, suhu)
                        if alt_ok:
                            ok, ytlink = 1, alt_stream
                            songname = title = alt_title
                            duration = alt_duration or duration
                            url = alt_url
                    if ok == 0:
                        await suhu.edit(
                            f"⚠️ YouTube/Audius/SoundCloud par matching audio available nahi. Original video yahan kholen: [YouTube link]({url})"
                        )
                    else:
                        if chat_id in QUEUE:
                            pos = add_to_queue(
                                chat_id, songname, ytlink, url, "Audio", 0
                            )
                            if pos == -1:
                                return await suhu.edit(f"🚫 queue is full (max {MAX_QUEUE_SIZE}).")
                            await suhu.delete()
                            requester = f"[{m.from_user.first_name}](tg://user?id={m.from_user.id})"
                            await m.reply_photo(
                                photo=image,
                                caption=f"💡 **Track added to queue »** `{pos}`\n\n🏷 **Name:** [{songname}]({url}) | `music`\n**⏱ Duration:** `{duration}`\n🎧 **Request by:** {requester}",
                                reply_markup=keyboard,
                            )
                        else:
                            try:
                                await suhu.edit("🔄 **Joining vc...**")
                                await call_py.play(chat_id, media_audio(ytlink))
                                add_to_queue(chat_id, songname, ytlink, url, "Audio", 0)
                                await suhu.delete()
                                requester = f"[{m.from_user.first_name}](tg://user?id={m.from_user.id})"
                                await m.reply_photo(
                                    photo=image,
                                    caption=f"🏷 **Name:** [{songname}]({url})\n**⏱ Duration:** `{duration}`\n💡 **Status:** `Playing`\n🎧 **Request by:** {requester}\n📹 **Stream type:** `Music`",
                                    reply_markup=keyboard,
                                )
                            except Exception as ep:
                                await suhu.delete()
                                await m.reply_text(f"🚫 error: `{ep}`")

    else:
        if len(cmd_args) < 2:
            await m.reply(
                "» reply to an **audio file** or **give something to search.**"
            )
        else:
            suhu = await c.send_message(chat_id, "🔍 **Searching...**", message_thread_id=thread_id)
            query = m.text.split(None, 1)[1]
            search = await asyncio.to_thread(ytsearch, query)
            if search == 0:
                await suhu.edit("❌ **no results found.**")
            else:
                songname = search[0]
                title = search[0]
                url = search[1]
                duration = search[2]
                thumbnail = search[3]
                userid = m.from_user.id
                gcname = m.chat.title
                try:
                    ctitle = await CHAT_TITLE(gcname)
                    image = await thumb(thumbnail, title, userid, ctitle)
                except Exception as e:
                    return await suhu.edit(f"🚫 couldn't build the thumbnail: `{e}`")
                format = "bestaudio[ext=m4a]"
                ok, ytlink, playback_url = await ytdl_with_fallback(query, url, suhu)
                if ok:
                    url = playback_url
                if ok == 0:
                    audius_query = title if _YT_RE.match(query) else query
                    alt_ok, alt_stream, alt_title, alt_duration, alt_url = await alternative_audio_fallback(audius_query, suhu)
                    if alt_ok:
                        ok, ytlink = 1, alt_stream
                        songname = title = alt_title
                        duration = alt_duration or duration
                        url = alt_url
                if ok == 0:
                    await suhu.edit(
                        f"⚠️ YouTube/Audius/SoundCloud par matching audio available nahi. Original video yahan kholen: [YouTube link]({url})"
                    )
                else:
                    if chat_id in QUEUE:
                        pos = add_to_queue(chat_id, songname, ytlink, url, "Audio", 0)
                        if pos == -1:
                            return await suhu.edit(f"🚫 queue is full (max {MAX_QUEUE_SIZE}).")
                        await suhu.delete()
                        requester = (
                            f"[{m.from_user.first_name}](tg://user?id={m.from_user.id})"
                        )
                        await m.reply_photo(
                            photo=image,
                            caption=f"💡 **Track added to queue »** `{pos}`\n\n🏷 **Name:** [{songname}]({url}) | `music`\n**⏱ Duration:** `{duration}`\n🎧 **Request by:** {requester}",
                            reply_markup=keyboard,
                        )
                    else:
                        try:
                            await suhu.edit("🔄 **Joining vc...**")
                            await call_py.play(chat_id, media_audio(ytlink))
                            add_to_queue(chat_id, songname, ytlink, url, "Audio", 0)
                            await suhu.delete()
                            requester = f"[{m.from_user.first_name}](tg://user?id={m.from_user.id})"
                            await m.reply_photo(
                                photo=image,
                                caption=f"🏷 **Name:** [{songname}]({url})\n**⏱ Duration:** `{duration}`\n💡 **Status:** `Playing`\n🎧 **Request by:** {requester}\n📹 **Stream type:** `Music`",
                                reply_markup=keyboard,
                            )
                        except Exception as ep:
                            await suhu.delete()
                            await m.reply_text(f"🚫 error: `{ep}`")
