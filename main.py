"""Kino Bot — ishga tushirish: `python main.py`"""
import asyncio
import logging

from config import ADMIN_IDS, BOT_TOKEN, DATA_DIR
from database import Database
from handlers import build_dispatcher
from utils.bot_manager import BotManager


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not BOT_TOKEN:
        raise SystemExit("❌ .env faylida BOT_TOKEN ko'rsatilmagan (.env.example ga qarang)")

    main_db = Database(DATA_DIR / "main.db")
    await main_db.connect()
    for admin_id in ADMIN_IDS:
        await main_db.add_admin(admin_id)

    manager = BotManager(main_db)
    manager.dp = build_dispatcher(manager)
    await manager.start_bot(BOT_TOKEN, is_parent=True)   # Parent bot
    await manager.load_children()                        # bazadagi Child botlar
    try:
        await asyncio.Event().wait()
    finally:
        await manager.shutdown()
        await main_db.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
