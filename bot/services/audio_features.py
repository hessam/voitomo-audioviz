import os
import hashlib
import json
import logging
import math
import subprocess
import tempfile
import asyncio
from typing import List, Dict, Any, Optional

import numpy as np

from contracts.manifest import (
    RenderManifest,
    PresetConfig,
    VideoConfig,
    AudioConfig,
    AudioMultibandFeatures,
    LyricsConfig,
    LyricLine,
    LyricWord,
    VisualizerPresetId,
)
from bot.services.audio_adapter import AudioIntelligenceAdapter
from bot.services.pitch_analysis import decode_band, detect_notes
from bot.services.spectral_bands import body_bands
from bot.services.rhythm_analysis import (
    OnsetAnalysis,
    decode_mono,
    detect_onsets,
    estimate_meter,
    estimate_riff_cycle,
)

logger = logging.getLogger(__name__)


def compute_sha256(filepath: str) -> str:
    """Compute SHA-256 hash of a file for immutable caching & integrity."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_audio_duration_seconds(audio_path: str) -> float:
    """Get precise duration in seconds using ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path
        ]
        res = subprocess.check_output(cmd, text=True).strip()
        return float(res)
    except Exception as e:
        logger.warning(f"Failed to read audio duration via ffprobe: {e}. Defaulting to 10.0s")
        return 10.0


BAND_FILTERS = {
    "bass": "lowpass=f=250,acompressor=threshold=-18dB:ratio=3",
    "mids": "highpass=f=250,lowpass=f=4000",
    "treble": "highpass=f=4000,lowpass=f=16000",
    "drums": "highpass=f=60,lowpass=f=8000,acompressor=threshold=-16dB:ratio=4",
    "vocal": "highpass=f=200,lowpass=f=3500",
    "macro": "volume=1.0",
}
# Levels are measured at the source rate (never below 44.1 kHz) so highs are not discarded.
BAND_SAMPLE_RATE = 48000
# Full-scale RMS below which a band counts as silence, so quiet leakage is not amplified.
SILENCE_FLOOR_RMS = 0.003
MIN_ONSET_STRENGTH_FOR_TRANSIENT = 0.3


def decode_band_levels(target_path: str, filter_str: str, fps: int, total_frames: int) -> List[float]:
    """Absolute RMS per video frame, measured before any time reduction.

    Frame f covers only audio BEFORE its own start time, [(f-1)/fps, f/fps), so the level can
    never anticipate a sound. Frame 0 is silent by construction.
    """
    try:
        cmd = ["ffmpeg", "-v", "error", "-i", target_path, "-af", filter_str,
               "-ar", str(BAND_SAMPLE_RATE), "-ac", "1", "-f", "f32le", "-"]
        raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    except Exception as e:
        logger.warning(f"Error extracting band levels ({filter_str}): {e}")
        return [0.0] * total_frames
    samples = np.frombuffer(raw, dtype="<f4").astype(np.float64)
    block = BAND_SAMPLE_RATE // fps
    blocks = len(samples) // block
    levels = np.zeros(total_frames)
    if blocks:
        rms = np.sqrt((samples[: blocks * block].reshape(blocks, block) ** 2).mean(axis=1))
        count = min(blocks, total_frames - 1)
        levels[1: 1 + count] = rms[:count]
    return levels.tolist()


def normalize_levels(levels: List[float]) -> List[float]:
    """Scale to [0, 1] by the 99th percentile (one spike must not flatten the song).

    A band whose loudest part is below the silence floor stays near zero.
    """
    arr = np.asarray(levels, dtype=float)
    if arr.size == 0:
        return []
    reference = max(float(np.percentile(arr, 99)), SILENCE_FLOOR_RMS)
    return [round(float(v), 4) for v in np.clip(arr / reference, 0.0, 1.0)]


