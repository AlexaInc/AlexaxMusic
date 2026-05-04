import re
import hashlib
import httpx
import os
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# URL to the verified channel list on GitHub
JSON_URL = "https://raw.githubusercontent.com/AlexaInc/AlexaxMusic/master/tv-channels.json"

async def fetch_channels():
    """Fetch pre-verified channels from GitHub JSON."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    }
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        try:
            response = await client.get(JSON_URL, timeout=15)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Error fetching TV JSON: {e}")
    return []

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
    all_cats = list(set([c["category"] for c in channels if "category" in c]))
    subs = []
    for cat in all_cats:
        if cat == parent or cat.startswith(f"{parent} - "):
            subs.append(cat)
    subs.sort()
    return subs

def get_category_channels(category, channels):
    """Filter channels by exact category."""
    return [c for c in channels if c.get("category") == category]

def category_markup(channels, parent=None):
    """Generate markup for either top-level parents or sub-categories."""
    if parent:
        items = get_subcategories(parent, channels)
    else:
        items = get_parents(channels)
        
    keyboard = []
    row = []
    for item in items:
        # For display, remove prefix if it's a sub-category button
        display_name = item
        if parent and item.startswith(f"{parent} - "):
            display_name = item.replace(f"{parent} - ", "")
            
        callback = f"tv_parent:{item}" if not parent else f"tv_cat:{item}"
        row.append(InlineKeyboardButton(display_name, callback_data=callback))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    if parent:
        keyboard.append([InlineKeyboardButton("🔙 Back to Main Categories", callback_data="tv_home")])
    
    return InlineKeyboardMarkup(keyboard)

def channel_markup(category, channels, page=0):
    page_size = 10
    cat_channels = get_category_channels(category, channels)
    total_pages = (len(cat_channels) - 1) // page_size + 1
    
    start = page * page_size
    end = start + page_size
    current_channels = cat_channels[start:end]
    
    keyboard = []
    for channel in current_channels:
        keyboard.append([InlineKeyboardButton(channel["title"], callback_data=f"tv_ch:{channel['id']}")])
    
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"tv_page:{category}:{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"tv_page:{category}:{page+1}"))
    
    if nav_row:
        keyboard.append(nav_row)
        
    # Improved navigation: back to parent menu
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
    return manifest_url
