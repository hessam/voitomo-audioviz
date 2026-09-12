import os
import hashlib
import json
import logging
import math
import struct
import subprocess
import tempfile
import asyncio
from typing import List, Dict, Any, Optional

from contracts.manifest import (
    RenderManifest,
    PresetConfig,
    VideoConfig,
    AudioConfig,
    AudioMultibandFeatures,
    LyricsConfig,
    LyricLine,
    VisualizerPresetId,
)
from bot.services.audio_adapter import AudioIntelligenceAdapter

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
    Extracts deterministic 30 FPS normalized [0.0, 1.0] multiband frequency features:
    - Bass: isolated bass stem or 20Hz - 250Hz lowpass filter
    - Mids: 250Hz - 4000Hz (harmonic melodies, instruments)
    - Treble: isolated other/highs or 4000Hz - 16000Hz (sparkles, shimmer)
    - Transients: frame indices with sharp onset peaks
    - Vocal Energy: isolated vocal envelope [0.0, 1.0]
    - Drums Energy: isolated drums envelope or percussion transient envelope [0.0, 1.0]
    - Macro Energy: overall track dynamic range [0.0, 1.0]
    - Rhythm Grid: BPM, beat frames, downbeat frames, and harmonic key from Music DNA
    """
    def get_band_rms(target_path: str, filter_str: str) -> List[float]:
        try:
            target_sr = fps * 100
            cmd = [
                "ffmpeg", "-y", "-i", target_path,
                "-af", filter_str,
                "-ar", str(target_sr),
                "-ac", "1",
                "-f", "s16le", "-"
            ]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            raw_bytes, _ = proc.communicate()

            num_samples = len(raw_bytes) // 2
            if num_samples == 0:
                return [0.0] * total_frames

            samples = struct.unpack(f"<{num_samples}h", raw_bytes)
            frame_energies: List[float] = []
            samples_per_frame = 100

            for f_idx in range(total_frames):
                start = f_idx * samples_per_frame
                end = min(start + samples_per_frame, num_samples)
                if start >= num_samples:
                    frame_energies.append(0.0)
                    continue

                chunk = samples[start:end]
                if not chunk:
                    frame_energies.append(0.0)
                    continue

                sum_sq = sum(s * s for s in chunk)
                rms = math.sqrt(sum_sq / len(chunk))
                frame_energies.append(rms)

            max_val = max(frame_energies) if frame_energies else 1.0
            if max_val > 0.001:
                return [round(min(1.0, e / max_val), 4) for e in frame_energies]
            return [0.0] * total_frames
        except Exception as e:
            logger.warning(f"Error extracting band RMS ({filter_str}): {e}")
            return [0.0] * total_frames

    # Extract Bass: isolated bass stem if available, else lowpass master
    bass_target = bass_path if (bass_path and os.path.exists(bass_path)) else audio_path
    bass_filter = "volume=1.0" if (bass_path and os.path.exists(bass_path)) else "lowpass=f=250,acompressor=threshold=-18dB:ratio=3"
    bass_raw = get_band_rms(bass_target, bass_filter)

    # Extract Mids
    mids_raw = get_band_rms(audio_path, "highpass=f=250,lowpass=f=4000")

    # Extract Treble / Shimmer
    treble_target = other_path if (other_path and os.path.exists(other_path)) else audio_path
    treble_filter = "highpass=f=4000,lowpass=f=16000"
    treble_raw = get_band_rms(treble_target, treble_filter)

    # Isolated Drums Energy: drums stem if available, else transient-focused percussion band
    drums_target = drums_path if (drums_path and os.path.exists(drums_path)) else audio_path
    drums_filter = "volume=1.0" if (drums_path and os.path.exists(drums_path)) else "highpass=f=60,lowpass=f=8000,acompressor=threshold=-16dB:ratio=4"
    drums_raw = get_band_rms(drums_target, drums_filter)

    # Macro overall track energy
    macro_raw = get_band_rms(audio_path, "volume=1.0")

    # Isolated vocal energy curve
    vocal_target = vocal_path if (vocal_path and os.path.exists(vocal_path)) else audio_path
    vocal_filter = "volume=1.0" if (vocal_path and os.path.exists(vocal_path)) else "highpass=f=200,lowpass=f=3500"
    vocal_raw = get_band_rms(vocal_target, vocal_filter)

    # Apply exponential smoothing
    def smooth(arr: List[float], alpha: float = 0.35) -> List[float]:
        if not arr:
            return arr
        smoothed = [arr[0]]
        for v in arr[1:]:
            smoothed.append(round(alpha * v + (1.0 - alpha) * smoothed[-1], 4))
        return smoothed

    bass_curve = smooth(bass_raw, alpha=0.45)
    mids_curve = smooth(mids_raw, alpha=0.35)
    treble_curve = smooth(treble_raw, alpha=0.30)
    vocal_curve = smooth(vocal_raw, alpha=0.40)
    drums_curve = smooth(drums_raw, alpha=0.50)
    macro_curve = smooth(macro_raw, alpha=0.25)

    # Detect transient drops/kicks
    transients: List[int] = []
    transient_source = drums_raw if drums_path else bass_raw
    for i in range(1, len(transient_source) - 1):
        if transient_source[i] > 0.45 and transient_source[i] > transient_source[i - 1] and transient_source[i] >= transient_source[i + 1]:
            transients.append(i)

    # Rhythm & Musical Key: Use Music DNA if available, else local adapter fallback
    if dna_data and isinstance(dna_data, dict) and dna_data.get("bpm"):
        bpm = float(dna_data.get("bpm", 120.0))
        beat_frames = [f for f in dna_data.get("beat_frames", []) if f < total_frames]
        downbeat_frames = [f for f in dna_data.get("downbeat_frames", []) if f < total_frames]
        musical_key = dna_data.get("musical_key", "C Major")
    else:
        rhythm = AudioIntelligenceAdapter.extract_rhythm_and_beats(audio_path, fps=fps)
        bpm = rhythm.get("bpm", 120.0)
        beat_frames = [f for f in rhythm.get("beat_frames", []) if f < total_frames]
        downbeat_frames = [f for f in rhythm.get("downbeat_frames", []) if f < total_frames]
        musical_key = "C Major"

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
    )


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
    ) -> RenderManifest:
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        duration_sec = get_audio_duration_seconds(audio_path)
        fps = 30
        total_frames = max(30, int(round(duration_sec * fps)))
        audio_hash = compute_sha256(audio_path)

        # 1. Attempt stem extraction via Audio Intelligence Adapter
        vocal_stem_path: Optional[str] = None
        bass_stem_path: Optional[str] = None
        drums_stem_path: Optional[str] = None
        other_stem_path: Optional[str] = None
        dna_data: Optional[Dict[str, Any]] = None

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
        # If words is empty or missing, run lyric transcription on isolated vocal stem
        if (not words or len(words) == 0) and vocal_stem_path and os.path.exists(vocal_stem_path):
            try:
                from bot.services.lyric_transcriber import transcribe_lyrics
                logger.info(f"🎙 Running singing transcription on isolated vocal stem: {vocal_stem_path}")
                lyric_res = await asyncio.to_thread(transcribe_lyrics, vocal_stem_path)
                words = lyric_res.get("words", [])
                logger.info(f"✅ Extracted {len(words)} lyric words from vocal stem")
            except Exception as e:
                logger.info(f"Fallback vocal lyric transcription skipped: {e}")

        lyric_lines: List[LyricLine] = []
        if words and isinstance(words, list):
            # Group words into clean sequential lines (3 to 6 words per line)
            current_line_words = []
            current_start_frame = 0
            current_end_frame = 0

            for w in words:
                w_text = w.get("word", "").strip()
                if not w_text:
                    continue
                w_start = float(w.get("start", 0.0))
                w_end = float(w.get("end", w_start + 0.3))

                w_start_frame = int(round(w_start * fps))
                w_end_frame = int(round(w_end * fps))

                if not current_line_words:
                    current_start_frame = w_start_frame

                current_line_words.append(w_text)
                current_end_frame = max(current_end_frame, w_end_frame)

                # Line break condition: punctuation, pause > 0.6s, or 5 words
                if len(current_line_words) >= 5 or w_text.endswith((".", "!", "؟", "?", "،", ",")):
                    line_text = " ".join(current_line_words)
                    lyric_lines.append(
                        LyricLine(
                            text=line_text,
                            startFrame=current_start_frame,
                            endFrame=current_end_frame,
                            isHero=(len(line_text) > 15),
                        )
                    )
                    current_line_words = []

            if current_line_words:
                lyric_lines.append(
                    LyricLine(
                        text=" ".join(current_line_words),
                        startFrame=current_start_frame,
                        endFrame=current_end_frame,
                        isHero=False,
                    )
                )

        # 4. Strict Sanitization Pass: Guarantee render_contract invariants for long songs
        sanitized_lyrics: List[LyricLine] = []
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
                )
            )
            prev_start = start

        # Sanitize event frame arrays (non-decreasing, non-negative, strictly < total_frames)
        features.transients = sorted(list(set(int(f) for f in features.transients if 0 <= f < total_frames)))
        features.beatFrames = sorted(list(set(int(f) for f in features.beatFrames if 0 <= f < total_frames)))
        features.downbeatFrames = sorted(list(set(int(f) for f in features.downbeatFrames if 0 <= f < total_frames)))

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
            lyrics=LyricsConfig(lines=sanitized_lyrics),
            environment={
                "concurrency": 2,
                "gpuBackend": "angle",
            },
        )

        return manifest
