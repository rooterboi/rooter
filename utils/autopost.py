"""Yangi kino/serial qo'shilganda avto-post kanallarga chiroyli post joylash."""
import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database import Database
from utils.helpers import bot_link, esc

log = logging.getLogger(__name__)


async def autopost(bot: Bot, db: Database, kind: str, row: dict) -> tuple[int, int]:
    """(muvaffaqiyatli, jami) qaytaradi."""
    channels = await db.list_channels("post")
    if not channels:
        return 0, 0
    me = await bot.me()
    icon = "🎬" if kind == "movie" else "📺"
    lines = [f"{icon} <b>{esc(row['title'])}</b>", ""]
    if row.get("genre"):
        lines.append(f"🎭 Janr: {esc(row['genre'])}")
    if row.get("year"):
        lines.append(f"🗓 Yil: {row['year']}")
    if row.get("lang"):
        lines.append(f"🌐 Til: {esc(row['lang'])}")
    if row.get("quality"):
        lines.append(f"💿 Sifat: {esc(row['quality'])}")
    lines.append(f"🔑 Kod: <code>{esc(str(row['code']))}</code>")
    if row.get("description"):
        lines += ["", f"📝 {esc(row['description'][:300])}"]
    lines += ["", f"🤖 @{me.username} ga o'ting va kodni yuboring!"]
    text = "\n".join(lines)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="▶️ Botga o'tish", url=bot_link(me.username, row["code"]))]])
    ok = 0
    for ch in channels:
        try:
            if row.get("poster"):
                await bot.send_photo(ch["chat_id"], row["poster"], caption=text, reply_markup=kb)
            else:
                await bot.send_message(ch["chat_id"], text, reply_markup=kb)
            ok += 1
        except Exception as e:  # noqa
            log.warning("Avto-post xatosi (%s): %s", ch["chat_id"], e)
    return ok, len(channels)
