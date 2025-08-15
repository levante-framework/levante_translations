#!/usr/bin/env python3
"""
Sync local or remote (GitHub) XLIFF and ICU JSON files to a Google Cloud Storage bucket.

- Ensures the bucket exists (creates if missing)
- Creates two logical prefixes in the bucket: `xliff/` and `json/`
- Local mode (default):
  - Copies all local *.xliff files from repository `xliff/` to `gs://<bucket>/xliff/`
  - Copies all local ICU *.json files from `xliff/translations-icu/` to `gs://<bucket>/json/`
- GitHub mode (--from-github):
  - Lists and downloads XLIFF files from a GitHub repo folder, uploads to `xliff/`
  - Parses each XLIFF to build ICU JSON per language and uploads to `json/`

Usage examples:
  # Local mode
  python xliff/sync_to_gcs.py --project hs-levante-admin-dev --bucket levante-translations-dev

  # GitHub mode (no local XLIFF needed)
  python xliff/sync_to_gcs.py --from-github --repo levante-framework/levante_translations \
    --ref l10n_pending --path translations --project hs-levante-admin-dev --bucket levante-translations-dev

Environment:
  Uses Google ADC. Set GOOGLE_APPLICATION_CREDENTIALS or run `gcloud auth application-default login`.
  Optional: GITHUB_TOKEN to increase GitHub API rate limits in --from-github mode.
"""

import argparse
import json
import mimetypes
import os
import sys
from typing import Dict, List

from google.cloud import storage

# Optional GitHub fetch helpers (import from sibling script to avoid duplication)
try:
	from convert_xliff_to_icu import (
		list_xliff_files as gh_list_xliff_files,
		build_raw_url as gh_build_raw_url,
		fetch_text as gh_fetch_text,
		parse_xliff as gh_parse_xliff,
		sanitize_lang_code,
	)
except Exception:
	gh_list_xliff_files = None
	gh_build_raw_url = None
	gh_fetch_text = None
	gh_parse_xliff = None
	def sanitize_lang_code(code: str) -> str:
		return (code or "").replace("_", "-").strip()

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
DEFAULT_XLIFF_DIR = os.path.join(REPO_ROOT, "xliff")
DEFAULT_JSON_DIR = os.path.join(REPO_ROOT, "xliff", "translations-icu")


def discover_files(directory: str, extensions: List[str]) -> List[str]:
	files: List[str] = []
	for root, _dirs, filenames in os.walk(directory):
		for fname in filenames:
			lower = fname.lower()
			if any(lower.endswith(ext) for ext in extensions):
				files.append(os.path.join(root, fname))
	return files


def ensure_bucket(project_id: str, bucket_name: str, location: str = "US") -> storage.Bucket:
	client = storage.Client(project=project_id)
	bucket = client.lookup_bucket(bucket_name)
	if bucket is None:
		bucket = storage.Bucket(client, name=bucket_name)
		bucket.location = location
		bucket.iam_configuration.uniform_bucket_level_access_enabled = True
		bucket = client.create_bucket(bucket)
		print(f"Created bucket: gs://{bucket_name} (location={bucket.location})")
	else:
		print(f"Using existing bucket: gs://{bucket_name}")
	return bucket


def upload_bytes(bucket: storage.Bucket, data: bytes, dest_blob: str, content_type: str, dry_run: bool = False) -> None:
	print(f"{'[DRY-RUN] ' if dry_run else ''}Uploading bytes -> gs://{bucket.name}/{dest_blob} ({content_type})")
	if dry_run:
		return
	blob = bucket.blob(dest_blob)
	blob.upload_from_string(data, content_type=content_type)


def upload_file(bucket: storage.Bucket, local_path: str, dest_blob: str, dry_run: bool = False) -> None:
	content_type, _ = mimetypes.guess_type(local_path)
	if content_type is None:
		if local_path.lower().endswith(".xliff"):
			content_type = "application/xml"
		elif local_path.lower().endswith(".json"):
			content_type = "application/json"
		else:
			content_type = "application/octet-stream"
	print(f"{'[DRY-RUN] ' if dry_run else ''}Uploading {local_path} -> gs://{bucket.name}/{dest_blob} ({content_type})")
	if dry_run:
		return
	blob = bucket.blob(dest_blob)
	blob.upload_from_filename(local_path, content_type=content_type)


