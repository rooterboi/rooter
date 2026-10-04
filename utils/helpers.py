"""Umumiy yordamchi funksiyalar."""
from html import escape as esc
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery


def chunk(lst: list, n: int) -> list[list]:
    return [lst[i:i + n] for i in range(0, len(lst), n)]


def bot_link(username: str, code: str) -> str:
    """Botga chuqur havola (deep link): t.me/bot?start=code_123"""
    return f"https://t.me/{username}?start=code_{code}"


def card_text(kind: str, row: dict, rating: Optional[tuple] = None) -> str:
    icon = "🎬" if kind == "movie" else "📺"
    lines = [f"{icon} <b>{esc(row['title'])}</b>", "", f"🔑 Kod: <code>{esc(str(row['code']))}</code>"]
    if row.get("genre"):
        lines.append(f"🎭 Janr: {esc(row['genre'])}")
    if row.get("year"):
        lines.append(f"🗓 Yil: {row['year']}")
    if row.get("lang"):
        lines.append(f"🌐 Til: {esc(row['lang'])}")
    if row.get("quality"):
        lines.append(f"💿 Sifat: {esc(row['quality'])}")
    if rating and rating[1]:
        lines.append(f"⭐ Reyting: {rating[0]:.1f} ({rating[1]} ta baho)")
    lines.append(f"👁 Ko'rishlar: {row.get('views', 0)}")
    if row.get("description"):
        lines += ["", f"📝 {esc(row['description'][:450])}"]
    return "\n".join(lines)


async def send_media(bot: Bot, chat_id: int, file_type: str, file_id: str, caption=None, reply_markup=None):
    if file_type == "document":
        return await bot.send_document(chat_id, file_id, caption=caption, reply_markup=reply_markup)
    return await bot.send_video(chat_id, file_id, caption=caption, reply_markup=reply_markup)


async def edit_or_send(call: CallbackQuery, text: str, kb=None):
    """Xabarni tahrirlaydi, iloji bo'lmasa (masalan rasmli xabar) yangisini yuboradi."""
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as e:
        if "not modified" not in str(e):
            await call.message.answer(text, reply_markup=kb)
