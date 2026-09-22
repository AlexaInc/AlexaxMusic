

import os
import re
import json
import shutil
import asyncio
from urllib.parse import urljoin, urlparse

import aiohttp
from pathlib import Path
from typing import Optional, Union

from pyrogram import enums, types
from py_yt import Playlist

from alexa import config, logger
from alexa.helpers import Track, utils

# ----------------------------------------------------------------- ytdlgo 1.0.0 config
_PROJECT = Path(__file__).resolve().parents[2]


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        logger.warning("Invalid integer in %s; using %s", name, default)
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


YTDLGO_VERSION = "1.0.0"
YTDL_BIN = os.getenv("YTDL_BIN") or str(_PROJECT / "bin" / "ytdl")
YTDL_BIN_DIR = os.getenv("YTDL_BIN_DIR") or str(Path(YTDL_BIN).parent)
HF_TOKEN = os.getenv("HF_TOKEN", "")
LOCAL_DISABLED = _env_bool("YTDL_DISABLE")
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "downloads"))
AUDIO_FORMAT = os.getenv("YTDL_AUDIO_FORMAT") or os.getenv("AUDIO_FORMAT") or "native"
RETRY_CLIENTS = os.getenv("YTDL_RETRY_CLIENTS", "default,android,mweb")
FORMAT_RETRY = _env_bool("YTDL_FORMAT_RETRY", True)
COOKIELESS_RETRY = _env_bool("YTDL_COOKIELESS_RETRY", True)

# Match the proven alexa-v3 fallback chain. Set YTDL_RELAYS=none to force
# local-only mode; an empty value uses these compatible services.
_DEFAULT_RELAYS = (
    "https://absolute-vonnie-alexainc-ec756816.koyeb.app,"
    "https://hansaka1-ytdl.hf.space,"
    "https://cold-lemming-3841.alexainc.deno.net"
)
_relay_setting = os.getenv("YTDL_RELAYS", "").strip()
if _relay_setting.lower() in {"none", "off", "disabled", "0"}:
    RELAYS = []
else:
    RELAYS = [
        relay.strip().rstrip("/")
        for relay in (_relay_setting or _DEFAULT_RELAYS).split(",")
        if relay.strip()
    ]

RELAY_KEY = os.getenv("YTDL_RELAY_KEY", "")
MAX_CONCURRENT = _env_int("YTDL_CONCURRENCY", 1, 1)
COMMAND_TIMEOUT = _env_int("YTDL_COMMAND_TIMEOUT", 900, 30)
RELAY_TIMEOUT = _env_int("YTDL_RELAY_TIMEOUT", 420, 30)
BOTCHECK_BACKOFF = _env_int("YTDL_BOTCHECK_BACKOFF", 15 * 60, 0)
_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_AUDIO_EXTENSIONS = {"m4a", "mp3", "opus", "webm"}
_VIDEO_EXTENSIONS = {"mp4"}
_FORMAT_ERROR = re.compile(
    r"requested format is not available|only images are available|no video formats found",
    re.IGNORECASE,
)

HEADERS = {
    "accept": "*/*",
    "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
    "User-Agent": "AlexaMusic/ytdlgo-1.0.0",
}


def _child_env(overrides: Optional[dict[str, str]] = None) -> dict:
    """Build the environment consumed by the pinned ytdlgo CLI."""
    env = dict(os.environ)
    if YTDL_BIN_DIR:
        env["PATH"] = f"{YTDL_BIN_DIR}:{env.get('PATH', '')}"
    env.setdefault("WORK_DIR", "/tmp/ytdl-work")

    # Use the same public variable names as alexa-v3 while translating them to
    # the names consumed by the ytdlgo 1.0.0 release.
    env["AUDIO_FORMAT"] = AUDIO_FORMAT
    if env.get("YTDL_MAX_HEIGHT"):
        env["MAX_HEIGHT"] = env["YTDL_MAX_HEIGHT"]

    # Backward compatibility with this project's old, space-separated variable.
    # ytdlgo itself consumes COOKIES_URLS (comma/newline separated).
    if not env.get("COOKIES_URLS") and env.get("COOKIES_URL"):
        env["COOKIES_URLS"] = ",".join(env["COOKIES_URL"].split())

    if overrides:
        env.update({key: str(value) for key, value in overrides.items()})
    return env


