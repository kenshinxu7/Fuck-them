"""
╔══════════════════════════════════════════════════════════╗
║     KENSHIN ANIME'S — Telegram Anime Search Bot          ║
║     Engine : Pyrogram v2.x + AniList GraphQL API         ║
║     Author : @KENSHIN_ANIME                              ║
╚══════════════════════════════════════════════════════════╝
"""

import os
import re
import html
import asyncio
import logging
from typing import Optional

import aiohttp
from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from pyrogram.errors import MessageNotModified, FloodWait

# ─────────────────────────────────────────────────────────────
#  Logging
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("KenshinAnimeBot")

# ─────────────────────────────────────────────────────────────
#  Environment Variables
# ─────────────────────────────────────────────────────────────
API_ID    = int(os.environ["API_ID"])
API_HASH  = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

# ─────────────────────────────────────────────────────────────
#  Pyrogram Client
# ─────────────────────────────────────────────────────────────
app = Client(
    "kenshin_anime_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# ─────────────────────────────────────────────────────────────
#  AniList GraphQL Queries
# ─────────────────────────────────────────────────────────────
ANILIST_URL = "https://graphql.anilist.co"

SEARCH_QUERY = """
query ($search: String) {
  Page(page: 1, perPage: 5) {
    media(search: $search, type: ANIME, sort: SEARCH_MATCH) {
      id
      title {
        romaji
        english
        native
      }
    }
  }
}
"""

DETAIL_QUERY = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    id
    title {
      romaji
      english
      native
    }
    coverImage {
      extraLarge
    }
    format
    season
    seasonYear
    episodes
    duration
    averageScore
    status
    genres
    studios(isMain: true) {
      nodes {
        name
      }
    }
    description(asHtml: false)
  }
}
"""

# ─────────────────────────────────────────────────────────────
#  HTTP Helper (Termux / SSL-safe)
# ─────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 12; Termux) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Mobile Safari/537.36"
    ),
    "Accept": "application/json",
    "Content-Type": "application/json",
}


async def anilist_request(query: str, variables: dict) -> Optional[dict]:
    """Execute a GraphQL request against AniList, SSL-safe for Termux."""
    connector = aiohttp.TCPConnector(ssl=False)
    try:
        async with aiohttp.ClientSession(
            connector=connector, headers=HEADERS
        ) as session:
            async with session.post(
                ANILIST_URL,
                json={"query": query, "variables": variables},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    log.warning("AniList returned HTTP %s", resp.status)
                    return None
                data = await resp.json(content_type=None)
                return data.get("data")
    except asyncio.TimeoutError:
        log.error("AniList request timed out")
        return None
    except Exception as exc:
        log.exception("AniList request failed: %s", exc)
        return None

# ─────────────────────────────────────────────────────────────
#  Unicode Math-Bold Digit Converter
# ─────────────────────────────────────────────────────────────
_MATH_BOLD_DIGITS = {
    "0": "𝟶", "1": "𝟷", "2": "𝟸", "3": "𝟹", "4": "𝟺",
    "5": "𝟻", "6": "𝟼", "7": "𝟽", "8": "𝟾", "9": "𝟿",
}


def to_math_bold(value: Optional[float | int | str]) -> str:
    """Convert a numeric string / number to mathematical bold unicode digits."""
    if value is None:
        return "N/A"
    text = str(value)
    return "".join(_MATH_BOLD_DIGITS.get(ch, ch) for ch in text)


# ─────────────────────────────────────────────────────────────
#  Caption Builders
# ─────────────────────────────────────────────────────────────

def _strip_html(text: str) -> str:
    """Remove HTML tags and unescape HTML entities."""
    clean = re.sub(r"<[^>]+>", "", text or "")
    return html.unescape(clean).strip()


def _format_season(season: Optional[str], year: Optional[int]) -> str:
    if not season:
        return "N/A"
    # Pad year to 2-digit style isn't standard, keep as SEASON YEAR
    season_name = season.capitalize()
    return f"{season_name} {year}" if year else season_name


def _format_status(status: Optional[str]) -> str:
    mapping = {
        "FINISHED":         "Finished ✅",
        "RELEASING":        "Airing 📡",
        "NOT_YET_RELEASED": "Upcoming 🔜",
        "CANCELLED":        "Cancelled ❌",
        "HIATUS":           "On Hiatus ⏸",
    }
    return mapping.get(status or "", status or "N/A")


def _format_format(fmt: Optional[str]) -> str:
    mapping = {
        "TV":         "TV Series",
        "TV_SHORT":   "TV Short",
        "MOVIE":      "Movie",
        "SPECIAL":    "Special",
        "OVA":        "OVA",
        "ONA":        "ONA",
        "MUSIC":      "Music Video",
        "MANGA":      "Manga",
        "NOVEL":      "Novel",
        "ONE_SHOT":   "One Shot",
    }
    return mapping.get(fmt or "", fmt or "N/A")


def build_caption(media: dict) -> str:
    title_romaji  = (media.get("title") or {}).get("romaji") or ""
    title_english = (media.get("title") or {}).get("english") or ""
    display_title = (title_english or title_romaji).upper()

    category  = _format_format(media.get("format"))
    season    = _format_season(media.get("season"), media.get("seasonYear"))
    episodes  = media.get("episodes") or "N/A"
    runtime   = f"{media.get('duration')} min" if media.get("duration") else "N/A"

    raw_score = media.get("averageScore")
    if raw_score is not None:
        score_float = raw_score / 10.0          # AniList gives 0-100
        # Format to one decimal, then bold-ify
        score_str = f"{score_float:.1f}"
    else:
        score_str = None
    bold_score = to_math_bold(score_str) if score_str else "N/A"

    status  = _format_status(media.get("status"))
    studios = [s["name"] for s in (media.get("studios") or {}).get("nodes", [])]
    studio_str = ", ".join(studios) if studios else "N/A"
    genres  = ", ".join(media.get("genres") or []) or "N/A"

    raw_desc = media.get("description") or "No synopsis available."
    synopsis = _strip_html(raw_desc)
    if len(synopsis) > 300:
        synopsis = synopsis[:297].rsplit(" ", 1)[0] + "…"

    caption = (
        f"<b>"
        f"<blockquote>「 {display_title} 」</blockquote>\n"
        f"═══════════════════\n"
        f"🌸 Category: {category}\n"
        f"🍥 Season: {season}\n"
        f"🧊 Episodes: {episodes}\n"
        f"🍣 Runtime: {runtime}\n"
        f"🍡 Rating: {bold_score}/📯\n"
        f"🍙 Status: {status}\n"
        f"🍵 Studio: {studio_str}\n"
        f"🎐 Genres: {genres}\n"
        f"═══════════════════\n"
        f"<blockquote>🥗 Synopsis: {synopsis}</blockquote>\n\n"
        f"<blockquote>POWERED BY: [@KENSHIN_ANIME]</blockquote>"
        f"</b>"
    )
    return caption


# ─────────────────────────────────────────────────────────────
#  Handlers
# ─────────────────────────────────────────────────────────────

@app.on_message(filters.text & ~filters.command([
    "start", "help", "about", "settings", "cancel",
    # extend as needed
]))
async def handle_search(client: Client, message: Message):
    """Triggered on any plain text — searches AniList and shows choice list."""
    query_text = message.text.strip()
    if not query_text:
        return

    log.info("Search | user=%s | query=%r", message.from_user.id, query_text)

    # Fetch top-5 results
    data = await anilist_request(SEARCH_QUERY, {"search": query_text})
    if not data:
        await message.reply(
            "⚠️ Couldn't reach AniList right now. Please try again later.",
            quote=True,
        )
        return

    results = (data.get("Page") or {}).get("media") or []
    if not results:
        await message.reply(
            f"😔 No results found for <b>{html.escape(query_text)}</b>.",
            parse_mode="html",
            quote=True,
        )
        return

    # Build inline keyboard — one button per result
    buttons = []
    for anime in results:
        anime_id = anime["id"]
        title = (
            anime["title"].get("english")
            or anime["title"].get("romaji")
            or "Unknown"
        )
        # Callback data format: "anime:<id>"
        buttons.append([
            InlineKeyboardButton(
                text=f"🎌 {title}",
                callback_data=f"anime:{anime_id}",
            )
        ])

    markup = InlineKeyboardMarkup(buttons)
    await message.reply(
        f"🔍 Found <b>{len(results)}</b> results for <b>{html.escape(query_text)}</b>. Pick one:",
        parse_mode="html",
        reply_markup=markup,
        quote=True,
    )


@app.on_callback_query(filters.regex(r"^anime:(\d+)$"))
async def handle_anime_detail(client: Client, callback: CallbackQuery):
    """Fetches full anime details and sends poster + styled caption."""
    anime_id = int(callback.matches[0].group(1))
    log.info("Detail | user=%s | anime_id=%d", callback.from_user.id, anime_id)

    await callback.answer("⏳ Loading anime info…", show_alert=False)

    data = await anilist_request(DETAIL_QUERY, {"id": anime_id})
    if not data or not data.get("Media"):
        try:
            await callback.edit_message_text(
                "⚠️ Failed to fetch anime details. Please try again.",
                parse_mode="html",
            )
        except MessageNotModified:
            pass
        return

    media   = data["Media"]
    caption = build_caption(media)
    poster  = (media.get("coverImage") or {}).get("extraLarge")

    # Remove the choice-list message, then send poster + caption
    try:
        await callback.message.delete()
    except Exception:
        pass  # Not critical

    if poster:
        try:
            await callback.message.reply_photo(
                photo=poster,
                caption=caption,
                parse_mode="html",
                quote=False,
            )
        except Exception as exc:
            log.warning("Photo send failed (%s), falling back to text.", exc)
            await callback.message.reply(
                caption,
                parse_mode="html",
                quote=False,
                disable_web_page_preview=True,
            )
    else:
        await callback.message.reply(
            caption,
            parse_mode="html",
            quote=False,
            disable_web_page_preview=True,
        )


# ─────────────────────────────────────────────────────────────
#  /start  &  /help
# ─────────────────────────────────────────────────────────────

@app.on_message(filters.command("start"))
async def cmd_start(client: Client, message: Message):
    await message.reply(
        "<b>「 KENSHIN ANIME'S — Search Bot 」</b>\n\n"
        "Just type any anime title and I'll find it for you! 🎌\n\n"
        "<i>Example: <code>Attack on Titan</code></i>\n\n"
        "<blockquote>POWERED BY: [@KENSHIN_ANIME]</blockquote>",
        parse_mode="html",
    )


@app.on_message(filters.command("help"))
async def cmd_help(client: Client, message: Message):
    await message.reply(
        "<b>How to use me:</b>\n\n"
        "1️⃣ Simply type the name of any anime.\n"
        "2️⃣ I'll show you the top 5 matching titles.\n"
        "3️⃣ Tap a title to see full details & poster.\n\n"
        "<i>No commands needed — just type and search!</i>",
        parse_mode="html",
    )


# ─────────────────────────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("Starting KENSHIN ANIME'S Bot…")
    app.run()
