from typing import Optional
from typing import Dict, Any


def read_expected_text_from_audio(audio_file_path: str, preferred_key: Optional[str] = None) -> Optional[str]:
    """Attempt to read expected/original text from an audio file's tags.

    Tries several common places:
    - TXXX frames with descriptions like expected_text, transcript, original_text
    - COMM (comments)
    - USLT (unsynchronized lyrics)
    - TIT2 (title) as a last resort

    If preferred_key is provided, it will prioritize a TXXX frame whose description matches it.
    Returns None if not found.
    """
    try:
        from mutagen import File  # type: ignore
        from mutagen.id3 import ID3, TXXX, COMM, USLT, TIT2  # type: ignore
    except Exception:
        return None

    muta = File(audio_file_path, easy=False)
    if muta is None:
        return None

    tags: Optional[ID3] = getattr(muta, "tags", None)
    if tags is None:
        return None

    # Helper to coerce values
    def _text_or_none(val: Any) -> Optional[str]:
        if val is None:
            return None
        if isinstance(val, str):
            return val.strip() or None
        # ID3 frames often carry list-like texts
        try:
            txt = str(val)
            return txt.strip() or None
        except Exception:
            return None

    # 1) Preferred TXXX
    if preferred_key:
        for frame in tags.getall("TXXX"):
            try:
                if hasattr(frame, "desc") and frame.desc:
                    if frame.desc.lower() == preferred_key.lower():
                        text = _text_or_none(frame.text[0] if getattr(frame, "text", None) else None)
                        if text:
                            return text
            except Exception:
                continue

    # 2) Heuristic TXXX keys
    for frame in tags.getall("TXXX"):
        try:
            key = (frame.desc or "").lower()
            if key in {"expected_text", "transcript", "original_text", "text", "expected", "target"}:
                text = _text_or_none(frame.text[0] if getattr(frame, "text", None) else None)
                if text:
                    return text
        except Exception:
            continue

    # 3) USLT (lyrics)
    uslt_list = tags.getall("USLT")
    for frame in uslt_list:
        try:
            text = _text_or_none(frame.text)
            if text:
                return text
        except Exception:
            continue

    # 4) COMM (comments)
    comm_list = tags.getall("COMM")
    for frame in comm_list:
        try:
            text = _text_or_none(frame.text)
            if text:
                return text
        except Exception:
            continue

    # 5) TIT2 (title)
    tit2_list = tags.getall("TIT2")
    for frame in tit2_list:
        try:
            text = _text_or_none(frame.text)
            if text:
                return text
        except Exception:
            continue

    # For non-MP3 containers, try a generic mapping
    if isinstance(tags, dict):  # some formats expose dict-like tags
        for key_guess in [
            preferred_key,
            "expected_text",
            "transcript",
            "original_text",
            "comment",
            "description",
            "title",
        ]:
            if not key_guess:
                continue
            value = tags.get(key_guess)
            text = _text_or_none(value)
            if text:
                return text

    return None
