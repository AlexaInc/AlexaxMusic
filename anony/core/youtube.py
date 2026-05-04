# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic

import os
import re
import asyncio
import aiohttp
from urllib.parse import quote
from pathlib import Path
from typing import Optional, Union

from pyrogram import enums, types
from py_yt import Playlist
import json
import traceback
from aiohttp_socks import ProxyConnector

from anony import config, logger
from anony.helpers import Track, utils

# New headers matching user's JS configuration
HEADERS = {
    'accept': '*/*',
    'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
    'content-type': 'application/json',
    'Referer': 'https://hansaka1-ytdl.hf.space/',
    'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
}

class YouTube:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = re.compile(
            r"(https?://)?(www\.|m\.|music\.)?"
            r"(youtube\.com/(watch\?v=|shorts/|playlist\?list=)|youtu\.be/)"
            r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)([&?][^\s]*)?"
        )

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

    async def search(self, query: str, m_id: int, video: bool = False) -> Track | None:
        url = "https://hansaka1-ytdl.hf.space/search"
        headers = {
            "accept": "*/*",
            "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
            "origin": "https://hansaka1-ytdl.hf.space",
            "referer": "https://hansaka1-ytdl.hf.space/",
            "sec-ch-ua": "\"Not=A?Brand\";v=\"24\", \"Chromium\";v=\"140\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
        }
        
        # Retry up to 2 times for search
        for attempt in range(2):
            try:
                # trust_env=False to bypass unstable system proxies
                async with aiohttp.ClientSession(headers=headers, trust_env=False) as session:
                    async with session.post(url, json={"query": query}, timeout=aiohttp.ClientTimeout(total=25)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            results = data.get("results", [])
                            
                            if results and isinstance(results, list) and len(results) > 0:
                                item = results[0]
                                video_id = item.get("videoId")
                                
                                if video_id:
                                    thumbnails = item.get("thumbnail", [])
                                    thumbnail_url = thumbnails[-1]['url'].split("?")[0] if thumbnails else None
                                    length_text = item.get("duration", "0:00")
                                    viewCountText = item.get("shortViewCount", "0 views").split(" ")[0]
                                    
                                    return Track(
                                        id=video_id,
                                        channel_name=item.get("channelName", "Unknown Channel")[:25],
                                        duration=length_text,
                                        duration_sec=utils.to_seconds(length_text),
                                        message_id=m_id,
                                        title=item.get("title", "Unknown Title")[:25],
                                        thumbnail=thumbnail_url,
                                        url=f"https://www.youtube.com/watch?v={video_id}",
                                        view_count=viewCountText,
                                        video=video,
                                    )
                        else:
                            logger.error(f"External Search API failed with status {resp.status} (Attempt {attempt+1})")
            except Exception as e:
                logger.error(f"Custom YouTube search attempt {attempt+1} failed: {type(e).__name__} - {e}")
                if attempt == 0:
                    await asyncio.sleep(1) # Brief pause before retry
                    
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

    # --- New Hansaka API Logic ---

    async def download(self, video_id: str, video: bool = False) -> Optional[str]:
        # Construct the full YouTube URL
        link = self.base + video_id
        
        ext = "mp4" if video else "mp3" 
        filename = f"downloads/{video_id}.{ext}"

        # Return existing file if already downloaded
        if Path(filename).exists():
            return filename

        # API parameters
        api_url = "https://hansaka1-ytdl.hf.space/download"
        payload = {
            "url": link,
            "type": "video" if video else "audio"
        }

        # Download logic using the new Hansaka API (returns raw buffer)
        for attempt in range(2):
            try:
                # Bypassing proxy for internal HF space communication
                async with aiohttp.ClientSession(headers=HEADERS, trust_env=False) as session:
                    async with session.post(api_url, json=payload, timeout=aiohttp.ClientTimeout(total=450)) as resp:
                        if resp.status == 200:
                            with open(filename, "wb") as f:
                                while True:
                                    chunk = await resp.content.read(1024 * 1024) # 1MB chunks
                                    if not chunk:
                                        break
                                    f.write(chunk)
                            
                            if os.path.exists(filename) and os.path.getsize(filename) > 0:
                                return filename
                            else:
                                logger.error(f"Downloaded file {filename} is empty (Attempt {attempt+1}).")
                                if os.path.exists(filename): os.remove(filename)
                        else:
                            error_text = await resp.text()
                            logger.error(f"Hansaka API Error {resp.status} (Attempt {attempt+1}): {error_text}")
            except Exception as ex:
                logger.error(f"Hansaka Download attempt {attempt+1} failed: {ex}")
                if os.path.exists(filename):
                    os.remove(filename)
                if attempt == 0:
                    await asyncio.sleep(2) # Pause before retry
        
        return None
        
        return None