def extract_multiband_features_ffmpeg(
    audio_path: str,
    fps: int = 30,
    total_frames: int = 300,
    vocal_path: Optional[str] = None,
    bass_path: Optional[str] = None,
    drums_path: Optional[str] = None,
    other_path: Optional[str] = None,
    dna_data: Optional[Dict[str, Any]] = None,
) -> AudioMultibandFeatures:
    """
    Extracts deterministic 30 FPS normalized [0.0, 1.0] feature curves and measured events.

    Curves are RAW physical envelopes: no smoothing here. Each style's motion compiler owns
    attack and release. Missing stems fall back to filtered master bands (an estimate).
    - Bass: bass stem, else 20-250 Hz of the master
    - Mids: 250-4000 Hz of the master
    - Treble: other stem or master, 4000-16000 Hz (measured at the native rate)
    - Drums / Vocal energy: stem, else a filtered master band
    - Onsets: classified hits (kick/snare/cymbal) from the drums stem or the master
    - Rhythm: beats from the music DNA broker (or librosa); bar starts only when a meter was
      estimated, otherwise they are marked as assumed. Unknown stays unknown.
    """
    def has(path: Optional[str]) -> bool:
        return bool(path and os.path.exists(path))

    def curve(path: Optional[str], band: str) -> List[float]:
        stem = has(path)
        target = path if stem else audio_path
        filt = "volume=1.0" if stem else BAND_FILTERS[band]
        return normalize_levels(decode_band_levels(target, filt, fps, total_frames))

    bass_curve = curve(bass_path, "bass")
    mids_curve = normalize_levels(decode_band_levels(audio_path, BAND_FILTERS["mids"], fps, total_frames))
    treble_target = other_path if has(other_path) else audio_path
    treble_curve = normalize_levels(decode_band_levels(treble_target, BAND_FILTERS["treble"], fps, total_frames))
    drums_curve = curve(drums_path, "drums")
    vocal_curve = curve(vocal_path, "vocal")
    macro_curve = normalize_levels(decode_band_levels(audio_path, BAND_FILTERS["macro"], fps, total_frames))

    # Hits from the drums stem when separated, else the master mix.
    try:
        onset_analysis = detect_onsets(decode_mono(drums_path if has(drums_path) else audio_path))
    except Exception as e:
        logger.warning(f"Onset detection skipped: {e}")
        onset_analysis = OnsetAnalysis([], [], [])
    onsets = onset_analysis.events(fps, total_frames)
    transients = [o.frame for o in onsets if o.strength >= MIN_ONSET_STRENGTH_FOR_TRANSIENT]

    # Pitched notes: bass line from the bass stem (else the low band of the mix), plus vocals when separated.
    # Monophonic estimates; weak or unpitched passages produce no note.
    notes = []
    try:
        bass_stem = has(bass_path)
        notes += detect_notes(decode_band(bass_path if bass_stem else audio_path, 30.0, 400.0), fps, total_frames,
                              stem="bass" if bass_stem else "mix-low", max_hz=400.0)
        if has(vocal_path):
            notes += detect_notes(decode_band(vocal_path, 80.0, 1200.0), fps, total_frames, stem="vocals",
                                  min_hz=80.0, max_hz=1000.0)
        notes.sort(key=lambda n: n.startFrame)
    except Exception as e:
        logger.warning(f"Note detection skipped: {e}")

    # Per-stem spectral bands for the Resonant Bodies style.
    try:
        bands = body_bands(
            {"bass": bass_path if has(bass_path) else None, "drums": drums_path if has(drums_path) else None,
             "vocals": vocal_path if has(vocal_path) else None, "other": other_path if has(other_path) else None},
            audio_path, fps, total_frames,
        )
    except Exception as e:
        logger.warning(f"Body bands skipped: {e}")
        bands = {}

    # Rhythm: never invent a grid. Unknown stays unknown.
    rhythm_source = "unknown"
    bpm: Optional[float] = None
    beat_times: List[float] = []
    beat_frames: List[int] = []
    downbeat_frames: List[int] = []
    downbeats_assumed = False
    musical_key = ""
    if dna_data and isinstance(dna_data, dict) and dna_data.get("bpm"):
        rhythm_source = "broker"
        bpm = float(dna_data["bpm"])
        beat_times = [float(t) for t in dna_data.get("beat_times", [])] or \
            [f / fps for f in dna_data.get("beat_frames", [])]
        musical_key = str(dna_data.get("musical_key") or "")
    else:
        rhythm = AudioIntelligenceAdapter.extract_rhythm_and_beats(audio_path, fps=fps)
        if rhythm.get("status") == "measured":
            rhythm_source = "estimated"
            bpm = float(rhythm["bpm"])
            beat_times = [float(t) for t in rhythm.get("beats_sec", [])]
    beat_frames = [f for f in (int(round(t * fps)) for t in beat_times) if 0 <= f < total_frames]

    meter_beats: Optional[int] = None
    riff_cycle = None
    if beat_times and onset_analysis.times:
        meter = estimate_meter(beat_times, onset_analysis.times, onset_analysis.strengths)
        if meter is not None:
            meter_beats = meter.beats_per_bar
            downbeat_frames = [f for i, f in enumerate(beat_frames) if i % meter.beats_per_bar == meter.downbeat_phase]
        riff_cycle = estimate_riff_cycle(beat_times, onset_analysis.times, onset_analysis.strengths, fps)
    if meter_beats is None and beat_frames:
        # No measured meter: say so instead of presenting "every 4th beat" as fact.
        downbeat_frames = beat_frames[::4]
        downbeats_assumed = True

    return AudioMultibandFeatures(
        bass=bass_curve,
        mids=mids_curve,
        treble=treble_curve,
        transients=transients,
        bpm=bpm,
        beatFrames=beat_frames,
        downbeatFrames=downbeat_frames,
        vocalEnergy=vocal_curve,
        drumsEnergy=drums_curve,
        macroEnergy=macro_curve,
        musicalKey=musical_key,
        rhythmSource=rhythm_source,
        downbeatsAssumed=downbeats_assumed,
        meterBeats=meter_beats,
        onsets=onsets,
        notes=notes,
        riffCycle=riff_cycle,
        bodyBands=bands,
    )


