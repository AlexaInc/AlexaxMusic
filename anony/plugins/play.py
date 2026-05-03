# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic

from pathlib import Path
from pyrogram import filters, types
from anony import anon, app, config, db, lang, queue, tg, yt
from anony.helpers import buttons, utils
from anony.helpers._play import checkUB
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from anony.helpers.radio import radio_markup



from anony.helpers.tv import category_markup, fetch_channels

@app.on_message(filters.command("tv") & filters.group & ~app.bl_users)
@lang.language()
@checkUB
async def tv_command_handler(
    _, 
    m: types.Message, 
    force: bool = False, 
    video: bool = False, 
    url: str = None
):
    sent = await m.reply_text("📡 <b>Fetching TV channels...</b>")
    channels = await fetch_channels()
    if not channels:
        return await sent.edit_text("❌ Failed to fetch TV channels. Please try again later.")
        
    await sent.edit_text(
        "📺 <b>TV Station Categories</b>\nChoose a category to find a station:",
        reply_markup=category_markup(channels)
    )


@app.on_message(filters.command("radio") & filters.group & ~app.bl_users)
@lang.language()
@checkUB
async def radio_command_handler(
    _, 
    m: types.Message, 
    force: bool = False, 
    video: bool = False, 
    url: str = None
):
    await m.reply_text(
        "📻 <b>Sri Lanka Live Radio Menu</b>\nSelect a station below to start streaming 24/7:",
        reply_markup=radio_markup(1)
    )


@app.on_message(
    filters.command(["play", "playforce", "vplay", "vplayforce"])
    & filters.group
    & ~app.bl_users
)
@lang.language()
@checkUB
async def play_hndlr(
    _,
    m: types.Message,
    force: bool = False,
    video: bool = False,
    url: str = None,
) -> None:
    mention = m.from_user.mention
    file = None
    tracks = []
    
    # 1. IMMEDIATE RADIO CHECK (Bypasses play_usage)
    if m.command[0] == "247":
        sent = await m.reply_text("📡 <b>Connecting to NuWaaV Radio (24/7 K-Pop)...</b>")
        
        from anony.helpers import Track
        
        file = Track(
            id="nuwaav_radio",
            channel_name="Live Radio",
            duration="Live",
            duration_sec=0,
            title="NuWaaV Radio (K-Pop 24/7)",
            url="https://nuwaav.com/radio/8020/radio.mp3",
            file_path="https://nuwaav.com/radio/8020/radio.mp3",
            message_id=m.id,
            thumbnail=config.DEFAULT_THUMB,
            user=mention,
            view_count="Live",
            video=False
        )
        file.stream_type = "live"

        try:
            # Bypass queue check for forced radio
            await anon.play_media(chat_id=m.chat.id, message=sent, media=file)
            queue.force_add(m.chat.id, file)
            
            await sent.edit_text(
                "📡 <b>NuWaaV Radio (24/7 K-Pop) is now streaming!</b>"
            )
            return # Exit after starting radio
        except Exception as e:
            await sent.edit_text(f"Failed to start NuWaaV Radio: {e}")
            return
    
    # 2. REGULAR PLAY LOGIC
    else:
        # We only send "Searching" for normal songs
        sent = await m.reply_text(m.lang["play_searching"])
        media = tg.get_media(m.reply_to_message) if m.reply_to_message else None

        if url:
            if "playlist" in url:
                await sent.edit_text(m.lang["playlist_fetch"])
                tracks = await yt.playlist(config.PLAYLIST_LIMIT, mention, url, video)
                if not tracks:
                    return await sent.edit_text(m.lang["playlist_error"])
                file = tracks[0]
                tracks.remove(file)
                file.message_id = sent.id
            else:
                file = await yt.search(url, sent.id, video=video)

        elif len(m.command) >= 2:
            query = " ".join(m.command[1:])
            file = await yt.search(query, sent.id, video=video)

        elif media:
            setattr(sent, "lang", m.lang)
            file = await tg.download(m.reply_to_message, sent)

    # 3. FINAL VALIDATION (Ensure 'file' exists for either Radio or Songs)
    if not file:
        return await sent.edit_text(m.lang["play_usage"])

    if not m.command[0] == "247": # Skip duration check for radio
        if file.duration_sec > config.DURATION_LIMIT:
            return await sent.edit_text(m.lang["play_duration_limit"].format(config.DURATION_LIMIT // 60))

    if await db.is_logger():
        await utils.play_log(m, file.title, file.duration)

    file.user = mention
    if force:
        queue.force_add(m.chat.id, file)
    else:
        position = queue.add(m.chat.id, file)
        if await db.get_call(m.chat.id):
            await sent.edit_text(
                m.lang["play_queued"].format(position, file.url, file.title, file.duration, m.from_user.mention),
                reply_markup=buttons.play_queued(m.chat.id, file.id, m.lang["play_now"]),
            )
            return

    # 4. DOWNLOAD (Only for YouTube, skipped for Radio)
    if not file.file_path:
        await sent.edit_text(m.lang["play_downloading"])
        file.file_path = await yt.download(file.id, video=video)

    # 5. START STREAM
    await anon.play_media(chat_id=m.chat.id, message=sent, media=file)

    if tracks:
        added = playlist_to_queue(m.chat.id, tracks)
        await app.send_message(
            chat_id=m.chat.id,
            text=m.lang["playlist_queued"].format(len(tracks)) + added,
        )