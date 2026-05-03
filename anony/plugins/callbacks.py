# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic


import re

from pyrogram import filters, types

from anony import anon, app, db, lang, queue, tg, yt
from anony.helpers import admin_check, buttons, can_manage_vc
from anony.helpers.radio import radio_markup

@app.on_callback_query(filters.regex("cancel_dl") & ~app.bl_users)
@lang.language()
async def cancel_dl(_, query: types.CallbackQuery):
    await query.answer()
    await tg.cancel(query)


@app.on_callback_query(filters.regex("controls") & ~app.bl_users)
@lang.language()
@can_manage_vc
async def _controls(_, query: types.CallbackQuery):
    args = query.data.split()
    action, chat_id = args[1], int(args[2])
    qaction = len(args) == 4
    user = query.from_user.mention

    if not await db.get_call(chat_id):
        return await query.answer(query.lang["not_playing"], show_alert=True)

    if action == "status":
        return await query.answer()
    await query.answer(query.lang["processing"], show_alert=True)

    if action == "pause":
        if not await db.playing(chat_id):
            return await query.answer(
                query.lang["play_already_paused"], show_alert=True
            )
        await anon.pause(chat_id)
        if qaction:
            return await query.edit_message_reply_markup(
                reply_markup=buttons.queue_markup(chat_id, query.lang["paused"], False)
            )
        status = query.lang["paused"]
        reply = query.lang["play_paused"].format(user)

    elif action == "resume":
        if await db.playing(chat_id):
            return await query.answer(query.lang["play_not_paused"], show_alert=True)
        await anon.resume(chat_id)
        if qaction:
            return await query.edit_message_reply_markup(
                reply_markup=buttons.queue_markup(chat_id, query.lang["playing"], True)
            )
        reply = query.lang["play_resumed"].format(user)

    elif action == "skip":
        await anon.play_next(chat_id)
        status = query.lang["skipped"]
        reply = query.lang["play_skipped"].format(user)

    elif action == "force":
        pos, media = queue.check_item(chat_id, args[3])
        if not media or pos == -1:
            return await query.edit_message_text(query.lang["play_expired"])

        m_id = queue.get_current(chat_id).message_id
        queue.force_add(chat_id, media, remove=pos)
        try:
            await app.delete_messages(
                chat_id=chat_id, message_ids=[m_id, media.message_id], revoke=True
            )
            media.message_id = None
        except:
            pass

        msg = await app.send_message(chat_id=chat_id, text=query.lang["play_next"])
        if not media.file_path:
            media.file_path = await yt.download(media.id, video=media.video)
        media.message_id = msg.id
        return await anon.play_media(chat_id, msg, media)

    elif action == "replay":
        media = queue.get_current(chat_id)
        media.user = user
        await anon.replay(chat_id)
        status = query.lang["replayed"]
        reply = query.lang["play_replayed"].format(user)

    elif action == "stop":
        await anon.stop(chat_id)
        status = query.lang["stopped"]
        reply = query.lang["play_stopped"].format(user)

    try:
        if action in ["skip", "replay", "stop"]:
            await query.message.reply_text(reply, quote=False)
            await query.message.delete()
        else:
            mtext = re.sub(
                r"\n\n<blockquote>.*?</blockquote>",
                "",
                query.message.caption.html or query.message.text.html,
                flags=re.DOTALL,
            )
            keyboard = buttons.controls(
                chat_id, status=status if action != "resume" else None
            )
        await query.edit_message_text(
            f"{mtext}\n\n<blockquote>{reply}</blockquote>", reply_markup=keyboard
        )
    except:
        pass


@app.on_callback_query(filters.regex("help") & ~app.bl_users)
@lang.language()
async def _help(_, query: types.CallbackQuery):
    data = query.data.split()
    if len(data) == 1:
        return await query.answer(url=f"https://t.me/{app.username}?start=help")

    if data[1] == "back":
        return await query.edit_message_text(
            text=query.lang["help_menu"], reply_markup=buttons.help_markup(query.lang)
        )
    elif data[1] == "close":
        try:
            await query.message.delete()
            return await query.message.reply_to_message.delete()
        except:
            pass

    await query.edit_message_text(
        text=query.lang[f"help_{data[1]}"],
        reply_markup=buttons.help_markup(query.lang, True),
    )



