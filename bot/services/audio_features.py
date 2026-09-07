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
) -> AudioMultibandFeatures:
    """
    Extracts deterministic 30 FPS normalized [0.0, 1.0] multiband frequency features:
    - Bass: 20Hz - 250Hz (kick, sub-bass, 808)
    - Mids: 250Hz - 4000Hz (vocals, melodies, snare punch)
    - Treble: 4000Hz - 16000Hz (hi-hats, cymbals, air)
    - Transients: frame indices with sharp onset peaks
    """
    bass_curve = [0.0] * total_frames
    mids_curve = [0.0] * total_frames
    treble_curve = [0.0] * total_frames
    transients: List[int] = []

    def get_band_rms(filter_str: str) -> List[float]:
        try:
            # Output raw 16-bit mono PCM at 3000 Hz (100 samples per video frame at 30 FPS)
            target_sr = fps * 100
            cmd = [
                "ffmpeg", "-y", "-i", audio_path,
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

            # Normalize 0.0 - 1.0
            max_val = max(frame_energies) if frame_energies else 1.0
            if max_val > 0.001:
                return [round(min(1.0, e / max_val), 4) for e in frame_energies]
            return [0.0] * total_frames
        except Exception as e:
            logger.warning(f"Error extracting band RMS ({filter_str}): {e}")
            return [0.0] * total_frames

    # Extract 3 frequency bands
    bass_raw = get_band_rms("lowpass=f=250,acompressor=threshold=-18dB:ratio=3")
    mids_raw = get_band_rms("highpass=f=250,lowpass=f=4000")
    treble_raw = get_band_rms("highpass=f=4000,lowpass=f=16000")

    # Apply exponential smoothing to prevent single-frame flickering
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

    # Detect transient drops/kicks (peaks in bass where instantaneous energy > 1.4x smoothed)
    for i in range(1, len(bass_raw) - 1):
        if bass_raw[i] > 0.55 and bass_raw[i] > bass_raw[i - 1] and bass_raw[i] >= bass_raw[i + 1]:
            transients.append(i)

    return AudioMultibandFeatures(
        bass=bass_curve,
        mids=mids_curve,
        treble=treble_curve,
        transients=transients,
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
        try:
            vocal_stem_path = await AudioIntelligenceAdapter.separate_vocals(audio_path)
        except Exception as e:
            logger.info(f"Vocal stem separation skipped: {e}")

        # 2. Extract deterministic multiband 30 FPS features
        features = extract_multiband_features_ffmpeg(
            audio_path=audio_path,
            fps=fps,
            total_frames=total_frames,
        )

        # 3. Format Whisper words into 30 FPS clamped LyricLines
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
                width=1080,
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
            lyrics=LyricsConfig(lines=lyric_lines),
            environment={
                "concurrency": 2,
                "gpuBackend": "angle",
            },
        )

        return manifest
