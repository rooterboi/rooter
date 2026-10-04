"""/start, /cancel, obunani tekshirish."""
from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database import Database
from keyboards.user_kb import main_menu
from utils.cards import show_by_code
from utils.helpers import esc

router = Router()


async def send_welcome(bot: Bot, chat_id: int, user_id: int, name: str, db: Database, payload: str = ""):
    is_admin = await db.is_admin(user_id)
    text = await db.get_setting("welcome") or (
        f"👋 Salom, <b>{esc(name)}</b>!\n\n🎬 Kino yoki serial <b>kodini</b> yuboring, "
        f"yoki nomi / janri / yili bo'yicha qidiring.")
    await bot.send_message(chat_id, text, reply_markup=main_menu(is_admin))
    if payload.startswith("code_"):
        kind, row = await db.find_code(payload[5:])
        if row:
            await show_by_code(bot, chat_id, db, kind, row, user_id, is_admin)


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext, db: Database, bot: Bot):
    await state.clear()
    await send_welcome(bot, message.chat.id, message.from_user.id, message.from_user.full_name,
                       db, command.args or "")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, db: Database):
    await state.clear()
    is_admin = await db.is_admin(message.from_user.id)
    await message.answer("✅ Bekor qilindi.", reply_markup=main_menu(is_admin))


@router.callback_query(F.data.startswith("check_sub"))
async def check_sub(call: CallbackQuery, db: Database, bot: Bot):
    # Bu yerga faqat obuna tekshiruvidan o'tganlar yetib keladi (ForceSubMiddleware)
    payload = call.data.split(":", 1)[1] if ":" in call.data else ""
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.answer("✅ Rahmat!")
    await send_welcome(bot, call.message.chat.id, call.from_user.id, call.from_user.full_name, db, payload)


@router.callback_query(F.data == "noop")
async def noop(call: CallbackQuery):
    await call.answer()