class YouTube:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = re.compile(
            r"(https?://)?(www\.|m\.|music\.)?"
            r"(youtube\.com/(watch\?v=|shorts/|playlist\?list=)|youtu\.be/)"
            r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)([&?][^\s]*)?"
        )
        self._sem = asyncio.Semaphore(MAX_CONCURRENT)
        self._inflight: dict[str, asyncio.Future] = {}
        self._local_ok: Optional[bool] = None  # None = not probed yet
        self._local_until = 0.0  # backoff deadline (loop time)

    # ------------------------------------------------------------- helpers
    def valid(self, url: str) -> bool:
        return bool(re.match(self.regex, url))

    def url(self, message_1: types.Message) -> Union[str, None]:
        messages = [message_1]
        link = None
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)

        for message in messages:
            text = message.text or message.caption or ""
            if message.entities:
                for entity in message.entities:
                    if entity.type == enums.MessageEntityType.URL:
                        link = text[entity.offset : entity.offset + entity.length]
                        break
            if message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == enums.MessageEntityType.TEXT_LINK:
                        link = entity.url
                        break

        if link:
            return link.split("&si")[0].split("?si")[0]
        return None

    # ------------------------------------------------------------- search (unchanged)
    async def search(self, query: str, m_id: int, video: bool = False) -> Track | None:
        url = "https://hansaka1-ytdl.hf.space/search"
        headers = {
            "accept": "*/*",
            "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
            "origin": "https://hansaka1-ytdl.hf.space",
            "referer": "https://hansaka1-ytdl.hf.space/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        }
        for attempt in range(2):
            try:
                async with aiohttp.ClientSession(headers=headers, trust_env=False) as session:
                    async with session.post(url, json={"query": query}, timeout=aiohttp.ClientTimeout(total=25)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            results = data.get("results", [])
                            if results and isinstance(results, list):
                                item = results[0]
                                video_id = item.get("videoId")
                                if video_id:
                                    thumbnails = item.get("thumbnail", [])
                                    thumbnail_url = thumbnails[-1]["url"].split("?")[0] if thumbnails else None
                                    length_text = item.get("duration", "0:00")
                                    view_count = item.get("shortViewCount", "0 views").split(" ")[0]
                                    return Track(
                                        id=video_id,
                                        channel_name=item.get("channelName", "Unknown Channel")[:25],
                                        duration=length_text,
                                        duration_sec=utils.to_seconds(length_text),
                                        message_id=m_id,
                                        title=item.get("title", "Unknown Title")[:25],
                                        thumbnail=thumbnail_url,
                                        url=f"https://www.youtube.com/watch?v={video_id}",
                                        view_count=view_count,
                                        video=video,
                                    )
                        else:
                            logger.error(f"External Search API failed with status {resp.status} (Attempt {attempt+1})")
            except Exception as e:
                logger.error(f"Custom YouTube search attempt {attempt+1} failed: {type(e).__name__} - {e}")
                if attempt == 0:
                    await asyncio.sleep(1)
        return None

    # ------------------------------------------------------------- playlist (unchanged)
    async def playlist(self, limit: int, user: str, url: str, video: bool) -> list[Track | None]:
        tracks = []
        try:
            plist = await Playlist.get(url)
            for data in plist["videos"][:limit]:
                track = Track(
                    id=data.get("id"),
                    channel_name=data.get("channel", {}).get("name", ""),
                    duration=data.get("duration"),
                    duration_sec=utils.to_seconds(data.get("duration")),
                    title=data.get("title")[:25],
                    thumbnail=data.get("thumbnails")[-1].get("url").split("?")[0],
                    url=data.get("link").split("&list=")[0],
                    user=user,
                    view_count="",
                    video=video,
                )
                tracks.append(track)
        except Exception:
            pass
        return tracks

    # ------------------------------------------------------------- ytdl CLI
    async def _run_ytdl(
        self,
        *args: str,
        timeout: Optional[int] = None,
        env_overrides: Optional[dict[str, str]] = None,
    ) -> dict:
        """Run the pinned ytdlgo CLI and return its final JSON response."""
        if not args:
            raise ValueError("a ytdl command is required")
        timeout = timeout or COMMAND_TIMEOUT
        try:
            proc = await asyncio.create_subprocess_exec(
                YTDL_BIN,
                *args,
                env=_child_env(env_overrides),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise RuntimeError(f"cannot start ytdlgo {YTDLGO_VERSION}: {exc}") from exc

        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            proc.kill()
            await proc.communicate()
            raise RuntimeError(f"ytdl {args[0]} timed out after {timeout}s") from exc

        stdout = out.decode(errors="replace").strip()
        stderr = err.decode(errors="replace").strip()
        try:
            data = json.loads(stdout.splitlines()[-1]) if stdout else {}
        except (json.JSONDecodeError, IndexError) as exc:
            detail = stderr.splitlines()[-1] if stderr else "invalid or empty JSON response"
            raise RuntimeError(f"ytdl {args[0]}: {detail}") from exc

        if proc.returncode != 0 or not data.get("ok", False):
            detail = data.get("error")
            if not detail and stderr:
                detail = stderr.splitlines()[-1]
            raise RuntimeError(str(detail or f"exit {proc.returncode}"))
        return data

    async def _local_available(self) -> bool:
        if LOCAL_DISABLED:
            return False
        if self._local_ok is None:
            if not os.access(YTDL_BIN, os.X_OK):
                logger.error(
                    "[ytdl] ytdlgo %s binary not found or not executable at %s",
                    YTDLGO_VERSION,
                    YTDL_BIN,
                )
                self._local_ok = False
            else:
                try:
                    doctor = await self._run_ytdl("doctor", timeout=60)
                    self._local_ok = bool(doctor.get("ytdlp")) and bool(doctor.get("ffmpeg"))
                    if not self._local_ok:
                        raise RuntimeError("doctor reports missing yt-dlp or ffmpeg")
                    logger.info(
                        "[ytdl] ytdlgo %s ready: yt-dlp=%s bucket=%s cookies=%d "
                        "format=%s clients=%s relays=%d",
                        YTDLGO_VERSION,
                        doctor.get("ytdlp"),
                        doctor.get("bucket") or "local-only",
                        len(doctor.get("cookies") or []),
                        doctor.get("format") or AUDIO_FORMAT,
                        ",".join(doctor.get("clients") or []),
                        len(RELAYS),
                    )
                except Exception as exc:
                    logger.error("[ytdl] ytdlgo doctor failed: %s", exc)
                    self._local_ok = False
        if not self._local_ok:
            return False
        return asyncio.get_running_loop().time() >= self._local_until

    async def _fetch_to(self, url: str, dest: Path, headers: Optional[dict] = None, timeout: Optional[int] = None) -> None:
        """Stream a result to an atomic temporary file before exposing it to the player."""
        tmp = dest.with_suffix(dest.suffix + ".part")
        tmp.unlink(missing_ok=True)
        try:
            async with aiohttp.ClientSession(trust_env=False) as session:
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout or COMMAND_TIMEOUT),
                ) as response:
                    if response.status not in {200, 206}:
                        raise RuntimeError(f"HTTP {response.status} fetching {url[:80]}")
                    with tmp.open("wb") as output:
                        async for chunk in response.content.iter_chunked(1024 * 1024):
                            output.write(chunk)
            if not tmp.exists() or tmp.stat().st_size == 0:
                raise RuntimeError("empty download")
            tmp.replace(dest)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    @staticmethod
    def _extension(value: object, video: bool) -> str:
        extension = str(value or ("mp4" if video else "m4a")).lower().lstrip(".")
        allowed = _VIDEO_EXTENSIONS if video else _AUDIO_EXTENSIONS
        if extension not in allowed:
            raise RuntimeError(f"ytdl returned unsupported extension: {extension}")
        return extension

    async def _get_local_result(self, video_id: str, video: bool) -> dict:
        """Download through ytdlgo, retrying format/cookie edge cases."""
        args = ("get", video_id, "--type", "video" if video else "audio")
        try:
            return await self._run_ytdl(*args)
        except RuntimeError as first_error:
            message = str(first_error)
            format_error = bool(_FORMAT_ERROR.search(message))
            bot_error = any(
                marker in message.lower()
                for marker in ("sign in", "not a bot", "login_required", "cookies")
            )
            if not format_error and not bot_error:
                raise

            attempts: list[tuple[str, dict[str, str]]] = []
            # native uses a stricter m4a-first selector, so MP3 is a useful
            # broad-format fallback. Explicit MP3/Opus requests already use the
            # broad selector and must keep the configured output format.
            fallback_format = "mp3" if AUDIO_FORMAT == "native" else AUDIO_FORMAT
            if format_error and FORMAT_RETRY:
                overrides = {"YT_CLIENTS": RETRY_CLIENTS}
                if not video:
                    overrides["AUDIO_FORMAT"] = fallback_format
                label = (
                    f"alternate client/format ({fallback_format})"
                    if not video and fallback_format != AUDIO_FORMAT
                    else "alternate clients"
                )
                attempts.append((label, overrides))
            if COOKIELESS_RETRY:
                overrides = {
                    "COOKIES_URLS": "",
                    "COOKIES_URL": "",
                    "YT_CLIENTS": RETRY_CLIENTS,
                }
                if not video:
                    overrides["AUDIO_FORMAT"] = fallback_format
                attempts.append(("cookie-less ytdlgo", overrides))

            last_error = first_error
            for label, overrides in attempts:
                logger.warning("[ytdl] %s failed for %s; retrying with %s", message, video_id, label)
                try:
                    return await self._run_ytdl(*args, env_overrides=overrides)
                except RuntimeError as retry_error:
                    last_error = retry_error
                    logger.warning("[ytdl] %s retry failed for %s: %s", label, video_id, retry_error)

            if last_error is first_error:
                raise
            raise RuntimeError(f"{message}; retry failed: {last_error}") from last_error

    async def _download_local(self, video_id: str, video: bool) -> Path:
        # ytdlgo checks the HF bucket cache, runs yt-dlp when needed, then returns JSON.
        result = await self._get_local_result(video_id, video)
        extension = self._extension(result.get("ext"), video)
        dest = DOWNLOAD_DIR / f"{video_id}.{extension}"
        local = result.get("local")
        if local and os.path.isfile(local):
            local_path = Path(local).resolve()
            shutil.move(str(local_path), dest)
            # ytdlgo places uncached results in a per-job folder under WORK_DIR.
            # Remove only that folder; never recursively delete an arbitrary path
            # returned by a subprocess.
            work_root = Path(_child_env()["WORK_DIR"]).resolve()
            if local_path.parent != work_root and work_root in local_path.parents:
                shutil.rmtree(local_path.parent, ignore_errors=True)
            return dest

        # A cache hit or successful upload may exist only in the HF bucket.
        bucket_url = result.get("bucket_url")
        if bucket_url:
            headers = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else None
            await self._fetch_to(bucket_url, dest, headers)
            return dest
        raise RuntimeError("ytdl returned neither a local file nor bucket_url")

    @staticmethod
    def _relay_headers() -> dict:
        headers = dict(HEADERS)
        if RELAY_KEY:
            headers["x-relay-key"] = RELAY_KEY
        return headers

    async def _download_relay(self, base: str, video_id: str, video: bool) -> Path:
        """Use a ytdlgo HTTP service; 202 means the same request must be polled."""
        payload = {"url": self.base + video_id, "type": "video" if video else "audio"}
        relay_headers = self._relay_headers()
        async with aiohttp.ClientSession(headers=relay_headers, trust_env=False) as session:
            deadline = asyncio.get_running_loop().time() + RELAY_TIMEOUT
            while True:
                async with session.post(
                    f"{base}/convert",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as response:
                    try:
                        body = await response.json(content_type=None)
                    except (json.JSONDecodeError, aiohttp.ContentTypeError) as exc:
                        text = await response.text()
                        raise RuntimeError(f"relay {response.status}: {text[:200]}") from exc
                    if response.status == 202 or body.get("status") == "processing":
                        if asyncio.get_running_loop().time() > deadline:
                            raise RuntimeError("relay timeout")
                        retry_after = min(30, max(1, int(body.get("retry_after", 5))))
                        await asyncio.sleep(retry_after)
                        continue
                    if response.status != 200:
                        raise RuntimeError(f"relay {response.status}: {body.get('error') or body}")
                    break

        raw_url = body.get("url")
        if not raw_url:
            raise RuntimeError("relay returned no url")
        file_url = urljoin(base + "/", raw_url)
        filename = str(body.get("filename") or "")
        extension = self._extension(filename.rsplit(".", 1)[-1] if "." in filename else None, video)
        dest = DOWNLOAD_DIR / f"{video_id}.{extension}"

        # A protected relay also guards /file/*. Do not leak its key to a CDN URL.
        download_headers = dict(HEADERS)
        if urlparse(file_url).netloc == urlparse(base).netloc and RELAY_KEY:
            download_headers["x-relay-key"] = RELAY_KEY
        await self._fetch_to(file_url, dest, download_headers)
        return dest

    async def _download_impl(self, video_id: str, video: bool) -> Optional[str]:
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        errors = []

        # Tier 1: the real ytdlgo 1.0.0 release binary.
        if await self._local_available():
            try:
                async with self._sem:
                    path = await self._download_local(video_id, video)
                return str(path)
            except Exception as exc:
                message = str(exc)
                errors.append(f"local: {message}")
                logger.error("[ytdl] local ytdlgo failed for %s: %s", video_id, message)
                if "sign in" in message.lower() or "bot" in message.lower():
                    self._local_until = asyncio.get_running_loop().time() + BOTCHECK_BACKOFF
                    logger.warning("[ytdl] YouTube bot-check; temporarily trying configured ytdlgo relays")
        elif not LOCAL_DISABLED:
            errors.append("local: ytdlgo binary or dependency unavailable")

        # Tier 2: optional services running ytdlgo's compatible HTTP API.
        for base in RELAYS:
            try:
                path = await self._download_relay(base, video_id, video)
                logger.info("[ytdl] %s downloaded through ytdlgo relay %s", video_id, base)
                return str(path)
            except Exception as exc:
                errors.append(f"{base}: {exc}")
                logger.error("[ytdl] relay %s failed for %s: %s", base, video_id, exc)

        logger.error("[ytdl] every ytdlgo source failed for %s: %s", video_id, " | ".join(errors) or "none configured")
        return None

    async def save_cookies(self, urls: list[str]) -> None:
        """Compatibility shim for the old COOKIES_URL startup hook.

        The ytdlgo binary downloads and rotates remote Netscape cookie files itself.
        """
        if urls and not os.environ.get("COOKIES_URLS"):
            os.environ["COOKIES_URLS"] = ",".join(urls)
            self._local_ok = None
            logger.info("[ytdl] passed %d legacy cookie URL(s) to ytdlgo", len(urls))

    async def download(self, video_id: str, video: bool = False) -> Optional[str]:
        if not _VIDEO_ID.fullmatch(video_id):
            logger.error("[ytdl] rejected invalid YouTube video id: %r", video_id)
            return None

        # Return an existing result if it has already been downloaded.
        extensions = _VIDEO_EXTENSIONS if video else _AUDIO_EXTENSIONS
        for extension in extensions:
            file = DOWNLOAD_DIR / f"{video_id}.{extension}"
            if file.exists() and file.stat().st_size > 0:
                return str(file)

        key = f"{video_id}:{'v' if video else 'a'}"
        future = self._inflight.get(key)
        if future is None:
            future = asyncio.create_task(self._download_impl(video_id, video))
            self._inflight[key] = future
            future.add_done_callback(lambda _: self._inflight.pop(key, None))
        return await future
