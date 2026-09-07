import os
import shutil
import json
import logging
import aiohttp
import asyncio
from typing import Dict, Any

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.services.audio_features import AudioFeatureExtractor, compute_sha256
from bot.services.transcriber import transcribe

logger = logging.getLogger(__name__)
router = Router(name="audioviz")

RENDERER_URL = os.environ.get("RENDERER_URL", "http://127.0.0.1:4001")
VAULT_STORAGE_PATH = os.environ.get("VAULT_STORAGE_PATH", "/opt/hermes-vault/viz")


class VisualizerState(StatesGroup):
    waiting_for_style = State()
    rendering = State()


def get_visualizer_keyboard(job_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🌟 Particle Sphere (Golden Glow)", callback_data=f"viz:{job_id}:sphere"),
            ],
            [
                InlineKeyboardButton(text="🌀 Quantum Iris (Cyan-Violet)", callback_data=f"viz:{job_id}:iris"),
            ],
            [
                InlineKeyboardButton(text="⚡ Neural Synapse (Emerald Web)", callback_data=f"viz:{job_id}:neural"),
            ],
            [
                InlineKeyboardButton(text="🏛️ Monolith Field (Acid-Lime)", callback_data=f"viz:{job_id}:monolith"),
            ],
        ]
    )


# Active audio cache by job_id
_AUDIO_CACHE: Dict[str, Dict[str, Any]] = {}


@router.message(F.audio | F.voice)
async def handle_audio_message(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id if message.from_user else 0
    job_id = f"viz-{user_id}-{message.message_id}"

    status_msg = await message.reply("📥 Downloading audio track...")

    os.makedirs("/tmp/audioviz-audio", exist_ok=True)
    audio_obj = message.audio or message.voice
    file_id = audio_obj.file_id

    file_info = await bot.get_file(file_id)
    file_ext = os.path.splitext(file_info.file_path or ".mp3")[1] or ".mp3"
    local_path = f"/tmp/audioviz-audio/{job_id}{file_ext}"

    await bot.download_file(file_info.file_path, local_path)

    # Fast transcription for synchronized lyrics
    await status_msg.edit_text("🔍 Extracting vocal lyrics via Whisper...")
    words = []
    try:
        res = await asyncio.to_thread(transcribe, local_path)
        words = res.get("words", [])
    except Exception as e:
        logger.info(f"Vocal transcription skipped or unavailable: {e}")

    _AUDIO_CACHE[job_id] = {
        "audio_path": local_path,
        "words": words,
    }

    keyboard = get_visualizer_keyboard(job_id)
    await status_msg.edit_text(
        "🎛 **Select a 3D Audio Visualizer Style:**\n\n"
        "• **Particle Sphere**: 20k gold-amber emissive particles with 3D noise\n"
        "• **Quantum Iris**: Torus knot inside-out ribbon with cyan-violet flare\n"
        "• **Neural Synapse**: 1,500 glowing nodes with emerald shockwaves\n"
        "• **Monolith Field**: 1,024 obsidian pillars with neon lime caps",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    await state.set_state(VisualizerState.waiting_for_style)


@router.callback_query(F.data.startswith("viz:"))
async def handle_style_selection(callback: CallbackQuery, state: FSMContext, bot: Bot):
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Invalid request.")
        return

    _, job_id, preset_id = parts
    cache_item = _AUDIO_CACHE.get(job_id)
    if not cache_item:
        await callback.answer("Audio session expired. Please re-send the audio.", show_alert=True)
        return

    await callback.answer()
    if callback.message:
        await callback.message.edit_text(f"⏳ **Rendering {preset_id.upper()} Visualizer...**\n\n1. Extracting multiband FFT arrays\n2. Evaluating deterministic WebGL frames", parse_mode="Markdown")

    audio_path = cache_item["audio_path"]
    words = cache_item.get("words", [])

    try:
        # 1. Compile Astra-compliant RenderManifest
        manifest = await AudioFeatureExtractor.extract_and_compile_manifest(
            job_id=job_id,
            audio_path=audio_path,
            preset_id=preset_id,  # type: ignore
            words=words,
        )

        manifest_dict = manifest.to_dict()

        # 2. Trigger Remotion render on port 4001
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{RENDERER_URL}/render",
                json={"manifest": manifest_dict},
                timeout=aiohttp.ClientTimeout(total=900),
            ) as resp:
                if resp.status != 200:
                    err_text = await resp.text()
                    raise RuntimeError(f"Render server error ({resp.status}): {err_text}")
                result = await resp.json()
                rendered_mp4 = result.get("path")

        if not rendered_mp4 or not os.path.exists(rendered_mp4):
            raise FileNotFoundError(f"Rendered video not found at: {rendered_mp4}")

        # 3. Async archival to Server 2 vault if mounted
        if os.path.exists(VAULT_STORAGE_PATH):
            vault_dest = os.path.join(VAULT_STORAGE_PATH, f"{job_id}.mp4")
            shutil.copyfile(rendered_mp4, vault_dest)
            logger.info(f"📦 Successfully mirrored render to vault: {vault_dest}")

        # 4. Deliver video to Telegram user
        video_file = FSInputFile(rendered_mp4)
        if callback.message:
            await callback.message.delete()
            await callback.message.answer_video(
                video=video_file,
                caption=f"✨ **Audioviz Render Complete**\nPreset: `{preset_id}` | Concurrency: 2 | 1080x1080",
                parse_mode="Markdown",
            )

    except Exception as e:
        logger.error(f"❌ Visualizer render failed: {e}", exc_info=True)
        if callback.message:
            await callback.message.answer(f"❌ Visualizer generation failed: {str(e)[:200]}")
    finally:
        await state.clear()
