import os
import sys
import gc
import re
import json
import time
import shutil
import logging
import tempfile
import subprocess
from typing import Optional, List, Dict, Any

# Ensure local packages can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("vast_ai_service")

app = FastAPI(title="Vast GPU AI Service", version="1.0.0")

_whisper_model = None
_separator = None
_align_model = None
_align_metadata = None

STORAGE_DIR = "/root/audioviz/storage"
os.makedirs(STORAGE_DIR, exist_ok=True)

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        logger.info("🚀 Loading faster-whisper large-v3 on CUDA (float16)...")
        _whisper_model = WhisperModel("large-v3", device="cuda", compute_type="float16")
        logger.info("✅ faster-whisper large-v3 warm in VRAM!")
    return _whisper_model

def get_separator():
    global _separator
    if _separator is None:
        from audio_separator.separator import Separator
        logger.info("🚀 Loading Mel-Band RoFormer (vocals_mel_band_roformer.ckpt) on CUDA...")
        models_dir = "/root/audioviz/models"
        os.makedirs(models_dir, exist_ok=True)
        _separator = Separator(
            output_format="WAV",
            model_file_dir=models_dir,
        )
        _separator.load_model("vocals_mel_band_roformer.ckpt")
        logger.info("✅ Mel-Band RoFormer warm in VRAM!")
    return _separator

def get_align_model(language_code: str = "fa"):
    global _align_model, _align_metadata
    if _align_model is None:
        try:
            import whisperx
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"🚀 Loading WhisperX aligner for '{language_code}' on {device}...")
            _align_model, _align_metadata = whisperx.load_align_model(
                language_code=language_code,
                device=device
            )
            logger.info(f"✅ WhisperX aligner for '{language_code}' warm in memory!")
        except Exception as e:
            logger.warning(f"WhisperX aligner not available or failed to load: {e}")
            _align_model = None
            _align_metadata = None
    return _align_model, _align_metadata

@app.on_event("startup")
def startup_prewarm():
    get_whisper_model()
    get_separator()

def clean_lyric_token(text: str) -> str:
    if not text:
        return ""
    t = text.strip()
    t = re.sub(r"[\[\(（【].*?[\]\)）】]", "", t)
    t = re.sub(r"[♪♫♬♩#]+", "", t)
    t = re.sub(r"^[،,.\-_!?؟\s]+", "", t)
    t = re.sub(r"[،,.\-_!?؟\s]+$", "", t)
    return t.strip()

@app.get("/health")
@app.get("/ai/health")
def health():
    import torch
    return {
        "status": "ok",
        "cuda_available": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "whisper_model": "large-v3"
    }

@app.post("/ai/transcribe")
async def transcribe(
    file: Optional[UploadFile] = File(None),
    filepath: Optional[str] = Form(None),
    language: Optional[str] = Form(None)
):
    start_t = time.time()
    temp_path = None
    if file:
        temp_path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        target_audio = temp_path
    elif filepath and os.path.exists(filepath):
        target_audio = filepath
    else:
        raise HTTPException(status_code=400, detail="Missing audio file or valid filepath")

    try:
        model = get_whisper_model()
        segments, info = model.transcribe(
            target_audio,
            beam_size=5,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
            language=language if language else None
        )

        words_out: List[Dict[str, Any]] = []
        full_text_list = []

        for segment in segments:
            for w in segment.words:
                cleaned = clean_lyric_token(w.word)
                if cleaned:
                    words_out.append({
                        "word": cleaned,
                        "start": round(w.start, 3),
                        "end": round(w.end, 3),
                        "confidence": round(w.probability, 2)
                    })
            if segment.text:
                full_text_list.append(segment.text.strip())

        elapsed = round(time.time() - start_t, 2)
        logger.info(f"⚡ Transcribed in {elapsed}s: {len(words_out)} words (Language: {info.language})")

        return {
            "status": "success",
            "duration": round(info.duration, 2),
            "language": info.language,
            "language_probability": round(info.language_probability, 2),
            "words": words_out,
            "text": " ".join(full_text_list).strip(),
            "elapsed_seconds": elapsed
        }
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

