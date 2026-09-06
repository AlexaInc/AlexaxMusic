# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic
#
# YouTube platform module
#   search   -> hansaka1-ytdl.hf.space/search   (unchanged)
#   playlist -> py_yt                            (unchanged)
#   download -> tier 1: local `ytdl` Go CLI (bin/ytdl, yt-dlp + cookies + HF bucket cache)
#               tier 2: Koyeb ytdl-go relay (POST /convert)
#
# Env (all optional except HF_TOKEN/HF_BUCKET/COOKIES_URLS for tier 1):
#   YTDL_BIN        path to the ytdl binary        default: <project>/bin/ytdl
#   YTDL_BIN_DIR    dir prepended to PATH          default: dirname(YTDL_BIN)  (yt-dlp_linux, deno, ffmpeg, xet-upload)
#   HF_TOKEN, HF_BUCKET, COOKIES_URLS, AUDIO_FORMAT, MAX_HEIGHT, WORK_DIR   -> passed through to ytdl
#   YTDL_RELAYS     comma-separated relay base URLs  default: Koyeb
#   YTDL_DISABLE=1  skip local binary, relay only
#   DOWNLOAD_DIR    where finished files go        default: downloads

import os
import re
import json
import shutil
import asyncio
import aiohttp
from pathlib import Path
from typing import Optional, Union

from pyrogram import enums, types
from py_yt import Playlist

from anony import config, logger
from anony.helpers import Track, utils

# ----------------------------------------------------------------- config
_PROJECT = Path(__file__).resolve().parents[2]  # .../anony/platforms/youtube.py -> project root
YTDL_BIN = os.getenv("YTDL_BIN") or str(_PROJECT / "bin" / "ytdl")
YTDL_BIN_DIR = os.getenv("YTDL_BIN_DIR") or str(Path(YTDL_BIN).parent)
HF_TOKEN = os.getenv("HF_TOKEN", "")
LOCAL_DISABLED = os.getenv("YTDL_DISABLE") == "1"
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "downloads"))
RELAYS = [
    r.strip().rstrip("/")
    for r in os.getenv("YTDL_RELAYS", "https://absolute-vonnie-alexainc-ec756816.koyeb.app").split(",")
    if r.strip()
]
MAX_CONCURRENT = max(1, int(os.getenv("YTDL_CONCURRENCY", "1")))
BOTCHECK_BACKOFF = 15 * 60  # seconds to avoid local yt-dlp after a "Sign in to confirm" error

HEADERS = {
    "accept": "*/*",
    "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
    "content-type": "application/json",
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
}


