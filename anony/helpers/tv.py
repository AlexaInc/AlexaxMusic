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
    "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8",
    "https://iptv-org.github.io/iptv/categories/kids.m3u",
    "https://iptv-org.github.io/iptv/categories/animation.m3u",
    "anony/helpers/adult.m3u"
]

def parse_m3u(content, filter_group=None, force_prefix=None):
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

        # Specialized grouping for Kids/Animation
        if force_prefix:
            # Extract subcategories (exclude the prefix itself)
            sub_cats = [c.strip() for c in group.split(";") if c.strip().lower() != force_prefix.lower()]
            if sub_cats:
                group = f"{force_prefix} - {sub_cats[0]}"
            else:
                group = force_prefix
        else:
            # Clean up group title (take first category)
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
                content = None
                prefix = None
                filter_pattern = None
                
                if url.startswith("http"):
                    response = await client.get(url, timeout=15)
                    if response.status_code == 200:
                        content = response.text
                        filter_pattern = "Movies" if "Free-TV/IPTV" in url else None
                        if "/kids.m3u" in url or "/animation.m3u" in url:
                            prefix = "Kids"
                        elif "/news.m3u" in url:
                            prefix = "News"
                        elif "Free-TV/IPTV" in url:
                            prefix = "Movies"
                        elif "/lk.m3u" in url or "/sin.m3u" in url:
                            prefix = "Sri Lanka"
                else:
                    # Handle local files (like anony/helpers/adult.m3u)
                    if os.path.exists(url):
                        with open(url, "r", encoding="utf-8") as f:
                            content = f.read()
                        if "adult.m3u" in url:
                            prefix = "Adult"
                
                if content:
                    channels.extend(parse_m3u(content, filter_group=filter_pattern, force_prefix=prefix))
            except Exception as e:
                print(f"Error fetching TV list from {url}: {e}")
    
    # Remove duplicates by manifest URL
    unique_channels = {}
    for ch in channels:
        if ch["manifest"] not in unique_channels:
            unique_channels[ch["manifest"]] = ch
            
    return list(unique_channels.values())

def get_parents(channels):
    """Extract top-level parent categories (e.g., 'Kids', 'Movies', 'News')."""
    categories = list(set([c["category"] for c in channels if "category" in c]))
    parents = set()
    for cat in categories:
        if " - " in cat:
            parents.add(cat.split(" - ")[0])
        else:
            parents.add(cat)
    res = list(parents)
    res.sort()
    return res

def get_subcategories(parent, channels):
    """Get actual categories that belong to a parent."""
    categories = list(set([c["category"] for c in channels if "category" in c]))
    subs = []
    for cat in categories:
        if cat == parent or cat.startswith(f"{parent} - "):
            subs.append(cat)
    subs.sort()
    return subs

def get_channels_by_category(category, channels):
    return [c for c in channels if c.get("category") == category]

def category_markup(channels, parent=None):
    """
    If parent is None, show top-level parents.
    If parent is provided, show subcategories for that parent.
    """
    if parent is None:
        items = get_parents(channels)
        callback_prefix = "tv_parent"
    else:
        items = get_subcategories(parent, channels)
        # If there's only one subcategory and it's equal to the parent, we might want to skip this level, 
        # but let's be consistent for now.
        callback_prefix = "tv_cat"
        
    keyboard = []
    row = []
    
    for item in items:
        # Display name: for sub-categories, strip the parent prefix for cleaner UI
        display_name = item
        if parent and item.startswith(f"{parent} - "):
            display_name = item.replace(f"{parent} - ", "")
            
        row.append(InlineKeyboardButton(display_name, callback_data=f"{callback_prefix}:{item}"))
        if len(row) >= 3:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
        
    if parent:
        keyboard.append([InlineKeyboardButton("🔙 Back to Main Categories", callback_data="tv_home")])
    else:
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
        
    # Improved navigation: check if this is part of a parent category
    if " - " in category:
        parent = category.split(" - ")[0]
        keyboard.append([
            InlineKeyboardButton(f"🔙 Back to {parent}", callback_data=f"tv_parent:{parent}"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="tv_home")
        ])
    else:
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
