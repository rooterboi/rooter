"""Admin: adminlar, yashirin buyruq/PIN sozlamalari (faqat Parent), sub-botlar boshqaruvi."""
import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton as IB, InlineKeyboardMarkup as IM, Message

from config import DEFAULT_ROOTER_CMD, DEFAULT_ROOTER_PIN
from database import Database
from handlers.filters import IsAdmin
from keyboards.admin_kb import CANCEL, cancel_kb
from utils.helpers import edit_or_send, esc
from utils.states import SettingsSt

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())
RESERVED = {"start", "admin", "cancel", "help"}
BACK = [IB(text="◀️ Orqaga", callback_data="adm:home")]


# ============================================================== adminlar
async def render_admins(target, db: Database, me: int):
    admins = await db.list_admins()
    rows = [[IB(text=f"🗑 {a}", callback_data=f"adm_ad:del:{a}")] for a in admins if a != me]
    rows += [[IB(text="➕ Admin qo'shish", callback_data="adm_ad:add")], BACK]
    text = "👥 <b>Adminlar</b>\n\n" + "\n".join(f"• <code>{a}</code>" + (" (siz)" if a == me else "") for a in admins)
    if isinstance(target, CallbackQuery):
        await edit_or_send(target, text, IM(inline_keyboard=rows))
    else:
        await target.answer(text, reply_markup=IM(inline_keyboard=rows))


@router.callback_query(F.data == "adm:admins")
async def admins_menu(call: CallbackQuery, db: Database):
    await call.answer()
    await render_admins(call, db, call.from_user.id)


@router.callback_query(F.data.startswith("adm_ad:del:"))
async def admin_del(call: CallbackQuery, db: Database):
    await db.remove_admin(int(call.data.split(":")[2]))
    await call.answer("O'chirildi")
    await render_admins(call, db, call.from_user.id)


