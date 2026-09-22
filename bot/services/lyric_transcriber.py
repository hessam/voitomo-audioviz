import os
import re
import subprocess
import tempfile
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "medium")

_whisper_model = None

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        logger.info(f"⚡ Loading faster-whisper {WHISPER_MODEL} for singing voice...")
        _whisper_model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8", cpu_threads=2)
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

AUDIOVIZ_BROKER_DIR = os.environ.get("AUDIOVIZ_BROKER_DIR", "/workspace/audioviz-broker")

def transcribe_lyrics_broker(vocal_audio_path: str, user_lyrics: Optional[str] = None, language: Optional[str] = None, timeout_sec: int = 600) -> Dict[str, Any]:
    import shutil
    import uuid
    import time
    import json
    job_id = f"transcribe_{uuid.uuid4().hex[:10]}"
    job_dir = os.path.join(AUDIOVIZ_BROKER_DIR, "jobs", job_id)
    os.makedirs(job_dir, exist_ok=True)
    try:
        input_dest = os.path.join(job_dir, "input.wav")
        shutil.copy2(vocal_audio_path, input_dest)
        trigger = {
            "job_id": job_id,
            "action": "transcribe",
            "audio_filename": "input.wav",
            "model": WHISPER_MODEL,
            "language": language
        }
        with open(os.path.join(job_dir, "trigger.json"), "w") as f:
            json.dump(trigger, f)

        logger.info(f"🚀 Sent transcribe job {job_id} ({WHISPER_MODEL}) to host orchestrator...")
        result_file = os.path.join(job_dir, "result.json")
        out_transcript = os.path.join(job_dir, "output", "transcript.json")

        start = time.time()
        while time.time() - start < timeout_sec:
            if os.path.exists(result_file):
                break
            time.sleep(0.5)

        if not os.path.exists(result_file):
            raise TimeoutError(f"Transcribe job {job_id} timed out after {timeout_sec}s")

        with open(result_file, "r") as f:
            res_data = json.load(f)

        if res_data.get("status") != "success":
            raise RuntimeError(f"Transcribe job {job_id} failed: {res_data.get('error')}")

        with open(out_transcript, "r", encoding="utf-8") as f:
            data = json.load(f)

        if user_lyrics and user_lyrics.strip():
            from bot.services.alignment import realign_transcript
            aligned_words = realign_transcript(data.get("words", []), user_lyrics.strip(), data.get("duration", 0.0))
            return {
                "text": user_lyrics.strip(),
                "words": aligned_words,
                "duration": data.get("duration", 0.0),
                "is_singing": True
            }
        data["is_singing"] = True
        return data
    finally:
        if os.path.exists(job_dir):
            try:
                shutil.rmtree(job_dir)
            except Exception:
                pass

def transcribe_lyrics_gpu(vocal_audio_path: str, ai_url: str, user_lyrics: Optional[str] = None, language: Optional[str] = None) -> Dict[str, Any]:
    import requests
    with open(vocal_audio_path, "rb") as f:
        files = {"file": (os.path.basename(vocal_audio_path), f, "audio/wav")}
        data = {}
        if language:
            data["language"] = language
        logger.info(f"🚀 Offloading singing voice transcription to GPU at {ai_url}/ai/transcribe (Whisper large-v3 CUDA)...")
        resp = requests.post(f"{ai_url}/ai/transcribe", files=files, data=data, timeout=120)
        if resp.status_code == 200:
            res_data = resp.json()
            if res_data.get("status") == "success":
                logger.info(f"⚡ GPU Transcription completed in {res_data.get('elapsed_seconds')}s: {len(res_data.get('words', []))} words")
                if user_lyrics and user_lyrics.strip():
                    from bot.services.alignment import realign_transcript
                    aligned_words = realign_transcript(res_data.get("words", []), user_lyrics.strip(), res_data.get("duration", 0.0))
                    return {
                        "text": user_lyrics.strip(),
                        "words": aligned_words,
                        "duration": res_data.get("duration", 0.0),
                        "is_singing": True
                    }
                res_data["is_singing"] = True
                return res_data
        raise RuntimeError(f"GPU transcribe returned {resp.status_code}: {resp.text}")

def transcribe_lyrics(vocal_audio_path: str, user_lyrics: Optional[str] = None, language: Optional[str] = None) -> Dict[str, Any]:
    """
    Singing-Voice Persian/English Transcription Engine:
    Strictly offloads to GPU AI endpoint (Whisper large-v3 CUDA) at port 4002.
    Zero Hetzner broker CPU offload.
    """
    ai_url = os.environ.get("REMOTE_RENDERER_URL") or os.environ.get("AUDIOVIZ_AI_URL") or "http://127.0.0.1:4002"
    try:
        return transcribe_lyrics_gpu(vocal_audio_path, ai_url, user_lyrics, language)
    except Exception as e:
        logger.error(f"GPU remote transcription failed: {e}")
        unload_whisper_model()
