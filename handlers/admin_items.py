"""Admin: kino va seriallarni qo'shish / tahrirlash / o'chirish, qismlar boshqaruvi."""
import re

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton as IB, InlineKeyboardMarkup as IM, Message

from database import Database
from handlers.filters import IsAdmin
from keyboards.admin_kb import (CANCEL, cancel_kb, confirm_del_kb, edit_kb, field_kb, movies_menu,
                                series_menu, skip_kb)
from keyboards.user_kb import results_kb
from utils.autopost import autopost
from utils.cards import send_card
from utils.helpers import edit_or_send, esc
from utils.states import AddEpisode, AddItem, EditItem, FindItem

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

CODE_RE = re.compile(r"^[A-Za-z0-9_-]{1,20}$")
# (kalit, savol, majburiymi)
FIELDS = [
    ("title", "📝 <b>Nomini</b> kiriting:", True),
    ("code", "🔑 <b>Kod</b> kiriting (harf/raqam, masalan <code>101</code>) yoki avto-kod tanlang:", True),
    ("genre", "🎭 <b>Janr</b>ni kiriting (masalan: Jangari, Drama):", False),
    ("year", "🗓 <b>Yil</b>ni kiriting (masalan: 2024):", False),
    ("lang", "🌐 <b>Til</b>ni kiriting (masalan: O'zbek tilida):", False),
    ("quality", "💿 <b>Sifat</b>ni kiriting (masalan: 1080p):", False),
    ("description", "📄 <b>Tavsif</b>ni kiriting:", False),
]
SAVE_KEYS = ("code", "title", "genre", "year", "lang", "quality", "description", "poster", "file_id", "file_type")


# =================================================================== menyular
@router.callback_query(F.data == "adm:movies")
async def m_movies(call: CallbackQuery):
    await call.answer()
    await edit_or_send(call, "🎬 <b>Kinolar bo'limi</b>", movies_menu())


@router.callback_query(F.data == "adm:series")
async def m_series(call: CallbackQuery):
    await call.answer()
    await edit_or_send(call, "📺 <b>Seriallar bo'limi</b>", series_menu())


@router.callback_query(F.data.startswith("adm:list:"))
async def list_items(call: CallbackQuery, db: Database):
    _, _, kind, page = call.data.split(":")
    items = await db.list_items(kind)
    back = "adm:movies" if kind == "movie" else "adm:series"
    await call.answer()
    await edit_or_send(call, f"📋 Jami: <b>{len(items)}</b> ta\n(Ochish uchun bosing)",
                       results_kb(items, int(page), f"adm:list:{kind}", back_cb=back))


# =========================================================== qo'shish (kino/serial)
@router.callback_query(F.data.startswith("adm:add:"))
async def add_start(call: CallbackQuery, state: FSMContext):
    kind = call.data.split(":")[2]
    await state.clear()
    await state.update_data(kind=kind, step=0)
    await call.answer()
    if kind == "movie":
        await state.set_state(AddItem.video)
        await call.message.answer("🎥 Kino <b>videosini</b> yuboring (video yoki fayl ko'rinishida):",
                                  reply_markup=cancel_kb())
    else:
        await state.set_state(AddItem.poster)
        await call.message.answer("🖼 Serial <b>posterini</b> (rasm) yuboring:", reply_markup=skip_kb())


@router.message(AddItem.video, F.video | F.document)
async def got_video(message: Message, state: FSMContext):
    if message.video:
        fid, ftype = message.video.file_id, "video"
    else:
        fid, ftype = message.document.file_id, "document"
    await state.update_data(file_id=fid, file_type=ftype)
    await state.set_state(AddItem.poster)
    await message.answer("🖼 Endi <b>poster</b> (rasm) yuboring:", reply_markup=skip_kb())


@router.message(AddItem.video)
async def bad_video(message: Message):
    await message.answer("❗️ Iltimos, video yoki video-fayl yuboring.")


async def begin_fields(msg: Message, state: FSMContext):
    await state.set_state(AddItem.fields)
    await state.update_data(step=0)
    await ask_field(msg, 0)


@router.message(AddItem.poster, F.photo)
async def got_poster(message: Message, state: FSMContext):
    await state.update_data(poster=message.photo[-1].file_id)
    await begin_fields(message, state)


