import os
import json
import subprocess
import tempfile
import requests
import logging
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

_model = None

OPENROUTER_API_KEY = os.environ.get(
    "OPENROUTER_API_KEY",
    ""
)
LLM_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-5.6-luna")

WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "medium")

def get_model():
    global _model
    if _model is None:
        logger.info(f"⚡ Loading faster-whisper {WHISPER_MODEL} (compute_type=int8)...")
        _model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    return _model

def normalize_words_with_llm(words: list) -> list:
    """
    Semantic Persian token normalizer using OpenRouter.
    Corrects colloquial ASR phonetics, attached prefixes (می‌), and half-spaces
    while strictly preserving the 1:1 array structure and millisecond timestamps.
    """
    if not words or not OPENROUTER_API_KEY:
        return words

    # Build indexed payload
    payload_tokens = [{"i": idx, "w": w["word"]} for idx, w in enumerate(words)]
    
    system_prompt = (
        "You are an expert Persian linguistic normalizer for automatic speech recognition transcripts.\n"
        "Your mission is to fix phonetic mishearings, correct colloquial Persian slang, and insert standard "
        "half-spaces (نیم‌فاصله) (e.g., 'می‌شه', 'نمونه‌کار', 'رفته‌بود').\n\n"
        "STRICT CONSTRAINTS:\n"
        "1. Output MUST be ONLY a valid JSON array of objects with schema: [{\"i\": <index>, \"w\": \"<corrected_word>\"}].\n"
        "2. The returned array MUST have the EXACT SAME length as the input array.\n"
        "3. Every index 'i' must correspond 1:1 to the input token index.\n"
        "4. Do NOT drop, add, or reorder items.\n"
        "5. Do NOT output markdown code fences, comments, or explanations. Only pure JSON."
    )

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(payload_tokens, ensure_ascii=False)}
                ],
                "temperature": 0.1,
                "max_tokens": 2048
            },
            timeout=15
        )
        
        if resp.status_code != 200:
            logger.warning(f"LLM normalizer HTTP {resp.status_code}: {resp.text}")
            return words

        content = (resp.json().get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
        # Clean markdown codeblocks if model wrapped output in ```json
        if content.startswith("```"):
            content = content.strip("`")
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        corrected_items = json.loads(content)
        if isinstance(corrected_items, list):
            for item in corrected_items:
                idx = item.get("i")
                corrected_w = item.get("w", "").strip()
                if idx is not None and 0 <= idx < len(words) and corrected_w:
                    words[idx]["word"] = corrected_w

    except Exception as e:
        logger.warning(f"LLM normalization skipped due to error: {e}")

    return words

def transcribe(audio_path: str) -> dict:
    """
    Hybrid Persian ASR Pipeline:
    1. faster-whisper large-v3-turbo with Silero VAD (min_silence=500ms) and Persian colloquial initial_prompt.
    2. LLM semantic token correction preserving millisecond timestamps.
    """
    # 1. Convert to 16kHz mono WAV for high-fidelity whisper feature extraction
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name
    subprocess.run([
        "ffmpeg", "-y", "-i", audio_path,
        "-ar", "16000", "-ac", "1", "-f", "wav", wav_path
    ], capture_output=True, check=True)

    try:
        model = get_model()
        segments, info = model.transcribe(
            wav_path,
            language="fa",
            task="transcribe",
            beam_size=5,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
            initial_prompt="متن فارسی محاوره‌ای، صحبت‌های عامیانه، کلمات واضح و روان بدون غلط املایی.",
            prepend_punctuations="«\"'([{-",
            append_punctuations="»\"'.)،!؟:;]}"
        )

        words = []
        full_text_parts = []
        for seg in segments:
            if seg.words:
                for w in seg.words:
                    w_str = w.word.strip()
                    if w_str:
                        words.append({
                            "word": w_str,
                            "start": float(round(w.start, 3)),
                            "end": float(round(w.end, 3))
                        })
                full_text_parts.append(seg.text.strip())

        # 2. Apply LLM token normalization pass
        words = normalize_words_with_llm(words)
        reconstructed_text = " ".join(w["word"] for w in words) if words else " ".join(full_text_parts)

        # 3. Acoustic Vocal Recovery Fallback
        # If standard conversational Whisper detected only music tokens or <= 1 word,
        # apply vocal formant bandpass filter + dynamic compression and re-transcribe without VAD.
        clean_check = reconstructed_text.strip()
        if clean_check in ("موسیقی", "[موسیقی]", "موزیک", "Music", "[music]", "") or len(words) <= 1:
            logger.info("⚡ Detected music/non-speech token ('%s'). Running acoustic vocal recovery fallback...", clean_check)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as vtmp:
                vocal_wav = vtmp.name
            try:
                subprocess.run([
                    "ffmpeg", "-y", "-i", audio_path,
                    "-af", "highpass=f=180,lowpass=f=4500,acompressor=threshold=-18dB:ratio=4:attack=15:release=100",
                    "-ar", "16000", "-ac", "1", vocal_wav
                ], capture_output=True, check=True)

                fb_segs, _ = model.transcribe(
                    vocal_wav,
                    language="fa",
                    task="transcribe",
                    beam_size=5,
                    word_timestamps=True,
                    vad_filter=False,
                    condition_on_previous_text=False
                )

                fb_words = []
                for seg in fb_segs:
                    if seg.words:
                        for w in seg.words:
                            w_str = w.word.strip()
                            # Filter out non-speech tags
                            if w_str and w_str not in ("موسیقی", "[موسیقی]", "موزیک", "music", "[music]"):
                                fb_words.append({
                                    "word": w_str,
                                    "start": float(round(w.start, 3)),
                                    "end": float(round(w.end, 3))
                                })

                if len(fb_words) > len(words):
                    logger.info("✅ Vocal recovery extracted %d lyric words (replacing previous %d words)", len(fb_words), len(words))
                    words = normalize_words_with_llm(fb_words)
                    reconstructed_text = " ".join(w["word"] for w in words)
            except Exception as e:
                logger.warning("Vocal recovery fallback failed: %s", e)
            finally:
                if os.path.exists(vocal_wav):
                    os.unlink(vocal_wav)

        return {
            "text": reconstructed_text.strip(),
            "words": words,
            "duration": info.duration
        }
    finally:
        if os.path.exists(wav_path):
            os.unlink(wav_path)
