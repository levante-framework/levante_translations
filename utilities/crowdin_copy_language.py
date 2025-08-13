#!/usr/bin/env python3
"""
Copy source (English) strings to a regional variant (e.g., en-GH) in Crowdin.

- Reads CROWDIN_API_TOKEN and CROWDIN_PROJECT_ID from environment variables
- Iterates strings (optionally only from item_bank_translations file)
- If target translation is missing/empty, creates it with the source text
- Supports dry-run and resumable, paginated processing

Usage examples:
  python3 utilities/crowdin_copy_language.py --target en-GH
  python3 utilities/crowdin_copy_language.py --target en-GH --only-item-bank
  python3 utilities/crowdin_copy_language.py --target en-GH --dry-run

Notes:
- Assumes project base language is English (en). If not, you can explicitly
  set --source en to enforce copying from the English source language.
"""

from __future__ import annotations

import os
import sys
import time
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


def _require_env(var_name: str) -> str:
	value = os.getenv(var_name)
	if not value:
		print(f"❌ Missing required environment variable: {var_name}")
		print("Set CROWDIN_API_TOKEN and CROWDIN_PROJECT_ID before running.")
		sys.exit(1)
	return value


def resolve_project_id(project_id_or_identifier: str, headers: Dict[str, str]) -> str:
	"""Return a numeric project id. If a non-numeric identifier/name is provided, search projects."""
	if project_id_or_identifier.isdigit():
		return project_id_or_identifier
	# Try direct fetch first (in case API accepts slug)
	try:
		_ = _http_get(f"{API_BASE}/projects/{project_id_or_identifier}", headers)
		return project_id_or_identifier
	except Exception:
		pass
	# Fallback: list projects and search by identifier or name
	offset = 0
	limit = 500
	while True:
		resp = _http_get(f"{API_BASE}/projects", headers, params={"limit": limit, "offset": offset})
		items = [item.get("data", {}) for item in resp.get("data", [])]
		for p in items:
			pid = str(p.get("id"))
			identifier = p.get("identifier") or ""
			name = p.get("name") or ""
			if project_id_or_identifier == identifier or project_id_or_identifier == name:
				return pid
		if len(items) < limit:
			break
		offset += limit
	raise SystemExit(
		f"❌ Could not resolve CROWDIN_PROJECT_ID '{project_id_or_identifier}'. Provide numeric id, or exact identifier/name."
	)


