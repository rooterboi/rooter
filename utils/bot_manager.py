"""Multibot menejer: bitta jarayonda Parent + barcha Child botlarni long-polling bilan yuritadi.

- Bitta Dispatcher (handlerlar umumiy), har bir bot uchun alohida polling vazifasi.
- Har bir botning o'z SQLite bazasi va roli (is_parent) BotCtx orqali middleware'ga beriladi.
- Child botda is_parent=False -> /rooter (sub-bot ochish) va "Sozlamalar" umuman ishlamaydi.
"""
import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramRetryAfter, TelegramUnauthorizedError
from aiogram.methods import GetUpdates
from aiogram.types import BotCommand

from config import DATA_DIR
from database import Database

log = logging.getLogger(__name__)


@dataclass
class BotCtx:
    db: Database
    is_parent: bool
    row_id: Optional[int] = None


class BotManager:
    def __init__(self, main_db: Database):
        self.main_db = main_db
        self.dp: Optional[Dispatcher] = None
        self.ctx: dict[int, BotCtx] = {}
        self.bots: dict[int, Bot] = {}
        self.tasks: dict[int, asyncio.Task] = {}
        self._bg: set[asyncio.Task] = set()

    # ------------------------------------------------------------ start / stop
    async def start_bot(self, token: str, is_parent: bool, row_id: Optional[int] = None,
                        owner_id: Optional[int] = None) -> Bot:
        bot = Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        try:
            me = await bot.get_me()
            if is_parent:
                db = self.main_db
            else:
                db = Database(DATA_DIR / f"bot_{row_id}.db")
                await db.connect()
                if owner_id:
                    await db.add_admin(owner_id)       # sub-bot egasi o'sha botning admini
            await bot.delete_webhook(drop_pending_updates=False)
            await bot.set_my_commands([BotCommand(command="start", description="Botni ishga tushirish")])
        except Exception:
            await bot.session.close()
            raise
        self.ctx[bot.id] = BotCtx(db, is_parent, row_id)
        self.bots[bot.id] = bot
        self.tasks[bot.id] = asyncio.create_task(self._poll(bot))
        log.info("Bot ishga tushdi: @%s (%s)", me.username, "PARENT" if is_parent else "CHILD")
        return bot

    async def create_child(self, token: str, owner_id: int) -> str:
        """Tokenni tekshiradi, bazaga saqlaydi va yangi sub-botni ishga tushiradi."""
        probe = Bot(token)
        try:
            me = await probe.get_me()
        finally:
            await probe.session.close()
        if me.id in self.ctx or await self.main_db.get_bot_by_token(token):
            raise ValueError("Bu bot allaqachon tizimga ulangan.")
        row_id = await self.main_db.add_bot(token, me.username, owner_id)
        try:
            await self.start_bot(token, False, row_id, owner_id)
        except Exception:
            await self.main_db.delete_bot(row_id)
            raise
        return me.username

    async def load_children(self):
        for row in await self.main_db.list_bots(active_only=True):
            try:
                await self.start_bot(row["token"], False, row["id"], row["owner_id"])
            except Exception as e:
                log.error("Sub-bot @%s ishga tushmadi: %s", row["username"], e)
                await self.main_db.set_bot_active(row["id"], False)

    async def stop_by_row(self, row_id: int):
        for bid, c in list(self.ctx.items()):
            if not c.is_parent and c.row_id == row_id:
                await self._stop(bid)

    async def _stop(self, bid: int):
        task = self.tasks.pop(bid, None)
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await task
        bot = self.bots.pop(bid, None)
        if bot:
            await bot.session.close()
        c = self.ctx.pop(bid, None)
        if c and not c.is_parent:
            await c.db.close()

    async def shutdown(self):
        for bid in list(self.ctx):
            await self._stop(bid)

    # ------------------------------------------------------------------ polling
    async def _poll(self, bot: Bot):
        offset = None
        allowed = self.dp.resolve_used_update_types()
        while True:
            try:
                updates = await bot(GetUpdates(offset=offset, timeout=30, allowed_updates=allowed),
                                    request_timeout=45)
            except asyncio.CancelledError:
                raise
            except TelegramUnauthorizedError:
                log.error("Token bekor qilingan, bot to'xtatildi: %s", bot.id)
                c = self.ctx.get(bot.id)
                if c and c.row_id:
                    await self.main_db.set_bot_active(c.row_id, False)
                return
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after)
                continue
            except Exception as e:
                log.warning("Polling xatosi (%s): %s", bot.id, e)
                await asyncio.sleep(3)
                continue
            for u in updates:
                offset = u.update_id + 1
                t = asyncio.create_task(self._feed(bot, u))
                self._bg.add(t)
                t.add_done_callback(self._bg.discard)

    async def _feed(self, bot: Bot, update):
        try:
            await self.dp.feed_update(bot, update)
        except Exception:
            log.exception("Update qayta ishlashda xato")
