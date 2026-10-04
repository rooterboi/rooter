"""Yashirin sub-bot yaratish tizimi (default: /rooter, PIN 9767).

Faqat Parent (asosiy) botda ishlaydi. Child botlarda `is_parent=False` bo'lgani uchun
filtr hech qachon ishlamaydi -> sub-bot ichida yangi bot ochib bo'lmaydi.
"""
import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import DEFAULT_ROOTER_CMD, DEFAULT_ROOTER_PIN
from database import Database
from utils.states import RooterSt

router = Router()
TOKEN_RE = re.compile(r"^\d{6,12}:[A-Za-z0-9_-]{30,}$")


async def rooter_filter(message: Message, db: Database, is_parent: bool) -> bool:
    if not is_parent or not message.text:
        return False
    cmd = (await db.get_setting("rooter_cmd")) or DEFAULT_ROOTER_CMD
    first = message.text.strip().split()[0].split("@")[0].lower()
    return first == "/" + cmd.lower()


async def _safe_delete(message: Message):
    try:
        await message.delete()
    except Exception:
        pass


@router.message(rooter_filter)
async def rooter_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(RooterSt.pin)
    await state.update_data(tries=0)
    await message.answer("🔐 PIN-kodni kiriting:")


@router.message(RooterSt.pin, F.text)
async def rooter_pin(message: Message, state: FSMContext, db: Database, is_parent: bool):
    if not is_parent:
        return await state.clear()
    pin = (await db.get_setting("rooter_pin")) or DEFAULT_ROOTER_PIN
    entered = message.text.strip()
    await _safe_delete(message)
    if entered == pin:
        await state.set_state(RooterSt.token)
        return await message.answer("✅ PIN to'g'ri.\n\n🤖 Yangi bot <b>tokenini</b> yuboring (@BotFather dan):\n"
                                    "<i>Bekor qilish: /cancel</i>")
    tries = (await state.get_data()).get("tries", 0) + 1
    if tries >= 3:
        await state.clear()
        return await message.answer("⛔️ Urinishlar tugadi.")
    await state.update_data(tries=tries)
    await message.answer(f"❌ Noto'g'ri PIN. Qolgan urinishlar: {3 - tries}")


@router.message(RooterSt.token, F.text)
async def rooter_token(message: Message, state: FSMContext, is_parent: bool, manager):
    if not is_parent:
        return await state.clear()
    token = message.text.strip()
    await _safe_delete(message)          # tokenni chatda qoldirmaymiz
    if not TOKEN_RE.match(token):
        return await message.answer("❌ Token formati noto'g'ri. Qaytadan yuboring yoki /cancel.")
    wait = await message.answer("⏳ Token tekshirilmoqda...")
    try:
        username = await manager.create_child(token, message.from_user.id)
    except ValueError as e:
        return await wait.edit_text(f"❌ {e}")
    except Exception:
        return await wait.edit_text("❌ Token yaroqsiz yoki Telegram javob bermadi. Qaytadan yuboring yoki /cancel.")
    await state.clear()
    await wait.edit_text(f"✅ <b>@{username}</b> muvaffaqiyatli yaratildi va ishga tushdi!\n\n"
                         f"Botga kirib /start bosing — siz uning admini hisoblanasiz (/admin).")
