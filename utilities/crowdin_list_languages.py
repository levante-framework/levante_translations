#!/usr/bin/env python3
"""
List Crowdin project target languages (and source language).

Usage:
  python3 utilities/crowdin_list_languages.py --project levantetranslations
  python3 utilities/crowdin_list_languages.py --project 756721

Token is read from CROWDIN_API_TOKEN or ~/.crowdin_api_token.
"""

import argparse
import json
import os
from pathlib import Path
import sys
import requests


API_BASE = os.environ.get("CROWDIN_API_BASE", "https://api.crowdin.com/api/v2").rstrip("/")


def get_token() -> str:
    t = os.environ.get("CROWDIN_API_TOKEN")
    if t:
        return t.strip()
    p = Path.home() / ".crowdin_api_token"
    if p.exists():
        return p.read_text().strip()
    print("ERROR: Missing CROWDIN_API_TOKEN (env) or ~/.crowdin_api_token file", file=sys.stderr)
    sys.exit(2)


def resolve_project_id(identifier_or_id: str, headers: dict) -> str:
    if identifier_or_id.isdigit():
        return identifier_or_id
    resp = requests.get(f"{API_BASE}/projects", headers=headers, timeout=30)
    resp.raise_for_status()
    for it in resp.json().get("data", []):
        data = it.get("data", {})
        if data.get("identifier") == identifier_or_id or data.get("name") == identifier_or_id:
            return str(data.get("id"))
    print(f"ERROR: Could not resolve project by identifier/name: {identifier_or_id}")
    sys.exit(3)


def main() -> int:
    ap = argparse.ArgumentParser(description="Crowdin: list project languages")
    ap.add_argument("--project", required=True, help="Project id or identifier (e.g., levantetranslations)")
    args = ap.parse_args()

    token = get_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    project_id = resolve_project_id(args.project, headers)
    proj = requests.get(f"{API_BASE}/projects/{project_id}", headers=headers, timeout=30)
    proj.raise_for_status()
    pdata = proj.json().get("data", {})
    source_lang = pdata.get("sourceLanguageId")
    # Some APIs expose target languages inline on the project object
    langs = pdata.get("targetLanguages") or pdata.get("targetLanguageIds") or []
    # Normalize shapes
    norm_langs = []
    if isinstance(langs, list):
        for l in langs:
            if isinstance(l, dict):
                norm_langs.append({"id": l.get("id"), "name": l.get("name")})
            else:
                norm_langs.append({"id": l, "name": None})
    else:
        norm_langs = []

    print(json.dumps({
        "project_id": project_id,
        "source_language": source_lang,
        "target_languages": norm_langs,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())


