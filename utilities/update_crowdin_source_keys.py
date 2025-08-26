#!/usr/bin/env python3
"""
Update source string identifiers (keys) in Crowdin directly.

This script allows you to rename source string keys in Crowdin without affecting
existing translations. It's specifically designed to fix navigation terms that
currently show as "unknown" source keys.

Usage:
  python3 utilities/update_crowdin_source_keys.py --dry-run
  python3 utilities/update_crowdin_source_keys.py

Notes:
- Requires CROWDIN_API_TOKEN and CROWDIN_PROJECT_ID environment variables
- Updates source string identifiers while preserving all existing translations
- Designed to fix navigation terms with proper source-based naming
"""

from __future__ import annotations

import os
import sys
import argparse
from typing import Dict, Any, List, Optional

# Prefer requests if available; otherwise, fall back to urllib
try:
    import requests  # type: ignore
except Exception as exc:  # pragma: no cover
    requests = None  # type: ignore

import json
import urllib.request
import urllib.parse

API_BASE = "https://api.crowdin.com/api/v2"

# Navigation key mappings to fix
NAVIGATION_KEY_MAPPINGS = {
    # Parent Survey Family
    "parent_survey_family_337": "navigation.startSurvey",
    "parent_survey_family_338": "navigation.previous", 
    "parent_survey_family_339": "navigation.next",
    "parent_survey_family_340": "navigation.finish",
    
    # Teacher Survey Classroom
    "teacher_survey_classroom_117": "navigation.startSurvey",
    "teacher_survey_classroom_118": "navigation.previous",
    "teacher_survey_classroom_119": "navigation.next", 
    "teacher_survey_classroom_120": "navigation.finish",
    
    # Teacher Survey General
    "teacher_survey_general_141": "navigation.startSurvey",
    "teacher_survey_general_142": "navigation.previous",
    "teacher_survey_general_143": "navigation.next",
    "teacher_survey_general_144": "navigation.finish",
}


def _require_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        print(f"❌ Missing required environment variable: {var_name}")
        print("Set CROWDIN_API_TOKEN and CROWDIN_PROJECT_ID before running.")
        sys.exit(1)
    return value


def _http_get(url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if requests:
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        return resp.json()
    else:
        # Fallback to urllib
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())


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


def resolve_project_id(project_id_or_identifier: str, headers: Dict[str, str]) -> str:
    """Resolve project identifier to numeric ID if needed."""
    if project_id_or_identifier.isdigit():
        return project_id_or_identifier
    
    # Try to find project by identifier
    resp = _http_get(f"{API_BASE}/projects", headers)
    for project in resp.get("data", []):
        project_data = project.get("data", {})
        if project_data.get("identifier") == project_id_or_identifier:
            return str(project_data["id"])
    
    raise ValueError(f"Could not find project with identifier: {project_id_or_identifier}")


def list_strings(project_id: str, headers: Dict[str, str], file_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """List all source strings in the project."""
    strings: List[Dict[str, Any]] = []
    offset = 0
    limit = 500
    params: Dict[str, Any] = {"limit": limit, "offset": offset}
    if file_id is not None:
        params["fileId"] = file_id
    while True:
        params["offset"] = offset
        resp = _http_get(f"{API_BASE}/projects/{project_id}/strings", headers, params=params)
        strings.extend([item["data"] for item in resp.get("data", [])])
        if len(resp.get("data", [])) < limit:
            break
        offset += limit
    return strings


def update_string_identifier(project_id: str, headers: Dict[str, str], string_id: int, new_identifier: str) -> None:
    """Update a source string's identifier (key)."""
    payload = {
        "identifier": new_identifier
    }
    _http_patch(f"{API_BASE}/projects/{project_id}/strings/{string_id}", headers, payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Update source string identifiers in Crowdin")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without making changes")
    args = parser.parse_args()

    api_token = _require_env("CROWDIN_API_TOKEN")
    project_id_env = _require_env("CROWDIN_PROJECT_ID")
    headers = {"Authorization": f"Bearer {api_token}", "Accept": "application/json"}

    project_id = resolve_project_id(project_id_env, headers)
    print(f"📌 Project {project_id}")

    # Get all strings
    print("🔍 Fetching source strings...")
    strings = list_strings(project_id, headers)
    print(f"📋 Found {len(strings)} strings")

    # Find strings that need to be updated
    updates_made = 0
    updates_skipped = 0
    
    for string_data in strings:
        string_id = string_data.get("id")
        current_identifier = string_data.get("identifier", "")
        
        if current_identifier in NAVIGATION_KEY_MAPPINGS:
            new_identifier = NAVIGATION_KEY_MAPPINGS[current_identifier]
            
            print(f"🔄 Updating string {string_id}: '{current_identifier}' → '{new_identifier}'")
            
            if not args.dry_run:
                try:
                    update_string_identifier(project_id, headers, string_id, new_identifier)
                    updates_made += 1
                    print(f"   ✅ Updated successfully")
                except Exception as e:
                    print(f"   ❌ Failed: {e}")
            else:
                print(f"   🏃 (dry-run mode)")
                updates_made += 1
        else:
            updates_skipped += 1

    print(f"\n✅ Done!")
    print(f"   Updated: {updates_made}")
    print(f"   Skipped: {updates_skipped}")
    
    if args.dry_run:
        print("\n💡 Run without --dry-run to apply changes")


if __name__ == "__main__":
    main()

