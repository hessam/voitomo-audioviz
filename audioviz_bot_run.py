#!/usr/bin/env python3
"""
Dedicated Telegram Bot Runner for Audioviz 3D Audio Visualizer Agent
Operates in 100% isolation from Voitomo
"""
import sys
import os
import fcntl
import asyncio
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import TelegramObject
from typing import Callable, Dict, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def acquire_single_instance_lock():
    """Ensures only ONE instance of the Audioviz Telegram bot runs at any time."""
    lock_file = "/tmp/audioviz_agent_bot.lock"
    lock_fd = open(lock_file, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()
        return lock_fd
    except (IOError, BlockingIOError):
        logger.warning("⚠️ Another instance of audioviz_bot_run.py is already running. Exiting cleanly.")
        sys.exit(0)


from bot.routers import audioviz

BOT_TOKEN = os.environ.get("AUDIOVIZ_BOT_TOKEN", "")
ALLOWED_USERS = set(int(x) for x in os.environ.get("TELEGRAM_ALLOWED_USERS", "92241363,6027086169").split(","))


class AuthMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable, event: TelegramObject, data: Dict[str, Any]) -> Any:
        user = data.get("event_from_user")
        if user and user.id in ALLOWED_USERS:
            return await handler(event, data)
        logger.warning(f"Unauthorized: user_id={getattr(user, 'id', '?')}")
        return None


async def resurrect_orphaned_jobs(bot: Bot) -> None:
    """
    On startup: find stem jobs that completed while we were killed,
    and re-deliver a notification to the original user.
    This ensures gateway restarts during long stem jobs don't silently
    drop user requests.
    """
    from bot.services.audio_adapter import AudioIntelligenceAdapter
    try:
        orphans = AudioIntelligenceAdapter.collect_orphaned_stem_jobs()
        for job_id, chat_id, message_id, stems in orphans:
            try:
                stem_names = ", ".join(stems.keys())
                await bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"✅ **Your stems are ready** (job recovered after server restart)\n\n"
                        f"Stems: {stem_names}\n\n"
                        f"Please re-send your audio to generate the visualizer."
                    ),
                    parse_mode="Markdown",
                )
                logger.info(f"🔁 Resurrected job {job_id} → notified chat_id={chat_id}")
            except Exception as e:
                logger.warning(f"Failed to notify for orphaned job {job_id}: {e}")
    except Exception as e:
        logger.warning(f"Resurrection scan failed: {e}")


async def main():
    from aiogram.client.session.aiohttp import AiohttpSession
    lock_fd = acquire_single_instance_lock()
    session = AiohttpSession(timeout=300.0)
    bot = Bot(token=BOT_TOKEN, session=session)
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.middleware(AuthMiddleware())
    dp.include_router(audioviz.router)

    logger.info(f"🚀 Audioviz 3D Visualizer Agent started (PID {os.getpid()}). Allowed: {ALLOWED_USERS}")
    # Recover any stem jobs that completed while the bot was killed mid-wait
    await resurrect_orphaned_jobs(bot)
    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
