import difflib
from typing import List, Dict

def patch_word(words: List[Dict], old_word: str, new_word: str) -> List[Dict]:
    """Replace a single word in the transcript while preserving timestamps exactly."""
    patched = []
    old_lower = old_word.strip().lower()
    replaced = False
    for w in words:
        if not replaced and w["word"].strip().lower() == old_lower:
            patched.append({**w, "word": new_word.strip()})
            replaced = True
        else:
            patched.append(w)
    return patched

def parse_edit_command(text: str):
    """Parse 'old -> new' edit syntax. Returns (old, new) or None."""
    if "->" not in text:
        return None
    parts = text.split("->", 1)
    if len(parts) != 2:
        return None
    old, new = parts[0].strip(), parts[1].strip()
    if old and new:
        return old, new
    return None

def realign_transcript(orig_words: List[Dict], new_text: str, total_duration: float = None) -> List[Dict]:
    """
    Align an arbitrarily edited full transcript text back to the original audio timestamps
    using difflib SequenceMatcher and linear time interpolation for edited segments.
    """
    if total_duration is None:
        total_duration = orig_words[-1]["end"] if orig_words else 10.0
    new_tokens = [w.strip() for w in new_text.split() if w.strip()]
    if not new_tokens:
        return orig_words

    if not orig_words:
        step = total_duration / len(new_tokens)
        return [{
            "word": token,
            "start": float(round(i * step, 3)),
            "end": float(round((i + 1) * step, 3))
        } for i, token in enumerate(new_tokens)]

    orig_tokens = [w["word"].strip().lower() for w in orig_words]
    new_tokens_lower = [w.lower() for w in new_tokens]

    matcher = difflib.SequenceMatcher(None, orig_tokens, new_tokens_lower)
    aligned_words = [None] * len(new_tokens)

    # 1. Match unchanged blocks
    for block in matcher.get_matching_blocks():
        orig_idx, new_idx, length = block.a, block.b, block.size
        for offset in range(length):
            oi = orig_idx + offset
            ni = new_idx + offset
            aligned_words[ni] = {
                "word": new_tokens[ni],
                "start": float(orig_words[oi]["start"]),
                "end": float(orig_words[oi]["end"])
            }

    # 2. Interpolate unmatched/edited gaps
    idx = 0
    N = len(new_tokens)
    while idx < N:
        if aligned_words[idx] is not None:
            idx += 1
            continue

        gap_start_idx = idx
        while idx < N and aligned_words[idx] is None:
            idx += 1
        gap_end_idx = idx

        prev_time = aligned_words[gap_start_idx - 1]["end"] if gap_start_idx > 0 else 0.0
        next_time = aligned_words[gap_end_idx]["start"] if gap_end_idx < N else max(total_duration, orig_words[-1]["end"])

        if next_time <= prev_time:
            next_time = prev_time + 0.4 * (gap_end_idx - gap_start_idx)

        gap_len = gap_end_idx - gap_start_idx
        time_slot = (next_time - prev_time) / gap_len

        for g_i in range(gap_len):
            curr_idx = gap_start_idx + g_i
            s = float(round(prev_time + g_i * time_slot, 3))
            e = float(round(prev_time + (g_i + 1) * time_slot, 3))
            aligned_words[curr_idx] = {
                "word": new_tokens[curr_idx],
                "start": s,
                "end": e
            }

    # 3. Monotonic sanity pass
    last_end = 0.0
    for w in aligned_words:
        if w["start"] < last_end:
            w["start"] = last_end
        if w["end"] <= w["start"]:
            w["end"] = float(round(w["start"] + 0.15, 3))
        last_end = w["end"]

    return aligned_words
