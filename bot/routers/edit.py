import os
import json
import aiohttp
import tempfile
from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext
import sys
sys.path.insert(0, "/root/workspace")
from bot.services.alignment import parse_edit_command, patch_word
from bot.services.director import direct_scenes_with_llm
from bot.routers.voice import VoiceState

router = Router()
RENDER_URL = "http://localhost:4000/render"

@router.message(VoiceState.waiting_for_edit, F.text.contains("->"))
async def handle_edit(message: Message, state: FSMContext):
    parsed = parse_edit_command(message.text)
    if not parsed:
        await message.answer("⚠️ فرمت: `کلمه_قدیم -> کلمه_جدید`", parse_mode="Markdown")
        return

    old_word, new_word = parsed
    data = await state.get_data()
    words = data.get("last_words", [])
    profile = data.get("last_profile", "swiss_clean")
    audio_path = data.get("last_audio")

    patched_words = patch_word(words, old_word, new_word)
    
    # Check if any replacement was made
    if patched_words == words:
        await message.answer(f"⚠️ کلمه «{old_word}» در متن یافت نشد.")
        return

    await message.answer(f"✏️ «{old_word}» → «{new_word}» | در حال رندر مجدد...")

    full_text = " ".join(w["word"] for w in patched_words)
    duration = patched_words[-1]["end"] if patched_words else 3.0
    scenes = direct_scenes_with_llm(patched_words, full_text, duration)

    props = {
        "scenes": scenes,
        "words": patched_words,
        "text": full_text,
        "audioSrc": audio_path,
        "durationInFrames": max(1, round(duration * 30)) if patched_words else 90,
        "profile": profile
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(RENDER_URL, json=props, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status != 200:
                    err = await resp.text()
                    await message.answer(f"❌ خطا در رندر: {err}")
                    return
                render_result = await resp.json()

        video_path = render_result["path"]
        await state.update_data(last_words=patched_words)

        video_file = FSInputFile(video_path)
        await message.answer_video(
            video=video_file,
            caption=f"✅ ویرایش اعمال شد: «{old_word}» → «{new_word}»\n\nمی‌توانید ادامه دهید.",
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(f"❌ خطا: {e}")
