import json
import os
import httpx
import re
import hashlib
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# IPTV links provided by user
M3U_URLS = [
    "https://iptv-org.github.io/iptv/countries/lk.m3u",
    "https://iptv-org.github.io/iptv/languages/sin.m3u",
    "https://iptv-org.github.io/iptv/categories/news.m3u",
    "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"
]

def parse_m3u(content, filter_group=None):
    channels = []
    # Match #EXTINF line and the following URL
    pattern = r'#EXTINF:-1(.*?),(.*?)\n(https?://[^\s]+)'
    matches = re.finditer(pattern, content)
    
    for match in matches:
        attrs_block = match.group(1)
        title = match.group(2).strip()
        url = match.group(3).strip()
        
        # Extract attributes from attrs_block
        tvg_id = re.search(r'tvg-id="([^"]*)"', attrs_block)
        tvg_logo = re.search(r'tvg-logo="([^"]*)"', attrs_block)
        group_title = re.search(r'group-title="([^"]*)"', attrs_block)
        
        tv_id = tvg_id.group(1) if tvg_id else hashlib.md5(url.encode()).hexdigest()[:10]
        logo = tvg_logo.group(1) if tvg_logo else ""
        group = group_title.group(1) if group_title else "General"
            
        # Filter by group if requested
        if filter_group and filter_group.lower() not in group.lower():
            continue

        # Clean up group title (remove extra spaces or semicolons if multiple categories)
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

async def fetch_channels():
    channels = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    }
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        for url in M3U_URLS:
            try:
                response = await client.get(url, timeout=15)
                if response.status_code == 200:
                    # Only filter for 'Movies' in the large Free-TV playlist
                    filter_pattern = "Movies" if "Free-TV/IPTV" in url else None
                    channels.extend(parse_m3u(response.text, filter_group=filter_pattern))
            except Exception as e:
                print(f"Error fetching TV list from {url}: {e}")
    
    # Remove duplicates by manifest URL
    unique_channels = {}
    for ch in channels:
        if ch["manifest"] not in unique_channels:
            unique_channels[ch["manifest"]] = ch
            
    return list(unique_channels.values())

def get_categories(channels):
    categories = list(set([c["category"] for c in channels if "category" in c]))
    categories.sort()
    return categories

def get_channels_by_category(category, channels):
    return [c for c in channels if c.get("category") == category]

def category_markup(channels):
    categories = get_categories(channels)
    keyboard = []
    row = []
    
    for cat in categories:
        row.append(InlineKeyboardButton(cat, callback_data=f"tv_cat:{cat}"))
        if len(row) >= 3:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
        
    keyboard.append([InlineKeyboardButton("❌ Close Play Menu", callback_data="help close")])
    return InlineKeyboardMarkup(keyboard)

def channel_markup(category, channels, page=1):
    category_channels = get_channels_by_category(category, channels)
    keyboard = []
    
    items_per_page = 10
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    
    current_channels = category_channels[start_idx:end_idx]

    for ch in current_channels:
        if len(keyboard) > 0 and len(keyboard[-1]) < 2:
            keyboard[-1].append(InlineKeyboardButton(f"📺 {ch['title']}", callback_data=f"tv_ch:{ch['id']}"))
        else:
            keyboard.append([InlineKeyboardButton(f"📺 {ch['title']}", callback_data=f"tv_ch:{ch['id']}")])

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Back", callback_data=f"tv_page:{category}:{page-1}"))
    if end_idx < len(category_channels):
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"tv_page:{category}:{page+1}"))
        
    if nav_row:
        keyboard.append(nav_row)
        
    keyboard.append([InlineKeyboardButton("🔙 Back to Categories", callback_data="tv_home")])
    return InlineKeyboardMarkup(keyboard)

async def fetch_stream_url(manifest_url):
    """Fetches the actual stream URL if it's a Viu manifest, otherwise returns directly."""
    if "api.viulk.xyz" not in manifest_url:
        return manifest_url
        
    from anony import config
    proxy_url = getattr(config, "PROXY_URL", None)

    async with httpx.AsyncClient(proxy=proxy_url) as client:
        try:
            response = await client.get(manifest_url)
            response.raise_for_status()
            data = response.json()
            if data.get("status") == "ok" and "url" in data.get("data", {}):
                return data["data"]["url"]
            return None
        except Exception as e:
            print(f"Error fetching TV manifest: {e}")
            return None
