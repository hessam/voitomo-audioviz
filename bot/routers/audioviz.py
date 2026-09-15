import os
import shutil
import json
import logging
import aiohttp
import asyncio
import time
from typing import Dict, Any

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.services.audio_features import AudioFeatureExtractor, compute_sha256
from bot.services.audio_adapter import AudioIntelligenceAdapter
from bot.services.lyric_transcriber import transcribe_lyrics

logger = logging.getLogger(__name__)
router = Router(name="audioviz")

RENDERER_URL = os.environ.get("RENDERER_URL", "http://127.0.0.1:4001")
VAULT_STORAGE_PATH = os.environ.get("VAULT_STORAGE_PATH", "/opt/hermes-vault/motion/renders")


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
    if getattr(audio_obj, "duration", None) and audio_obj.duration > 600:
        mins = audio_obj.duration // 60
        await status_msg.edit_text(
            f"⚠️ **Audio file is too long ({mins} minutes).**\n\n"
            "The 60fps 3D Visualizer engine supports tracks up to 10 minutes maximum to guarantee rendering fidelity. Please trim your track and re-send."
        )
        return

    file_id = audio_obj.file_id

    file_info = await bot.get_file(file_id)
    file_ext = os.path.splitext(file_info.file_path or ".mp3")[1] or ".mp3"
    local_path = f"/tmp/audioviz-audio/{job_id}{file_ext}"

    await bot.download_file(file_info.file_path, local_path)

    # 1. Isolate vocals first (Voitomo pipeline) to prevent music from contaminating ASR
    await status_msg.edit_text("🎙 Isolating vocals via stem separator...")
    vocal_path = None
    try:
        vocal_path = await AudioIntelligenceAdapter.separate_vocals(local_path)
    except Exception as e:
        logger.info(f"Pre-vocal separation skipped/fallback: {e}")

    # 2. Singing-voice lyric transcription on isolated vocals (or master fallback)
    await status_msg.edit_text("🔍 Extracting vocal lyrics via Whisper...")
    words = []
    transcribe_target = vocal_path if vocal_path and os.path.exists(vocal_path) else local_path
    try:
        res = await asyncio.to_thread(transcribe_lyrics, transcribe_target)
        words = res.get("words", [])
        if not words and transcribe_target != local_path:
            res_fb = await asyncio.to_thread(transcribe_lyrics, local_path)
            words = res_fb.get("words", [])
    except Exception as e:
        logger.info(f"Vocal transcription skipped or unavailable: {e}")

    _AUDIO_CACHE[job_id] = {
        "audio_path": local_path,
        "vocal_path": vocal_path,
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
        chat_id = callback.message.chat.id if callback.message else 0
        message_id = callback.message.message_id if callback.message else 0
        manifest = await AudioFeatureExtractor.extract_and_compile_manifest(
            job_id=job_id,
            audio_path=audio_path,
            preset_id=preset_id,  # type: ignore
            words=words,
            chat_id=chat_id,
            message_id=message_id,
        )

        manifest_dict = manifest.to_dict()

        # 2. Trigger Remotion render on port 4001 with live progress polling
        total_render_timeout = max(3600, int(manifest.video.frameCount * 2.5))
        rendered_mp4 = None
        async with aiohttp.ClientSession() as session:
            # Trigger render in async job mode
            async with session.post(
                f"{RENDERER_URL}/render",
                json={"manifest": manifest_dict, "jobId": job_id, "async": True},
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status != 200:
                    err_text = await resp.text()
                    raise RuntimeError(f"Render server error ({resp.status}): {err_text}")

            poll_interval = 4.0
            last_edit_ts = 0.0
            last_pct = -1
            poll_deadline = time.time() + total_render_timeout

            render_error = None
            while time.time() < poll_deadline:
                await asyncio.sleep(poll_interval)
                try:
                    async with session.get(
                        f"{RENDERER_URL}/render/jobs/{job_id}",
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as status_resp:
                        if status_resp.status != 200:
                            continue
                        job_info = await status_resp.json()
                        st = job_info.get("status")
                        if st == "done":
                            rendered_mp4 = job_info.get("path")
                            break
                        elif st == "error":
                            render_error = job_info.get("error") or "Unknown render server failure"
                            break

                        pct = int(job_info.get("percent", 0))
                        frames_done = job_info.get("renderedFrames", 0)
                        total_f = job_info.get("totalFrames", manifest.video.frameCount)
                        eta_sec = int(job_info.get("etaSeconds", 0))

                        now = time.time()
                        if (now - last_edit_ts) >= 3.0:
                            last_edit_ts = now
                            last_pct = pct
                            filled = min(10, max(0, pct // 10))
                            bar = "█" * filled + "░" * (10 - filled)

                            if pct >= 100 or frames_done >= total_f:
                                status_text = (
                                    f"⏳ **Rendering {preset_id.upper()} Visualizer...**\n\n"
                                    f"`[██████████]` **100%** (Frames complete)\n"
                                    f"🎬 Finalizing video & audio encoding with FFmpeg..."
                                )
                            else:
                                if eta_sec > 0:
                                    m, s = divmod(eta_sec, 60)
                                    eta_str = f"{m}m {s}s" if m > 0 else f"{s}s"
                                else:
                                    eta_str = "Calculating..."

                                status_text = (
                                    f"⏳ **Rendering {preset_id.upper()} Visualizer...**\n\n"
                                    f"`[{bar}]` **{pct}%**\n"
                                    f"🎞 Frames: `{frames_done}/{total_f}`\n"
                                    f"⏱ Est. Remaining: `{eta_str}`"
                                )

                            if callback.message:
                                try:
                                    await callback.message.edit_text(
                                        status_text,
                                        parse_mode="Markdown",
                                    )
                                except Exception:
                                    pass
                except Exception as poll_err:
                    logger.debug(f"Progress poll notice: {poll_err}")

            if render_error:
                raise RuntimeError(f"Render server error: {render_error}")

        if not rendered_mp4 or not os.path.exists(rendered_mp4):
            raise FileNotFoundError(f"Rendered video not found at: {rendered_mp4}")

        # 3. Async archival to Server 2 vault if mounted
        if os.path.exists(VAULT_STORAGE_PATH):
            vault_dest = os.path.join(VAULT_STORAGE_PATH, f"{job_id}.mp4")
            shutil.copyfile(rendered_mp4, vault_dest)
            logger.info(f"📦 Successfully mirrored render to vault: {vault_dest}")

        # 4. Guarantee file is under Telegram's 50MB bot upload limit (target <= 44MB)
        file_size = os.path.getsize(rendered_mp4)
        send_path = rendered_mp4
        if file_size > 48 * 1024 * 1024:
            duration_s = max(1.0, manifest.video.frameCount / 30.0)
            target_kbits = 44 * 8 * 1024  # 44 MB safety ceiling in kbits
            audio_kbps = 128
            target_v_kbps = max(350, int((target_kbits / duration_s) - audio_kbps))
            target_v_kbps = min(5500, target_v_kbps)
            maxrate_kbps = int(target_v_kbps * 1.3)
            bufsize_kbps = int(target_v_kbps * 2)

            logger.warning(
                f"⚠️ Video size ({file_size / (1024*1024):.2f}MB) exceeds Telegram 48MB limit. "
                f"Compressing with target {target_v_kbps}k for {duration_s:.1f}s video..."
            )
            compressed_path = rendered_mp4.replace(".mp4", "_tg_compat.mp4")
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-i", rendered_mp4,
                "-c:v", "libx264", "-b:v", f"{target_v_kbps}k", "-maxrate", f"{maxrate_kbps}k", "-bufsize", f"{bufsize_kbps}k",
                "-c:a", "aac", "-b:a", f"{audio_kbps}k",
                "-preset", "fast", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                compressed_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            if os.path.exists(compressed_path) and os.path.getsize(compressed_path) > 0:
                send_path = compressed_path
                logger.info(f"✅ Video compressed to {os.path.getsize(send_path) / (1024*1024):.2f}MB")

        # 5. Deliver video to Telegram user
        video_file = FSInputFile(send_path)
        if callback.message:
            await callback.message.delete()
            await callback.message.answer_video(
                video=video_file,
                caption=f"✨ **Audioviz Render Complete**\nPreset: `{preset_id}` | Concurrency: 2 | 1080x1080",
                parse_mode="Markdown",
            )

        # Immediate cleanup of temporary renders to prevent disk exhaustion
        for p in {rendered_mp4, send_path}:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

    except Exception as e:
        logger.error(f"❌ Visualizer render failed: {e}", exc_info=True)
        if callback.message:
            await callback.message.answer(f"❌ Visualizer generation failed: {str(e)[:200]}")
    finally:
        await state.clear()