def _child_env() -> dict:
    env = dict(os.environ)
    if YTDL_BIN_DIR:
        env["PATH"] = f"{YTDL_BIN_DIR}:{env.get('PATH', '')}"
    env.setdefault("WORK_DIR", "/tmp/ytdl-work")
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
    async def _run_ytdl(self, *args: str, timeout: int = 600) -> dict:
        """Spawn the Go CLI; returns the parsed JSON object from stdout (raises on failure)."""
        proc = await asyncio.create_subprocess_exec(
            YTDL_BIN, *args, env=_child_env(),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            raise RuntimeError(f"ytdl {args[0]} timed out after {timeout}s")
        text = out.decode(errors="replace").strip()
        try:
            data = json.loads(text.splitlines()[-1]) if text else {}
        except Exception:
            data = {}
        if proc.returncode != 0 or not data.get("ok", False):
            msg = data.get("error") or err.decode(errors="replace").strip().splitlines()[-1:] or f"exit {proc.returncode}"
            raise RuntimeError(str(msg))
        return data

    async def _local_available(self) -> bool:
        if LOCAL_DISABLED:
            return False
        if self._local_ok is None:
            if not os.access(YTDL_BIN, os.X_OK):
                logger.warning(f"[ytdl] binary not found at {YTDL_BIN}; relay only")
                self._local_ok = False
            else:
                try:
                    d = await self._run_ytdl("doctor", timeout=60)
                    self._local_ok = bool(d.get("ytdlp")) and bool(d.get("ffmpeg"))
                    logger.info(f"[ytdl] local ok: yt-dlp {d.get('ytdlp')}, bucket={d.get('bucket')}, cookies={len(d.get('cookies') or [])}")
                except Exception as e:
                    logger.warning(f"[ytdl] doctor failed, relay only: {e}")
                    self._local_ok = False
        if not self._local_ok:
            return False
        return asyncio.get_event_loop().time() >= self._local_until

    async def _fetch_to(self, url: str, dest: Path, headers: Optional[dict] = None, timeout: int = 600) -> None:
        tmp = dest.with_suffix(dest.suffix + ".part")
        async with aiohttp.ClientSession(trust_env=False) as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status} fetching {url[:80]}")
                with open(tmp, "wb") as f:
                    async for chunk in resp.content.iter_chunked(1024 * 1024):
                        f.write(chunk)
        if tmp.stat().st_size == 0:
            tmp.unlink(missing_ok=True)
            raise RuntimeError("empty download")
        tmp.replace(dest)

    async def _download_local(self, video_id: str, video: bool) -> Path:
        # CLI: bucket cache check -> (yt-dlp -> upload) -> JSON. File is then fetched from the bucket CDN
        # (fast); "local" is only present when the upload failed (no HF creds / HF outage).
        r = await self._run_ytdl("get", video_id, "--type", "video" if video else "audio")
        ext = r.get("ext") or ("mp4" if video else "m4a")
        dest = DOWNLOAD_DIR / f"{video_id}.{ext}"
        local = r.get("local")
        if local and os.path.exists(local):
            shutil.move(local, dest)
            shutil.rmtree(os.path.dirname(local), ignore_errors=True)
            return dest
        # cache hit: file lives only in the bucket -> pull it (token needed for private bucket)
        if r.get("bucket_url"):
            hdr = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else None
            await self._fetch_to(r["bucket_url"], dest, hdr)
            return dest
        raise RuntimeError("ytdl returned neither local nor bucket_url")

    async def _download_relay(self, base: str, video_id: str, video: bool) -> Path:
        payload = {"url": self.base + video_id, "type": "video" if video else "audio"}
        async with aiohttp.ClientSession(headers=HEADERS, trust_env=False) as session:
            deadline = asyncio.get_event_loop().time() + 420
            while True:
                async with session.post(f"{base}/convert", json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    body = await resp.json(content_type=None)
                    if resp.status == 202 or body.get("status") == "processing":
                        if asyncio.get_event_loop().time() > deadline:
                            raise RuntimeError("relay timeout")
                        await asyncio.sleep(int(body.get("retry_after", 5)))
                        continue
                    if resp.status != 200:
                        raise RuntimeError(f"relay {resp.status}: {body.get('error') or body}")
                    break
        file_url = body.get("url")
        if not file_url:
            raise RuntimeError("relay returned no url")
        ext = (body.get("filename") or "").rsplit(".", 1)[-1] or ("mp4" if video else "m4a")
        dest = DOWNLOAD_DIR / f"{video_id}.{ext}"
        await self._fetch_to(file_url, dest, HEADERS)
        return dest

    async def _download_impl(self, video_id: str, video: bool) -> Optional[str]:
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        errors = []

        # tier 1: local binary
        if await self._local_available():
            try:
                async with self._sem:
                    p = await self._download_local(video_id, video)
                return str(p)
            except Exception as e:
                msg = str(e)
                errors.append(f"local: {msg}")
                logger.error(f"[ytdl] local failed for {video_id}: {msg}")
                if "sign in" in msg.lower() or "bot" in msg.lower():
                    self._local_until = asyncio.get_event_loop().time() + BOTCHECK_BACKOFF
                    logger.warning("[ytdl] YouTube bot-check on this IP; using relays for 15 min")

        # tier 2: relays
        for base in RELAYS:
            try:
                p = await self._download_relay(base, video_id, video)
                logger.info(f"[ytdl] {video_id} via relay {base}")
                return str(p)
            except Exception as e:
                errors.append(f"{base}: {e}")
                logger.error(f"[ytdl] relay {base} failed for {video_id}: {e}")

        logger.error(f"[ytdl] all sources failed for {video_id}: {' | '.join(errors)}")
        return None

    async def download(self, video_id: str, video: bool = False) -> Optional[str]:
        # Return existing file if already downloaded (any extension we might have produced)
        for ext in (("mp4",) if video else ("m4a", "mp3", "opus", "webm")):
            f = DOWNLOAD_DIR / f"{video_id}.{ext}"
            if f.exists() and f.stat().st_size > 0:
                return str(f)

        key = f"{video_id}:{'v' if video else 'a'}"
        fut = self._inflight.get(key)
        if fut is None:
            fut = asyncio.ensure_future(self._download_impl(video_id, video))
            self._inflight[key] = fut
            fut.add_done_callback(lambda _: self._inflight.pop(key, None))
        return await fut
