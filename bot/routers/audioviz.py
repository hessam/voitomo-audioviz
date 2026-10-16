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

from bot.services.r2_delivery import load_config as load_r2_config, upload_and_link
from bot.services.audio_features import AudioFeatureExtractor, compute_sha256
from bot.services.audio_adapter import AudioIntelligenceAdapter
from bot.services.alignment import patch_word, parse_edit_command, realign_transcript, parse_offset_command, shift_words

logger = logging.getLogger(__name__)
router = Router(name="audioviz")

VAULT_STORAGE_PATH = os.environ.get("VAULT_STORAGE_PATH", "/opt/hermes-vault/motion/renders")

# Every style the renderer knows. Only the ones listed in AUDIOVIZ_ENABLED_STYLES are offered, so a
# new style stays hidden until it has passed capture and response checks (default: sphere only).
STYLE_CATALOG: Dict[str, tuple] = {
    "sphere": ("🌟 Particle Sphere", "energy and emotion: bass pressure, drum shockwaves, vocal flow"),
    "orrery": ("🪐 Polymeter Orrery", "rhythm: rings for the bar and the riff cycle, one mark per hit"),
    "cymatic": ("🎼 Cymatic Plate", "pitch: sand settles on the vibration pattern of the notes"),
    "bodies": ("🎸 Resonant Bodies", "timbre: strings, skins and cymbals that ring like the real sound"),
}
LYRIC_MODES = ("off", "subtitles", "video")
LYRIC_MODE_LABELS = {"off": "Off", "subtitles": "Subtitles", "video": "Lyric video"}


def enabled_styles() -> list:
    wanted = [x.strip() for x in os.environ.get("AUDIOVIZ_ENABLED_STYLES", "sphere").split(",")]
    styles = [x for x in wanted if x in STYLE_CATALOG]
    return styles or ["sphere"]


R2_LINK_EXPIRES_S = int(os.environ.get("R2_LINK_HOURS", "24")) * 3600


def delivery_mode() -> str:
    """document = original file (default), video = Telegram inline player (re-encoded by Telegram), both."""
    mode = os.environ.get("AUDIOVIZ_DELIVERY", "document").strip().lower()
    return mode if mode in ("document", "video", "both") else "document"


def next_lyric_mode(mode: str) -> str:
    return LYRIC_MODES[(LYRIC_MODES.index(mode) + 1) % len(LYRIC_MODES)] if mode in LYRIC_MODES else "subtitles"


def style_menu_text(lyric_preview: str = "") -> str:
    lines = "\n".join(f"• **{STYLE_CATALOG[s][0][2:]}**: {STYLE_CATALOG[s][1]}" for s in enabled_styles())
    return f"{lyric_preview}🎛 **Select a visualizer style:**\n\n{lines}"


def lyric_preview_text(words, mode: str, heading: str = "Detected lyrics") -> str:
    if not words:
        return ""
    if mode == "off":
        return "🚫 _Lyrics are off: the video shows only the visualizer._\n\n"
    full_lyrics = " ".join(w.get("word", "") for w in words).strip()
    if len(full_lyrics) > 280:
        full_lyrics = full_lyrics[:280] + "..."
    return f"🎙 **{heading}** ({LYRIC_MODE_LABELS[mode]}):\n_{full_lyrics}_\n\n"

@router.message(Command("gpu", "gpu_status"))
async def cmd_gpu_status(message: Message):
    from bot.services.gpu_provider import active_provider, get_gpu_manager
    mgr = get_gpu_manager()
    if active_provider() == "modal":
        text = await mgr.status_text()
    else:
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
    from bot.services.gpu_provider import get_gpu_manager
    mgr = get_gpu_manager()
    if action == "wake":
        await callback.answer("Waking GPU...")
        if callback.message:
            await callback.message.edit_text("⏳ Waking up GPU...")
        ready = await mgr.ensure_gpu_ready()
        if callback.message:
            if ready:
                await callback.message.edit_text("✅ **GPU is ONLINE and ready!**", parse_mode="Markdown")
            else:
                await callback.message.edit_text("⚠️ **GPU wake failed or resources busy.**", parse_mode="Markdown")
    elif action == "stop":
        await callback.answer("Stopping GPU...")
        stopped = await mgr.stop_gpu()
        if callback.message:
            text = (
                "🛑 **GPU stopped.**"
                if stopped else
                "⚠️ **GPU stop was not confirmed.** Wait for active processing to finish and retry."
            )
            await callback.message.edit_text(text, parse_mode="Markdown")


class VisualizerState(StatesGroup):
    waiting_for_style = State()
    waiting_for_edit = State()
    rendering = State()