def _http_get(url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
	if requests:
		resp = requests.get(url, headers=headers, params=params, timeout=60)
		resp.raise_for_status()
		return resp.json()
	else:  # urllib fallback
		if params:
			url = f"{url}?{urllib.parse.urlencode(params)}"
		req = urllib.request.Request(url, headers=headers)
		with urllib.request.urlopen(req, timeout=60) as r:  # nosec B310
			return json.loads(r.read().decode("utf-8"))


def _http_post(url: str, headers: Dict[str, str], data: Dict[str, Any]) -> Dict[str, Any]:
	if requests:
		resp = requests.post(url, headers={**headers, "Content-Type": "application/json"}, json=data, timeout=60)
		resp.raise_for_status()
		return resp.json()
	else:
		payload = json.dumps(data).encode("utf-8")
		req = urllib.request.Request(url, data=payload, headers={**headers, "Content-Type": "application/json"}, method="POST")
		with urllib.request.urlopen(req, timeout=60) as r:  # nosec B310
			return json.loads(r.read().decode("utf-8"))


def get_project(project_id: str, headers: Dict[str, str]) -> Dict[str, Any]:
	return _http_get(f"{API_BASE}/projects/{project_id}", headers)


def list_files(project_id: str, headers: Dict[str, str]) -> List[Dict[str, Any]]:
	files: List[Dict[str, Any]] = []
	offset = 0
	limit = 500
	while True:
		resp = _http_get(f"{API_BASE}/projects/{project_id}/files", headers, params={"limit": limit, "offset": offset})
		files.extend([item["data"] for item in resp.get("data", [])])
		if len(resp.get("data", [])) < limit:
			break
		offset += limit
	return files


def find_item_bank_file_id(project_id: str, headers: Dict[str, str]) -> Optional[int]:
	candidates = {"item_bank_translations.csv", "item-bank-translations.csv"}
	for f in list_files(project_id, headers):
		name = f.get("name", "")
		if name in candidates or any(k in name for k in ["item_bank_translations", "item-bank-translations"]):
			return f.get("id")
	return None


def list_strings(project_id: str, headers: Dict[str, str], file_id: Optional[int] = None) -> List[Dict[str, Any]]:
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


def get_translation(project_id: str, headers: Dict[str, str], string_id: int, language_id: str) -> Optional[str]:
	resp = _http_get(
		f"{API_BASE}/projects/{project_id}/translations",
		headers,
		params={"stringId": string_id, "languageId": language_id, "limit": 1, "offset": 0},
	)
	data = resp.get("data", [])
	if not data:
		return None
	# Crowdin returns list of translations; pick the latest entry text
	return (data[0].get("data", {}) or {}).get("text")


def create_or_update_translation(project_id: str, headers: Dict[str, str], string_id: int, language_id: str, text: str) -> None:
	payload = {
		"stringId": string_id,
		"languageId": language_id,
		"text": text,
		# "pluralForm": None,
		# "labelIds": [],
		# "isApproved": False,
	}
	_http_post(f"{API_BASE}/projects/{project_id}/translations", headers, payload)


def main() -> None:
	parser = argparse.ArgumentParser(description="Copy source (English) strings to a target locale in Crowdin")
	parser.add_argument("--target", required=True, help="Target Crowdin language ID, e.g., en-GH")
	parser.add_argument("--source", default=None, help="Source language ID (defaults to project base language)")
	parser.add_argument("--only-item-bank", action="store_true", help="Limit to item_bank_translations file only")
	parser.add_argument("--dry-run", action="store_true", help="Show actions without writing changes")
	parser.add_argument("--sleep", type=float, default=0.0, help="Optional sleep in seconds between API calls to avoid rate limits")
	args = parser.parse_args()

	api_token = _require_env("CROWDIN_API_TOKEN")
	project_id_env = _require_env("CROWDIN_PROJECT_ID")
	headers = {"Authorization": f"Bearer {api_token}", "Accept": "application/json"}

	project_id = resolve_project_id(project_id_env, headers)

	proj = get_project(project_id, headers)
	# Prefer sourceLanguageId for project base/source language
	base_lang = proj.get("data", {}).get("sourceLanguageId") or proj.get("data", {}).get("targetLanguageId") or "en"
	source_lang = args.source or base_lang
	print(f"📌 Project {project_id} | base={base_lang} | copying source={source_lang} -> target={args.target}")

	file_id: Optional[int] = None
	if args.only_item_bank:
		file_id = find_item_bank_file_id(project_id, headers)
		if file_id:
			print(f"🗂️  Limiting to fileId={file_id} (item_bank_translations)")
		else:
			print("⚠️ Could not locate item_bank_translations file; processing all strings")

	strings = list_strings(project_id, headers, file_id=file_id)
	print(f"🧾 Found {len(strings)} strings to process")

	successful = 0
	skipped = 0
	errors = 0
	for s in strings:
		string_id = s.get("id")
		if string_id is None:
			continue
		# In Crowdin, the English source is usually the string's "text"
		source_text = s.get("text", "")
		if not source_text:
			# Some projects store sources in fields per language; skip if empty
			skipped += 1
			continue

		# Skip if translation already exists and is non-empty
		try:
			existing = get_translation(project_id, headers, string_id, args.target)
		except Exception as e:  # pragma: no cover
			print(f"❗ Error checking translation for string {string_id}: {e}")
			errors += 1
			continue

		if existing and existing.strip():
			# Already translated; do not overwrite
			skipped += 1
			continue

		print(f"➕ Copying stringId={string_id} → {args.target}")
		if not args.dry_run:
			try:
				create_or_update_translation(project_id, headers, string_id, args.target, source_text)
				successful += 1
			except Exception as e:  # pragma: no cover
				print(f"❌ Failed to create translation for string {string_id}: {e}")
				errors += 1
		if args.sleep > 0:
			time.sleep(args.sleep)

	print("\n✅ Done")
	print(f"   Created: {successful}")
	print(f"   Skipped (already translated or no source): {skipped}")
	print(f"   Errors: {errors}")


if __name__ == "__main__":
	main()
