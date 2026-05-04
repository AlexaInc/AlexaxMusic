import asyncio
import httpx
import re
import hashlib
import json
import os
import sys

# IPTV links to fetch
M3U_URLS = [
    "https://iptv-org.github.io/iptv/countries/lk.m3u",
    "https://iptv-org.github.io/iptv/languages/sin.m3u",
    "https://iptv-org.github.io/iptv/categories/news.m3u",
    "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8",
    "https://iptv-org.github.io/iptv/categories/kids.m3u",
    "https://iptv-org.github.io/iptv/categories/animation.m3u",
    "https://iptvmate.net/files/adult.m3u",
    "anony/helpers/adult.m3u"
]

def parse_m3u(content, filter_group=None, force_prefix=None):
    channels = []
    pattern = r'#EXTINF:(-?\d+)(.*?),(.*?)\n(https?://[^\s]+)'
    matches = re.finditer(pattern, content)
    
    for match in matches:
        attrs_block = match.group(2)
        title = match.group(3).strip()
        url = match.group(4).strip()
        
        tvg_id = re.search(r'tvg-id="([^"]*)"', attrs_block)
        tvg_logo = re.search(r'tvg-logo="([^"]*)"', attrs_block)
        group_title = re.search(r'group-title="([^"]*)"', attrs_block)
        
        tv_id = tvg_id.group(1) if tvg_id else hashlib.md5(url.encode()).hexdigest()[:10]
        logo = tvg_logo.group(1) if tvg_logo else ""
        group = group_title.group(1) if group_title else "General"
            
        if filter_group and filter_group.lower() not in group.lower():
            continue

        if force_prefix:
            sub_cats = [c.strip() for c in group.split(";") if c.strip().lower() != force_prefix.lower()]
            if sub_cats and sub_cats[0].lower() not in ["general", "other", ""]:
                group = f"{force_prefix} - {sub_cats[0]}"
            else:
                group = force_prefix
        else:
            if ";" in group:
                group = group.split(";")[0]
            
        channels.append({
            "id": tv_id,
            "title": title,
            "category": group,
            "manifest": url,
            "thumbnail": logo
        })
    return channels

async def verify_channel(semaphore, channel, timeout=10):
    """Use ffprobe to verify if the stream has a valid video source."""
    async with semaphore:
        url = channel["manifest"]
        # Use ffprobe to check for video streams.
        cmd = [
            "ffprobe",
            "-v", "error",
            "-user_agent", "Mozilla/5.0", # Bypass User-Agent blocks
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0",
            "-timeout", str(timeout * 1000000), # microseconds
            url
        ]
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            try:
                stdout, _ = await asyncio.wait_for(process.communicate(), timeout=timeout + 2)
                output = stdout.decode().lower()
                if "video" in output: # Check if video stream exists at all
                    return channel
            except asyncio.TimeoutError:
                try:
                    process.terminate()
                except:
                    pass
        except Exception:
            pass
    return None

async def main():
    print("Starting TV channel update...")
    all_channels = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    }

    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        # 1. Fetch and parse all M3Us
        for url in M3U_URLS:
            print(f"Fetching {url}...")
            content = None
            prefix = None
            filter_pattern = None
            
            try:
                if url.startswith("http"):
                    resp = await client.get(url, timeout=15)
                    if resp.status_code == 200:
                        content = resp.text
                        if "Free-TV/IPTV" in url: filter_pattern = "Movies"
                        if "/kids" in url or "/animation" in url: prefix = "Kids"
                        elif "/news" in url: prefix = "News"
                        elif "Free-TV/IPTV" in url: prefix = "Movies"
                        elif "/lk.m3u" in url or "/sin.m3u" in url: prefix = "Sri Lanka"
                        elif "iptvmate.net" in url: prefix = "Adult"
                else:
                    if os.path.exists(url):
                        with open(url, "r", encoding="utf-8") as f:
                            content = f.read()
                        if "adult.m3u" in url: prefix = "Adult"
                
                if content:
                    parsed = parse_m3u(content, filter_group=filter_pattern, force_prefix=prefix)
                    all_channels.extend(parsed)
            except Exception as e:
                print(f"Error processing {url}: {e}")

        # 2. Remove duplicates
        unique_map = {c["manifest"]: c for c in all_channels}
        channels_to_verify = list(unique_map.values())
        print(f"Found {len(channels_to_verify)} unique channels. Verifying...")

        # 3. Verify channels in parallel
        semaphore = asyncio.Semaphore(15) # Limit concurrency for ffprobe
        tasks = [verify_channel(semaphore, ch) for ch in channels_to_verify]
        results = await asyncio.gather(*tasks)
        
        working_channels = [r for r in results if r]
        print(f"Verification complete. {len(working_channels)} working channels found.")

        # 4. Save to JSON
        with open("tv-channels.json", "w", encoding="utf-8") as f:
            json.dump(working_channels, f, indent=2, ensure_ascii=False)
        
        print("Updated tv-channels.json successfully.")

if __name__ == "__main__":
    asyncio.run(main())
