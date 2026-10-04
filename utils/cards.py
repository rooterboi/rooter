"""Kino / serial / qism kartochkalarini yuborish."""
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from database import Database
from keyboards.user_kb import episode_kb, item_kb
from utils.helpers import bot_link, card_text, esc, send_media


async def build_card(bot: Bot, db: Database, kind: str, row: dict, user_id: int, is_admin: bool):
    rating = await db.get_rating(kind, row["id"])
    fav = await db.is_fav(user_id, kind, row["id"])
    me = await bot.me()
    return card_text(kind, row, rating), item_kb(kind, row, fav, is_admin, bot_link(me.username, row["code"]))


async def send_card(bot: Bot, chat_id: int, db: Database, kind: str, row: dict, user_id: int, is_admin: bool):
    text, kb = await build_card(bot, db, kind, row, user_id, is_admin)
    if row.get("poster"):
        try:
            return await bot.send_photo(chat_id, row["poster"], caption=text, reply_markup=kb)
        except TelegramBadRequest:
            pass
    return await bot.send_message(chat_id, text, reply_markup=kb)


async def refresh_card(call: CallbackQuery, bot: Bot, db: Database, kind: str, item_id: int, is_admin: bool):
    row = await db.get_item(kind, item_id)
    if not row:
        return
    text, kb = await build_card(bot, db, kind, row, call.from_user.id, is_admin)
    try:
        if call.message.photo:
            await call.message.edit_caption(caption=text, reply_markup=kb)
        else:
            await call.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        pass


async def send_episode(bot: Bot, chat_id: int, db: Database, ep: dict, is_admin: bool):
    series = await db.get_item("series", ep["series_id"])
    nxt = await db.adjacent_episode(ep)
    title = esc(series["title"]) if series else "Serial"
    caption = (f"📺 <b>{title}</b>\n{ep['season']}-sezon, {ep['episode']}-qism\n"
               f"🔑 Kod: <code>{esc(str(ep['code']))}</code>")
    await send_media(bot, chat_id, ep["file_type"], ep["file_id"], caption, episode_kb(ep, nxt, is_admin))
    await db.add_view("series", ep["series_id"])


async def show_by_code(bot: Bot, chat_id: int, db: Database, kind: str, row: dict, user_id: int, is_admin: bool):
    if kind == "episode":
        await send_episode(bot, chat_id, db, row, is_admin)
    else:
        await send_card(bot, chat_id, db, kind, row, user_id, is_admin)
