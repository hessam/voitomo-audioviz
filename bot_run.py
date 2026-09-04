#!/usr/bin/env python3
"""Standalone bot runner with single-instance lock to prevent TelegramConflictError"""
import sys
import os
import fcntl

sys.path.insert(0, "/root/workspace")

import asyncio
import logging
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import TelegramObject
from typing import Callable, Dict, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

def acquire_single_instance_lock():
    """Ensures only ONE instance of the Telegram bot runs at any time across containers and cron jobs."""
    lock_file = "/tmp/motion_agent_bot.lock"
    lock_fd = open(lock_file, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Write PID to lockfile
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()
        return lock_fd
    except (IOError, BlockingIOError):
        logger.warning("⚠️ Another instance of bot_run.py is already running. Exiting cleanly to avoid TelegramConflictError.")
        sys.exit(0)

# Import routers with full path
from bot.routers import voice, edit, music

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ALLOWED_USERS = set(int(x) for x in os.environ.get("TELEGRAM_ALLOWED_USERS", "92241363,6027086169").split(","))

class AuthMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable, event: TelegramObject, data: Dict[str, Any]) -> Any:
        user = data.get("event_from_user")
        if user and user.id in ALLOWED_USERS:
            return await handler(event, data)
        logger.warning(f"Unauthorized: user_id={getattr(user, 'id', '?')}")
        return None

async def main():
    lock_fd = acquire_single_instance_lock()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.middleware(AuthMiddleware())
    dp.include_router(voice.router)
    dp.include_router(music.router)
    dp.include_router(edit.router)
    logger.info(f"🤖 Motion Agent started (PID {os.getpid()}). Allowed: {ALLOWED_USERS}")
    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        except Exception:
            pass

if __name__ == "__main__":
    asyncio.run(main())
