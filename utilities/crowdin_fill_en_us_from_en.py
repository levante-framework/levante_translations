#!/usr/bin/env python3
"""
Fill en-US in Crowdin from English source text WITHOUT overwriting existing en-US translations.

Strategy:
- For each file in the Crowdin project, list its strings
- For each string, check if an en-US translation exists
- If missing, include the string in an XLIFF (target=en-US) with target = source text
- Import that XLIFF for en-US for that file (only missing entries are included)

Requirements:
- CROWDIN_API_TOKEN must be set (or ~/.crowdin_api_token file)

Usage:
  python utilities/crowdin_fill_en_us_from_en.py --project <project_id_or_identifier> [--dry-run]

Notes:
- Uses existing helpers from crowdin_xliff_manager and csv_to_xliff_converter
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List
import json

from crowdin_xliff_manager import (
    get_crowdin_token,
    make_request,
    list_project_files,
    find_file_by_path,
    import_translations_for_file,
)
from csv_to_xliff_converter import create_xliff_structure, escape_xml_text, determine_translation_state
from xml.dom import minidom
import xml.etree.ElementTree as ET


API_BASE = os.environ.get("CROWDIN_API_BASE", "https://api.crowdin.com/api/v2").rstrip("/")


def resolve_project_id(identifier_or_id: str, headers: Dict[str, str]) -> str:
    if identifier_or_id.isdigit():
        return identifier_or_id
    resp = make_request("GET", f"{API_BASE}/projects", headers)
    for item in resp.json().get("data", []):
        data = item.get("data", {})
        if data.get("identifier") == identifier_or_id or data.get("name") == identifier_or_id:
            return str(data["id"])
    raise ValueError(f"Could not resolve project: {identifier_or_id}")


def get_project_source_language(project_id: str, headers: Dict[str, str]) -> str:
    resp = make_request("GET", f"{API_BASE}/projects/{project_id}", headers)
    data = resp.json().get("data", {})
    return data.get("sourceLanguageId", "en")


def list_strings_for_file(project_id: str, headers: Dict[str, str], file_id: str) -> List[Dict]:
    strings: List[Dict] = []
    offset = 0
    limit = 500
    while True:
        params = {"limit": limit, "offset": offset, "fileId": file_id}
        resp = make_request("GET", f"{API_BASE}/projects/{project_id}/strings", headers, params=params)
        batch = [it["data"] for it in resp.json().get("data", [])]
        strings.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return strings


def list_translated_string_ids(project_id: str, headers: Dict[str, str], *, strings: List[Dict], language_id: str, progress_cb=None) -> set:
    """List stringIds that have translations for the language by querying per-string (reliable v2 path).

    Emits heartbeat progress every 100 strings (or when provided by progress_cb).
    """
    translated_ids: set[int] = set()
    total = len(strings)
    processed = 0
    for s in strings:
        sid = s.get("id")
        if sid is None:
            continue
        try:
            params = {"languageId": language_id, "stringId": sid, "limit": 1}
            resp = make_request("GET", f"{API_BASE}/projects/{project_id}/translations", headers, params=params)
            items = [it.get("data", {}) for it in resp.json().get("data", [])]
            if items:
                txt = (items[0].get("text") or "").strip()
                if txt:
                    translated_ids.add(int(sid))
        except Exception:
            # If this check fails for a string, treat as missing so we still include it (safer than skipping)
            pass
        processed += 1
        if progress_cb and processed % 100 == 0:
            progress_cb({"event": "heartbeat", "stage": "check_translations", "processed": processed, "total": total})
    return translated_ids
def add_trans_unit_with_resname(body: ET.Element, unit_id: str, unit_resname: str, source_text: str,
                                target_text: str, target_lang: str, context: str = None, task: str = None) -> None:
    """Add a trans-unit allowing separate id (numeric stringId) and resname (human identifier)."""
    trans_unit = ET.SubElement(body, "trans-unit")
    trans_unit.set("id", unit_id)
    trans_unit.set("resname", unit_resname)
    state = determine_translation_state(source_text, target_text, target_lang)
    trans_unit.set("approved", "yes")

    source = ET.SubElement(trans_unit, "source")
    source.text = escape_xml_text(source_text)

    if target_text and target_text.strip():
        target = ET.SubElement(trans_unit, "target")
        target.text = escape_xml_text(target_text)
        target.set("state", state)

    if context or task:
        note = ET.SubElement(trans_unit, "note")
        note.set("from", "developer")
        parts = []
        if task:
            parts.append(f"Task: {task}")
        if context:
            parts.append(f"Context: {context}")
        note.text = " | ".join(parts)



def build_missing_xliff_for_file(project_id: str, headers: Dict[str, str], *, file_path: str, file_id: str,
                                 source_lang: str, target_lang: str, progress_cb=None) -> tuple[Path, List[Dict], set]:
    """Build an XLIFF for strings missing target translations.

    Returns: (xliff_path, strings_list, translated_ids_set)
    """
    strings = list_strings_for_file(project_id, headers, file_id)
    if progress_cb:
        progress_cb({
            "event": "strings_listed",
            "file": file_path,
            "fileId": file_id,
            "count": len(strings)
        })
    xliff_root, body = create_xliff_structure(source_lang=source_lang, target_lang=target_lang, original=file_path)
    # Bulk fetch translated ids to avoid N API calls
    # Query per-string to avoid unsupported filters
    def hb(ev: Dict):
        # Print a concise heartbeat and log to progress file if provided via progress_cb upstream
        msg = ev.copy()
        msg.update({"file": file_path})
        if progress_cb:
            progress_cb(msg)
        # Console heartbeat
        if ev.get("event") == "heartbeat":
            print(f"   ⏳ Checking existing en-US: {ev.get('processed')}/{ev.get('total')}...", flush=True)

    translated_ids = list_translated_string_ids(project_id, headers, strings=strings, language_id=target_lang, progress_cb=hb)

    added = 0
    for s in strings:
        sid = s.get("id")
        source_text = s.get("text", "")
        if not source_text:
            continue
        # Skip if en-US already exists
        if int(sid) in translated_ids:
            continue
        # Use numeric stringId for id, and human identifier for resname (fallback to id)
        unit_id = str(sid)
        unit_resname = s.get("identifier") or unit_id
        # Target equals source (copy)
        add_trans_unit_with_resname(body, unit_id, unit_resname, source_text, source_text, target_lang, context=s.get("identifier"), task=None)
        added += 1

    out_dir = Path("xliff-temp-fill-en-us")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (Path(file_path).name.replace('.xlsx', '').strip('/').replace('/', '_') + f"-missing-{target_lang}.xliff")

    if added == 0:
        # Write an empty but valid XLIFF to signal no work (import will be skipped by caller)
        rough_string = ET.tostring(xliff_root, encoding='utf-8', xml_declaration=True)
    else:
        rough_string = ET.tostring(xliff_root, encoding='utf-8', xml_declaration=True)
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent="  ", encoding=None)
    pretty_lines = [line for line in pretty_xml.split('\n') if line.strip()]
    if pretty_lines and pretty_lines[0].startswith('<?xml'):
        pretty_lines[0] = '<?xml version="1.0" encoding="UTF-8"?>'
    out_path.write_text('\n'.join(pretty_lines), encoding='utf-8')
    # If nothing added, caller will decide to skip import
    return out_path, strings, translated_ids


def main() -> int:
    parser = argparse.ArgumentParser(description="Fill en-US from English source in Crowdin without overwriting existing en-US translations")
    parser.add_argument("--project", required=True, help="Crowdin project ID or identifier")
    parser.add_argument("--dry-run", action="store_true", help="Build XLIFFs but do not import into Crowdin")
    parser.add_argument("--limit-files", type=int, default=0, help="Limit number of files processed (for testing)")
    parser.add_argument("--progress-log", default="xliff-temp-fill-en-us/progress.jsonl", help="Path to JSONL progress log")
    parser.add_argument("--only-file", help="Process only files whose Crowdin path ends with this value (e.g., glossary.csv)")
    parser.add_argument("--mode", choices=["api","xliff"], default="api", help="Import mode: direct API or XLIFF upload (default: api)")
    args = parser.parse_args()

    token = get_crowdin_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    project_id = resolve_project_id(args.project, headers)
    source_lang = get_project_source_language(project_id, headers)
    target_lang = "en-US"

    files = list_project_files(project_id, headers)
    if not files:
        print("No files in project")
        return 0

    print(f"Project {project_id}: source={source_lang}, target={target_lang}, files={len(files)}", flush=True)

    # Verify target languages via project object (avoid languages endpoint inconsistencies)
    enabled_langs = set()
    try:
        proj_resp = make_request("GET", f"{API_BASE}/projects/{project_id}", headers)
        pdata = proj_resp.json().get("data", {})
        tlangs = pdata.get("targetLanguages") or pdata.get("targetLanguageIds") or []
        if isinstance(tlangs, list):
            for l in tlangs:
                enabled_langs.add(l.get("id") if isinstance(l, dict) else l)
    except Exception:
        pass
    if enabled_langs and target_lang not in enabled_langs:
        print(f"➡️  '{target_lang}' not listed as target on project, proceeding anyway (will skip imports that fail).", flush=True)

    # Progress logger
    prog_path = Path(args.progress_log)
    prog_path.parent.mkdir(parents=True, exist_ok=True)
    def log_event(obj: Dict):
        try:
            with prog_path.open('a', encoding='utf-8') as f:
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        except Exception:
            pass

    total_created = 0
    total_skipped = 0
    processed = 0
    for f in files:
        info = f.get("data", {})
        file_path = info.get("path")
        file_id = info.get("id")
        if not file_path or not file_id:
            continue
        if args.only_file and not str(file_path).endswith(args.only_file):
            continue
        processed += 1
        if args.limit_files and processed > args.limit_files:
            break
        print(f"\n🔎 Processing file: {file_path}", flush=True)
        log_event({"event": "file_start", "file": file_path, "fileId": file_id})
        xliff_path, strings, translated_ids = build_missing_xliff_for_file(
            project_id,
            headers,
            file_path=file_path,
            file_id=file_id,
            source_lang=source_lang,
            target_lang=target_lang,
            progress_cb=log_event,
        )
        # Detect whether the XLIFF contains any trans-units beyond header
        content = xliff_path.read_text(encoding='utf-8')
        has_units = '<trans-unit' in content
        if not has_units:
            print("   ✅ en-US already complete (no missing entries)", flush=True)
            log_event({"event": "file_complete", "file": file_path, "missing": 0})
            total_skipped += 1
            continue
        missing_count = len([s for s in strings if s.get('id') is not None and int(s.get('id')) not in translated_ids])
        print(f"   📝 Missing count: {missing_count}", flush=True)
        if args.dry_run:
            total_created += 1
            log_event({"event": "file_ready", "file": file_path, "missing_count": missing_count, "import": False})
            continue
        if args.mode == "api":
            # Directly create translations via API, one per missing string
            created = 0
            for s in strings:
                sid = s.get("id")
                if sid is None or int(sid) in translated_ids:
                    continue
                text = s.get("text", "")
                if not text:
                    continue
                payload = {"stringId": sid, "languageId": target_lang, "text": text}
                try:
                    resp = make_request("POST", f"{API_BASE}/projects/{project_id}/translations", headers, json=payload)
                    if resp.ok:
                        created += 1
                except Exception:
                    pass
            print(f"   ✅ Created {created} translations via API", flush=True)
            log_event({"event": "file_imported_api", "file": file_path, "created": created})
            total_created += 1
        else:
            # Fallback to XLIFF import
            ok = import_translations_for_file(project_id, headers, crowdin_file_path=file_path, local_xliff_path=str(xliff_path), target_language_id=target_lang)
            if ok:
                print("   ✅ Imported missing en-US translations (XLIFF)", flush=True)
                log_event({"event": "file_imported", "file": file_path, "xliff": str(xliff_path)})
                total_created += 1
            else:
                print("   ❌ Import failed", flush=True)
                log_event({"event": "file_failed", "file": file_path})

    print(f"\nSummary: created_or_imported={total_created}, up_to_date={total_skipped}", flush=True)
    log_event({"event": "summary", "created_or_imported": total_created, "up_to_date": total_skipped})
    return 0


if __name__ == "__main__":
    sys.exit(main())


