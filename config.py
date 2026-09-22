import logging
from os import getenv
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def env_bool(name: str, default: bool = False) -> bool:
    value = getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    def __init__(self):
        self.PORT = int(getenv("PORT", 7860))
        self.API_ID = int(getenv("API_ID", 0))
        self.API_HASH = getenv("API_HASH")

        self.BOT_TOKEN = getenv("BOT_TOKEN")
        self.MONGO_URL = getenv("MONGO_URL")
        self.MONGO_DB_NAME = getenv("MONGO_DB_NAME", "Alexa")

        self.LOGGER_ID = int(getenv("LOGGER_ID", 0))
        self.OWNER_ID = int(getenv("OWNER_ID", 0))

        self.DURATION_LIMIT = int(getenv("DURATION_LIMIT", 60)) * 60
        self.QUEUE_LIMIT = int(getenv("QUEUE_LIMIT", 20))
        self.PLAYLIST_LIMIT = int(getenv("PLAYLIST_LIMIT", 20))

        self.SESSION1 = getenv("SESSION", None)
        self.SESSION2 = getenv("SESSION2", None)
        self.SESSION3 = getenv("SESSION3", None)

        self.SUPPORT_CHANNEL = getenv("SUPPORT_CHANNEL", "https://t.me/AlexaInc_updates")
        self.SUPPORT_CHAT = getenv("SUPPORT_CHAT", "https://t.me/+_9LokVOOdrdlOGQ1")

        self.AUTO_END = env_bool("AUTO_END", False)
        self.AUTO_LEAVE = env_bool("AUTO_LEAVE", False)
        self.VIDEO_PLAY = env_bool("VIDEO_PLAY", True)

        # Legacy compatibility only. New deployments should use COOKIES_URLS,
        # which is consumed directly by the ytdlgo 1.0.0 binary.
        legacy_cookie_urls = getenv("COOKIES_URL", "").replace(",", " ")
        self.COOKIES_URL = [url for url in legacy_cookie_urls.split() if url]
        self.DEFAULT_THUMB = getenv("DEFAULT_THUMB", "https://te.legra.ph/file/3e40a408286d4eda24191.jpg")
        self.PING_IMG = getenv("PING_IMG", "https://files.catbox.moe/haagg2.png")
        self.START_IMG = getenv("START_IMG", "https://files.catbox.moe/zvziwk.jpg")
        self.MUSIC_BOT_NAME = getenv("MUSIC_BOT_NAME", "Alexa Music")
        
        # Proxy Support
        self.PROXY_URL = getenv("PROXY_URL")
        if self.PROXY_URL:
            self.PROXY_URL = self.PROXY_URL.strip().strip("'").strip('"')
            
        self.PROXY = self._parse_proxy(self.PROXY_URL)

    def _parse_proxy(self, proxy_url: str | None) -> dict | None:
        if not proxy_url:
            return None
        
        try:
            from urllib.parse import urlparse
            parsed = urlparse(proxy_url)
            scheme = parsed.scheme.lower()
            
            if scheme not in ["http", "socks4", "socks5"]:
                logger.warning(f"Invalid proxy scheme: {scheme}")
                return None
            
            res = {
                "scheme": scheme,
                "hostname": parsed.hostname,
                "port": parsed.port,
            }
            if parsed.username:
                res["username"] = parsed.username
            if parsed.password:
                res["password"] = parsed.password
                
            logger.info(f"Proxy configuration parsed for {scheme}://{parsed.hostname}:{parsed.port}")
            return res
        except Exception as e:
            logger.error(f"Error parsing PROXY_URL: {e}")
            return None

    def check(self):
        missing = [
            var
            for var in ["API_ID", "API_HASH", "BOT_TOKEN", "MONGO_URL", "LOGGER_ID", "OWNER_ID", "SESSION1"]
            if not getattr(self, var)
        ]
        if missing:
            raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")