@app.post("/ai/separate-stems")
async def separate_stems(
    file: Optional[UploadFile] = File(None),
    filepath: Optional[str] = Form(None),
    job_id: Optional[str] = Form(None)
):
    from audio_separator.separator import Separator
    start_t = time.time()
    
    jid = job_id or f"stem_{int(time.time()*1000)}"
    job_out_dir = os.path.join(STORAGE_DIR, jid)
    os.makedirs(job_out_dir, exist_ok=True)

    temp_path = None
    if file:
        temp_path = os.path.join(job_out_dir, "input.wav")
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        target_audio = temp_path
    elif filepath and os.path.exists(filepath):
        target_audio = filepath
    else:
        raise HTTPException(status_code=400, detail="Missing audio file or valid filepath")

    try:
        sep = get_separator()
        sep.output_dir = job_out_dir
        outputs = sep.separate(target_audio)

        stems_dict = {}
        for out_name in outputs:
            base = os.path.basename(out_name)
            full_p = os.path.join(job_out_dir, base)
            if not os.path.exists(full_p):
                candidates = [
                    os.path.join("/root", base),
                    os.path.join("/root/audioviz", base),
                    out_name
                ]
                for c in candidates:
                    if os.path.exists(c):
                        shutil.move(c, full_p)
                        break

            lower = base.lower()
            if "vocal" in lower:
                stems_dict["vocals"] = f"/ai/stems/{jid}/vocal"
            elif "inst" in lower or "no_vocals" in lower:
                stems_dict["instrumental"] = f"/ai/stems/{jid}/instrumental"

        elapsed = round(time.time() - start_t, 2)
        logger.info(f"⚡ Separated stems in {elapsed}s: {list(stems_dict.keys())}")

        return {
            "status": "success",
            "job_id": jid,
            "stems": stems_dict,
            "elapsed_seconds": elapsed
        }
    except Exception as e:
        logger.error(f"Stem separation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ai/stems/{job_id}/{stem_type}")
async def get_stem_file(job_id: str, stem_type: str):
    job_dir = os.path.join(STORAGE_DIR, job_id)
    if not os.path.exists(job_dir):
        raise HTTPException(status_code=404, detail="Job not found")
    for f in os.listdir(job_dir):
        if f.endswith(".wav") and stem_type in f.lower():
            return FileResponse(os.path.join(job_dir, f), media_type="audio/wav")
    raise HTTPException(status_code=404, detail=f"Stem {stem_type} not found")

@app.post("/ai/align")
async def align_transcript_endpoint(
    file: Optional[UploadFile] = File(None),
    filepath: Optional[str] = Form(None),
    text: str = Form(...),
    language: str = Form("fa"),
    total_duration: Optional[float] = Form(None)
):
    start_t = time.time()
    temp_path = None
    if file:
        temp_path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        target_audio = temp_path
    elif filepath and os.path.exists(filepath):
        target_audio = filepath
    else:
        raise HTTPException(status_code=400, detail="Missing audio file or valid filepath")

    try:
        # Determine actual audio duration
        duration = float(total_duration or 0.0)
        if duration <= 0.0:
            try:
                cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", target_audio]
                res = subprocess.check_output(cmd, text=True).strip()
                duration = float(res)
            except Exception:
                duration = 10.0

        align_model, align_metadata = get_align_model(language)
        aligned_words = []
        if align_model is not None and align_metadata is not None:
            try:
                import whisperx
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
                audio_arr = whisperx.load_audio(target_audio)
                
                # Format text into segments for WhisperX
                raw_lines = [line.strip() for line in text.split("\n") if line.strip()]
                if not raw_lines:
                    raw_lines = [text.strip()]
                
                line_dur = duration / max(len(raw_lines), 1)
                segments = []
                for idx, line in enumerate(raw_lines):
                    s_start = round(idx * line_dur, 3)
                    s_end = round(min((idx + 1) * line_dur, duration), 3)
                    segments.append({"text": line, "start": s_start, "end": s_end})

                aligned_res = whisperx.align(
                    segments,
                    align_model,
                    align_metadata,
                    audio_arr,
                    device=device,
                    return_char_alignments=False
                )
                
                raw_words = aligned_res.get("word_segments", [])
                for w in raw_words:
                    w_txt = clean_lyric_token(w.get("word", ""))
                    if not w_txt:
                        continue
                    w_start = float(w.get("start", 0.0))
                    w_end = float(w.get("end", w_start + 0.2))
                    w_score = float(w.get("score", 0.8))
                    is_interp = ("score" not in w) or bool(w.get("is_interpolated", False))
                    aligned_words.append({
                        "word": w_txt,
                        "start": round(max(0.0, min(w_start, duration)), 3),
                        "end": round(max(w_start + 0.05, min(w_end, duration)), 3),
                        "score": round(w_score, 3),
                        "is_interpolated": is_interp,
                        "alignment_source": "whisperx_ctc" if not is_interp else "interpolated"
                    })
            except Exception as e:
                logger.warning(f"WhisperX alignment execution failed: {e}")
                aligned_words = []

        # Fallback to deterministic realign_transcript if model missing or failed
        if not aligned_words:
            from bot.services.alignment import realign_transcript
            aligned_words = realign_transcript([], text, total_duration=duration)

        elapsed = round(time.time() - start_t, 2)
        scores = [w.get("score", 0.0) for w in aligned_words if w.get("score") is not None]
        avg_score = round(sum(scores) / len(scores), 3) if scores else 0.0

        return {
            "status": "success",
            "words": aligned_words,
            "alignment_score": avg_score,
            "duration": round(duration, 3),
            "language": language,
            "elapsed_seconds": elapsed
        }
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5001)