@app.on_callback_query(filters.regex(r"^radio_") & ~app.bl_users)
@lang.language()
async def radio_callback_handler(_, query: types.CallbackQuery):
    data = query.data
    chat_id = query.message.chat.id
    user_mention = query.from_user.mention

    if data.startswith("radio_page_"):
        page = int(data.split("_")[2])
        return await query.edit_message_reply_markup(reply_markup=radio_markup(page))

    links = {
        "radio_1": ("Hiru FM", "https://radio.lotustechnologieslk.net:2020/stream/hirufmgarden"),
        "radio_2": ("Shaa FM", "https://radio.lotustechnologieslk.net:2020/stream/shaafmgarden"),
        "radio_3": ("FM Derana", "https://cp12.serverse.com/proxy/fmderana/stream"),
        "radio_4": ("ITN FM", "https://cp12.serverse.com/proxy/itnfm?mp=/stream"),
        "radio_5": ("Rhythm FM", "https://dc02.onlineradio.voaplus.com/rhythmfm"),
        "radio_6": ("NuWaaV K-Pop", "https://streaming.live365.com/a46701"),
        "radio_7": ("Sirasa FM", "http://live.trusl.com:1170/listen.pls"),
        "radio_8": ("Kiss FM", "https://srv01.onlineradio.voaplus.com/kissfm"),
        "radio_9": ("Lakhada FM", "https://cp12.serverse.com/proxy/itnfm?mp=/stream"),
        "radio_10": ("ABC Gold FM", "https://radio.lotustechnologieslk.net:8000/stream/1/"),
        "radio_11": ("bestcoast.fm", "https://streams.radio.co/sea5dddd6b/listen"),
        "radio_12": ("Bathusha Radio", "https://eu10.fastcast4u.com:14550/stream"),
        "radio_13": ("E FM", "http://207.148.74.192:7860/stream.mp3"),
        "radio_14": ("Fox", "https://cp11.serverse.com/proxy/foxfm/stream/;stream.mp3"),
        "radio_15": ("Freefm.lk", "https://stream.zeno.fm/z7q96fbw7rquv"),
        "radio_16": ("Imai FM Radio", "https://centova71.instainternet.com/proxy/imaifmradio?mp=/stream/1/"),
        "radio_17": ("Krushi Radio", "https://radioserver.krushiradio.lk:8000/radio.mp3"),
        "radio_18": ("Lite FM", "https://srv01.onlineradio.voaplus.com/lite878"),
        "radio_19": ("LiveFM", "https://cp11.serverse.com/proxy/livefm?mp=/stream"),
        "radio_20": ("Neth FM", "http://cp11.serverse.com:7669/stream/1/"),
        "radio_21": ("Ran FM", "http://207.148.74.192:7860/ran.mp3"),
        "radio_22": ("Rangiri Sri Lanka Radio", "https://rangiri.radioca.st/stream/1/"),
        "radio_23": ("Rasa FM", "https://sonic01.instainternet.com/8084/stream"),
        "radio_24": ("Real Radio", "https://srv01.onlineradio.voaplus.com/realfm"),
        "radio_25": ("Shakthi FM", "http://live.trusl.com:1160/stream/1/"),
        "radio_26": ("Red FM", "https://shaincast.caster.fm:47830/listen.mp3"),
        "radio_27": ("Shraddha Radio", "https://cp11.serverse.com/proxy/kqxjpewq?mp=/stream/1/"),
        "radio_28": ("Shree FM", "http://207.148.74.192:7860/stream2.mp3"),
        "radio_29": ("Siyatha FM", "https://dc02.onlineradio.voaplus.com/siyathafm"),
        "radio_30": ("Sitha FM", "https://shaincast.caster.fm:48148/listen.mp3"),
        "radio_31": ("SLBC City FM", "https://stream.zeno.fm/53g2h8033d0uv"),
        "radio_32": ("SLBC Kandurata FM", "http://220.247.227.20:8000/kandystream"),
        "radio_33": ("SLBC Radio Sri Lanka", "http://220.247.227.20:8000/RSLstream"),
        "radio_34": ("SLBC Tamil National Service", "http://220.247.227.6:8000/Tnsstream"),
        "radio_35": ("SLBC Sinhala Commercial Service", "https://stream.zeno.fm/fkq6fvc43d0uv.aac"),
        "radio_36": ("SLBC Thendral FM", "http://220.247.227.20:8000/Threndralstream"),
        "radio_37": ("Sun FM", "https://radio.lotustechnologieslk.net:2020/stream/sunfmgarden/stream/1/"),
        "radio_38": ("SLCB Sinhala National Service", "http://220.247.227.6:8000/Snsstream"),
        "radio_39": ("Sooriyan FM", "https://radio.lotustechnologieslk.net:2020/stream/sooriyanfmgarden/stream/1/"),
        "radio_40": ("V FM Radio", "https://dc1.serverse.com/proxy/fmlanka/stream/1/"),
        "radio_41": ("Vasantham", "https://cp12.serverse.com/proxy/vasanthamfm/stream/1/"),
        "radio_42": ("Yes FM", "http://live.trusl.com:1150/stream/1/"),
        "radio_43": ("Waharaka Radio", "http://s6.voscast.com:8112/stream/1/"),
        "radio_44": ("Y FM", "https://mbc.thestreamtech.com:7032/")
    }

    if data not in links: 
        return await query.answer("Station Not Found!")

    name, radio_url = links[data]
    await query.answer(f"Switching to {name}...", show_alert=False)

    from anony.helpers import Track
    from anony import config
    
    media_obj = Track(
        id="radio_live",
        channel_name="Live Radio",
        duration="Live",
        duration_sec=0,
        title=f"Radio: {name}",
        url=radio_url,
        file_path=radio_url,
        message_id=query.message.id,
        thumbnail=config.DEFAULT_THUMB,
        user=user_mention,
        view_count="Live",
        video=False
    )
    media_obj.stream_type = "live"

    try:
        # Switch the stream
        await anon.play_media(chat_id=chat_id, message=query.message, media=media_obj)
        queue.force_add(chat_id, media_obj)
        # Edit the message text while keeping the persistent buttons
        await query.edit_message_text(
            f"📡 <b>Now Streaming:</b> <code>{name}</code>\n"
            f"👤 <b>Requested by:</b> {user_mention}\n\n"
            "<i>Select another station to switch or use /stop to end.</i>",
            reply_markup=query.message.reply_markup
        )
    except Exception as e:
        await query.message.reply_text(f"❌ <b>Error:</b> <code>{e}</code>")








