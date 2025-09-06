#!/usr/bin/env python3
"""
Mirror item bank translations from an existing Crowdin project to a new one using XLIFF.

Steps:
- Download current translations from OLD project as XLIFF
- Import those XLIFFs into NEW project file /item-bank-translations.xlsx

Usage:
  python3 utilities/crowdin_mirror_itembank.py --old OLD_PROJECT --new NEW_PROJECT \
    --out xliff-mirror

Notes:
- Requires CROWDIN_API_TOKEN env var (or ~/.crowdin_api_token)
"""

import argparse
import os
import sys
from pathlib import Path

from crowdin_xliff_manager import (
    get_crowdin_token,
    list_project_files,
    list_project_languages,
    make_request,
    download_xliff_translations,
    import_translations_directory,
    find_file_by_path,
    import_translations_for_file,
)
from xml.dom import minidom
import xml.etree.ElementTree as ET
from csv_to_xliff_converter import create_xliff_structure, add_trans_unit


def resolve_project_id(identifier_or_id: str, headers: dict) -> str:
    if identifier_or_id.isdigit():
        return identifier_or_id
    resp = make_request("GET", "https://api.crowdin.com/api/v2/projects", headers)
    for item in resp.json().get("data", []):
        data = item.get("data", {})
        if data.get("identifier") == identifier_or_id or data.get("name") == identifier_or_id:
            return str(data["id"])
    raise ValueError(f"Could not resolve project: {identifier_or_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Mirror item bank translations between Crowdin projects")
    parser.add_argument("--old", required=True, help="Old/source Crowdin project id or identifier")
    parser.add_argument("--new", required=True, help="New/destination Crowdin project id or identifier")
    parser.add_argument("--out", default="xliff-mirror", help="Output directory for downloaded XLIFFs")
    args = parser.parse_args()

    token = get_crowdin_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    old_id = resolve_project_id(args.old, headers)
    new_id = resolve_project_id(args.new, headers)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Determine source language and file id in old project
    proj_resp = make_request("GET", f"https://api.crowdin.com/api/v2/projects/{old_id}", headers)
    proj = proj_resp.json().get("data", {})
    source_lang = proj.get("sourceLanguageId", "en")
    file_info = find_file_by_path(old_id, headers, "/item-bank-translations.xlsx")
    if not file_info:
        print("❌ Could not find /item-bank-translations.xlsx in old project")
        return 1
    file_id = file_info["id"]

    # Fetch all strings for that file
    print(f"📋 Fetching strings from old project fileId={file_id} ...")
    strings = []
    offset = 0
    limit = 500
    while True:
        params = {"limit": limit, "offset": offset, "fileId": file_id}
        s_resp = make_request("GET", f"https://api.crowdin.com/api/v2/projects/{old_id}/strings", headers, params=params)
        batch = [it["data"] for it in s_resp.json().get("data", [])]
        strings.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    print(f"   Found {len(strings)} strings")

    # Prepare language list to mirror
    mirror_langs = ["de","de-CH","en","en-GH","es-AR","es-CO","fr-CA","nl"]

    # Build XLIFF per language from strings API
    xliff_paths = []
    for lang in mirror_langs:
        print(f"🛠️  Building XLIFF for {lang} ...")
        xliff_root, body = create_xliff_structure(source_lang=source_lang, target_lang=lang, original="/item-bank-translations.xlsx")

        # Fetch translations for this language using per-string requests
        translations_map = {}
        for s in strings:
            sid = s.get("id")
            t_resp = make_request(
                "GET",
                f"https://api.crowdin.com/api/v2/projects/{old_id}/translations",
                headers,
                params={"languageId": lang, "stringId": sid, "limit": 1},
            )
            items = [it["data"] for it in t_resp.json().get("data", [])]
            if items:
                translations_map[str(sid)] = items[0].get("text") or ""

        # Add units
        for s in strings:
            identifier = s.get("identifier") or s.get("text", "")[:64]
            source_text = s.get("text", "")
            target_text = translations_map.get(str(s.get("id")), "")
            add_trans_unit(body, identifier, source_text, target_text, lang, context=None, task=None)

        # Write file
        out_path = out_dir / f"itembank-{lang}.xliff"
        rough_string = ET.tostring(xliff_root, encoding='utf-8', xml_declaration=True)
        reparsed = minidom.parseString(rough_string)
        pretty_xml = reparsed.toprettyxml(indent="  ", encoding=None)
        pretty_lines = [line for line in pretty_xml.split('\n') if line.strip()]
        if pretty_lines and pretty_lines[0].startswith('<?xml'):
            pretty_lines[0] = '<?xml version="1.0" encoding="UTF-8"?>'
        out_path.write_text('\n'.join(pretty_lines), encoding='utf-8')
        xliff_paths.append((lang, str(out_path)))

    # Import into new project
    print(f"📤 Importing into new project {new_id} ...")
    results = {}
    for lang, path in xliff_paths:
        ok = import_translations_for_file(new_id, headers, crowdin_file_path="/item-bank-translations.xlsx", local_xliff_path=path, target_language_id=lang)
        results[lang] = ok
    ok_count = sum(1 for v in results.values() if v)
    print(f"✅ Imported languages: {ok_count}/{len(results)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())


