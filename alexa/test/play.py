# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of Alexa Music

from pathlib import Path
from pyrogram import filters, types
from alexa import player, app, config, db, lang, queue, tg, yt
from alexa.helpers import buttons, utils
from alexa.helpers._play import checkUB
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from alexa.helpers.radio import radio_markup



def tv_markup():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📺 Hiru TV", callback_data="tv_1"),
            InlineKeyboardButton("📺 kiddo", callback_data="tv_2"),
            InlineKeyboardButton("📺 Horror TV", callback_data="tv_3")
        ],
        [
            InlineKeyboardButton("📺 BEST ACTION TV", callback_data="tv_4"),
            InlineKeyboardButton("📺 Swarnawahini", callback_data="tv_5"),
            InlineKeyboardButton("📺 Cartoon TV", callback_data="tv_6")
        ],
        [
            InlineKeyboardButton("📺 JTBC", callback_data="tv_7"),
            InlineKeyboardButton("📺 TVN", callback_data="tv_8"),
            InlineKeyboardButton("📺 KRCN", callback_data="tv_9")
        ],
        [InlineKeyboardButton("❌ Close Menu", callback_data="help close")]
    ])

def playlist_to_queue(chat_id: int, tracks: list) -> str:
    text = "<blockquote expandable>"
    for track in tracks:
        pos = queue.add(chat_id, track)
        text += f"<b>{pos}.</b> {track.title}\n"
    text = text[:1948] + "</blockquote>"
    return text


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
    # We accept force, video, and url to stop the TypeError, 
    # but we only need 'm' to send the button menu.
    await m.reply_text(
        "📻 <b>Sri Lanka Live Radio Menu</b>\nSelect a station below to start streaming 24/7:",
        reply_markup=radio_markup(1)
    )



@app.on_message(filters.command("tv") & filters.group & ~app.bl_users)
@lang.language()
@checkUB
async def radio_command_handler(
    _, 
    m: types.Message, 
    force: bool = False, 
    video: bool = False, 
    url: str = None
):
    # We ignore force, video, and url because it's a radio command, 
    # but we must include them in the arguments to avoid the error.
    await m.reply_text(
        "📺 <b>TV Station Selection</b>\nChoose a station to start streaming 24/7:",
        reply_markup=tv_markup()
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
        
        class RadioMedia:
            def __init__(self):
                self.id = "nuwaav_radio"
                self.title = "NuWaaV Radio (K-Pop 24/7)"
                self.duration = "Live"
                self.duration_sec = 0  # Pass limit checks
                self.url = "https://nuwaavradio.com/"
                self.file_path = "https://streaming.live365.com/a46701"
                self.video = False
                self.user = mention
                self.message_id = sent.id

        file = RadioMedia()
    
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
    await player.play_media(chat_id=m.chat.id, message=sent, media=file)

    if tracks:
        added = playlist_to_queue(m.chat.id, tracks)
        await app.send_message(
            chat_id=m.chat.id,
            text=m.lang["playlist_queued"].format(len(tracks)) + added,
        )