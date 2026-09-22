import os
import shutil
import json
import logging
import aiohttp
import asyncio
import time
from urllib.parse import quote
from typing import Dict, Any

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.services.audio_features import AudioFeatureExtractor, compute_sha256
from bot.services.audio_adapter import AudioIntelligenceAdapter
from bot.services.lyric_transcriber import transcribe_lyrics
from bot.services.alignment import patch_word, parse_edit_command, realign_transcript

logger = logging.getLogger(__name__)
router = Router(name="audioviz")

RENDERER_URL = os.environ.get("REMOTE_RENDERER_URL") or os.environ.get("RENDERER_URL", "http://127.0.0.1:4002")
VAULT_STORAGE_PATH = os.environ.get("VAULT_STORAGE_PATH", "/opt/hermes-vault/motion/renders")

@router.message(Command("gpu", "gpu_status"))
async def cmd_gpu_status(message: Message):
    from bot.services.vast_lifecycle import VastLifecycleManager
    mgr = VastLifecycleManager.get_instance()
    inst = await mgr.get_active_instance()
    if not inst:
        await message.reply("❌ No Vast GPU instance configured.")
        return
    st = inst.get("actual_status", "unknown")
    gpu = inst.get("gpu_name", "RTX 3060")
    cost = inst.get("dph_total", 0.05)
    idle = int(time.time() - mgr.last_active_time)
    
    text = (
        f"🖥️ **Vast GPU Status:** `{st.upper()}`\n"
        f"• **Hardware:** {gpu} (12GB VRAM)\n"
        f"• **Hourly Rate:** ${cost:.3f}/hr\n"
        f"• **Idle Time:** {idle}s / 300s limit\n\n"
        f"Instance auto-stops when idle for >5 minutes to eliminate waste."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚡ Wake GPU", callback_data="gpu:wake"),
            InlineKeyboardButton(text="🛑 Stop GPU", callback_data="gpu:stop")
        ]
    ])
    await message.reply(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("gpu:"))
async def handle_gpu_callback(callback: CallbackQuery):
    action = callback.data.split(":")[1]
    from bot.services.vast_lifecycle import VastLifecycleManager
    mgr = VastLifecycleManager.get_instance()
    if action == "wake":
        await callback.answer("Waking GPU...")
        if callback.message:
            await callback.message.edit_text("⏳ Waking up GPU instance (~20-30s)...")
        ready = await mgr.ensure_gpu_ready()
        if callback.message:
            if ready:
                await callback.message.edit_text("✅ **GPU is ONLINE and tunnel is active!**", parse_mode="Markdown")
            else:
                await callback.message.edit_text("⚠️ **GPU wake failed or resources busy.**", parse_mode="Markdown")
    elif action == "stop":
        await callback.answer("Stopping GPU...")
        await mgr.stop_gpu()
        if callback.message:
            await callback.message.edit_text("🛑 **GPU stopped. Billing paused.**", parse_mode="Markdown")


class VisualizerState(StatesGroup):
    waiting_for_style = State()
    waiting_for_edit = State()
    rendering = State()