from anony.helpers.tv import category_markup, channel_markup, fetch_stream_url, fetch_channels

@app.on_callback_query(filters.regex("tv_home") & ~app.bl_users)
@lang.language()
async def tv_home_callback(_, query: types.CallbackQuery):
    await query.answer("Fetching categories...")
    channels = await fetch_channels()
    await query.edit_message_text(
        "📺 <b>TV Station Categories</b>\nChoose a category to find a station:",
        reply_markup=category_markup(channels)
    )

@app.on_callback_query(filters.regex(r"^tv_cat:") & ~app.bl_users)
@lang.language()
async def tv_category_callback(_, query: types.CallbackQuery):
    category = query.data.split(":")[1]
    await query.answer(f"Fetching {category} channels...")
    channels = await fetch_channels()
    await query.edit_message_text(
        f"📺 <b>Category: {category}</b>\nChoose a station:",
        reply_markup=channel_markup(category, channels, 1)
    )

@app.on_callback_query(filters.regex(r"^tv_page:") & ~app.bl_users)
@lang.language()
async def tv_page_callback(_, query: types.CallbackQuery):
    _, category, page = query.data.split(":")
    await query.answer(f"Fetching page {page}...")
    channels = await fetch_channels()
    await query.edit_message_text(
        f"📺 <b>Category: {category}</b>\nChoose a station (Page {page}):",
        reply_markup=channel_markup(category, channels, int(page))
    )

@app.on_callback_query(filters.regex(r"^tv_ch:") & ~app.bl_users)
@lang.language()
async def tv_channel_callback(_, query: types.CallbackQuery):
    channel_id = query.data.split(":")[1]
    chat_id = query.message.chat.id
    user_mention = query.from_user.mention
    
    channels = await fetch_channels()
    target_channel = next((c for c in channels if c["id"] == channel_id), None)
    
    if not target_channel:
        return await query.answer("Unknown Station!", show_alert=True)
        
    await query.answer(f"Fetching {target_channel['title']} stream...", show_alert=False)
    
    stream_url = await fetch_stream_url(target_channel["manifest"])
    if not stream_url:
        return await query.message.reply_text("❌ Failed to fetch the stream URL. Please try again later.")

    from anony.helpers import Track
    from anony import config
    
    media_obj = Track(
        id="tv_live",
        channel_name="Live TV",
        duration="Live",
        duration_sec=0,
        title=f"TV: {target_channel['title']}",
        url=stream_url,
        file_path=stream_url,
        message_id=query.message.id,
        thumbnail=target_channel.get("thumbnail") or config.DEFAULT_THUMB,
        user=user_mention,
        view_count="Live",
        video=True
    )
    # Hint to py-tgcalls for low quality if using an overloaded approach
    media_obj.stream_type = "live"
    media_obj.quality = "low"
    media_obj.ffmpeg_parameters = "-reconnect 1 -reconnect_at_eof 1 -reconnect_streamed 1 -reconnect_delay_max 2"
    media_obj.headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    }
    
    try:
        from anony import logger
        logger.info(f"📺 TV Playback URL for {target_channel['title']}: {stream_url}")

        await anon.play_media(chat_id=chat_id, message=query.message, media=media_obj)
        queue.force_add(chat_id, media_obj)
        
        await query.edit_message_text(
            f"📡 <b>Now Streaming:</b> {target_channel['title']} (Low Quality)\nRequested by: {user_mention}\n\nSelect another station to switch:",
            reply_markup=query.message.reply_markup
        )
    except Exception as e:
        await query.message.reply_text(f"❌ Error switching station: {type(e).__name__} - {e}")








@app.on_callback_query(filters.regex("settings") & ~app.bl_users)
@lang.language()
@admin_check
async def _settings_cb(_, query: types.CallbackQuery):
    cmd = query.data.split()
    if len(cmd) == 1:
        return await query.answer()
    await query.answer(query.lang["processing"], show_alert=True)

    chat_id = query.message.chat.id
    _admin = await db.get_play_mode(chat_id)
    _delete = await db.get_cmd_delete(chat_id)
    _language = await db.get_lang(chat_id)

    if cmd[1] == "delete":
        _delete = not _delete
        await db.set_cmd_delete(chat_id, _delete)
    elif cmd[1] == "play":
        await db.set_play_mode(chat_id, _admin)
        _admin = not _admin
    await query.edit_message_reply_markup(
        reply_markup=buttons.settings_markup(
            query.lang,
            _admin,
            _delete,
            _language,
            chat_id,
        )
    )
