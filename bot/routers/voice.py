import os
import json
import asyncio
import aiohttp
import tempfile
import time
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import sys
sys.path.insert(0, "/root/workspace")
from bot.services.transcriber import transcribe
from bot.services.director import direct_scenes_with_llm, direct_creative_spec
from bot.services.alignment import realign_transcript
from bot.services.normalizer import normalize_persian_asr
from bot.services.audit import WorkflowAudit, LOGS_DIR

router = Router()

RENDER_URL = "http://localhost:4000/render"
RENDER_SEMAPHORE = asyncio.Semaphore(1)

PROFILES = {
    "swiss_clean": "✦ Swiss Generative (Glitch-Decode)",
    "dark_neon": "⚡ Dark Neon",
    "tiktok_pop": "🎬 TikTok Pop"
}

class VoiceState(StatesGroup):
    waiting_for_style = State()
    waiting_for_full_edit = State()
    waiting_for_edit = State()

def style_keyboard():
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f"style:{key}")]
        for key, label in PROFILES.items()
    ]
    buttons.append([InlineKeyboardButton(text="✏️ ویرایش کل متن قبل از ساخت", callback_data="action:edit_full")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.message(CommandStart())
async def handle_start(message: Message):
    await message.answer(
        "👋 *به ربات هوشمند موشن‌گرافی خوش آمدید!*\n\n"
        "🎙 برای شروع، کافیست یک *پیام صوتی (Voice)* بفرستید.\n\n"
        "قابلیت‌های کلیدی:\n"
        "✦ *طراحی هوشمند کینتیک:* تشخیص تم، ریتم و موشن پرده‌ها توسط Art Director\n"
        "📋 *سیستم شفافیت و لاگ تصمیم‌گیری:* توضیح دقیق چرایی هر تصمیم و پرده روایی\n"
        "✏️ *ویرایش متن:* امکان اصلاح کامل متن قبل از رندر\n\n"
        "دستور /audit برای مشاهده آخرین گزارش تصمیم‌گیری در دسترس است.",
        parse_mode="Markdown"
    )

@router.message(Command("audit"))
@router.message(Command("log"))
async def handle_audit_command(message: Message, state: FSMContext):
    data = await state.get_data()
    last_audit_id = data.get("last_audit_id")
    
    if not last_audit_id:
        # Find latest audit file in logs
        if os.path.exists(LOGS_DIR):
            files = sorted([f for f in os.listdir(LOGS_DIR) if f.startswith("audit-") and f.endswith(".md")])
            if files:
                last_audit_id = files[-1].replace("audit-", "").replace(".md", "")

    if not last_audit_id:
        await message.answer("⚠️ هنوز هیچ گزارشی ثبت نشده است. ابتدا یک وویس بفرستید.")
        return

    md_path = os.path.join(LOGS_DIR, f"audit-{last_audit_id}.md")
    if os.path.exists(md_path):
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Truncate for telegram message limit if needed
        summary = content[:3500] if len(content) > 3500 else content
        await message.answer(summary, parse_mode=None)
        await message.answer_document(FSInputFile(md_path), caption="📄 فایل گزارش کامل تصمیمات کارگردان (Markdown)")
    else:
        await message.answer(f"⚠️ فایل لاگ {last_audit_id} یافت نشد.")

@router.message(F.voice)
async def handle_voice(message: Message, state: FSMContext):
    await message.answer("🎙 در حال پردازش صدا با هوش مصنوعی و ثبت لاگ تصمیم‌گیری...")
    
    audit = WorkflowAudit()
    
    bot = message.bot
    file = await bot.get_file(message.voice.file_id)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        ogg_path = tmp.name
    await bot.download_file(file.file_path, destination=ogg_path)

    try:
        result = transcribe(ogg_path)
    except Exception as e:
        await message.answer(f"❌ خطا در رونویسی: {e}")
        os.unlink(ogg_path)
        return
    finally:
        if os.path.exists(ogg_path):
            os.unlink(ogg_path)

    if not result["words"]:
        await message.answer("⚠️ متنی شناسایی نشد.")
        return

    # Normalize Persian ASR text to fix typos and colloquialisms
    clean_text, clean_words, diffs = normalize_persian_asr(result["text"], result["words"])
    raw_spoken_text = result["text"]
    result["text"] = clean_text
    result["words"] = clean_words

    # Record ASR to audit
    audit.record_asr(
        audio_path=f"telegram_voice_{message.voice.file_id[:8]}.ogg",
        duration=result["duration"],
        raw_text=raw_spoken_text,
        words_count=len(result["words"])
    )
    if diffs:
        audit.record_normalizer(len(clean_words), len(diffs), diffs)
    audit.save()

    await state.update_data(
        transcript=result,
        audio_file_id=message.voice.file_id,
        audit_run_id=audit.run_id
    )

    await state.set_state(VoiceState.waiting_for_style)
    await message.answer(
        f"📝 *متن شناسایی شده:*\n\n{result['text']}\n\n"
        f"⏱ مدت: {result['duration']:.1f}s | {len(result['words'])} کلمه\n\n"
        f"سبک ویدیو را انتخاب کنید یا در صورت نیاز روی «ویرایش کل متن» بزنید:",
        parse_mode="Markdown",
        reply_markup=style_keyboard()
    )

@router.callback_query(VoiceState.waiting_for_style, F.data == "action:edit_full")
async def start_full_edit(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.answer()
    except Exception:
        pass

    data = await state.get_data()
    transcript = data["transcript"]

    await state.set_state(VoiceState.waiting_for_full_edit)
    await callback.message.answer(
        "✍️ *متن کامل را ویرایش کرده و ارسال کنید:*\n\n"
        "می‌توانید کلمات را کم یا زیاد کنید یا غلط‌های املایی را اصلاح نمایید. "
        "زمان‌بندی صدا به‌صورت خودکار بر اساس متن جدید شما تنظیم خواهد شد.\n\n"
        f"متن فعلی جهت کپی و ویرایش:\n`{transcript['text']}`",
        parse_mode="Markdown"
    )

@router.message(VoiceState.waiting_for_full_edit, F.text)
async def handle_full_text_edit(message: Message, state: FSMContext):
    new_text = message.text.strip()
    data = await state.get_data()
    orig_transcript = data["transcript"]

    # Realign timestamps
    realigned_words = realign_transcript(orig_transcript["words"], new_text, orig_transcript["duration"])

    # Update transcript in state
    updated_transcript = {
        "text": new_text,
        "words": realigned_words,
        "duration": orig_transcript["duration"]
    }

    # Record edit to audit
    audit = WorkflowAudit(run_id=data.get("audit_run_id"))
    audit.record_user_edit(
        original_text=orig_transcript["text"],
        edited_text=new_text,
        realigned_tokens=len(realigned_words)
    )

    await state.update_data(transcript=updated_transcript)
    await state.set_state(VoiceState.waiting_for_style)

    await message.answer(
        f"✅ *متن با موفقیت ویرایش و زمان‌بندی شد!*\n\n"
        f"تعداد کلمات هماهنگ‌شده: {len(realigned_words)}\n\n"
        "اکنون سبک ویدیوی مورد نظر خود را انتخاب کنید:",
        parse_mode="Markdown",
        reply_markup=style_keyboard()
    )

@router.callback_query(VoiceState.waiting_for_style, F.data.startswith("style:"))
async def handle_style_choice(callback: CallbackQuery, state: FSMContext):
    profile_key = callback.data.split(":", 1)[1]
    data = await state.get_data()
    transcript = data["transcript"]
    audit = WorkflowAudit(run_id=data.get("audit_run_id"))
    
    # Guarantee ASR stage presence in audit
    if not audit.stages.get("asr_transcription") or not audit.stages["asr_transcription"].get("raw_text"):
        audit.record_asr(
            audio_path=f"telegram_voice_{data.get('audio_file_id', '')[:8]}.ogg",
            duration=transcript.get("duration", 0),
            raw_text=transcript.get("text", ""),
            words_count=len(transcript.get("words", []))
        )
        audit.save()
    
    try:
        await callback.answer()
    except Exception:
        pass
    
    await callback.message.edit_text(f"🎨 در حال تحلیل معنایی، کارگردانی پرده‌ها و رندر با سبک {PROFILES.get(profile_key, profile_key)}...")

    bot = callback.bot
    file = await bot.get_file(data["audio_file_id"])
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        ogg_path = tmp.name
    await bot.download_file(file.file_path, destination=ogg_path)

    # Frame-accurate duration strictly matching audio duration
    duration_frames = max(1, round(transcript["duration"] * 30))

    if profile_key == "swiss_clean":
        spec = direct_creative_spec(
            words=transcript["words"],
            fps=30,
            duration_sec=transcript["duration"],
            audit=audit
        )
        props = {
            "creativeSpec": spec.to_dict(),
            "words": transcript["words"],
            "audioSrc": ogg_path,
            "durationInFrames": duration_frames,
            "profile": profile_key
        }
    else:
        # Legacy template rendering for dark_neon / tiktok_pop
        scenes = direct_scenes_with_llm(
            words=transcript["words"],
            full_text=transcript["text"],
            duration=transcript["duration"],
            audit=audit
        )
        props = {
            "scenes": scenes,
            "words": transcript["words"],
            "text": transcript["text"],
            "audioSrc": ogg_path,
            "durationInFrames": duration_frames,
            "profile": profile_key
        }

    try:
        render_start = time.time()
        async with RENDER_SEMAPHORE:
            async with aiohttp.ClientSession() as session:
                async with session.post(RENDER_URL, json=props, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                    if resp.status != 200:
                        err = await resp.text()
                        await callback.message.answer(f"❌ خطا در رندر: {err}")
                        return
                    render_result = await resp.json()
        
        render_time = time.time() - render_start
        video_path = render_result["path"]
        file_size = os.path.getsize(video_path) if os.path.exists(video_path) else 0

        # Record render metrics in audit
        audit.record_render(
            video_path=video_path,
            duration_frames=duration_frames,
            fps=30,
            render_time=render_time,
            file_size_bytes=file_size
        )

        # Save both JSON and Markdown audit logs
        log_files = audit.save()

        await state.update_data(
            last_words=transcript["words"],
            last_profile=profile_key,
            last_audio=ogg_path,
            last_audit_id=audit.run_id
        )
        await state.set_state(VoiceState.waiting_for_edit)

        # Build video reply keyboard with Audit Log button
        audit_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 مشاهده گزارش تصمیمات کارگردان (Audit Log)", callback_data=f"audit:{audit.run_id}")]
        ])

        video_file = FSInputFile(video_path)
        await callback.message.answer_video(
            video=video_file,
            caption=f"✅ ویدیو آماده شد!\n\n🔍 شناسه تصمیم‌گیری: `{audit.run_id}`\n\nبرای ویرایش کلمه بنویسید:\n`کلمه_قدیم -> کلمه_جدید`",
            parse_mode="Markdown",
            reply_markup=audit_keyboard
        )
    except Exception as e:
        await callback.message.answer(f"❌ خطای رندر: {e}")

@router.callback_query(F.data.startswith("audit:"))
async def handle_audit_callback(callback: CallbackQuery):
    try:
        await callback.answer()
    except Exception:
        pass

    run_id = callback.data.split(":", 1)[1]
    md_path = os.path.join(LOGS_DIR, f"audit-{run_id}.md")

    if os.path.exists(md_path):
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
        summary = content[:3800] if len(content) > 3800 else content
        await callback.message.answer(summary, parse_mode=None)
        await callback.message.answer_document(FSInputFile(md_path), caption=f"📄 فایل تفصیلی لاگ تصمیم‌گیری `{run_id}`")
    else:
        await callback.message.answer(f"⚠️ لاگ `{run_id}` یافت نشد.")

@router.message(VoiceState.waiting_for_edit, F.text)
async def handle_word_edit(message: Message, state: FSMContext):
    text = message.text.strip()
    if "->" not in text:
        await message.answer("⚠️ لطفاً در فرمت `کلمه_قدیم -> کلمه_جدید` ارسال کنید.", parse_mode="Markdown")
        return

    old_w, new_w = [x.strip() for x in text.split("->", 1)]
    data = await state.get_data()
    words = data.get("last_words", [])

    found = False
    for w in words:
        if w["word"] == old_w:
            w["word"] = new_w
            found = True

    if not found:
        await message.answer(f"⚠️ کلمه «{old_w}» پیدا نشد.")
        return

    await message.answer(f"🔄 کلمه «{old_w}» با «{new_w}» جایگزین شد. در حال بازسازی ویدیو...")

    profile_key = data.get("last_profile", "swiss_clean")
    ogg_path = data.get("last_audio")
    full_text = " ".join(w["word"] for w in words)
    duration = words[-1]["end"] if words else 10.0

    scenes = direct_scenes_with_llm(words, full_text, duration)

    props = {
        "scenes": scenes,
        "words": words,
        "text": full_text,
        "audioSrc": ogg_path,
        "durationInFrames": max(1, round(duration * 30)),
        "profile": profile_key
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(RENDER_URL, json=props, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                render_result = await resp.json()

        video_path = render_result["path"]
        await state.update_data(last_words=words)

        video_file = FSInputFile(video_path)
        await message.answer_video(
            video=video_file,
            caption=f"✅ ویدیوی اصلاح‌شده آماده است!\n\nتغییر: `{old_w}` ➔ `{new_w}`",
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(f"❌ خطا در بازسازی ویدیو: {e}")
