#!/usr/bin/env python3
"""
Mirror survey files from an existing Crowdin project to a new one using XLIFF.

For each survey-like file in the OLD project:
- Build a source-only XLIFF from its strings
- Create/update the file in the NEW project under /surveys/<basename>.xliff
- Build bilingual XLIFF per enabled language and import into the NEW project

Usage:
  python3 utilities/crowdin_mirror_surveys.py \
    --old 756721 --new 825428 --pattern survey --out xliff-mirror-surveys
"""

import argparse
import os
from pathlib import Path
from typing import List
from xml.dom import minidom
import xml.etree.ElementTree as ET

from crowdin_xliff_manager import (
    get_crowdin_token,
    make_request,
    list_project_files,
    list_project_languages,
    upload_xliff_file,
    import_translations_for_file,
)
from csv_to_xliff_converter import create_xliff_structure, add_trans_unit


def fetch_all_strings(project_id: str, headers: dict, *, file_id: int) -> List[dict]:
    strings = []
    offset = 0
    limit = 500
    while True:
        params = {"limit": limit, "offset": offset, "fileId": file_id}
        resp = make_request("GET", f"https://api.crowdin.com/api/v2/projects/{project_id}/strings", headers, params=params)
        batch = [it["data"] for it in resp.json().get("data", [])]
        strings.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return strings


def fetch_translation_text(project_id: str, headers: dict, *, language_id: str, string_id: int) -> str:
    resp = make_request(
        "GET",
        f"https://api.crowdin.com/api/v2/projects/{project_id}/translations",
        headers,
        params={"languageId": language_id, "stringId": string_id, "limit": 1},
    )
    items = [it["data"] for it in resp.json().get("data", [])]
    return (items[0].get("text") if items else "") or ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Mirror survey files from one Crowdin project to another")
    parser.add_argument("--old", required=True, help="Old/source Crowdin project id or identifier")
    parser.add_argument("--new", required=True, help="New/destination Crowdin project id or identifier")
    parser.add_argument("--pattern", default="survey", help="Substring to match files (default: survey)")
    parser.add_argument("--out", default="xliff-mirror-surveys", help="Output directory for generated XLIFFs")
    args = parser.parse_args()

    token = get_crowdin_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Resolve numeric ids if identifiers were provided
    def resolve(project: str) -> str:
        if project.isdigit():
            return project
        resp = make_request("GET", "https://api.crowdin.com/api/v2/projects", headers)
        for it in resp.json().get("data", []):
            d = it.get("data", {})
            if d.get("identifier") == project or d.get("name") == project:
                return str(d["id"])
        raise ValueError(f"Could not resolve project: {project}")

    old_id = resolve(args.old)
    new_id = resolve(args.new)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Source language from old project
    proj_resp = make_request("GET", f"https://api.crowdin.com/api/v2/projects/{old_id}", headers)
    source_lang = proj_resp.json().get("data", {}).get("sourceLanguageId", "en")

    # Enabled languages in new project
    try:
        langs_resp = list_project_languages(new_id, headers)
        enabled_langs = {row["data"]["id"] for row in langs_resp}
    except Exception:
        enabled_langs = set()

    # Find survey-like files in old project
    files = list_project_files(old_id, headers)
    survey_files = []
    for row in files:
        d = row.get("data", {})
        name = d.get("name", "")
        path = d.get("path", "")
        if args.pattern.lower() in name.lower() or args.pattern.lower() in path.lower():
            survey_files.append(d)

    if not survey_files:
        print("No survey files found.")
        return 0

    print(f"Found {len(survey_files)} survey files to mirror.")

    # Languages we will attempt (skip 'en' if present; Crowdin will reject if it's source-only)
    candidate_langs = ["de","de-CH","en-GH","es-AR","es-CO","fr-CA","nl"]
    if enabled_langs:
        candidate_langs = [l for l in candidate_langs if l in enabled_langs]

    for f in survey_files:
        file_id = f["id"]
        name = f.get("name") or "survey"
        base = os.path.splitext(name)[0]
        # Build source-only XLIFF from strings
        strings = fetch_all_strings(old_id, headers, file_id=file_id)
        if not strings:
            print(f"Skipping {name}: no strings")
            continue

        xliff_root, body = create_xliff_structure(source_lang=source_lang, target_lang=None, original=f"/surveys/{base}.xliff")
        for s in strings:
            identifier = s.get("identifier") or s.get("text", "")[:64]
            source_text = s.get("text", "")
            add_trans_unit(body, identifier, source_text, target_text='', target_lang=source_lang)

        src_path = out_dir / f"{base}-source-{source_lang}.xliff"
        rough = ET.tostring(xliff_root, encoding='utf-8', xml_declaration=True)
        pretty = minidom.parseString(rough).toprettyxml(indent="  ", encoding=None)
        lines = [ln for ln in pretty.split('\n') if ln.strip()]
        if lines and lines[0].startswith('<?xml'):
            lines[0] = '<?xml version="1.0" encoding="UTF-8"?>'
        src_path.write_text('\n'.join(lines), encoding='utf-8')

        # Create or update file in NEW project under /surveys/<base>.xliff
        target_crowdin_path = f"/surveys/{base}.xliff"
        upload_xliff_file(new_id, headers, str(src_path), target_crowdin_path, update_existing=True)

        # Build and import translations for each language
        for lang in candidate_langs:
            xliff_root_t, body_t = create_xliff_structure(source_lang=source_lang, target_lang=lang, original=target_crowdin_path)
            for s in strings:
                sid = s.get("id")
                identifier = s.get("identifier") or s.get("text", "")[:64]
                source_text = s.get("text", "")
                target_text = fetch_translation_text(old_id, headers, language_id=lang, string_id=sid)
                add_trans_unit(body_t, identifier, source_text, target_text, target_lang=lang)

            t_path = out_dir / f"{base}-{lang}.xliff"
            rough_t = ET.tostring(xliff_root_t, encoding='utf-8', xml_declaration=True)
            pretty_t = minidom.parseString(rough_t).toprettyxml(indent="  ", encoding=None)
            lines_t = [ln for ln in pretty_t.split('\n') if ln.strip()]
            if lines_t and lines_t[0].startswith('<?xml'):
                lines_t[0] = '<?xml version="1.0" encoding="UTF-8"?>'
            t_path.write_text('\n'.join(lines_t), encoding='utf-8')

            try:
                import_translations_for_file(new_id, headers, crowdin_file_path=target_crowdin_path, local_xliff_path=str(t_path), target_language_id=lang)
                print(f"✅ Imported {lang} for {target_crowdin_path}")
            except Exception as e:
                print(f"❌ Failed import {lang} for {target_crowdin_path}: {e}")

    print("\n✅ Survey mirroring complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


