"""Middleware'lar: kontekst (db/rol) injeksiyasi, foydalanuvchini qayd etish, majburiy obuna."""
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from keyboards.user_kb import sub_kb


class ContextMiddleware(BaseMiddleware):
    """Update qaysi botga tegishli bo'lsa, o'sha botning db va rolini (parent/child) beradi."""

    def __init__(self, manager):
        self.manager = manager

    async def __call__(self, handler, event, data):
        ctx = self.manager.ctx.get(data["bot"].id)
        if ctx is None:
            return None
        data["db"] = ctx.db
        data["is_parent"] = ctx.is_parent
        data["manager"] = self.manager
        return await handler(event, data)


class TrackUserMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user and not user.is_bot:
            await data["db"].upsert_user(user.id, user.full_name, user.username)
        return await handler(event, data)


class ForceSubMiddleware(BaseMiddleware):
    """Majburiy obuna: admin qo'shgan kanallarga a'zo bo'lmaguncha bot ishlamaydi."""

    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)
        db, bot = data["db"], data["bot"]
        if await db.is_admin(user.id):
            return await handler(event, data)
        channels = await db.list_channels("sub")
        if not channels:
            return await handler(event, data)

        missing = []
        for ch in channels:
            try:
                m = await bot.get_chat_member(ch["chat_id"], user.id)
                if m.status in ("left", "kicked"):
                    missing.append(ch)
            except Exception:   # bot kanalda admin emas / kanal topilmadi -> o'tkazib yuboramiz
                continue
        is_check = isinstance(event, CallbackQuery) and (event.data or "").startswith("check_sub")
        if not missing:
            return await handler(event, data)

        payload = ""
        if isinstance(event, Message) and event.text and event.text.startswith("/start "):
            payload = event.text.split(maxsplit=1)[1]
        elif is_check:
            payload = event.data.split(":", 1)[1] if ":" in event.data else ""
        text = "❗️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling, so'ng <b>Tekshirish</b> tugmasini bosing:"
        if isinstance(event, CallbackQuery):
            if is_check:
                await event.answer("❌ Hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)
            else:
                await event.answer()
                await event.message.answer(text, reply_markup=sub_kb(missing, payload))
        else:
            await event.answer(text, reply_markup=sub_kb(missing, payload))
        return None
