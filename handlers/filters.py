from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from database import Database


class IsAdmin(BaseFilter):
    """Faqat shu botning adminlari uchun."""

    async def __call__(self, event: Message | CallbackQuery, db: Database) -> bool:
        return await db.is_admin(event.from_user.id)