def _word_score(word: Dict[str, Any]) -> float:
    """
    Alignment emits 'score'; transcription emits 'confidence'.
    A word with neither keeps the legacy 1.0 default.
    """
    raw = word.get("score", word.get("confidence"))
    return float(raw) if raw is not None else 1.0


def group_words_into_phrases(
    words: List[Dict[str, Any]],
    fps: int = 30,
    pause_threshold_sec: float = 0.5,
    max_words_per_phrase: int = 6,
) -> List[LyricLine]:
    """
    Groups aligned words into coherent visual phrases (LyricLines) using:
    1. Acoustic pause detection (split when gap between words >= pause_threshold_sec)
    2. Punctuation boundaries (split on '.', '!', '؟', '?', '،', ',')
    3. Natural phrase length limit (max_words_per_phrase)
    4. Preserves word-level timing, confidence score, and interpolation flags.
    """
    if not words or not isinstance(words, list):
        return []

    phrases: List[LyricLine] = []
    current_words: List[LyricWord] = []
    current_raw_words: List[str] = []
    prev_end_sec: Optional[float] = None

    def flush_phrase():
        nonlocal current_words, current_raw_words, prev_end_sec
        if not current_words:
            return
        line_text = " ".join(current_raw_words).strip()
        if line_text:
            start_f = min(w.startFrame for w in current_words)
            end_f = max(w.endFrame for w in current_words)
            if end_f <= start_f:
                end_f = start_f + 4
            scores = [w.score for w in current_words if w.score is not None]
            avg_score = sum(scores) / len(scores) if scores else 1.0
            phrases.append(
                LyricLine(
                    text=line_text,
                    startFrame=start_f,
                    endFrame=end_f,
                    isHero=(len(line_text) > 15),
                    confidence=round(avg_score, 3),
                    words=list(current_words),
                )
            )
        current_words = []
        current_raw_words = []

    for w in words:
        w_text = str(w.get("word", "")).strip()
        if not w_text:
            continue
        try:
            w_start_sec = float(w.get("start", 0.0))
            w_end_sec = float(w.get("end", w_start_sec + 0.3))
        except (ValueError, TypeError):
            continue

        if w_end_sec <= w_start_sec:
            w_end_sec = w_start_sec + 0.1

        # Pause detection: acoustic gap since previous word end
        is_pause = (prev_end_sec is not None) and ((w_start_sec - prev_end_sec) >= pause_threshold_sec)
        is_length_exceeded = len(current_raw_words) >= max_words_per_phrase

        if is_pause or is_length_exceeded:
            flush_phrase()

        w_start_frame = int(round(w_start_sec * fps))
        w_end_frame = max(w_start_frame + 1, int(round(w_end_sec * fps)))
        w_score = _word_score(w)
        w_interp = bool(w.get("is_interpolated", False))
        w_src = str(w.get("alignment_source", "acoustic"))

        current_words.append(
            LyricWord(
                word=w_text,
                startFrame=w_start_frame,
                endFrame=w_end_frame,
                score=w_score,
                isInterpolated=w_interp,
                alignmentSource=w_src,
            )
        )
        current_raw_words.append(w_text)
        prev_end_sec = w_end_sec

        # Punctuation check: split after punctuation
        if w_text.endswith((".", "!", "؟", "?", "،", ",")):
            flush_phrase()

    flush_phrase()
    return phrases


