"""Foydalanuvchi bo'limi: qidiruv, janr/yil, top, saqlanganlar, baholash, serial qismlari."""
from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database import Database
from keyboards.user_kb import episodes_kb, genres_kb, results_kb, seasons_kb, years_kb
from utils.cards import refresh_card, send_card, send_episode, show_by_code
from utils.helpers import edit_or_send, esc, send_media

router = Router()

TITLES = {"text": "🔎 Qidiruv natijalari", "genre": "🎭 Janr", "year": "📅 Yil",
          "top": "🔥 Eng ko'p ko'rilganlar", "new": "🆕 Yangi qo'shilganlar", "fav": "⭐ Saqlanganlar"}


async def get_results(db: Database, mode: str, q: str, user_id: int):
    return await db.list_favs(user_id) if mode == "fav" else await db.search(mode, q)


async def show_results(msg: Message, state: FSMContext, db: Database, mode: str, q: str, user_id: int):
    results = await get_results(db, mode, q, user_id)
    if not results:
        await msg.answer("😔 Hech narsa topilmadi.\nBoshqa nom/kod bilan urinib ko'ring.")
        return
    await state.update_data(sr_mode=mode, sr_q=q)
    title = TITLES[mode] + (f": <b>{esc(q)}</b>" if mode in ("text", "genre", "year") else "")
    await msg.answer(f"{title}\n📦 Topildi: {len(results)} ta", reply_markup=results_kb(results, 0, "sr"))


# ------------------------------------------------------------ menyu
@router.message(F.text == "🔍 Qidirish")
async def menu_search(message: Message):
    await message.answer("🔍 Kino/serial <b>kodi</b>, <b>nomi</b>, <b>janri</b> yoki <b>yilini</b> yuboring:")


@router.message(F.text == "🎭 Janrlar")
async def menu_genres(message: Message, db: Database):
    genres = await db.genres()
    if not genres:
        return await message.answer("Hozircha janrlar yo'q.")
    await message.answer("🎭 Janrni tanlang:", reply_markup=genres_kb(genres))


@router.message(F.text == "📅 Yillar")
async def menu_years(message: Message, db: Database):
    years = await db.years()
    if not years:
        return await message.answer("Hozircha yillar yo'q.")
    await message.answer("📅 Yilni tanlang:", reply_markup=years_kb(years))


@router.message(F.text == "🔥 Top")
async def menu_top(message: Message, state: FSMContext, db: Database):
    await show_results(message, state, db, "top", "", message.from_user.id)


@router.message(F.text == "🆕 Yangilar")
async def menu_new(message: Message, state: FSMContext, db: Database):
    await show_results(message, state, db, "new", "", message.from_user.id)


@router.message(F.text == "⭐ Saqlanganlar")
async def menu_fav(message: Message, state: FSMContext, db: Database):
    await show_results(message, state, db, "fav", "", message.from_user.id)


# ----------------------------------------------------- matnli qidiruv
@router.message(StateFilter(None), F.text, ~F.text.startswith("/"))
async def text_search(message: Message, state: FSMContext, db: Database, bot: Bot):
    q = message.text.strip()
    kind, row = await db.find_code(q)
    if row:
        is_admin = await db.is_admin(message.from_user.id)
        return await show_by_code(bot, message.chat.id, db, kind, row, message.from_user.id, is_admin)
    mode = "year" if (q.isdigit() and len(q) == 4) else "text"
    await show_results(message, state, db, mode, q, message.from_user.id)


# -------------------------------------------------------- callbacklar
@router.callback_query(F.data.startswith("g:"))
async def cb_genre(call: CallbackQuery, state: FSMContext, db: Database):
    await call.answer()
    await show_results(call.message, state, db, "genre", call.data[2:], call.from_user.id)


@router.callback_query(F.data.startswith("y:"))
async def cb_year(call: CallbackQuery, state: FSMContext, db: Database):
    await call.answer()
    await show_results(call.message, state, db, "year", call.data[2:], call.from_user.id)


