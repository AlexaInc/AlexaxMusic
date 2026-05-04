from ntgcalls import ConnectionNotFound, TelegramServerError
from pyrogram.errors import MessageIdInvalid
from pyrogram.types import InputMediaPhoto, Message
from pytgcalls import PyTgCalls, exceptions, filters, types
from pytgcalls.pytgcalls_session import PyTgCallsSession
from pytgcalls.types import VideoQuality

# TRICKY HACK: Override SD_360p value to be 240p and alias it.
# This bypasses strict type-checking in pytgcalls (NewVideoQuality class was rejected).
if hasattr(VideoQuality, "SD_360p"):
    VideoQuality.SD_360p._value_ = (426, 240, 30)
    VideoQuality.SD_240p = VideoQuality.SD_360p

import anony.core.youtube as yt

from anony import app, config, db, lang, logger, queue, userbot, yt
from anony.helpers import Media, Track, buttons, thumb

# --- MONKEY PATCH: Bypass PyTgCalls FFprobe timeout for TV/Live streams ---
import pytgcalls.ffmpeg
import pytgcalls.types.stream.media_stream
import asyncio

_original_check_stream = pytgcalls.types.stream.media_stream.check_stream

async def _fast_check_stream(file_path: str, *args, **kwargs):
    if "live365" in str(file_path) or "m3u8" in str(file_path).lower() or ".mpd" in str(file_path).lower():
        from pytgcalls.exceptions import LiveStreamFound
        logger.warning(f"[FFPROBE FAST PASS] Forcing LiveStreamFound for {file_path}")
        raise LiveStreamFound("Bypassed Stream Check for Live Media")
    
    return await _original_check_stream(file_path, *args, **kwargs)

pytgcalls.types.stream.media_stream.check_stream = _fast_check_stream
pytgcalls.ffmpeg.check_stream = _fast_check_stream
# --------------------------------------------------------------------------