class AudioFeatureExtractor:
    """
    Compiles an Astra-compliant immutable Pre-Render Manifest.
    Guarantees:
    - 100% precalculated 30 FPS multiband arrays (zero runtime DSP during render)
    - Whisper lyrics aligned to 30 FPS frame intervals
    - SHA-256 verification hashes for audio inputs
    """

    @classmethod
    async def extract_and_compile_manifest(
        cls,
        job_id: str,
        audio_path: str,
        preset_id: VisualizerPresetId,
        words: Optional[List[Dict[str, Any]]] = None,
        preset_params: Optional[Dict[str, Any]] = None,
        seed: int = 42,
        chat_id: int = 0,
        message_id: int = 0,
        pre_extracted_stems: Optional[Dict[str, str]] = None,
        show_lyrics: bool = True,
        lyric_mode: str = "subtitles",
    ) -> RenderManifest:
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        duration_sec = get_audio_duration_seconds(audio_path)
        fps = 30
        total_frames = max(30, int(round(duration_sec * fps)))
        audio_hash = compute_sha256(audio_path)

        # 1. Attempt stem extraction via Audio Intelligence Adapter or reuse pre-extracted stems
        vocal_stem_path: Optional[str] = None
        bass_stem_path: Optional[str] = None
        drums_stem_path: Optional[str] = None
        other_stem_path: Optional[str] = None
        dna_data: Optional[Dict[str, Any]] = None

        if pre_extracted_stems and isinstance(pre_extracted_stems, dict):
            vocal_stem_path = pre_extracted_stems.get("vocals")
            bass_stem_path = pre_extracted_stems.get("bass")
            drums_stem_path = pre_extracted_stems.get("drums")
            other_stem_path = pre_extracted_stems.get("other") or pre_extracted_stems.get("instrumental")
            logger.info(f"⚡ Reusing pre-extracted stems: {list(pre_extracted_stems.keys())}")
        else:
            try:
                stems = await AudioIntelligenceAdapter.separate_stems_broker(
                    audio_path,
                    chat_id=chat_id,
                    message_id=message_id,
                )
                vocal_stem_path = stems.get("vocals")
                bass_stem_path = stems.get("bass")
                drums_stem_path = stems.get("drums")
                other_stem_path = stems.get("other") or stems.get("instrumental")
                if not vocal_stem_path:
                    vocal_stem_path = await AudioIntelligenceAdapter.separate_vocals(audio_path)
            except Exception as e:
                logger.info(f"Stem separation skipped: {e}")

        # 2. Attempt Music DNA extraction via Audio Intelligence Adapter
        try:
            dna_data = await AudioIntelligenceAdapter.extract_music_dna_broker(audio_path)
        except Exception as e:
            logger.info(f"Music DNA extraction skipped: {e}")

        # 3. Extract deterministic multiband 30 FPS features with stem & rhythm awareness
        features = extract_multiband_features_ffmpeg(
            audio_path=audio_path,
            fps=fps,
            total_frames=total_frames,
            vocal_path=vocal_stem_path,
            bass_path=bass_stem_path,
            drums_path=drums_stem_path,
            other_path=other_stem_path,
            dna_data=dna_data,
        )

        # 3. Format Whisper words into 30 FPS clamped LyricLines
        # If words is empty or missing, run lyric transcription on isolated vocal stem ONLY if show_lyrics is True
        if show_lyrics and (not words or len(words) == 0) and vocal_stem_path and os.path.exists(vocal_stem_path):
            try:
                from bot.services.lyric_transcriber import transcribe_lyrics_managed
                logger.info(f"🎙 Running singing transcription on isolated vocal stem: {vocal_stem_path}")
                lyric_res = await transcribe_lyrics_managed(vocal_stem_path)
                words = lyric_res.get("words", [])
                logger.info(f"✅ Extracted {len(words)} lyric words from vocal stem")
            except Exception as e:
                logger.info(f"Fallback vocal lyric transcription skipped: {e}")

        lyric_lines: List[LyricLine] = []
        if show_lyrics and words and isinstance(words, list):
            lyric_lines = group_words_into_phrases(
                words,
                fps=fps,
                pause_threshold_sec=0.5,
                max_words_per_phrase=6,
            )

        # 4. Strict Sanitization Pass: Guarantee render_contract invariants for long songs
        sanitized_lyrics: List[LyricLine] = []
        if show_lyrics:
            prev_start = -1
            for l in lyric_lines:
                text = l.text.strip()
                if not text:
                    continue
                start = max(0, l.startFrame)
                if start <= prev_start:
                    start = prev_start + 1
                if start >= total_frames - 2:
                    break
                end = max(start + 4, l.endFrame)
                end = min(end, total_frames)
                if start >= end:
                    continue
                sanitized_lyrics.append(
                    LyricLine(
                        text=text,
                        startFrame=start,
                        endFrame=end,
                        isHero=bool(l.isHero),
                        confidence=float(getattr(l, "confidence", 1.0)),
                        words=list(getattr(l, "words", [])),
                    )
                )
                prev_start = start

        # Sanitize event frame arrays (non-decreasing, non-negative, strictly < total_frames)
        features.transients = sorted(list(set(int(f) for f in features.transients if 0 <= f < total_frames)))
        features.beatFrames = sorted(list(set(int(f) for f in features.beatFrames if 0 <= f < total_frames)))
        features.downbeatFrames = sorted(list(set(int(f) for f in features.downbeatFrames if 0 <= f < total_frames)))
        features.notes = sorted(
            (n for n in features.notes if 0 <= n.startFrame < n.endFrame <= total_frames and n.pitchHz > 0),
            key=lambda n: n.startFrame,
        )
        features.onsets = sorted(
            (o for o in features.onsets if 0 <= o.frame < total_frames and 0.0 <= o.strength <= 1.0),
            key=lambda o: o.frame,
        )

        # Guarantee curve arrays match total_frames exactly
        for curve_name in ["bass", "mids", "treble", "vocalEnergy", "drumsEnergy", "macroEnergy"]:
            val = getattr(features, curve_name, [])
            if len(val) < total_frames:
                val = val + [0.0] * (total_frames - len(val))
            elif len(val) > total_frames:
                val = val[:total_frames]
            val = [max(0.0, min(1.0, float(v))) for v in val]
            setattr(features, curve_name, val)

        manifest = RenderManifest(
            schemaVersion=1,
            jobId=job_id,
            seed=seed,
            preset=PresetConfig(
                id=preset_id,
                version="1.0.0",
                parameters=preset_params or {},
            ),
            video=VideoConfig(
                width=1920,
                height=1080,
                fpsNumerator=30,
                fpsDenominator=1,
                frameCount=total_frames,
            ),
            audio=AudioConfig(
                masterUri=audio_path,
                sha256=audio_hash,
                sampleRate=44100,
                vocalStemUri=vocal_stem_path,
                bassStemUri=bass_stem_path,
                features=features,
            ),
            lyrics=LyricsConfig(lines=sanitized_lyrics, mode=lyric_mode if show_lyrics else "off"),
            environment={
                "concurrency": 2,
                "gpuBackend": "angle",
            },
        )

        return manifest
