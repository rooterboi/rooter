"""Admin panel: bosh menyu, statistika, bekor qilish."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database import Database
from handlers.filters import IsAdmin
from keyboards.admin_kb import admin_menu
from utils.helpers import edit_or_send

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(Command("admin"))
@router.message(F.text == "👑 Admin panel")
async def admin_open(message: Message, state: FSMContext, is_parent: bool):
    await state.clear()
    await message.answer("👑 <b>Admin panel</b>", reply_markup=admin_menu(is_parent))


@router.callback_query(F.data.in_({"adm:home", "adm:cancel"}))
async def admin_home(call: CallbackQuery, state: FSMContext, is_parent: bool):
    await state.clear()
    await call.answer()
    await edit_or_send(call, "👑 <b>Admin panel</b>", admin_menu(is_parent))


@router.callback_query(F.data == "adm:close")
async def admin_close(call: CallbackQuery):
    await call.answer()
    try:
        await call.message.delete()
    except Exception:
        pass


@router.callback_query(F.data == "adm:stats")
async def admin_stats(call: CallbackQuery, db: Database, is_parent: bool, manager):
    s = await db.stats()
    text = (f"📊 <b>Statistika</b>\n\n"
            f"👥 Foydalanuvchilar: <b>{s['users']}</b>\n"
            f"🆕 Bugun qo'shilgan: <b>{s['today']}</b>\n"
            f"🟢 Bugun faol: <b>{s['active']}</b>\n"
            f"🚫 Botni bloklaganlar: <b>{s['blocked']}</b>\n\n"
            f"🎬 Kinolar: <b>{s['movies']}</b>\n"
            f"📺 Seriallar: <b>{s['series']}</b> ({s['episodes']} qism)\n"
            f"👁 Jami ko'rishlar: <b>{s['views']}</b>\n\n"
            f"📢 Majburiy obuna kanallari: <b>{s['subs']}</b>\n"
            f"📡 Avto-post kanallari: <b>{s['posts']}</b>")
    if is_parent:
        text += f"\n🤖 Sub-botlar: <b>{len(await manager.main_db.list_bots())}</b>"
    from aiogram.types import InlineKeyboardButton as IB, InlineKeyboardMarkup as IM
    await call.answer()
    await edit_or_send(call, text, IM(inline_keyboard=[[IB(text="◀️ Orqaga", callback_data="adm:home")]]))