def get_visualizer_keyboard(job_id: str, has_words: bool = False, lyric_mode: str = "subtitles") -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=STYLE_CATALOG[style][0], callback_data=f"viz:{job_id}:{style}")]
        for style in enabled_styles()
    ]
    if has_words:
        action_row = [
            InlineKeyboardButton(text=f"📝 Lyrics: {LYRIC_MODE_LABELS[lyric_mode]} (tap to change)",
                                 callback_data=f"viz:{job_id}:lyrics")
        ]
        if lyric_mode != "off":
            action_row.append(InlineKeyboardButton(text="✏️ Edit lyrics", callback_data=f"viz:{job_id}:edit"))
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
        prepared = await AudioIntelligenceAdapter.prepare_visualizer_audio(
            local_path,
            status_callback=update_status,
            language="fa",
        )
        stems = prepared["stems"]
        vocal_path = prepared["vocal_path"]
        words = prepared["words"]
    except Exception as e:
        logger.error(f"Stem separation failed: {e}")
        await status_msg.edit_text(
            f"❌ **GPU Processing Error:**\n\n"
            f"Could not run Mel-Band RoFormer on GPU: {e}\n\n"
            "Stem separation is strictly executed on dedicated GPU hardware (Hetzner CPU fallback is disabled). Please try again in a few moments.",
            parse_mode="Markdown"
        )
        return

    _AUDIO_CACHE[job_id] = {
        "audio_path": local_path,
        "vocal_path": vocal_path,
        "stems": stems,
        "words": words,
        "lyric_mode": "subtitles",
    }

    keyboard = get_visualizer_keyboard(job_id, has_words=bool(words), lyric_mode="subtitles")

    await status_msg.edit_text(
        style_menu_text(lyric_preview_text(words, "subtitles")),
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

    # Handle lyric mode change (stale on/off buttons from older menus map to subtitles/off)
    if preset_id in ("lyrics", "disable_lyrics", "enable_lyrics"):
        if preset_id == "lyrics":
            lyric_mode = next_lyric_mode(cache_item.get("lyric_mode", "subtitles"))
        else:
            lyric_mode = "subtitles" if preset_id == "enable_lyrics" else "off"
        cache_item["lyric_mode"] = lyric_mode
        await callback.answer(f"Lyrics: {LYRIC_MODE_LABELS[lyric_mode]}")

        words = cache_item.get("words", [])
        updated_keyboard = get_visualizer_keyboard(job_id, has_words=bool(words), lyric_mode=lyric_mode)

        if callback.message:
            try:
                await callback.message.edit_text(
                    style_menu_text(lyric_preview_text(words, lyric_mode)),
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
                "✏️ **Edit lyrics**\n\n"
                f"Current lyrics:\n_{full_lyrics}_\n\n"
                "To fix one word, send it like this:\n"
                "`old_word -> new_word`\n\n"
                "To replace everything, paste the full corrected lyrics. They are timed against the vocals.\n\n"
                "If the words appear too early or too late, send `offset +120` or `offset -80` "
                "(milliseconds; positive makes them later).",
                parse_mode="Markdown",
            )
        return

    if preset_id not in enabled_styles():
        await callback.answer("That style is not available.", show_alert=True)
        return

    await callback.answer()
    if callback.message:
        await callback.message.edit_text(f"⏳ **Rendering {preset_id.upper()} Visualizer...**\n\n1. Extracting multiband FFT arrays\n2. Evaluating deterministic WebGL frames", parse_mode="Markdown")

    try:
        from bot.services.gpu_provider import get_gpu_manager
        get_gpu_manager().record_activity()
    except Exception:
        pass

    audio_path = cache_item["audio_path"]
    lyric_mode = cache_item.get("lyric_mode", "subtitles")
    show_lyrics = lyric_mode != "off"
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
            lyric_mode=lyric_mode,
        )

        manifest_dict = manifest.to_dict()

        # 2. Trigger Remotion render strictly on GPU renderer
        from bot.services.gpu_provider import gpu_base_url, gpu_request_headers, get_gpu_manager
        mgr = get_gpu_manager()

        async def gpu_status_cb(msg: str):
            if callback.message:
                try:
                    await callback.message.edit_text(msg, parse_mode="Markdown")
                except Exception:
                    pass

        async with mgr.managed_gpu(status_callback=gpu_status_cb):
            total_render_timeout = max(3600, int(manifest.video.frameCount * 2.5))
            rendered_mp4 = None
            renderer_url = gpu_base_url()
            async with aiohttp.ClientSession(headers=gpu_request_headers()) as session:
                # Upload master audio to GPU renderer via HTTP tunnel
                master_audio = manifest_dict.get("audio", {}).get("masterUri")
                if master_audio and os.path.exists(master_audio):
                    upload_url = f"{renderer_url}/upload?path={quote(master_audio)}"
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
                    f"{renderer_url}/render",
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
                    mgr.record_activity()
                    try:
                        async with session.get(
                            f"{renderer_url}/render/jobs/{job_id}",
                            timeout=aiohttp.ClientTimeout(total=10),
                        ) as status_resp:
                            if status_resp.status != 200:
                                continue
                            job_info = await status_resp.json()
                            st = job_info.get("status")
                            if st == "done":
                                local_dest = os.path.join("/tmp/audioviz_work", f"{job_id}.mp4")
                                os.makedirs("/tmp/audioviz_work", exist_ok=True)
                                dl_url = f"{renderer_url}/download/{job_id}"
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

        # 4a. Full-quality delivery through R2 (no size limit, no Telegram re-encode)
        r2_link = None
        r2 = load_r2_config()
        if r2:
            try:
                r2_link = await upload_and_link(r2, rendered_mp4, f"{job_id}.mp4", R2_LINK_EXPIRES_S)
            except Exception as r2_error:
                logger.error(f"R2 delivery failed, falling back to Telegram: {r2_error}")

        # 4b. Otherwise guarantee the file is under Telegram's 50MB bot upload limit (target <= 44MB)
        file_size = os.path.getsize(rendered_mp4)
        send_path = rendered_mp4
        if not r2_link and file_size > 48 * 1024 * 1024:
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
            caption = f"✨ **Audioviz Render Complete**\nPreset: `{preset_id}` | 1080x1080"
            mode = delivery_mode()
            if r2_link:
                hours = R2_LINK_EXPIRES_S // 3600
                size_mb = file_size / (1024 * 1024)
                await callback.message.answer(
                    f"Audioviz render complete ({preset_id}, 1080x1080)\nOriginal quality, {size_mb:.1f} MB\n"
                    f"Download: {r2_link}\nThe link expires in {hours} hours.",
                    disable_web_page_preview=True,
                )
                mode = "video" if mode in ("video", "both") and file_size <= 48 * 1024 * 1024 else ""
            if mode in ("document", "both"):
                # A document is stored as uploaded; Telegram re-encodes anything sent as a video.
                await callback.message.answer_document(
                    document=video_file,
                    caption=caption + ("\nOriginal quality file." if mode == "document" else "\nOriginal quality file (the inline preview is compressed by Telegram)."),
                    parse_mode="Markdown",
                )
            if mode in ("video", "both"):
                await callback.message.answer_video(
                    video=FSInputFile(send_path),
                    caption=caption,
                    parse_mode="Markdown",
                    supports_streaming=True,
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
        await message.answer("⚠️ The edit session expired. Please send the audio file again.")
        await state.clear()
        return

    cache_item = _AUDIO_CACHE[job_id]
    orig_words = cache_item.get("words", [])
    text = (message.text or "").strip()

    offset_ms = parse_offset_command(text)
    parsed = None if offset_ms is not None else parse_edit_command(text)
    if offset_ms is not None:
        cache_item["words"] = shift_words(orig_words, offset_ms)
        await message.answer(f"✅ All lyrics moved {'later' if offset_ms >= 0 else 'earlier'} by {abs(offset_ms)} ms.")
    elif parsed:
        old_word, new_word = parsed
        patched_words = patch_word(orig_words, old_word, new_word)
        if patched_words == orig_words:
            await message.answer(f"⚠️ The word «{old_word}» was not found in the lyrics. Please check its spelling.")
            return
        cache_item["words"] = patched_words
        await message.answer(f"✅ Fixed: «{old_word}» → «{new_word}»")
    else:
        # Full text replacement aligned to acoustic audio timestamps
        from bot.services.audio_features import get_audio_duration_seconds
        from bot.services.audio_adapter import AudioIntelligenceAdapter
        from bot.services.gpu_provider import gpu_base_url
        audio_p = cache_item.get("audio_path", "")
        vocal_p = cache_item.get("vocal_path")
        target_audio = vocal_p if vocal_p and os.path.exists(vocal_p) else audio_p
        total_dur = get_audio_duration_seconds(audio_p) if audio_p and os.path.exists(audio_p) else 0.0

        realigned = []
        try:
            ai_url = gpu_base_url()
        except RuntimeError as e:
            logger.info(f"Remote GPU alignment unavailable, using local alignment: {e}")
            ai_url = None
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
            await message.answer("⚠️ Lyrics updated. Note: the timing of some new words is estimated, not matched to the sound.")
        else:
            await message.answer("✅ Lyrics updated and timed against the vocals.")

    # Re-display style selection with updated lyrics
    updated_words = cache_item.get("words", [])
    lyric_mode = cache_item.get("lyric_mode", "subtitles")

    keyboard = get_visualizer_keyboard(job_id, has_words=bool(updated_words), lyric_mode=lyric_mode)
    await message.answer(
        style_menu_text(lyric_preview_text(updated_words, lyric_mode, heading="Updated lyrics")),
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    await state.set_state(VisualizerState.waiting_for_style)