def get_visualizer_keyboard(job_id: str, has_words: bool = False, show_lyrics: bool = True) -> InlineKeyboardMarkup:
    buttons = [
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
    if has_words:
        toggle_label = "📝 متن ترانه: فعال (خاموش کردن)" if show_lyrics else "🚫 متن ترانه: غیرفعال (روشن کردن)"
        toggle_action = "disable_lyrics" if show_lyrics else "enable_lyrics"
        action_row = [
            InlineKeyboardButton(text=toggle_label, callback_data=f"viz:{job_id}:{toggle_action}")
        ]
        if show_lyrics:
            action_row.append(
                InlineKeyboardButton(text="✏️ ویرایش متن", callback_data=f"viz:{job_id}:edit")
            )
        buttons.append(action_row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Active audio cache by job_id
_AUDIO_CACHE: Dict[str, Dict[str, Any]] = {}


@router.message(F.audio | F.voice | (F.document & F.document.mime_type.startswith("audio/")))
async def handle_audio_message(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id if message.from_user else 0
    job_id = f"viz-{user_id}-{message.message_id}"

    status_msg = await message.reply("📥 Downloading audio track...")

    os.makedirs("/tmp/audioviz-audio", exist_ok=True)
    audio_obj = message.audio or message.voice or message.document
    if getattr(audio_obj, "duration", None) and audio_obj.duration > 600:
        mins = audio_obj.duration // 60
        await status_msg.edit_text(
            f"⚠️ **Audio file is too long ({mins} minutes).**\n\n"
            "The 60fps 3D Visualizer engine supports tracks up to 10 minutes maximum to guarantee rendering fidelity. Please trim your track and re-send."
        )
        return

    file_id = audio_obj.file_id

    file_info = await bot.get_file(file_id)
    file_ext = os.path.splitext(file_info.file_path or getattr(audio_obj, "file_name", "") or ".mp3")[1] or ".mp3"
    local_path = f"/tmp/audioviz-audio/{job_id}{file_ext}"

    await bot.download_file(file_info.file_path, local_path)

    # 1. Isolate vocals with Mel-Band RoFormer strictly on GPU (up to 5m wait)
    async def update_status(text: str):
        try:
            await status_msg.edit_text(text, parse_mode="Markdown")
        except Exception:
            pass

    await update_status("⚡ **Connecting to GPU for Mel-Band RoFormer stem separation...**")
    try:
        stems = await AudioIntelligenceAdapter.separate_stems_broker(
            local_path,
            timeout_seconds=300,
            status_callback=update_status
        )
        vocal_path = stems.get("vocals")
    except Exception as e:
        logger.error(f"Stem separation failed: {e}")
        await status_msg.edit_text(
            f"❌ **GPU Processing Error:**\n\n"
            f"Could not run Mel-Band RoFormer on GPU: {e}\n\n"
            "Stem separation is strictly executed on dedicated GPU hardware (Hetzner CPU fallback is disabled). Please try again in a few moments.",
            parse_mode="Markdown"
        )
        return

    # 2. Singing-voice lyric transcription on isolated vocals (or master fallback)
    await status_msg.edit_text("🔍 Extracting vocal lyrics via Whisper...")
    words = []
    transcribe_target = vocal_path if vocal_path and os.path.exists(vocal_path) else local_path
    try:
        res = await asyncio.to_thread(transcribe_lyrics, transcribe_target, None, "fa")
        words = res.get("words", [])
        if not words and transcribe_target != local_path:
            res_fb = await asyncio.to_thread(transcribe_lyrics, local_path, None, "fa")
            words = res_fb.get("words", [])
    except Exception as e:
        logger.info(f"Vocal transcription skipped or unavailable: {e}")

    _AUDIO_CACHE[job_id] = {
        "audio_path": local_path,
        "vocal_path": vocal_path,
        "stems": stems,
        "words": words,
        "show_lyrics": True,
    }

    keyboard = get_visualizer_keyboard(job_id, has_words=bool(words), show_lyrics=True)
    
    lyric_preview = ""
    if words:
        full_lyrics = " ".join(w.get("word", "") for w in words).strip()
        if len(full_lyrics) > 280:
            full_lyrics = full_lyrics[:280] + "..."
        lyric_preview = f"🎙 **متن شناسایی‌شده ترانه:**\n_{full_lyrics}_\n\n"

    await status_msg.edit_text(
        f"{lyric_preview}🎛 **Select a 3D Audio Visualizer Style:**\n\n"
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

    # Handle Lyrics Toggle
    if preset_id in ("disable_lyrics", "enable_lyrics"):
        show_lyrics = (preset_id == "enable_lyrics")
        cache_item["show_lyrics"] = show_lyrics
        await callback.answer("متن ترانه غیرفعال شد (فقط ویژوالایزر)" if not show_lyrics else "متن ترانه فعال شد")
        
        words = cache_item.get("words", [])
        updated_keyboard = get_visualizer_keyboard(job_id, has_words=bool(words), show_lyrics=show_lyrics)
        
        lyric_preview = ""
        if words and show_lyrics:
            full_lyrics = " ".join(w.get("word", "") for w in words).strip()
            if len(full_lyrics) > 280:
                full_lyrics = full_lyrics[:280] + "..."
            lyric_preview = f"🎙 **متن شناسایی‌شده ترانه:**\n_{full_lyrics}_\n\n"
        elif words and not show_lyrics:
            lyric_preview = "🚫 _حالت بدون متن انتخاب شده است (فقط انیمیشن ۳ بعدی ویژوالایزر)_\n\n"

        if callback.message:
            try:
                await callback.message.edit_text(
                    f"{lyric_preview}🎛 **Select a 3D Audio Visualizer Style:**\n\n"
                    "• **Particle Sphere**: 20k gold-amber emissive particles with 3D noise\n"
                    "• **Quantum Iris**: Torus knot inside-out ribbon with cyan-violet flare\n"
                    "• **Neural Synapse**: 1,500 glowing nodes with emerald shockwaves\n"
                    "• **Monolith Field**: 1,024 obsidian pillars with neon lime caps",
                    reply_markup=updated_keyboard,
                    parse_mode="Markdown",
                )
            except Exception:
                pass
        return

    # Handle Edit Request
    if preset_id == "edit":
        await callback.answer()
        await state.update_data(current_edit_job_id=job_id)
        await state.set_state(VisualizerState.waiting_for_edit)
        words = cache_item.get("words", [])
        full_lyrics = " ".join(w.get("word", "") for w in words).strip()
        if callback.message:
            await callback.message.reply(
                "✏️ **ویرایش متن ترانه / Edit Lyrics**\n\n"
                f"متن فعلی:\n_{full_lyrics}_\n\n"
                "برای اصلاح، کلمه مورد نظر را به شکل زیر بفرستید:\n"
                "`کلمه_قدیم -> کلمه_جدید`\n\n"
                "یا در صورت نیاز، کل متن اصلاح‌شده را به صورت یکجا ارسال نمایید.",
                parse_mode="Markdown",
            )
        return

    await callback.answer()
    if callback.message:
        await callback.message.edit_text(f"⏳ **Rendering {preset_id.upper()} Visualizer...**\n\n1. Extracting multiband FFT arrays\n2. Evaluating deterministic WebGL frames", parse_mode="Markdown")

    try:
        from bot.services.vast_lifecycle import VastLifecycleManager
        VastLifecycleManager.get_instance().record_activity()
    except Exception:
        pass

    audio_path = cache_item["audio_path"]
    show_lyrics = cache_item.get("show_lyrics", True)
    words = cache_item.get("words", []) if show_lyrics else []

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
            pre_extracted_stems=cache_item.get("stems"),
            show_lyrics=show_lyrics,
        )

        manifest_dict = manifest.to_dict()

        # 2. Trigger Remotion render strictly on GPU renderer
        from bot.services.vast_lifecycle import VastLifecycleManager
        mgr = VastLifecycleManager.get_instance()
        gpu_ready = await mgr.ensure_gpu_ready()
        if not gpu_ready:
            raise RuntimeError("GPU instance failed to wake up within 5 minutes for Remotion rendering.")

        total_render_timeout = max(3600, int(manifest.video.frameCount * 2.5))
        rendered_mp4 = None
        async with aiohttp.ClientSession() as session:
            # Upload master audio to GPU renderer via HTTP tunnel
            master_audio = manifest_dict.get("audio", {}).get("masterUri")
            if master_audio and os.path.exists(master_audio):
                upload_url = f"{RENDERER_URL}/upload?path={quote(master_audio)}"
                logger.info(f"📤 Uploading audio to GPU renderer via tunnel: {master_audio}")
                with open(master_audio, "rb") as f:
                    async with session.post(
                        upload_url,
                        data=f,
                        headers={"Content-Type": "application/octet-stream"},
                        timeout=aiohttp.ClientTimeout(total=180),
                    ) as up_resp:
                        if up_resp.status != 200:
                            err_txt = await up_resp.text()
                            raise RuntimeError(f"Failed to upload audio to render server: {err_txt}")

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
                            local_dest = os.path.join("/tmp/audioviz_work", f"{job_id}.mp4")
                            os.makedirs("/tmp/audioviz_work", exist_ok=True)
                            dl_url = f"{RENDERER_URL}/download/{job_id}"
                            logger.info(f"📥 Downloading rendered MP4 from GPU: {dl_url}...")
                            async with session.get(dl_url, timeout=aiohttp.ClientTimeout(total=600)) as dl_resp:
                                if dl_resp.status != 200:
                                    raise RuntimeError(f"Failed to download rendered video ({dl_resp.status})")
                                with open(local_dest, "wb") as out_f:
                                    while True:
                                        chunk = await dl_resp.content.read(1024 * 1024)
                                        if not chunk:
                                            break
                                        out_f.write(chunk)
                            rendered_mp4 = local_dest
                            logger.info(f"✅ Rendered MP4 retrieved ({os.path.getsize(rendered_mp4) / (1024*1024):.1f}MB)")
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


@router.message(VisualizerState.waiting_for_edit, F.text)
async def handle_lyric_edit(message: Message, state: FSMContext):
    data = await state.get_data()
    job_id = data.get("current_edit_job_id")
    if not job_id or job_id not in _AUDIO_CACHE:
        await message.answer("⚠️ نشست ویرایش منقضی شده است. لطفا فایل صوتی را دوباره ارسال کنید.")
        await state.clear()
        return

    cache_item = _AUDIO_CACHE[job_id]
    orig_words = cache_item.get("words", [])
    text = (message.text or "").strip()

    parsed = parse_edit_command(text)
    if parsed:
        old_word, new_word = parsed
        patched_words = patch_word(orig_words, old_word, new_word)
        if patched_words == orig_words:
            await message.answer(f"⚠️ کلمه «{old_word}» در متن ترانه یافت نشد. لطفا املای آن را بررسی کنید.")
            return
        cache_item["words"] = patched_words
        await message.answer(f"✅ اصلاح شد: «{old_word}» → «{new_word}»")
    else:
        # Full text replacement aligned to acoustic audio timestamps
        from bot.services.audio_features import get_audio_duration_seconds
        from bot.services.audio_adapter import AudioIntelligenceAdapter
        audio_p = cache_item.get("audio_path", "")
        vocal_p = cache_item.get("vocal_path")
        target_audio = vocal_p if vocal_p and os.path.exists(vocal_p) else audio_p
        total_dur = get_audio_duration_seconds(audio_p) if audio_p and os.path.exists(audio_p) else 0.0

        ai_url = os.environ.get("REMOTE_RENDERER_URL") or os.environ.get("AUDIOVIZ_AI_URL")
        realigned = []
        if ai_url and target_audio and os.path.exists(target_audio):
            try:
                gpu_align = await AudioIntelligenceAdapter.align_lyrics_gpu(
                    target_audio, text, ai_url, language="fa", total_duration=total_dur
                )
                realigned = gpu_align.get("words", [])
            except Exception as e:
                logger.info(f"Remote GPU forced alignment failed, falling back to local: {e}")

        if not realigned:
            realigned = realign_transcript(orig_words, text, total_duration=total_dur)

        cache_item["words"] = realigned
        has_interpolated = any(w.get("is_interpolated", False) for w in realigned)
        if has_interpolated:
            await message.answer("⚠️ متن ترانه به‌روزرسانی شد. توجه: بخش‌هایی از کلمات جدید بدون تطابق آکوستیک دقیق تخمین زده شده‌اند.")
        else:
            await message.answer("✅ کل متن ترانه به‌روزرسانی و با زمان‌بندی دقیق آکوستیک همگام‌سازی شد.")

    # Re-display style selection with updated lyrics
    updated_words = cache_item.get("words", [])
    show_lyrics = cache_item.get("show_lyrics", True)
    full_lyrics = " ".join(w.get("word", "") for w in updated_words).strip()
    if len(full_lyrics) > 280:
        full_lyrics = full_lyrics[:280] + "..."
    lyric_preview = f"🎙 **متن اصلاح‌شده ترانه:**\n_{full_lyrics}_\n\n" if full_lyrics else ""

    keyboard = get_visualizer_keyboard(job_id, has_words=bool(updated_words), show_lyrics=show_lyrics)
    await message.answer(
        f"{lyric_preview}🎛 **اکنون استایل ویژوالایزر را انتخاب کنید:**",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    await state.set_state(VisualizerState.waiting_for_style)

