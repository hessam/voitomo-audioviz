import os
import sys

# Add repository root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bot.services.music_director import direct_music_scenes, snap_to_nearest_beat
from bot.services.lyric_transcriber import clean_lyric_token

def test_clean_lyric_token():
    assert clean_lyric_token("[music]") == ""
    assert clean_lyric_token("(موسیقی)") == ""
    assert clean_lyric_token("♪ دل من هواتو کرده ♪") == "دل من هواتو کرده"
    assert clean_lyric_token("،آسمان آبی!") == "آسمان آبی"
    print("✅ test_clean_lyric_token passed!")

def test_snap_to_nearest_beat():
    beat_frames = [0, 30, 60, 90, 120]
    # Frame 28 should snap to 30
    assert snap_to_nearest_beat(28, beat_frames, tolerance_frames=5) == 30
    # Frame 45 is too far (dist 15 > 5), should stay 45
    assert snap_to_nearest_beat(45, beat_frames, tolerance_frames=5) == 45
    print("✅ test_snap_to_nearest_beat passed!")

def test_direct_music_scenes():
    lyric_words = [
        {"word": "دل", "start": 0.5, "end": 0.8},
        {"word": "من", "start": 0.9, "end": 1.2},
        {"word": "هواتو", "start": 1.3, "end": 1.8},
        {"word": "کرده", "start": 1.9, "end": 2.4},
        {"word": "روشنه", "start": 2.6, "end": 3.0},
        {"word": "ستاره", "start": 3.2, "end": 3.8},
        {"word": "امشب", "start": 3.9, "end": 4.5}
    ]
    full_lyrics = "دل من هواتو کرده روشنه ستاره امشب"
    duration = 5.0
    rhythm_info = {
        "bpm": 120.0,
        "beat_frames": [0, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150],
        "downbeat_frames": [0, 60, 120],
        "beats_sec": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
    }

    scenes = direct_music_scenes(lyric_words, full_lyrics, duration, rhythm_info, fps=30)
    assert len(scenes) >= 1
    assert scenes[0]["startFrame"] == 0
    assert scenes[-1]["endFrame"] == round(duration * 30)
    for s in scenes:
        assert s.get("isLyrical") is True
        assert len(s["lines"]) > 0
    print(f"✅ test_direct_music_scenes passed ({len(scenes)} scenes generated)!")

if __name__ == "__main__":
    test_clean_lyric_token()
    test_snap_to_nearest_beat()
    test_direct_music_scenes()
    print("\n🎉 ALL MUSIC TESTS PASSED CLEANLY!")
