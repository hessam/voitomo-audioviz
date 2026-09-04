import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import TelegramObject, Update
from typing import Callable, Dict, Any, Awaitable
from bot.routers import voice, edit

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8655355943:AAH18lgbOPHAG7a_Op6zxH4LrfvXB5qRsdg")
ALLOWED_USERS = set(int(x) for x in os.environ.get("TELEGRAM_ALLOWED_USERS", "92241363").split(","))

class AuthMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable, event: TelegramObject, data: Dict[str, Any]) -> Any:
        user = data.get("event_from_user")
        if user and user.id in ALLOWED_USERS:
            return await handler(event, data)
        logger.warning(f"Unauthorized access attempt from user_id={getattr(user, 'id', 'unknown')}")
        return None

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.update.middleware(AuthMiddleware())

    dp.include_router(voice.router)
    dp.include_router(edit.router)

    logger.info(f"🤖 Motion Agent bot started. Allowed users: {ALLOWED_USERS}")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    asyncio.run(main())