class TgCall(PyTgCalls):
    def __init__(self):
        self.clients = []

    async def pause(self, chat_id: int) -> bool:
        client = await db.get_assistant(chat_id)
        await db.playing(chat_id, paused=True)
        return await client.pause(chat_id)

    async def resume(self, chat_id: int) -> bool:
        client = await db.get_assistant(chat_id)
        await db.playing(chat_id, paused=False)
        return await client.resume(chat_id)

    async def stop(self, chat_id: int) -> None:
        client = await db.get_assistant(chat_id)
        try:
            queue.clear(chat_id)
            await db.remove_call(chat_id)
        except:
            pass

        try:
            await client.leave_call(chat_id, close=False)
        except:
            pass


    async def play_media(
        self,
        chat_id: int,
        message: Message,
        media: Media | Track,
        seek_time: int = 0,
    ) -> None:
        client = await db.get_assistant(chat_id)
        _lang = await lang.get_lang(chat_id)
        _thumb = (
            await thumb.generate(media)
            if isinstance(media, Track)
            else config.DEFAULT_THUMB
        )

        if not media.file_path:
            return await message.edit_text(_lang["error_no_file"].format(config.SUPPORT_CHAT))

        media_headers = getattr(media, "headers", None)
        
        media_ffmpeg = getattr(media, "ffmpeg_parameters", "")
        final_ffmpeg = f"-ss {seek_time}" if seek_time > 1 else ""
        if media_ffmpeg:
            final_ffmpeg = f"{media_ffmpeg} {final_ffmpeg}".strip()
        if not final_ffmpeg:
            final_ffmpeg = None

        a_flag = types.MediaStream.Flags.REQUIRED
        v_flag = (
            types.MediaStream.Flags.REQUIRED
            if getattr(media, "id", "") == "tv_live"
            else (types.MediaStream.Flags.AUTO_DETECT if media.video else types.MediaStream.Flags.IGNORE)
        )
        logger.info(f"[TV_DEBUG] stream_type is: {getattr(media, 'stream_type', 'none')}")
        logger.info(f"[TV_DEBUG] Setting audio_flags to: {a_flag}, video_flags to: {v_flag}")

        stream = types.MediaStream(
            media_path=media.file_path,
            audio_parameters=types.AudioQuality.LOW,
            video_parameters=VideoQuality.SD_240p,
            audio_flags=a_flag,
            video_flags=v_flag,
            ffmpeg_parameters=final_ffmpeg,
            headers=media_headers
        )
        retry_count = 2
        for attempt in range(retry_count):
            try:
                if await db.get_call(chat_id):
                    await client.change_stream(
                        chat_id=chat_id,
                        stream=stream,
                    )
                else:
                    await client.play(
                        chat_id=chat_id,
                        stream=stream,
                        config=types.GroupCallConfig(auto_start=False),
                    )
                break # Success
            except Exception as e:
                if attempt == retry_count - 1:
                    raise e # Re-raise on last attempt
                logger.warning(f"Playback attempt {attempt+1} failed for {chat_id}: {e}. Retrying...")
                await asyncio.sleep(2)
            if not seek_time:
                media.time = 1
                await db.add_call(chat_id)
                text = _lang["play_media"].format(
                    media.url,
                    media.title,
                    media.duration,
                    media.user,
                )
                keyboard = buttons.controls(chat_id)
                try:
                    await message.edit_media(
                        media=InputMediaPhoto(
                            media=_thumb,
                            caption=text,
                        ),
                        reply_markup=keyboard,
                    )
                except MessageIdInvalid:
                    media.message_id = (await app.send_photo(
                        chat_id=chat_id,
                        photo=_thumb,
                        caption=text,
                        reply_markup=keyboard,
                    )).id
        except FileNotFoundError:
            await message.edit_text(_lang["error_no_file"].format(config.SUPPORT_CHAT))
            await self.play_next(chat_id)
        except exceptions.NoActiveGroupCall:
            await self.stop(chat_id)
            await message.edit_text(_lang["error_no_call"])
        except exceptions.NoAudioSourceFound:
            await message.edit_text(_lang["error_no_audio"])
            await self.play_next(chat_id)
        except (ConnectionNotFound, TelegramServerError):
            await self.stop(chat_id)
            await message.edit_text(_lang["error_tg_server"])


    async def replay(self, chat_id: int) -> None:
        if not await db.get_call(chat_id):
            return

        media = queue.get_current(chat_id)
        _lang = await lang.get_lang(chat_id)
        msg = await app.send_message(chat_id=chat_id, text=_lang["play_again"])
        await self.play_media(chat_id, msg, media)


    async def play_next(self, chat_id: int) -> None:
        if not await db.get_call(chat_id):
            return

        media = queue.get_next(chat_id)
        try:
            if media.message_id:
                await app.delete_messages(
                    chat_id=chat_id,
                    message_ids=media.message_id,
                    revoke=True,
                )
                media.message_id = 0
        except:
            pass

        if not media:
            return await self.stop(chat_id)

        _lang = await lang.get_lang(chat_id)
        msg = await app.send_message(chat_id=chat_id, text=_lang["play_next"])
        if not media.file_path:
            media.file_path = await yt.download(media.id, video=media.video)
            if not media.file_path:
                await self.stop(chat_id)
                return await msg.edit_text(
                    _lang["error_no_file"].format(config.SUPPORT_CHAT)
                )

        media.message_id = msg.id
        await self.play_media(chat_id, msg, media)


    async def ping(self) -> float:
        pings = [client.ping for client in self.clients]
        return round(sum(pings) / len(pings), 2)


    async def decorators(self, client: PyTgCalls) -> None:
        for client in self.clients:

            @client.on_update()
            async def update_handler(_, update: types.Update) -> None:
                if isinstance(update, types.StreamEnded):
                    if update.stream_type == types.StreamEnded.Type.AUDIO:
                        media = queue.get_current(update.chat_id)
                        if getattr(media, "id", "") == "tv_live":
                            # Silently retry TV stream once if it ends
                            logger.info(f"[TV_RECONNECT] Stream ended for {update.chat_id}, retrying...")
                            try:
                                # We need a dummy message or use the existing one if available
                                # For now, just call play_next which will handle it, 
                                # but play_next might skip to next. 
                                # Since TV is usually one item, it might just restart or stop.
                                await self.play_next(update.chat_id)
                            except Exception as e:
                                logger.error(f"[TV_RECONNECT] Retry failed: {e}")
                        else:
                            await self.play_next(update.chat_id)
                elif isinstance(update, types.ChatUpdate):
                    if update.status in [
                        types.ChatUpdate.Status.KICKED,
                        types.ChatUpdate.Status.LEFT_GROUP,
                        types.ChatUpdate.Status.CLOSED_VOICE_CHAT,
                    ]:
                        await self.stop(update.chat_id)


    async def boot(self) -> None:
        PyTgCallsSession.notice_displayed = True
        for ub in userbot.clients:
            client = PyTgCalls(ub, cache_duration=20)
            await client.start()
            self.clients.append(client)
            await self.decorators(client)
        logger.info("PyTgCalls client(s) started.")
