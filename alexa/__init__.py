# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of Alexa Music


import os
import time
import logging
from os import getenv
from logging.handlers import RotatingFileHandler

# Early Proxy Injection
PROXY_URL = getenv("PROXY_URL")
if PROXY_URL:
    PROXY_URL = PROXY_URL.strip().strip("'").strip('"')
    os.environ["http_proxy"] = PROXY_URL
    os.environ["https_proxy"] = PROXY_URL
    os.environ["all_proxy"] = PROXY_URL

logging.basicConfig(
    format="[%(asctime)s - %(levelname)s] - %(name)s: %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        RotatingFileHandler("log.txt", maxBytes=10485760, backupCount=5),
        logging.StreamHandler(),
    ],
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("ntgcalls").setLevel(logging.CRITICAL)
logging.getLogger("pymongo").setLevel(logging.ERROR)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("pytgcalls").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

# Log Global Proxy Injection (if any)
if PROXY_URL:
    logger.info(f"Global Proxy Injected: {PROXY_URL.split('@')[-1]}")

__version__ = "3.1.0"

from config import Config

config = Config()
config.check()
tasks = []
boot = time.time()

from alexa.core.bot import Bot
app = Bot()

from alexa.core.dir import ensure_dirs
ensure_dirs()

from alexa.core.userbot import Userbot
userbot = Userbot()

from alexa.core.mongo import MongoDB
db = MongoDB()

from alexa.core.lang import Language
lang = Language()

from alexa.core.telegram import Telegram
from alexa.core.youtube import YouTube
tg = Telegram()
yt = YouTube()

from alexa.helpers import Queue
queue = Queue()

from alexa.core.calls import TgCall
player = TgCall()


async def stop() -> None:
    logger.info("Stopping...")
    for task in tasks:
        task.cancel()
        try:
            await task
        except:
            pass

    await app.exit()
    await userbot.exit()
    await db.close()

    logger.info("Stopped.\n")
