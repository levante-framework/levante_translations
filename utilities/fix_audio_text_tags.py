#!/usr/bin/env python3
"""
Fix MP3 ID3 custom 'text' tags that incorrectly store the item key instead of the real expected string.

Context:
- validate_audio resolves expected_text from the audio file's ID3 tags (TXXX frames), preferring keys like 'text'.
- Some audio files (notably de) have the custom tag 'text' set to e.g. "general-intro1" or "['general-intro1']".
- That causes the Audio Validation "Expected" column to show keys instead of the real prompt.

This script:
1) Loads the item bank translations CSV (default: translations/item-bank-translations.csv).
2) Walks a local audio directory (default: audio_files/<lang>).
3) Detects "bad" text tags (key/list-of-key/empty) and replaces them with the correct string from the CSV.
4) Audits other tags (voice/service/lang_code/created/title/artist/album) and writes a report.

Safe by default: runs in DRY RUN mode unless --apply is passed.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


def _strip_version_suffix(file_stem: str) -> str:
    # e.g. item_v003 -> item
    return re.sub(r"_v\d{3}$", "", file_stem, flags=re.IGNORECASE)


def _iter_audio_files(audio_dir: Path) -> Iterable[Path]:
    for p in sorted(audio_dir.glob("*.mp3")):
        if p.is_file():
            yield p


def _parse_key_listish(text: str) -> Optional[str]:
    """
    If text looks like "['general-intro1']" or '["general-intro1"]', return the inner key.
    Otherwise return None.
    """
    t = (text or "").strip()
    m = re.match(r'^\[\s*[\'"]([^\'"]+)[\'"]\s*\]$', t)
    if m:
        return m.group(1).strip()
    return None


def _is_bad_expected_text(tag_value: str, item_key: str) -> bool:
    """
    Heuristics for "bad" values we want to replace:
    - empty
    - equals item_key (case-sensitive compare on trimmed)
    - equals "['item_key']" / '["item_key"]'
    """
    if tag_value is None:
        return True
    t = str(tag_value).strip()
    if not t:
        return True
    if t == item_key:
        return True
    inner = _parse_key_listish(t)
    if inner == item_key:
        return True
    return False


def _load_translation_map(csv_path: Path, lang_code: str, lang_column: Optional[str] = None) -> Tuple[Dict[str, str], str]:
    """
    Returns (identifier -> expected_text, used_column_name)
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise RuntimeError("CSV appears to have no header row.")

        # Decide which column to use for expected text.
        fieldnames = [h.strip() for h in reader.fieldnames if h]
        chosen = lang_column
        if not chosen:
            if lang_code == "en":
                # English source text lives in column 'text' in this CSV.
                chosen = "text" if "text" in fieldnames else None
            else:
                chosen = lang_code if lang_code in fieldnames else None
        if not chosen:
            raise RuntimeError(
                f"Could not find a column for lang={lang_code}. "
                f"Pass --lang-column. Available: {', '.join(fieldnames[:30])}{'...' if len(fieldnames) > 30 else ''}"
            )

        id_col = "identifier" if "identifier" in fieldnames else ("item_id" if "item_id" in fieldnames else None)
        if not id_col:
            raise RuntimeError("CSV missing identifier/item_id column.")

        mapping: Dict[str, str] = {}
        for row in reader:
            key = (row.get(id_col) or "").strip()
            if not key:
                continue
            val = row.get(chosen) or ""
            # keep whitespace as-is except trimming ends (avoid accidental spaces causing WER pain)
            txt = str(val).strip()
            if txt:
                mapping[key] = txt
        return mapping, chosen


def _safe_parse_datetime(value: str) -> bool:
    if not value:
        return False
    v = str(value).strip()
    if not v:
        return False
    # Accept ISO-ish timestamps as "good enough"
    try:
        datetime.fromisoformat(v.replace("Z", "+00:00"))
        return True
    except Exception:
        return False


@dataclass
class FileReport:
    file: str
    item_key: str
    changed_text: bool
    old_text: str
    new_text: str
    missing_in_csv: bool
    tag_issues: List[str]