@router.callback_query(F.data == "adm_ad:add")
async def admin_add(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(SettingsSt.add_admin)
    await call.answer()
    await call.message.answer("👤 Yangi adminning Telegram <b>ID</b> sini yuboring:", reply_markup=cancel_kb())


@router.message(SettingsSt.add_admin, F.text)
async def admin_add_got(message: Message, state: FSMContext, db: Database):
    if not message.text.strip().isdigit():
        return await message.answer("❗️ Faqat raqamli ID yuboring.")
    await db.add_admin(int(message.text.strip()))
    await state.clear()
    await message.answer("✅ Admin qo'shildi.")
    await render_admins(message, db, message.from_user.id)


# ================================================== sozlamalar (faqat Parent)
@router.callback_query(F.data == "adm:settings")
async def settings(call: CallbackQuery, db: Database, is_parent: bool):
    if not is_parent:
        return await call.answer("Bu bo'lim faqat asosiy botda mavjud", show_alert=True)
    cmd = (await db.get_setting("rooter_cmd")) or DEFAULT_ROOTER_CMD
    pin = (await db.get_setting("rooter_pin")) or DEFAULT_ROOTER_PIN
    text = (f"⚙️ <b>Sozlamalar</b>\n\n🕵️ Yashirin buyruq: <code>/{esc(cmd)}</code>\n"
            f"🔐 PIN-kod: <tg-spoiler>{esc(pin)}</tg-spoiler>")
    kb = IM(inline_keyboard=[
        [IB(text="✏️ Buyruq nomini o'zgartirish", callback_data="set:cmd")],
        [IB(text="🔐 PIN-kodni o'zgartirish", callback_data="set:pin")],
        [IB(text="🤖 Sub-botlar", callback_data="adm:subbots")], BACK])
    await call.answer()
    await edit_or_send(call, text, kb)


@router.callback_query(F.data == "set:cmd")
async def set_cmd(call: CallbackQuery, state: FSMContext, is_parent: bool):
    if not is_parent:
        return await call.answer()
    await state.clear()
    await state.set_state(SettingsSt.rooter_cmd)
    await call.answer()
    await call.message.answer("✏️ Yangi buyruq nomini yuboring (slashsiz, lotin harf/raqam/_ , 3–32 belgi).\n"
                              "Masalan: <code>panel</code>", reply_markup=cancel_kb())


@router.message(SettingsSt.rooter_cmd, F.text)
async def set_cmd_got(message: Message, state: FSMContext, db: Database, is_parent: bool):
    if not is_parent:
        return await state.clear()
    v = message.text.strip().lstrip("/").lower()
    if not re.fullmatch(r"[a-z0-9_]{3,32}", v) or v in RESERVED:
        return await message.answer("❗️ Noto'g'ri nom. Lotin harf/raqam/_ , 3–32 belgi bo'lsin va band nomlar bo'lmasin.")
    await db.set_setting("rooter_cmd", v)
    await state.clear()
    await message.answer(f"✅ Yashirin buyruq endi: <code>/{v}</code>")


@router.callback_query(F.data == "set:pin")
async def set_pin(call: CallbackQuery, state: FSMContext, is_parent: bool):
    if not is_parent:
        return await call.answer()
    await state.clear()
    await state.set_state(SettingsSt.rooter_pin)
    await call.answer()
    await call.message.answer("🔐 Yangi PIN-kodni yuboring (4–16 belgi, harf/raqam):", reply_markup=cancel_kb())


@router.message(SettingsSt.rooter_pin, F.text)
async def set_pin_got(message: Message, state: FSMContext, db: Database, is_parent: bool):
    if not is_parent:
        return await state.clear()
    v = message.text.strip()
    try:
        await message.delete()
    except Exception:
        pass
    if not (4 <= len(v) <= 16 and v.isalnum()):
        return await message.answer("❗️ PIN 4–16 ta harf/raqamdan iborat bo'lsin.")
    await db.set_setting("rooter_pin", v)
    await state.clear()
    await message.answer("✅ PIN-kod yangilandi (xabaringiz xavfsizlik uchun o'chirildi).")


# ========================================================== sub-botlar
async def render_bots(call: CallbackQuery, manager):
    bots = await manager.main_db.list_bots()
    rows, lines = [], []
    for b in bots:
        st = "🟢" if b["active"] else "⚪️"
        lines.append(f"{st} @{b['username']} — egasi: <code>{b['owner_id']}</code>")
        rows.append([IB(text=("⏸ To'xtatish" if b["active"] else "▶️ Yoqish") + f" @{b['username']}",
                        callback_data=f"sb:toggle:{b['id']}"),
                     IB(text="🗑", callback_data=f"sb:del:{b['id']}")])
    rows.append([IB(text="◀️ Orqaga", callback_data="adm:settings")])
    text = "🤖 <b>Sub-botlar</b>\n\n" + ("\n".join(lines) if lines else "Hozircha sub-botlar yo'q.")
    await edit_or_send(call, text, IM(inline_keyboard=rows))


@router.callback_query(F.data == "adm:subbots")
async def subbots(call: CallbackQuery, is_parent: bool, manager):
    if not is_parent:
        return await call.answer("Faqat asosiy botda", show_alert=True)
    await call.answer()
    await render_bots(call, manager)


@router.callback_query(F.data.startswith("sb:"))
async def subbot_action(call: CallbackQuery, is_parent: bool, manager):
    if not is_parent:
        return await call.answer("Faqat asosiy botda", show_alert=True)
    _, action, rid = call.data.split(":")
    rid = int(rid)
    row = await manager.main_db.get_bot_row(rid)
    if not row:
        return await call.answer("Topilmadi", show_alert=True)
    if action == "toggle":
        if row["active"]:
            await manager.stop_by_row(rid)
            await manager.main_db.set_bot_active(rid, False)
            await call.answer("⏸ To'xtatildi")
        else:
            try:
                await manager.start_bot(row["token"], False, rid, row["owner_id"])
                await manager.main_db.set_bot_active(rid, True)
                await call.answer("▶️ Ishga tushdi")
            except Exception as e:
                return await call.answer(f"Xato: {e}"[:190], show_alert=True)
    else:
        await manager.stop_by_row(rid)
        await manager.main_db.delete_bot(rid)
        await call.answer("🗑 O'chirildi (ma'lumotlar fayli data/ papkasida qoladi)", show_alert=True)
    await render_bots(call, manager)