@router.callback_query(F.data.startswith("sr:"))
async def cb_page(call: CallbackQuery, state: FSMContext, db: Database):
    page = int(call.data.split(":")[1])
    d = await state.get_data()
    if "sr_mode" not in d:
        return await call.answer("Qaytadan qidiring", show_alert=True)
    results = await get_results(db, d["sr_mode"], d.get("sr_q", ""), call.from_user.id)
    try:
        await call.message.edit_reply_markup(reply_markup=results_kb(results, page, "sr"))
    except TelegramBadRequest:
        pass
    await call.answer()


@router.callback_query(F.data.startswith("open:"))
async def cb_open(call: CallbackQuery, db: Database, bot: Bot):
    _, kind, iid = call.data.split(":")
    row = await db.get_item(kind, int(iid))
    if not row:
        return await call.answer("Topilmadi (o'chirilgan bo'lishi mumkin)", show_alert=True)
    await send_card(bot, call.message.chat.id, db, kind, row, call.from_user.id,
                    await db.is_admin(call.from_user.id))
    await call.answer()


@router.callback_query(F.data.startswith("watch:movie:"))
async def cb_watch(call: CallbackQuery, db: Database, bot: Bot):
    iid = int(call.data.split(":")[2])
    row = await db.get_item("movie", iid)
    if not row or not row.get("file_id"):
        return await call.answer("Video mavjud emas", show_alert=True)
    await call.answer("📥 Yuborilmoqda...")
    me = await bot.me()
    caption = f"🎬 <b>{esc(row['title'])}</b>\n🔑 Kod: <code>{esc(str(row['code']))}</code>\n\n🤖 @{me.username}"
    await send_media(bot, call.message.chat.id, row["file_type"], row["file_id"], caption)
    await db.add_view("movie", iid)


@router.callback_query(F.data.startswith("fav:"))
async def cb_fav(call: CallbackQuery, db: Database, bot: Bot):
    _, kind, iid = call.data.split(":")
    added = await db.toggle_fav(call.from_user.id, kind, int(iid))
    await call.answer("❤️ Saqlandi" if added else "💔 Olib tashlandi")
    await refresh_card(call, bot, db, kind, int(iid), await db.is_admin(call.from_user.id))


@router.callback_query(F.data.startswith("rate:"))
async def cb_rate(call: CallbackQuery, db: Database, bot: Bot):
    _, kind, iid, n = call.data.split(":")
    await db.set_rating(call.from_user.id, kind, int(iid), int(n))
    await call.answer(f"Rahmat! Bahoyingiz: {n}⭐")
    await refresh_card(call, bot, db, kind, int(iid), await db.is_admin(call.from_user.id))


# ------------------------------------------------------ serial qismlari
async def show_episodes(call: CallbackQuery, db: Database, sid: int, season: int, multi: bool):
    series = await db.get_item("series", sid)
    eps = await db.list_episodes(sid, season)
    if not series or not eps:
        return await call.answer("Qismlar topilmadi", show_alert=True)
    await edit_or_send(call, f"📺 <b>{esc(series['title'])}</b> — {season}-sezon\n\nQismni tanlang:",
                       episodes_kb(sid, eps, multi))


@router.callback_query(F.data.startswith("seasons:"))
async def cb_seasons(call: CallbackQuery, db: Database):
    sid = int(call.data.split(":")[1])
    seasons = await db.season_counts(sid)
    if not seasons:
        return await call.answer("Hozircha qismlar qo'shilmagan", show_alert=True)
    await call.answer()
    if len(seasons) == 1:
        return await show_episodes(call, db, sid, seasons[0]["season"], False)
    series = await db.get_item("series", sid)
    await edit_or_send(call, f"📺 <b>{esc(series['title'])}</b>\n\nSezonni tanlang:", seasons_kb(sid, seasons))


@router.callback_query(F.data.startswith("season:"))
async def cb_season(call: CallbackQuery, db: Database):
    _, sid, season = call.data.split(":")
    await call.answer()
    multi = len(await db.season_counts(int(sid))) > 1
    await show_episodes(call, db, int(sid), int(season), multi)


@router.callback_query(F.data.startswith("ep:"))
async def cb_episode(call: CallbackQuery, db: Database, bot: Bot):
    ep = await db.get_episode(int(call.data.split(":")[1]))
    if not ep:
        return await call.answer("Qism topilmadi", show_alert=True)
    await call.answer("📥 Yuborilmoqda...")
    await send_episode(bot, call.message.chat.id, db, ep, await db.is_admin(call.from_user.id))
