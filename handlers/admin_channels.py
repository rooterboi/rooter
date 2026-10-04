"""Admin: majburiy obuna (sub) va avto-post (post) kanallarini boshqarish."""
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton as IB, InlineKeyboardMarkup as IM, Message

from database import Database
from handlers.filters import IsAdmin
from keyboards.admin_kb import cancel_kb
from utils.helpers import edit_or_send, esc
from utils.states import ChannelSt

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

NAMES = {"sub": "📢 Majburiy obuna kanallari", "post": "📡 Avto-post kanallari"}


async def render(call_or_msg, db: Database, kind: str):
    chs = await db.list_channels(kind)
    rows = [[IB(text=f"🗑 {c['title'] or c['chat_id']}", callback_data=f"ch_del:{c['id']}:{kind}")] for c in chs]
    rows.append([IB(text="➕ Kanal qo'shish", callback_data=f"ch_add:{kind}")])
    rows.append([IB(text="◀️ Orqaga", callback_data="adm:home")])
    text = f"<b>{NAMES[kind]}</b>\n\nJami: {len(chs)} ta" + ("\n(O'chirish uchun nomini bosing)" if chs else "")
    if isinstance(call_or_msg, CallbackQuery):
        await edit_or_send(call_or_msg, text, IM(inline_keyboard=rows))
    else:
        await call_or_msg.answer(text, reply_markup=IM(inline_keyboard=rows))


@router.callback_query(F.data.startswith("adm:ch:"))
async def ch_menu(call: CallbackQuery, db: Database):
    await call.answer()
    await render(call, db, call.data.split(":")[2])


@router.callback_query(F.data.startswith("ch_del:"))
async def ch_del(call: CallbackQuery, db: Database):
    _, cid, kind = call.data.split(":")
    await db.delete_channel(int(cid))
    await call.answer("🗑 O'chirildi")
    await render(call, db, kind)


@router.callback_query(F.data.startswith("ch_add:"))
async def ch_add(call: CallbackQuery, state: FSMContext):
    kind = call.data.split(":")[1]
    await state.clear()
    await state.set_state(ChannelSt.add)
    await state.update_data(kind=kind)
    await call.answer()
    await call.message.answer(
        "1️⃣ Avval botni kanalga <b>admin</b> qiling.\n"
        "2️⃣ Keyin kanaldan istalgan xabarni <b>forward</b> qiling yoki kanal <code>@username</code> / ID sini yuboring.",
        reply_markup=cancel_kb())


@router.message(ChannelSt.add)
async def ch_got(message: Message, state: FSMContext, db: Database, bot: Bot):
    kind = (await state.get_data())["kind"]
    ref = None
    origin = getattr(message, "forward_origin", None)
    if origin is not None and getattr(origin, "chat", None) is not None:
        ref = origin.chat.id
    elif message.text:
        t = message.text.strip()
        ref = int(t) if t.lstrip("-").isdigit() else t
    if ref is None:
        return await message.answer("❗️ Kanaldan xabar forward qiling yoki @username / ID yuboring.")
    try:
        chat = await bot.get_chat(ref)
        me = await bot.get_chat_member(chat.id, bot.id)
        if me.status not in ("administrator", "creator"):
            return await message.answer("❗️ Bot bu kanalda admin emas. Avval botni admin qiling.")
        link = f"https://t.me/{chat.username}" if chat.username else (
            chat.invite_link or await bot.export_chat_invite_link(chat.id))
    except Exception as e:
        return await message.answer(f"❌ Kanal topilmadi yoki bot admin emas.\n<code>{esc(str(e))}</code>")
    await db.add_channel(chat.id, chat.title or str(chat.id), link, kind)
    await state.clear()
    await message.answer(f"✅ <b>{esc(chat.title or '')}</b> qo'shildi.")
    await render(message, db, kind)
