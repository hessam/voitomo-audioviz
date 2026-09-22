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
    Guarantees:
    - 0 <= start < end <= total_duration
    - Every word has explicit 'is_interpolated' and 'alignment_source'
    - Never extends past master audio duration
    """
    if total_duration is None:
        total_duration = float(orig_words[-1]["end"]) if orig_words else 10.0
    total_duration = max(0.1, float(total_duration))

    new_tokens = [w.strip() for w in new_text.split() if w.strip()]
    if not new_tokens:
        return orig_words

    if not orig_words:
        step = total_duration / len(new_tokens)
        return [{
            "word": token,
            "start": float(round(i * step, 3)),
            "end": float(round(min(total_duration, (i + 1) * step), 3)),
            "score": 0.0,
            "is_interpolated": True,
            "alignment_source": "interpolated"
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
            matched_dict = dict(orig_words[oi])
            matched_dict["word"] = new_tokens[ni]
            matched_dict["start"] = float(orig_words[oi]["start"])
            matched_dict["end"] = float(orig_words[oi]["end"])
            matched_dict["is_interpolated"] = bool(orig_words[oi].get("is_interpolated", False))
            matched_dict["alignment_source"] = str(orig_words[oi].get("alignment_source", "acoustic"))
            aligned_words[ni] = matched_dict

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
        next_time = aligned_words[gap_end_idx]["start"] if gap_end_idx < N else total_duration

        # Clamp bounds strictly within [0.0, total_duration]
        prev_time = max(0.0, min(prev_time, total_duration))
        next_time = max(prev_time, min(next_time, total_duration))

        gap_len = gap_end_idx - gap_start_idx
        available_span = next_time - prev_time

        # If no positive span available, distribute tightly within remaining budget
        if available_span <= 0.001:
            remaining_after = total_duration - prev_time
            if remaining_after > 0.005:
                next_time = min(total_duration, prev_time + remaining_after)
                available_span = next_time - prev_time
            else:
                # Borrow tiny room backwards if needed without violating bounds
                prev_time = max(0.0, total_duration - 0.01 * gap_len)
                next_time = total_duration
                available_span = next_time - prev_time

        time_slot = available_span / gap_len

        for g_i in range(gap_len):
            curr_idx = gap_start_idx + g_i
            s = float(round(prev_time + g_i * time_slot, 4))
            e = float(round(prev_time + (g_i + 1) * time_slot, 4))
            e = min(total_duration, max(s + 0.0001, e))
            aligned_words[curr_idx] = {
                "word": new_tokens[curr_idx],
                "start": s,
                "end": e,
                "score": 0.0,
                "is_interpolated": True,
                "alignment_source": "interpolated"
            }

    # 3. Monotonic sanity & strict total_duration clamping pass
    # Ensure starts and ends are strictly monotonic
    for i in range(len(aligned_words)):
        w = aligned_words[i]
        if i > 0:
            prev_e = aligned_words[i - 1]["end"]
            if w["start"] < prev_e:
                w["start"] = prev_e
        if w["end"] <= w["start"]:
            w["end"] = w["start"] + 0.001

    # If the end of any word exceeds total_duration, proportionally scale all timestamps
    max_end = aligned_words[-1]["end"]
    if max_end > total_duration:
        scale = total_duration / max_end
        for w in aligned_words:
            w["start"] = float(round(w["start"] * scale, 4))
            w["end"] = float(round(w["end"] * scale, 4))

    # Final hard invariant check
    last_end = 0.0
    for i, w in enumerate(aligned_words):
        w["start"] = max(0.0, min(float(w["start"]), total_duration))
        if w["start"] < last_end:
            w["start"] = last_end
        # Guarantee minimum positive duration
        min_end = min(total_duration, w["start"] + 0.001)
        w["end"] = max(min_end, min(float(w["end"]), total_duration))
        if w["end"] <= w["start"] and w["start"] < total_duration:
            w["end"] = total_duration
        last_end = w["end"]

    return aligned_words