def _read_id3_tags_dict(mp3_path: Path) -> Dict[str, str]:
    """
    Reads ID3 tags into a dict. Uses utilities.utilities.read_id3_tags if available,
    otherwise falls back to direct mutagen parsing.
    """
    try:
        # Local import to avoid sys.path complications for callers.
        from utilities.utilities import read_id3_tags  # type: ignore

        return {k: ("" if v is None else str(v)) for k, v in (read_id3_tags(str(mp3_path)) or {}).items()}
    except Exception:
        # Fallback: minimal mutagen reader
        try:
            from mutagen.mp3 import MP3  # type: ignore
            from mutagen.id3 import ID3  # type: ignore
        except Exception:
            return {}
        audio = MP3(str(mp3_path), ID3=ID3)
        tags = audio.tags
        out: Dict[str, str] = {}
        if tags:
            # Standard
            for frame_id, key in [("TIT2", "title"), ("TPE1", "artist"), ("TALB", "album"), ("TDRC", "date"), ("TCON", "genre")]:
                try:
                    fr = tags.get(frame_id)
                    if fr:
                        out[key] = str(fr.text[0]) if getattr(fr, "text", None) else str(fr)
                except Exception:
                    pass
            # Custom TXXX
            try:
                for frame in tags.getall("TXXX"):
                    if getattr(frame, "desc", None) and getattr(frame, "text", None):
                        out[str(frame.desc)] = str(frame.text[0]) if frame.text else ""
            except Exception:
                pass
        return out


def _get_ci(tags: Dict[str, str], key: str) -> str:
    """Case-insensitive lookup for tag keys (TXXX desc values can vary in casing)."""
    target = (key or "").lower()
    if not target:
        return ""
    for k, v in tags.items():
        try:
            if str(k).lower() == target:
                return "" if v is None else str(v)
        except Exception:
            continue
    return ""


