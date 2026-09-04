import os
import re
import json
import time
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.environ.get(
    "OPENROUTER_API_KEY",
    "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"
)
LLM_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-5.6-luna")

def snap_to_nearest_beat(frame: int, beat_frames: List[int], tolerance_frames: int = 15) -> int:
    """Snaps an arbitrary frame number to the nearest musical downbeat if within tolerance."""
    if not beat_frames:
        return frame
    closest = min(beat_frames, key=lambda b: abs(b - frame))
    if abs(closest - frame) <= tolerance_frames:
        return closest
    return frame

def direct_music_scenes(
    lyric_words: List[Dict],
    full_lyrics: str,
    duration: float,
    rhythm_info: Dict[str, Any],
    fps: int = 30
) -> List[Dict]:
    """
    Directs kinetic typography scenes synchronized to musical tempo and beat grid.
    Scene boundaries snap to downbeats (musical bars), with strict lyrical grounding.
    """
    total_frames = max(30, round(duration * fps))
    downbeat_frames = rhythm_info.get("downbeat_frames", [])
    beat_frames = rhythm_info.get("beat_frames", [])
    bpm = rhythm_info.get("bpm", 120.0)

    if not lyric_words:
        return [{
            "type": "HERO_BLOCK",
            "startFrame": 0,
            "endFrame": total_frames,
            "theme": "dark",
            "alignment": "center",
            "lines": [full_lyrics or "♫"],
            "badgeLabel": "موسیقی",
            "isLyrical": True,
            "beatFrames": beat_frames
        }]

    # Step 1: Cluster lyric words into poetic verses/lines based on musical downbeats
    scenes = []
    chunk = []
    chunk_start_frame = 0
    theme_cycle = ["dark", "accent", "light"]
    archetypes = ["HERO_BLOCK", "SPLIT_VIEWPORT", "CALLOUT_CARD", "HERO_BLOCK"]
    scene_idx = 0

    # Minimum scene length: 2 musical bars (approx 2.0s - 4.0s depending on BPM)
    min_frames = max(36, int((60.0 / bpm) * 4 * fps))

    for i, w in enumerate(lyric_words):
        chunk.append(w["word"])
        current_frame = int(round(w["end"] * fps))
        elapsed_frames = current_frame - chunk_start_frame

        is_scene_boundary = (
            (elapsed_frames >= min_frames and len(chunk) >= 3 and (
                any(abs(current_frame - db) <= 10 for db in downbeat_frames) or
                len(chunk) >= 7
            ))
            or (i == len(lyric_words) - 1)
        )

        if is_scene_boundary:
            end_frame = snap_to_nearest_beat(current_frame, downbeat_frames, tolerance_frames=12)
            if i == len(lyric_words) - 1:
                end_frame = total_frames

            # Format lines: Split into 1 or 2 high-impact lyrical phrases
            mid = max(1, len(chunk) // 2)
            l1 = " ".join(chunk[:mid]).strip()
            l2 = " ".join(chunk[mid:]).strip() if len(chunk) > mid else ""
            lines = [l1] if not l2 else [l1, l2]

            atype = archetypes[scene_idx % len(archetypes)]
            badge = "ترانه" if scene_idx == 0 else ("بیت" if atype == "SPLIT_VIEWPORT" else None)

            scenes.append({
                "type": atype,
                "startFrame": chunk_start_frame,
                "endFrame": end_frame,
                "theme": theme_cycle[scene_idx % len(theme_cycle)],
                "alignment": "center",
                "lines": lines,
                "badgeLabel": badge,
                "icon": "Sparkles" if atype == "CALLOUT_CARD" else None,
                "isLyrical": True,
                "beatFrames": [f for f in beat_frames if chunk_start_frame <= f <= end_frame]
            })

            chunk_start_frame = end_frame
            chunk = []
            scene_idx += 1

    # Step 2: Ensure strictly continuous frames without gaps or overlaps
    if scenes:
        scenes[0]["startFrame"] = 0
        for idx in range(len(scenes) - 1):
            if scenes[idx]["endFrame"] <= scenes[idx]["startFrame"]:
                scenes[idx]["endFrame"] = scenes[idx]["startFrame"] + min_frames
            scenes[idx + 1]["startFrame"] = scenes[idx]["endFrame"]
        scenes[-1]["endFrame"] = total_frames

    return scenes