@router.callback_query(AddItem.poster, F.data == "af:skip")
async def skip_poster(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await begin_fields(call.message, state)


@router.message(AddItem.poster)
async def bad_poster(message: Message):
    await message.answer("❗️ Iltimos, rasm yuboring (yoki o'tkazib yuboring).")


async def ask_field(msg: Message, step: int):
    key, prompt, required = FIELDS[step]
    await msg.answer(f"<b>[{step + 1}/{len(FIELDS)}]</b> {prompt}", reply_markup=field_kb(key, required))


async def process_field(msg: Message, state: FSMContext, db: Database, bot: Bot, user_id: int, value):
    d = await state.get_data()
    step = d["step"]
    key = FIELDS[step][0]
    if value is not None:
        if key == "code":
            if not CODE_RE.match(value):
                return await msg.answer("❗️ Kod faqat harf, raqam, _ yoki - dan iborat bo'lsin (maks. 20 belgi).")
            if await db.code_exists(value):
                return await msg.answer("❗️ Bu kod band. Boshqa kod kiriting yoki avto-kodni tanlang.")
        elif key == "year":
            if not (value.isdigit() and 1880 <= int(value) <= 2100):
                return await msg.answer("❗️ Yilni to'g'ri kiriting (masalan: 2024).")
            value = int(value)
        await state.update_data(**{key: value})
    step += 1
    if step >= len(FIELDS):
        return await finish_add(msg, state, db, bot, user_id)
    await state.update_data(step=step)
    await ask_field(msg, step)


@router.message(AddItem.fields, F.text)
async def field_text(message: Message, state: FSMContext, db: Database, bot: Bot):
    await process_field(message, state, db, bot, message.from_user.id, message.text.strip())


@router.callback_query(AddItem.fields, F.data == "af:skip")
async def field_skip(call: CallbackQuery, state: FSMContext, db: Database, bot: Bot):
    await call.answer()
    await process_field(call.message, state, db, bot, call.from_user.id, None)


@router.callback_query(AddItem.fields, F.data == "af:auto")
async def field_auto(call: CallbackQuery, state: FSMContext, db: Database, bot: Bot):
    d = await state.get_data()
    if FIELDS[d["step"]][0] != "code":
        return await call.answer()
    await call.answer()
    await process_field(call.message, state, db, bot, call.from_user.id, await db.next_code())


async def finish_add(msg: Message, state: FSMContext, db: Database, bot: Bot, user_id: int):
    d = await state.get_data()
    kind = d["kind"]
    payload = {k: d[k] for k in SAVE_KEYS if d.get(k) is not None}
    item_id = await db.add_item(kind, **payload)
    await state.clear()
    row = await db.get_item(kind, item_id)
    await msg.answer("✅ Muvaffaqiyatli qo'shildi!" + ("\n\n➕ Endi <b>Seriallar → Qism qo'shish</b> orqali qismlarni biriktiring."
                                                      if kind == "series" else ""))
    await send_card(bot, msg.chat.id, db, kind, row, user_id, True)
    ok, total = await autopost(bot, db, kind, row)       # avto-post
    if total:
        await msg.answer(f"📡 Avto-post: {ok}/{total} ta kanalga joylandi.")


# ============================================================ topish (kod bo'yicha)
@router.callback_query(F.data.startswith("adm:find:"))
async def find_start(call: CallbackQuery, state: FSMContext):
    action = call.data.split(":")[2]
    await state.clear()
    await state.set_state(FindItem.code)
    await state.update_data(action=action)
    await call.answer()
    await call.message.answer("🔑 Kino/serial <b>kodini</b> yuboring:", reply_markup=cancel_kb())


@router.message(FindItem.code, F.text)
async def find_code(message: Message, state: FSMContext, db: Database):
    action = (await state.get_data())["action"]
    kind, row = await db.find_code(message.text)
    if not row:
        return await message.answer("❌ Bu kod bo'yicha hech narsa topilmadi. Qayta yuboring yoki bekor qiling.")
    if action in ("eps", "epadd") and kind != "series":
        return await message.answer("❗️ Bu serial kodi emas. Serial kodini yuboring.")
    await state.clear()
    if action == "edit":
        if kind == "episode":
            return await message.answer("ℹ️ Qismni tahrirlab bo'lmaydi — o'chirib, qaytadan qo'shing.",
                                        reply_markup=confirm_del_kb(kind, row["id"]))
        await message.answer(f"✏️ <b>{esc(row['title'])}</b>\nNimani o'zgartiramiz?", reply_markup=edit_kb(kind, row["id"]))
    elif action == "del":
        await message.answer(f"🗑 <b>{esc(row.get('title') or row['code'])}</b> o'chirilsinmi?",
                             reply_markup=confirm_del_kb(kind, row["id"]))
    elif action == "eps":
        await show_episode_list(message, db, row["id"])
    elif action == "epadd":
        await start_episode(message, state, db, row["id"])


# ================================================================== tahrirlash
@router.callback_query(F.data.startswith("adm_edit:"))
async def edit_menu(call: CallbackQuery):
    _, kind, iid = call.data.split(":")
    await call.answer()
    await call.message.answer("✏️ Nimani o'zgartiramiz?", reply_markup=edit_kb(kind, int(iid)))


@router.callback_query(F.data.startswith("ef:"))
async def edit_field(call: CallbackQuery, state: FSMContext):
    _, kind, iid, field = call.data.split(":")
    await state.clear()
    await state.set_state(EditItem.value)
    await state.update_data(kind=kind, iid=int(iid), field=field)
    prompts = {"poster": "🖼 Yangi <b>poster</b> (rasm) yuboring:", "file_id": "🎥 Yangi <b>video</b> yuboring:"}
    await call.answer()
    await call.message.answer(prompts.get(field, "✍️ Yangi qiymatni yuboring:"), reply_markup=cancel_kb())


@router.message(EditItem.value)
async def edit_value(message: Message, state: FSMContext, db: Database, bot: Bot):
    d = await state.get_data()
    kind, iid, field = d["kind"], d["iid"], d["field"]
    if field == "poster":
        if not message.photo:
            return await message.answer("❗️ Rasm yuboring.")
        updates = {"poster": message.photo[-1].file_id}
    elif field == "file_id":
        if message.video:
            updates = {"file_id": message.video.file_id, "file_type": "video"}
        elif message.document:
            updates = {"file_id": message.document.file_id, "file_type": "document"}
        else:
            return await message.answer("❗️ Video yuboring.")
    else:
        if not message.text:
            return await message.answer("❗️ Matn yuboring.")
        value = message.text.strip()
        if field == "code":
            if not CODE_RE.match(value):
                return await message.answer("❗️ Kod faqat harf, raqam, _ yoki - bo'lsin.")
            k, r = await db.find_code(value)
            if r and not (k == kind and r["id"] == iid):
                return await message.answer("❗️ Bu kod band.")
        elif field == "year":
            if not (value.isdigit() and 1880 <= int(value) <= 2100):
                return await message.answer("❗️ Yilni to'g'ri kiriting.")
            value = int(value)
        updates = {field: value}
    for k, v in updates.items():
        await db.update_item(kind, iid, k, v)
    await state.clear()
    await message.answer("✅ Yangilandi!")
    row = await db.get_item(kind, iid)
    await send_card(bot, message.chat.id, db, kind, row, message.from_user.id, True)


# ================================================================== o'chirish
@router.callback_query(F.data.startswith("adm_del:"))
async def del_ask(call: CallbackQuery):
    _, kind, iid = call.data.split(":")
    await call.answer()
    await call.message.answer("🗑 Rostdan ham o'chirasizmi? Bu amalni qaytarib bo'lmaydi.",
                              reply_markup=confirm_del_kb(kind, int(iid)))


@router.callback_query(F.data.startswith("adm_delok:"))
async def del_ok(call: CallbackQuery, db: Database):
    _, kind, iid = call.data.split(":")
    if kind == "episode":
        await db.delete_episode(int(iid))
    else:
        await db.delete_item(kind, int(iid))
    await call.answer("🗑 O'chirildi")
    await edit_or_send(call, "✅ O'chirildi.")


# ============================================================ serial qismlari
async def show_episode_list(msg: Message, db: Database, sid: int):
    series = await db.get_item("series", sid)
    eps = await db.list_episodes(sid)
    if not eps:
        return await msg.answer("📭 Bu serialda hali qismlar yo'q.")
    rows = [[IB(text=f"🗑 {e['season']}-sezon {e['episode']}-qism  [{e['code']}]",
                callback_data=f"adm_del:episode:{e['id']}")] for e in eps[:95]]
    await msg.answer(f"📃 <b>{esc(series['title'])}</b> — qismlar ({len(eps)} ta)\nO'chirish uchun bosing:",
                     reply_markup=IM(inline_keyboard=rows))


@router.callback_query(F.data.startswith("adm_eps:"))
async def cb_eps(call: CallbackQuery, db: Database):
    await call.answer()
    await show_episode_list(call.message, db, int(call.data.split(":")[1]))


async def start_episode(msg: Message, state: FSMContext, db: Database, sid: int):
    series = await db.get_item("series", sid)
    seasons = [s["season"] for s in await db.season_counts(sid)]
    nums = seasons + [(max(seasons) + 1) if seasons else 1]
    await state.clear()
    await state.set_state(AddEpisode.season)
    await state.update_data(series_id=sid)
    rows = [[IB(text=f"{n}-sezon" + (" (yangi)" if n not in seasons else ""), callback_data=f"es:{n}")] for n in nums]
    rows.append([CANCEL])
    await msg.answer(f"📺 <b>{esc(series['title'])}</b>\n\n📂 Sezon raqamini yuboring yoki tanlang:",
                     reply_markup=IM(inline_keyboard=rows))


@router.callback_query(F.data.startswith("adm_epadd:"))
async def cb_epadd(call: CallbackQuery, state: FSMContext, db: Database):
    await call.answer()
    await start_episode(call.message, state, db, int(call.data.split(":")[1]))


async def set_season(msg: Message, state: FSMContext, db: Database, season: int):
    sid = (await state.get_data())["series_id"]
    nxt = await db.next_episode_number(sid, season)
    await state.update_data(season=season)
    await state.set_state(AddEpisode.episode)
    kb = IM(inline_keyboard=[[IB(text=f"{nxt}-qism", callback_data=f"en:{nxt}")], [CANCEL]])
    await msg.answer(f"🎞 {season}-sezon. <b>Qism raqamini</b> yuboring yoki tavsiyani tanlang:", reply_markup=kb)


@router.callback_query(AddEpisode.season, F.data.startswith("es:"))
async def ep_season_cb(call: CallbackQuery, state: FSMContext, db: Database):
    await call.answer()
    await set_season(call.message, state, db, int(call.data.split(":")[1]))


@router.message(AddEpisode.season, F.text.regexp(r"^\d{1,3}$"))
async def ep_season_txt(message: Message, state: FSMContext, db: Database):
    await set_season(message, state, db, int(message.text))


async def set_episode(msg: Message, state: FSMContext, db: Database, num: int):
    d = await state.get_data()
    if await db.episode_exists(d["series_id"], d["season"], num):
        return await msg.answer("❗️ Bu qism raqami allaqachon mavjud. Boshqa raqam yuboring.")
    await state.update_data(episode=num)
    await state.set_state(AddEpisode.video)
    await msg.answer(f"🎥 {d['season']}-sezon {num}-qism <b>videosini</b> yuboring:", reply_markup=cancel_kb())


@router.callback_query(AddEpisode.episode, F.data.startswith("en:"))
async def ep_num_cb(call: CallbackQuery, state: FSMContext, db: Database):
    await call.answer()
    await set_episode(call.message, state, db, int(call.data.split(":")[1]))


@router.message(AddEpisode.episode, F.text.regexp(r"^\d{1,4}$"))
async def ep_num_txt(message: Message, state: FSMContext, db: Database):
    await set_episode(message, state, db, int(message.text))


@router.message(AddEpisode.video, F.video | F.document)
async def ep_video(message: Message, state: FSMContext):
    if message.video:
        await state.update_data(file_id=message.video.file_id, file_type="video")
    else:
        await state.update_data(file_id=message.document.file_id, file_type="document")
    await state.set_state(AddEpisode.code)
    kb = IM(inline_keyboard=[[IB(text="🔢 Avto kod", callback_data="ec:auto")], [CANCEL]])
    await message.answer("🔑 Qism uchun <b>kod</b> kiriting yoki avto-kod tanlang:", reply_markup=kb)


async def save_episode(msg: Message, state: FSMContext, db: Database, code: str):
    d = await state.get_data()
    await db.add_episode(d["series_id"], d["season"], d["episode"], code, d["file_id"], d["file_type"])
    nxt = d["episode"] + 1
    await state.set_state(AddEpisode.video)
    await state.update_data(episode=nxt, file_id=None)
    await msg.answer(f"✅ {d['season']}-sezon {d['episode']}-qism saqlandi (kod: <code>{esc(code)}</code>).\n\n"
                     f"🎥 Davom etish uchun <b>{nxt}-qism</b> videosini yuboring.",
                     reply_markup=IM(inline_keyboard=[[IB(text="✅ Tugatish", callback_data="adm:cancel")]]))


@router.message(AddEpisode.code, F.text)
async def ep_code_txt(message: Message, state: FSMContext, db: Database):
    code = message.text.strip()
    if not CODE_RE.match(code):
        return await message.answer("❗️ Kod faqat harf, raqam, _ yoki - bo'lsin.")
    if await db.code_exists(code):
        return await message.answer("❗️ Bu kod band.")
    await save_episode(message, state, db, code)


@router.callback_query(AddEpisode.code, F.data == "ec:auto")
async def ep_code_auto(call: CallbackQuery, state: FSMContext, db: Database):
    await call.answer()
    await save_episode(call.message, state, db, await db.next_code())


@router.message(AddEpisode.season)
@router.message(AddEpisode.episode)
async def ep_bad_number(message: Message):
    await message.answer("❗️ Faqat raqam yuboring.")


@router.message(AddEpisode.video)
async def ep_bad_video(message: Message):
    await message.answer("❗️ Video yuboring (yoki /cancel).")
