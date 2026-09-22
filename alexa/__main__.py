# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of Alexa Music

import asyncio
import importlib
from aiohttp import web # <--- 1. Import web module
from pyrogram import idle

from alexa import (player, app, config, db,
                   logger, stop, userbot, yt)
from alexa.plugins import all_modules

# --- 2. Define the Fake Health Route ---
async def health_check(request):
    return web.Response(text="Alive")

async def start_health_server():
    # Create a simple web app
    server = web.Application()
    server.router.add_get("/", health_check)
    server.router.add_get("/health", health_check)
    
    # Create the runner
    runner = web.AppRunner(server)
    await runner.setup()
    
    # Listen on port (Hugging Face Default is 7860)
    site = web.TCPSite(runner, "0.0.0.0", config.PORT)
    await site.start()
    logger.info(f"Health Server started on port {config.PORT}")
# ---------------------------------------

async def net_probe():
    import socket
    import time
    
    logger.info("Verifying global DNS resolution (google.com)...")
    try:
        ip = socket.gethostbyname("google.com")
        logger.info(f"✅ Global DNS is working. google.com -> {ip}")
    except Exception as e:
        logger.error(f"❌ GLOBAL DNS FAILURE: {e}")

    if config.PROXY:
        p = config.PROXY
        logger.info(f"Checking Proxy Connectivity to {p['hostname']}:{p['port']}...")
        
        # DNS Retry Loop
        resolved_ip = None
        for i in range(3):
            try:
                logger.info(f"Resolving DNS for {p['hostname']} (Attempt {i+1}/3)...")
                resolved_ip = socket.gethostbyname(p['hostname'].strip())
                logger.info(f"✅ DNS Resolved {p['hostname']} to {resolved_ip}")
                break
            except Exception as e:
                logger.warning(f"DNS Attempt {i+1} failed: {e}")
                if i < 2: time.sleep(2)
        
        if resolved_ip:
            try:
                socket.create_connection((resolved_ip, p['port']), timeout=10).close()
                logger.info("✅ Proxy server is reachable.")
            except Exception as e:
                logger.error(f"❌ Proxy connection failed: {e}")
        else:
            logger.error("❌ Proxy hostname could not be resolved after 3 attempts.")
            
    logger.info("Checking connection to Telegram (149.154.167.51:443)...")
    try:
        socket.create_connection(("149.154.167.51", 443), timeout=5).close()
        logger.info("✅ Telegram is reachable directly.")
    except Exception as e:
        logger.warning(f"⚠️ Telegram is NOT reachable directly: {e}")

async def main():
    await start_health_server() # Ensure HF sees port 7860 early
    await net_probe()
    await db.connect()
    await app.boot()
    await userbot.boot()
    await player.boot()

    # --- 3. Start the Fake Server ---

    # --------------------------------

    for module in all_modules:
        importlib.import_module(f"alexa.plugins.{module}")
    logger.info(f"Loaded {len(all_modules)} modules.")

    if config.COOKIES_URL:
        await yt.save_cookies(config.COOKIES_URL)

    sudoers = await db.get_sudoers()
    app.sudoers.update(sudoers)
    app.bl_users.update(await db.get_blacklisted())
    logger.info(f"Loaded {len(app.sudoers)} sudo users.")

    await idle()
    await stop()


if __name__ == "__main__":
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except KeyboardInterrupt:
        pass