import re
from typing import List, Dict, Tuple

# Common Whisper large-v3-turbo Persian misrecognitions & typos
PHONETIC_CORRECTIONS = {
    r"\bمحصه\b": "مهسا",
    r"\bمهصا\b": "مهسا",
    r"\bحوضه\b": "حوزه",
    r"\bدیژیتال\b": "دیجیتال",
    r"\bترکیم\b": "ترکیه",
    r"\bمضافه\b": "به اضافه",
    r"\bکاری مارکتینگ\b": "کارهای مارکتینگ",
    r"\bجذب\s*تن\s*قسمت\s*ها\b": "جذاب‌ترین قسمت‌ها",
    r"\bجذب\s*تنقسمتها\b": "جذاب‌ترین قسمت‌ها",
    r"\bجذاب\s*ترین\b": "جذاب‌ترین",
    r"\bلینکتین\b": "لینکدین",
    r"\bقبیتاً\b": "",
    r"\bساکن\s+ترکیه‌م\b": "ساکن ترکیه",
    r"\bساکن\s+ترکیم\b": "ساکن ترکیه",
    r"\bپونزه[،\s]+شونزه\s+سالی\b": "۱۵ الی ۱۶ سال",
    r"\bپونزه[،\s]+شونزه\b": "۱۵-۱۶",
    r"\bشیش\s+سالی\b": "۶ سال",
    r"\bشیش\b": "۶"
}

def normalize_persian_asr(raw_text: str, words: List[Dict]) -> Tuple[str, List[Dict], List[Dict]]:
    """
    Normalizes raw Whisper Persian ASR text into:
    1. clean_text: Grammatically corrected full transcript
    2. clean_words: Word tokens with phoneme corrections, keeping timing intact
    3. diff_log: List of corrections made for audit reporting
    """
    clean_text = raw_text
    diff_log = []

    for pattern, replacement in PHONETIC_CORRECTIONS.items():
        if re.search(pattern, clean_text):
            old_val = re.search(pattern, clean_text).group(0)
            clean_text = re.sub(pattern, replacement, clean_text)
            diff_log.append({"original": old_val, "corrected": replacement})

    # Clean double spaces
    clean_text = re.sub(r"\s+", " ", clean_text).strip()

    # Apply word-level corrections preserving timestamps
    clean_words = []
    for w in words:
        orig_w = w["word"]
        new_w = orig_w
        for pattern, replacement in PHONETIC_CORRECTIONS.items():
            if re.search(pattern, new_w):
                new_w = re.sub(pattern, replacement, new_w)
        new_w = new_w.strip()
        if new_w:
            clean_words.append({
                "word": new_w,
                "start": w["start"],
                "end": w["end"]
            })

    return clean_text, clean_words, diff_log
