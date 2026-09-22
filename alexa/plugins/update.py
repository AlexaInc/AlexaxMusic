# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of Alexa Music


import os
import sys
import asyncio
import subprocess

from pyrogram import filters, types

from alexa import app, lang, stop


@app.on_message(filters.command(["update"]) & app.sudoers)
@lang.language()
async def update_bot(_, m: types.Message):
    sent = await m.reply_text("Updating... please wait.")
    
    try:
        # Pull from the repository
        # Use git to pull latest changes
        out = subprocess.check_output(
            ["git", "pull", "https://github.com/AlexaInc/AlexaxMusic.git", "master"],
            stderr=subprocess.STDOUT,
        )
        out = out.decode("utf-8")
        
        if "Already up to date." in out:
            return await sent.edit_text("Bot is already up to date.")
            
        await sent.edit_text(f"Updated successfully!\n\n<code>{out[:1000]}</code>\n\nRestarting...")
    except Exception as e:
        return await sent.edit_text(f"Update failed!\n\nError: <code>{str(e)}</code>")

    # Restarting the bot
    await asyncio.sleep(2)
    asyncio.create_task(stop())
    await asyncio.sleep(2)

    try: os.remove("log.txt")
    except: pass

    os.execl(sys.executable, sys.executable, "-m", "alexa")
