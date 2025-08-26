#!/usr/bin/env python3
"""
Fix "unknown" navigation keys in Crowdin survey files.

This script updates specific string IDs in Crowdin that currently have "unknown" 
identifiers but contain navigation text (Start Survey, Previous, Next, Finish).

Usage:
  python3 utilities/fix_crowdin_unknown_navigation_keys.py --dry-run
  python3 utilities/fix_crowdin_unknown_navigation_keys.py

Notes:
- Requires CROWDIN_API_TOKEN and CROWDIN_PROJECT_ID environment variables
- Updates specific string IDs to proper navigation.* identifiers
"""

from __future__ import annotations

import os
import sys
import argparse
from typing import Dict, Any

# Prefer requests if available; otherwise, fall back to urllib
try:
    import requests  # type: ignore
except Exception as exc:  # pragma: no cover
    requests = None  # type: ignore

import json
import urllib.request
import urllib.parse

API_BASE = "https://api.crowdin.com/api/v2"

# Specific string IDs and their target identifiers based on our findings
NAVIGATION_UPDATES = {
    # Parent Survey Family (fileId=464)
    # 89482: "navigation.startSurvey",  # "Start Survey" - ALREADY FIXED
    89484: "navigation.previous",     # "Previous" 
    89486: "navigation.next",         # "Next"
    89488: "navigation.finish",       # "Finish"
    
    # Teacher Survey General (fileId=468)
    90010: "navigation.startSurvey",  # "Start Survey"
    90012: "navigation.previous",     # "Previous"
    90014: "navigation.next",         # "Next" 
    90016: "navigation.finish",       # "Finish"
    
    # Teacher Survey Classroom (fileId=470)
    89722: "navigation.startSurvey",  # "Start Survey"
    89724: "navigation.previous",     # "Previous"
    89726: "navigation.next",         # "Next"
    89728: "navigation.finish",       # "Finish"
}


def _require_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        print(f"❌ Missing required environment variable: {var_name}")
        print("Set CROWDIN_API_TOKEN and CROWDIN_PROJECT_ID before running.")
        sys.exit(1)
    return value


def _http_patch(url: str, headers: Dict[str, str], data: Dict[str, Any]) -> Dict[str, Any]:
    headers = {**headers, "Content-Type": "application/json"}
    if requests:
        resp = requests.patch(url, headers=headers, json=data)
        resp.raise_for_status()
        return resp.json()
    else:
        # Fallback to urllib
        req = urllib.request.Request(
            url, 
            data=json.dumps(data).encode(),
            headers=headers,
            method='PATCH'
        )
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())


def update_string_identifier(project_id: str, headers: Dict[str, str], string_id: int, new_identifier: str) -> None:
    """Update a source string's identifier (key)."""
    payload = [
        {
            "op": "replace",
            "path": "/identifier", 
            "value": new_identifier
        }
    ]
    _http_patch(f"{API_BASE}/projects/{project_id}/strings/{string_id}", headers, payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fix unknown navigation keys in Crowdin survey files")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without making changes")
    args = parser.parse_args()

    api_token = _require_env("CROWDIN_API_TOKEN")
    project_id = _require_env("CROWDIN_PROJECT_ID")
    headers = {"Authorization": f"Bearer {api_token}", "Accept": "application/json"}

    print(f"📌 Project {project_id}")
    print(f"🎯 Fixing {len(NAVIGATION_UPDATES)} navigation keys with 'unknown' identifiers")

    updates_made = 0
    errors = 0
    
    for string_id, new_identifier in NAVIGATION_UPDATES.items():
        print(f"🔄 Updating string {string_id}: 'unknown' → '{new_identifier}'")
        
        if not args.dry_run:
            try:
                update_string_identifier(project_id, headers, string_id, new_identifier)
                updates_made += 1
                print(f"   ✅ Updated successfully")
            except Exception as e:
                print(f"   ❌ Failed: {e}")
                errors += 1
        else:
            print(f"   🏃 (dry-run mode)")
            updates_made += 1

    print(f"\n✅ Done!")
    print(f"   Updated: {updates_made}")
    print(f"   Errors: {errors}")
    
    if args.dry_run:
        print("\n💡 Run without --dry-run to apply changes")
    else:
        print("\n🎉 Navigation keys fixed! Survey files now have proper source-based identifiers.")


if __name__ == "__main__":
    main()
