import os
import re
import subprocess
import tempfile
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "medium")

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        logger.info(f"⚡ Loading faster-whisper {WHISPER_MODEL} for singing voice...")
        _whisper_model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    return _whisper_model

def unload_whisper_model():
    global _whisper_model
    if _whisper_model is not None:
        del _whisper_model
        _whisper_model = None
        import gc
        gc.collect()
        logger.info("🧹 Unloaded singing-voice Whisper model and freed RAM.")

def clean_lyric_token(text: str) -> str:
    """Filters out Whisper non-speech artifacts such as [music], (موسیقی), ♪, etc."""
    if not text:
        return ""
    t = text.strip()
    # Strip bracketed hallucinations
    t = re.sub(r"[\[\(（【].*?[\]\)）】]", "", t)
    # Strip musical symbols
    t = re.sub(r"[♪♫♬♩#]+", "", t)
    # Strip redundant punctuation
    t = re.sub(r"^[،,.\-_!?؟\s]+", "", t)
    t = re.sub(r"[،,.\-_!?؟\s]+$", "", t)
    return t.strip()

def transcribe_lyrics(vocal_audio_path: str, user_lyrics: Optional[str] = None, language: Optional[str] = None) -> Dict[str, Any]:
    """
    Singing-Voice Persian/English Transcription Engine:
    1. Suppresses non-speech [music] hallucinations.
    2. Uses condition_on_previous_text=False to prevent repetitive cascades.
    3. Primes ASR with poetic lyrical meter.
    4. If user provides verified lyrics, aligns them with acoustic timestamps.
    """
    # 1. Convert to 16kHz mono WAV
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name
    
    subprocess.run([
        "ffmpeg", "-y", "-i", vocal_audio_path,
        "-ar", "16000", "-ac", "1", "-f", "wav", wav_path
    ], capture_output=True, check=True)

    try:
        model = get_whisper_model()
        
        prompt = (
            "متن ترانه، شعر فارسی، کلمات آواز و موسیقی روان و بدون غلط."
            if language == "fa"
            else "Song lyrics, clean vocal words, singing transcript without errors."
            if language == "en"
            else "متن ترانه، شعر فارسی و انگلیسی، کلمات آواز و موسیقی روان."
        )

        # We disable condition_on_previous_text so singing pauses do not loop hallucinations
        segments, info = model.transcribe(
            wav_path,
            language=language,
            task="transcribe",
            beam_size=5,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=600, speech_pad_ms=300),
            initial_prompt=prompt,
            condition_on_previous_text=False,
            prepend_punctuations="«\"'([{-",
            append_punctuations="»\"'.)،!؟:;]}"
        )

        raw_words = []
        full_text_parts = []

        for seg in segments:
            if seg.words:
                for w in seg.words:
                    clean_w = clean_lyric_token(w.word)
                    # Exclude non-speech markers like 'music', 'موزیک', etc.
                    if clean_w and clean_w.lower() not in ["music", "موزیک", "آهنگ", "موسیقی", "..."]:
                        raw_words.append({
                            "word": clean_w,
                            "start": float(round(w.start, 3)),
                            "end": float(round(w.end, 3))
                        })
            seg_text = clean_lyric_token(seg.text)
            if seg_text:
                full_text_parts.append(seg_text)

        reconstructed_text = " ".join(w["word"] for w in raw_words) if raw_words else " ".join(full_text_parts)

        # 2. If user supplied verified lyrics, realign them to acoustic timestamps
        if user_lyrics and user_lyrics.strip():
            from bot.services.alignment import realign_transcript
            aligned_words = realign_transcript(raw_words, user_lyrics.strip(), info.duration)
            return {
                "text": user_lyrics.strip(),
                "words": aligned_words,
                "duration": info.duration,
                "is_singing": True
            }

        return {
            "text": reconstructed_text.strip(),
            "words": raw_words,
            "duration": info.duration,
            "is_singing": True
        }

    finally:
        if os.path.exists(wav_path):
            os.unlink(wav_path)
        unload_whisper_model()
