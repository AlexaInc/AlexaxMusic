import asyncio
from pyrogram import enums, errors, types
from alexa import app, config, db, queue, yt

def checkUB(play):
    async def wrapper(_, m: types.Message):
        if not m.from_user:
            return await m.reply_text(m.lang["play_user_invalid"])

        chat_id = m.chat.id
        if m.chat.type != enums.ChatType.SUPERGROUP:
            await m.reply_text(m.lang["play_chat_invalid"])
            return await app.leave_chat(chat_id)

        # Bypass argument check if the command is 'radio'
        if not m.reply_to_message and m.command[0] not in ["radio", "tv"] and (
            len(m.command) < 2 or (len(m.command) == 2 and m.command[1] == "-f")
        ):
            return await m.reply_text(m.lang["play_usage"])

        if len(queue.get_queue(chat_id)) >= config.QUEUE_LIMIT:
            return await m.reply_text(m.lang["play_queue_full"].format(config.QUEUE_LIMIT))

        force = m.command[0].endswith("force") or (len(m.command) > 1 and "-f" in m.command[1])
        video = m.command[0][0] == "v" and config.VIDEO_PLAY
        url = yt.url(m) if m.command[0] not in ["radio", "tv"] else None
        
        if url and not yt.valid(url):
            return await m.reply_text(m.lang["play_unsupported"])

        play_mode = await db.get_play_mode(chat_id)
        if play_mode or force:
            adminlist = await db.get_admins(chat_id)
            if m.from_user.id not in adminlist and not await db.is_auth(chat_id, m.from_user.id) and not m.from_user.id in app.sudoers:
                return await m.reply_text(m.lang["play_admin"])

        if chat_id not in db.active_calls:
            client = await db.get_client(chat_id)
            try:
                member = await app.get_chat_member(chat_id, client.id)
                if member.status in [enums.ChatMemberStatus.BANNED, enums.ChatMemberStatus.RESTRICTED]:
                    try: await app.unban_chat_member(chat_id=chat_id, user_id=client.id)
                    except: return await m.reply_text(m.lang["play_banned"].format(app.name, client.id, client.mention, f"@{client.username}" if client.username else None))
            except errors.ChatAdminRequired: return await m.reply_text(m.lang["admin_required"])
            except errors.UserNotParticipant:
                invite_link = m.chat.username if m.chat.username else (await app.get_chat(chat_id)).invite_link
                if not invite_link: invite_link = await app.export_chat_invite_link(chat_id)
                umm = await m.reply_text(m.lang["play_invite"].format(app.name))
                await asyncio.sleep(2)
                try: await client.join_chat(invite_link)
                except: pass
                await umm.delete()

        return await play(_, m, force, video, url)
    return wrapper