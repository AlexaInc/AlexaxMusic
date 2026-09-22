# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of Alexa Music


import os
import re
import yt_dlp
import random
import shutil
import asyncio
import aiohttp
from pathlib import Path

from py_yt import Playlist, VideosSearch

from alexa import logger
from alexa.helpers import Track, utils


class YouTube:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.cookies = []
        self.checked = False
        self.cookie_dir = "alexa/cookies"
        self.warned = False
        self.regex = re.compile(
            r"(https?://)?(www\.|m\.|music\.)?"
            r"(youtube\.com/(watch\?v=|shorts/|playlist\?list=)|youtu\.be/)"
            r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)([&?][^\s]*)?"
        )

    def get_cookies(self):
        if not self.checked:
            for file in os.listdir(self.cookie_dir):
                if file.endswith(".txt"):
                    self.cookies.append(f"{self.cookie_dir}/{file}")
            self.checked = True
        if not self.cookies:
            if not self.warned:
                self.warned = True
                logger.warning("Cookies are missing; downloads might fail.")
            return None
        return random.choice(self.cookies)

    async def save_cookies(self, urls: list[str]) -> None:
        logger.info("Saving cookies from urls...")
        async with aiohttp.ClientSession() as session:
            for i, url in enumerate(urls):
                path = f"{self.cookie_dir}/cookie_{i}.txt"
                link = "https://batbin.me/api/v2/paste/" + url.split("/")[-1]
                async with session.get(link) as resp:
                    resp.raise_for_status()
                    with open(path, "wb") as fw:
                        fw.write(await resp.read())
        logger.info(f"Cookies saved in {self.cookie_dir}.")

    def valid(self, url: str) -> bool:
        return bool(re.match(self.regex, url))

    async def search(self, query: str, m_id: int, video: bool = False) -> Track | None:
        _search = VideosSearch(query, limit=1, with_live=False)
        results = await _search.next()
        if results and results["result"]:
            data = results["result"][0]
            return Track(
                id=data.get("id"),
                channel_name=data.get("channel", {}).get("name"),
                duration=data.get("duration"),
                duration_sec=utils.to_seconds(data.get("duration")),
                message_id=m_id,
                title=data.get("title")[:25],
                thumbnail=data.get("thumbnails", [{}])[-1].get("url").split("?")[0],
                url=data.get("link"),
                view_count=data.get("viewCount", {}).get("short"),
                video=video,
            )
        return None

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
        except:
            pass
        return tracks

    async def download(self, video_id: str, video: bool = False) -> str | None:
        url = self.base + video_id
        
        # Check if file already exists
        for ext in ["webm", "mp4", "m4a", "mp3", "opus"]:
            if Path(f"downloads/{video_id}.{ext}").exists():
                return f"downloads/{video_id}.{ext}"

        cookie = self.get_cookies()
        
        # Temp cookie handling
        temp_cookie = None
        if cookie:
            temp_cookie = f"downloads/temp_cookie_{video_id}.txt"
            shutil.copyfile(cookie, temp_cookie)

        base_opts = {
            "outtmpl": f"downloads/{video_id}.%(ext)s", 
            "quiet": True,
            "noplaylist": True,
            "geo_bypass": True,
            "no_warnings": True,
            "overwrites": False,
            "nocheckcertificate": True,
            "cookiefile": temp_cookie if temp_cookie else cookie,
            "external_downloader": "aria2c",
            "external_downloader_args": ["-x", "16", "-s", "16", "-k", "1M"],
        }

        if video:
            ydl_opts = {
                **base_opts,
                "format": "best[ext=mp4]/bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best",
                "merge_output_format": "mp4",
            }
        else:
            # FIXED: Removed faulty 'webm' conversion. 
            # Now prefers 'm4a' which is native to YouTube (faster & no errors).
            ydl_opts = {
                **base_opts,
                "format": "bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a", # Changed from 'webm' to 'm4a'
                    "preferredquality": "192",
                }],
            }

        def _download():
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    try:
                        ydl.download([url])
                    except (yt_dlp.utils.DownloadError, yt_dlp.utils.ExtractorError):
                        if cookie and cookie in self.cookies: 
                            self.cookies.remove(cookie)
                        return None
                    except Exception as ex:
                        logger.warning("Download failed: %s", ex)
                        return None
                
                # Smart File Finder
                for f in os.listdir("downloads"):
                    if f.startswith(video_id) and not f.startswith("temp_cookie"):
                        return f"downloads/{f}"
                return None
            finally:
                if temp_cookie and os.path.exists(temp_cookie):
                    try:
                        os.remove(temp_cookie)
                    except:
                        pass

        return await asyncio.to_thread(_download)