def main() -> int:
	parser = argparse.ArgumentParser(description="Sync XLIFF and ICU JSON to GCS")
	parser.add_argument("--project", default="hs-levante-admin-dev", help="Google Cloud project ID")
	parser.add_argument("--bucket", default="levante-translations-dev", help="Target GCS bucket name")
	parser.add_argument("--location", default="US", help="Bucket location if created")
	parser.add_argument("--from-github", action="store_true", help="Fetch XLIFF from GitHub instead of local files")
	parser.add_argument("--repo", default="levante-framework/levante_translations", help="GitHub repo (owner/name) for --from-github")
	parser.add_argument("--ref", default="l10n_pending", help="Git ref (branch/tag) for --from-github")
	parser.add_argument("--path", default="translations", help="Path within repo to list .xliff files for --from-github")
	parser.add_argument("--xliff-dir", default=DEFAULT_XLIFF_DIR, help="Local directory to find *.xliff files (local mode)")
	parser.add_argument("--json-dir", default=DEFAULT_JSON_DIR, help="Local directory to find ICU *.json files (local mode)")
	parser.add_argument("--dry-run", action="store_true", help="Print actions without uploading")
	args = parser.parse_args()

	bucket = ensure_bucket(args.project, args.bucket, args.location)

	if args.from_github:
		if not (gh_list_xliff_files and gh_build_raw_url and gh_fetch_text and gh_parse_xliff):
			print("GitHub helpers not available (convert_xliff_to_icu import failed)", file=sys.stderr)
			return 1
		import os as _os
		token = _os.environ.get("GITHUB_TOKEN")
		try:
			files = gh_list_xliff_files(args.repo, args.ref, args.path, token)
		except Exception as e:
			print(f"Error listing GitHub XLIFF files: {e}", file=sys.stderr)
			return 1
		if not files:
			print("No .xliff files found in the specified repo path/ref.")
			return 0
		# Build per-language ICU map in memory
		lang_to_strings: Dict[str, Dict[str, str]] = {}
		for fi in files:
			name = fi.get("name")
			download_url = fi.get("download_url") or gh_build_raw_url(args.repo, args.ref, args.path, name)
			try:
				xliff_text = gh_fetch_text(download_url, token)
			except Exception as e:
				print(f"Warning: failed to fetch {name}: {e}", file=sys.stderr)
				continue
			# Upload XLIFF directly
			upload_bytes(bucket, xliff_text.encode("utf-8"), f"xliff/{name}", content_type="application/xml", dry_run=args.dry_run)
			# Parse to ICU strings
			try:
				lang_code, strings = gh_parse_xliff(xliff_text)
			except Exception as e:
				print(f"Warning: failed to parse {name}: {e}", file=sys.stderr)
				continue
			lang_code = sanitize_lang_code(lang_code)
			lang_to_strings.setdefault(lang_code, {}).update(strings)
		# Upload ICU JSONs
		for lang, data in sorted(lang_to_strings.items()):
			payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
			upload_bytes(bucket, payload, f"json/{lang}.json", content_type="application/json", dry_run=args.dry_run)
		print("Done (GitHub mode).")
		return 0

	# Local mode
	if not os.path.isdir(args.xliff_dir):
		print(f"XLIFF directory not found: {args.xliff_dir}", file=sys.stderr)
		return 1
	if not os.path.isdir(args.json_dir):
		print(f"JSON directory not found: {args.json_dir}", file=sys.stderr)
		return 1

	# Discover files
	xliff_files = [p for p in discover_files(args.xliff_dir, [".xliff"]) if os.path.basename(p).lower().endswith(".xliff")]
	json_files = [p for p in discover_files(args.json_dir, [".json"]) if os.path.basename(p).lower().endswith(".json")]

	if not xliff_files:
		print("No .xliff files found to upload.")
	if not json_files:
		print("No .json files found to upload (expected ICU JSONs).")

	# Upload XLIFF into xliff/ prefix (flat)
	for local_path in sorted(xliff_files):
		filename = os.path.basename(local_path)
		dest_blob = f"xliff/{filename}"
		upload_file(bucket, local_path, dest_blob, args.dry_run)

	# Upload JSON into json/ prefix (flat)
	for local_path in sorted(json_files):
		filename = os.path.basename(local_path)
		dest_blob = f"json/{filename}"
		upload_file(bucket, local_path, dest_blob, args.dry_run)

	print("Done (local mode).")
	return 0


if __name__ == "__main__":
	sys.exit(main())
