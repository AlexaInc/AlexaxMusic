from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

STATION_NAMES = [
    "Hiru FM", "Shaa FM", "FM Derana", "ITN FM", "Rhythm FM", "NuWaaV K-Pop",
    "Sirasa FM", "Kiss FM", "Lakhada FM", "ABC Gold FM", "bestcoast.fm",
    "Bathusha Radio", "E FM", "Fox", "Freefm.lk", "Imai FM", "Krushi Radio",
    "Lite FM", "LiveFM", "Neth FM", "Ran FM", "Rangiri SL", "Rasa FM",
    "Real Radio", "Shakthi FM", "Red FM", "Shraddha", "Shree FM", "Siyatha FM",
    "Sitha FM", "City FM", "Kandurata", "Radio SL", "Tamil National",
    "Sinhala Comm", "Thendral FM", "Sun FM", "Sinhala Nat", "Sooriyan FM",
    "V FM Radio", "Vasantham", "Yes FM", "Waharaka", "Y FM"
]

def radio_markup(page=1):
    items_per_page = 8
    total_pages = (len(STATION_NAMES) + items_per_page - 1) // items_per_page
    start = (page - 1) * items_per_page
    end = start + items_per_page
    
    buttons = []
    current_stations = STATION_NAMES[start:end]
    for i in range(0, len(current_stations), 2):
        row = [InlineKeyboardButton(current_stations[i], callback_data=f"radio_{start + i + 1}")]
        if i + 1 < len(current_stations):
            row.append(InlineKeyboardButton(current_stations[i+1], callback_data=f"radio_{start + i + 2}"))
        buttons.append(row)

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Back", callback_data=f"radio_page_{page-1}"))
    nav_buttons.append(InlineKeyboardButton(f"Page {page}/{total_pages}", callback_data="none"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"radio_page_{page+1}"))
    buttons.append(nav_buttons)
    
    buttons.append([InlineKeyboardButton("❌ Close Menu", callback_data="help close")])
    return InlineKeyboardMarkup(buttons)