def _upsert_txxx(mp3_path: Path, desc: str, value: str, apply: bool) -> None:
    """
    Replace any existing TXXX frames (case-insensitive desc match) and add one with the given value.
    Does nothing in dry-run mode.
    """
    if not apply:
        return
    from mutagen.mp3 import MP3  # type: ignore
    from mutagen.id3 import ID3, TXXX  # type: ignore

    audio = MP3(str(mp3_path), ID3=ID3)
    if audio.tags is None:
        audio.add_tags()

    # Remove existing matching TXXX frames to avoid duplicates
    existing = list(audio.tags.getall("TXXX"))
    for frame in existing:
        try:
            if (frame.desc or "").lower() == desc.lower():
                # Remove frames with the same desc (mutagen uses "TXXX:<desc>" keys)
                audio.tags.delall("TXXX:" + frame.desc)  # type: ignore[attr-defined]
        except Exception:
            # delall is finicky; fallback to manual removal
            try:
                audio.tags.remove(frame)
            except Exception:
                pass

    audio.tags.add(TXXX(encoding=3, desc=desc, text=str(value)))
    audio.save()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Fix bad ID3 'text' tags for audio validation.")
    parser.add_argument("--lang", required=True, help="Language code (e.g. de, es-CO, en).")
    parser.add_argument(
        "--audio-dir",
        help="Directory of MP3 files to scan. Default: audio_files/<lang> (relative to repo root).",
    )
    parser.add_argument(
        "--csv",
        default=str(Path("translations") / "item-bank-translations.csv"),
        help="Path to item-bank-translations.csv",
    )
    parser.add_argument(
        "--lang-column",
        default=None,
        help="Override CSV column name to use for expected text (e.g. 'de', 'es-CO', 'text').",
    )
    parser.add_argument("--apply", action="store_true", help="Actually write tag changes. Default is dry-run.")
    parser.add_argument(
        "--fix-metadata",
        action="store_true",
        help="Also fill missing custom tags (service/created/lang_code) when possible.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Limit number of files processed (0 = no limit).")
    parser.add_argument("--report", default="", help="Optional path to write a JSON report.")
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    lang = (args.lang or "").strip()
    audio_dir = Path(args.audio_dir) if args.audio_dir else (repo_root / "audio_files" / lang)
    csv_path = Path(args.csv)
    if not csv_path.is_absolute():
        csv_path = repo_root / csv_path

    if not audio_dir.exists():
        print(f"❌ audio dir not found: {audio_dir}")
        return 2

    # Ensure mutagen available if applying changes
    if args.apply:
        try:
            import mutagen  # type: ignore  # noqa: F401
        except Exception as e:
            print(f"❌ mutagen is required to write tags: {e}")
            return 2

    mapping, used_col = _load_translation_map(csv_path, lang_code=lang, lang_column=args.lang_column)
    print(f"📄 Loaded {len(mapping):,} translations from {csv_path} (column: {used_col})")
    print(f"🎧 Scanning: {audio_dir}")
    print(f"{'🧪 DRY RUN' if not args.apply else '✍️ APPLY MODE'}")

    processed = 0
    changed = 0
    missing_csv = 0
    issues_counter: Dict[str, int] = {}
    reports: List[FileReport] = []

    for mp3 in _iter_audio_files(audio_dir):
        processed += 1
        if args.limit and processed > args.limit:
            break

        item_key = _strip_version_suffix(mp3.stem)
        tags = _read_id3_tags_dict(mp3)
        current_text = (_get_ci(tags, "text") or _get_ci(tags, "expected_text") or "").strip()

        expected = mapping.get(item_key, "")
        missing = not bool(expected)
        if missing:
            missing_csv += 1

        tag_issues: List[str] = []

        # Audit other tags (do not change them here, just report)
        if not (_get_ci(tags, "voice") or "").strip():
            tag_issues.append("missing_voice")
        service_val = (_get_ci(tags, "service") or "").strip()
        if not service_val:
            tag_issues.append("missing_service")
        created_val = (_get_ci(tags, "created") or "").strip()
        if not _safe_parse_datetime(created_val):
            tag_issues.append("missing_or_bad_created")
        lang_tag = (_get_ci(tags, "lang_code") or "").strip()
        if lang_tag and lang_tag != lang:
            tag_issues.append(f"lang_code_mismatch:{lang_tag}")
        if not (_get_ci(tags, "title") or "").strip():
            tag_issues.append("missing_title")
        if not (_get_ci(tags, "artist") or "").strip():
            tag_issues.append("missing_artist")
        if not (_get_ci(tags, "album") or "").strip():
            tag_issues.append("missing_album")

        # Fix only if expected exists and tag value is clearly a key/list-of-key/empty.
        should_fix_text = (not missing) and _is_bad_expected_text(current_text, item_key)
        old_text = current_text
        new_text = expected if should_fix_text else ""

        if should_fix_text:
            changed += 1
            if args.apply:
                _upsert_txxx(mp3, desc="text", value=expected, apply=True)
            else:
                # dry run: no write
                pass

        # Optional metadata fixes for custom tags
        if args.apply and args.fix_metadata:
            now_iso = datetime.now().isoformat()
            if not service_val:
                # Best-effort inference
                artist_val = (_get_ci(tags, "artist") or "").lower()
                comment_val = (_get_ci(tags, "comment") or "").lower()
                inferred = ""
                if "eleven" in artist_val or "eleven" in comment_val:
                    inferred = "ElevenLabs"
                elif "playht" in artist_val or "playht" in comment_val or "play ht" in artist_val or "play ht" in comment_val:
                    inferred = "PlayHT"
                if inferred:
                    _upsert_txxx(mp3, desc="service", value=inferred, apply=True)
            if not _safe_parse_datetime(created_val):
                _upsert_txxx(mp3, desc="created", value=now_iso, apply=True)
            if not lang_tag:
                _upsert_txxx(mp3, desc="lang_code", value=lang, apply=True)

        for issue in tag_issues:
            issues_counter[issue] = issues_counter.get(issue, 0) + 1

        if should_fix_text or tag_issues:
            reports.append(
                FileReport(
                    file=str(mp3),
                    item_key=item_key,
                    changed_text=should_fix_text,
                    old_text=old_text,
                    new_text=new_text,
                    missing_in_csv=missing,
                    tag_issues=tag_issues,
                )
            )

    print("\n✅ Scan complete.")
    print(f"   Files processed: {processed:,}")
    print(f"   Missing CSV entries: {missing_csv:,}")
    print(f"   Bad 'text' tags {'would be' if not args.apply else 'were'} fixed: {changed:,}")

    if issues_counter:
        print("\n🔎 Tag issues (count):")
        for k in sorted(issues_counter.keys()):
            print(f"   {k}: {issues_counter[k]:,}")

    if args.report:
        out_path = Path(args.report)
        if not out_path.is_absolute():
            out_path = Path.cwd() / out_path
        payload = {
            "lang": lang,
            "audio_dir": str(audio_dir),
            "csv": str(csv_path),
            "csv_column": used_col,
            "apply": bool(args.apply),
            "processed": processed,
            "missing_csv": missing_csv,
            "fixed_text_tags": changed,
            "issues_counter": issues_counter,
            "files": [asdict(r) for r in reports],
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n📄 Wrote report: {out_path}")

    if not args.apply:
        print("\nNext: re-run with --apply to write fixes.")
        print(f"Example:\n  python utilities/fix_audio_text_tags.py --lang {lang} --apply --report fix-report-{lang}.json")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


