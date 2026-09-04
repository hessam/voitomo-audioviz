import os
import json
import asyncio
import aiohttp
import tempfile
import time
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.services.audio_adapter import AudioIntelligenceAdapter
from bot.services.lyric_transcriber import transcribe_lyrics
from bot.services.music_director import direct_music_scenes
from bot.services.normalizer import normalize_persian_asr

router = Router()
RENDER_URL = "http://localhost:4000/render"

PROFILES = {
    "dark_neon": "⚡ Dark Neon (موزیک ویدیو)",
    "swiss_clean": "✦ Swiss Clean (تایپوگرافی تمیز)",
    "tiktok_pop": "🎬 TikTok Pop (ریتمیک پاپ)"
}

class MusicState(StatesGroup):
    waiting_for_audio = State()
    waiting_for_lyrics = State()
    waiting_for_style = State()

def music_style_keyboard():
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f"music_style:{key}")]
        for key, label in PROFILES.items()
    ]
    buttons.append([InlineKeyboardButton(text="✍️ وارد کردن متن ترانه / شعر", callback_data="action:provide_lyrics")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.message(Command("music"))
@router.message(Command("song"))
async def handle_music_command(message: Message, state: FSMContext):
    await state.set_state(MusicState.waiting_for_audio)
    await message.answer(
        "🎵 *حالت ساخت موشن‌گرافی موزیک و ترانه*\n\n"
        "لطفاً یک فایل صوتی یا آهنگ (MP3 / Voice) ارسال کنید.\n\n"
        "✦ سیستم با کمک ایجنت مهندسی صدا، صدای خواننده را از سازها تفکیک کرده و متن ترانه را استخراج می‌کند.\n"
        "✦ کات‌های تصویر دقیقاً روی ریتم و ضرب‌آهنگ (Beat Grid) هماهنگ می‌شوند.",
        parse_mode="Markdown"
    )

@router.message(MusicState.waiting_for_audio, F.audio | F.voice | F.document)
@router.message(F.audio)
async def handle_music_file(message: Message, state: FSMContext):
    await message.answer("🎵 در حال دریافت آهنگ و تفکیک صدای خواننده از موسیقی (Mel-Band RoFormer)...")
    
    bot = message.bot
    media = message.audio or message.voice or message.document
    if not media:
        await message.answer("⚠️ لطفاً یک فایل معتبر صوتی ارسال کنید.")
        return

    file = await bot.get_file(media.file_id)
    ext = ".mp3" if message.audio else ".ogg"
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        input_audio_path = tmp.name
    await bot.download_file(file.file_path, destination=input_audio_path)

    try:
        # Step 1: Isolate vocals via Audio Engineer Agent / RoFormer
        vocal_path = await AudioIntelligenceAdapter.separate_vocals(input_audio_path)

        # Step 2: Extract musical rhythm, BPM & Beat Grid via Music DNA Agent
        rhythm_info = AudioIntelligenceAdapter.extract_rhythm_and_beats(input_audio_path)

        # Step 3: Singing-voice lyric transcription (filtering [music] hallucinations)
        lyric_res = transcribe_lyrics(vocal_path)

        if not lyric_res.get("words"):
            await message.answer("⚠️ متنی در این بخش از ترانه شناسایی نشد. می‌توانید متن ترانه را دستی ارسال کنید.")
            lyric_res["words"] = []
            lyric_res["text"] = "♫ ترانه و موسیقی ♫"

        # Standard Persian orthography cleanup
        clean_text, clean_words, _ = normalize_persian_asr(lyric_res["text"], lyric_res["words"])
        lyric_res["text"] = clean_text
        lyric_res["words"] = clean_words

        await state.update_data(
            audio_path=input_audio_path,
            vocal_path=vocal_path,
            rhythm_info=rhythm_info,
            lyrics=lyric_res
        )

        await state.set_state(MusicState.waiting_for_style)
        await message.answer(
            f"🎵 *متن ترانه استخراج شده:*\n\n{lyric_res['text']}\n\n"
            f"⚡ ریتم: {rhythm_info.get('bpm')} BPM | ضرب‌آهنگ: {len(rhythm_info.get('beats_sec', []))} ضرب\n\n"
            f"سبک ویدیوی موزیک را انتخاب کنید:",
            parse_mode="Markdown",
            reply_markup=music_style_keyboard()
        )

    except Exception as e:
        await message.answer(f"❌ خطا در پردازش موزیک: {e}")

@router.callback_query(MusicState.waiting_for_style, F.data == "action:provide_lyrics")
async def ask_user_lyrics(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.answer()
    except Exception:
        pass
    await state.set_state(MusicState.waiting_for_lyrics)
    await callback.message.answer(
        "✍️ *متن کامل شعر یا ترانه را ارسال کنید:*\n\n"
        "سیستم کلمات دقیق ترانه شما را با زمان‌بندی صدای خواننده سینک خواهد کرد.",
        parse_mode="Markdown"
    )

@router.message(MusicState.waiting_for_lyrics, F.text)
async def process_user_lyrics(message: Message, state: FSMContext):
    user_text = message.text.strip()
    data = await state.get_data()
    vocal_path = data.get("vocal_path")
    
    # Re-run transcription with forced alignment against user's lyrics
    lyric_res = transcribe_lyrics(vocal_path, user_lyrics=user_text)
    await state.update_data(lyrics=lyric_res)
    await state.set_state(MusicState.waiting_for_style)

    await message.answer(
        f"✅ *متن ترانه با موفقیت سینک شد!*\n\n"
        f"تعداد کلمات: {len(lyric_res['words'])}\n\n"
        "اکنون سبک موزیک ویدیو را انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=music_style_keyboard()
    )

@router.callback_query(MusicState.waiting_for_style, F.data.startswith("music_style:"))
async def render_music_video(callback: CallbackQuery, state: FSMContext):
    profile_key = callback.data.split(":", 1)[1]
    data = await state.get_data()
    lyrics = data.get("lyrics", {})
    rhythm_info = data.get("rhythm_info", {})
    audio_path = data.get("audio_path")

    try:
        await callback.answer()
    except Exception:
        pass

    await callback.message.edit_text(f"🎬 در حال کارگردانی پرده‌های ترانه و رندر روی ضرب‌آهنگ با سبک {PROFILES.get(profile_key, profile_key)}...")

    # Direct kinetic scenes synced to musical beat grid
    scenes = direct_music_scenes(
        lyric_words=lyrics.get("words", []),
        full_lyrics=lyrics.get("text", ""),
        duration=lyrics.get("duration", 30.0),
        rhythm_info=rhythm_info
    )

    duration_frames = max(1, round(lyrics.get("duration", 30.0) * 30))
    props = {
        "scenes": scenes,
        "words": lyrics.get("words", []),
        "text": lyrics.get("text", ""),
        "audioSrc": audio_path,
        "durationInFrames": duration_frames,
        "profile": profile_key,
        "isLyrical": True,
        "beatFrames": rhythm_info.get("beat_frames", [])
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(RENDER_URL, json=props, timeout=aiohttp.ClientTimeout(total=180)) as resp:
                if resp.status != 200:
                    err = await resp.text()
                    await callback.message.answer(f"❌ خطا در رندر: {err}")
                    return
                render_result = await resp.json()

        video_path = render_result["path"]
        video_file = FSInputFile(video_path)

        await callback.message.answer_video(
            video=video_file,
            caption=f"🎵 *موزیک ویدیوی کینتیک آماده شد!*\n\n"
                    f"⚡ هماهنگ‌شده با ضرب‌آهنگ {rhythm_info.get('bpm')} BPM\n"
                    f"✦ پرده‌های روایی: {len(scenes)} پرده ریتمیک",
            parse_mode="Markdown"
        )

    except Exception as e:
        await callback.message.answer(f"❌ خطا در تولید ویدیو: {e}")
