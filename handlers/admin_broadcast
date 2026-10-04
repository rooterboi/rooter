"""Admin: barcha foydalanuvchilarga xabarnoma (rassilka)."""
import asyncio

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton as IB, InlineKeyboardMarkup as IM, Message

from database import Database
from handlers.filters import IsAdmin
from keyboards.admin_kb import CANCEL, cancel_kb
from utils.states import BroadcastSt

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())
_tasks: set = set()


@router.callback_query(F.data == "adm:bc")
async def bc_start(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(BroadcastSt.content)
    await call.answer()
    await call.message.answer("✉️ Yubormoqchi bo'lgan xabaringizni yuboring (matn, rasm, video, tugmasiz).",
                              reply_markup=cancel_kb())


@router.message(BroadcastSt.content)
async def bc_content(message: Message, state: FSMContext, db: Database):
    await state.update_data(chat_id=message.chat.id, msg_id=message.message_id)
    await state.set_state(BroadcastSt.confirm)
    total = len(await db.user_ids())
    kb = IM(inline_keyboard=[[IB(text=f"✅ Yuborish ({total} ta)", callback_data="bc:go")], [CANCEL]])
    await message.reply("Yuqoridagi xabar barcha foydalanuvchilarga yuboriladi. Tasdiqlaysizmi?", reply_markup=kb)


async def _run(bot: Bot, db: Database, from_chat: int, msg_id: int, admin_chat: int):
    ok = fail = 0
    for uid in await db.user_ids():
        try:
            await bot.copy_message(uid, from_chat, msg_id)
            ok += 1
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await bot.copy_message(uid, from_chat, msg_id)
                ok += 1
            except Exception:
                fail += 1
        except TelegramForbiddenError:
            await db.mark_blocked(uid)
            fail += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)      # Telegram limiti: ~30 xabar/soniya
    await bot.send_message(admin_chat, f"✅ Rassilka tugadi!\n\n📨 Yuborildi: <b>{ok}</b>\n🚫 Yetmadi: <b>{fail}</b>")


@router.callback_query(BroadcastSt.confirm, F.data == "bc:go")
async def bc_go(call: CallbackQuery, state: FSMContext, db: Database, bot: Bot):
    d = await state.get_data()
    await state.clear()
    await call.answer("🚀 Boshlandi")
    await call.message.answer("🚀 Rassilka fonda boshlandi. Tugagach xabar beraman.")
    t = asyncio.create_task(_run(bot, db, d["chat_id"], d["msg_id"], call.message.chat.id))
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)
