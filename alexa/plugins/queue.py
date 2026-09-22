# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of Alexa Music

from pyrogram import filters, types
from alexa import app, config, db, lang, queue
from alexa.helpers import Track, buttons, thumb

@app.on_message(filters.command(["queue", "playing"]) & filters.group & ~app.bl_users)
@lang.language()
async def _queue_func(_, m: types.Message):
    if not await db.get_call(m.chat.id):
        return await m.reply_text(m.lang["not_playing"])

    _reply = await m.reply_text(m.lang["queue_fetching"])
    _queue = queue.get_queue(m.chat.id)
    
    if not _queue:
        return await _reply.edit_text("The queue is currently empty.")

    _media = _queue[0]
    
    # --- FIX FOR RADIO QUEUE ---
    # Check if it is a Radio stream (duration is "Live")
    is_radio = getattr(_media, "duration", "") == "Live"

    _thumb = config.DEFAULT_THUMB
    if not is_radio and isinstance(_media, Track):
        try:
            _thumb = await thumb.generate(_media)
        except Exception:
            _thumb = config.DEFAULT_THUMB
    # --- END FIX ---

    _text = m.lang["queue_curr"].format(
        _media.url,
        _media.title[:50],
        _media.duration,
        _media.user,
    )
    
    # Create a copy to show the rest of the queue
    _temp_queue = list(_queue)
    _temp_queue.pop(0)

    if _temp_queue:
        _text += "<blockquote expandable>"
        for i, media in enumerate(_temp_queue, start=1):
            if i == 15:
                break
            _text += m.lang["queue_item"].format(
                i + 1, media.title, media.duration
            )
        _text += "</blockquote>"

    _playing = await db.playing(m.chat.id)
    
    try:
        await _reply.edit_media(
            media=types.InputMediaPhoto(
                media=_thumb,
                caption=_text,
            ),
            reply_markup=buttons.queue_markup(
                m.chat.id,
                m.lang["playing"] if _playing else m.lang["paused"],
                _playing,
            ),
        )
    except Exception as e:
        # Fallback to text if photo editing fails on your low-RAM VPS
        await _reply.edit_text(_text)