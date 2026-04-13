"""
Build per-task, per-language flat JSON maps from Crowdin (approved translations only).

Unless ``--languages`` lists explicit locale codes, reads locale keys from
``languageoptions.json`` on the dev assets bucket. Maps them to
Crowdin language ids (``de-DE`` → ``de`` is the only special case), pulls strings from
item-bank files using ``change_check.utils.build_task_file_map``, and writes
``item-bank-translations.json`` for each (task, language) pair under ``gs://levante-assets-dev/``
by default (override with ``--output-bucket``).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from crowdin_api import CrowdinClient

from change_check import config, utils

# Allowed CLI names; Airtable ``taskManual`` is matched case-insensitively if needed (e.g. trog ↔ TROG).
ITEMBANK_TASK_NAMES = (
	"general",
	"hearts-and-flowers",
	"hostile-attribution",
	"math",
	"memory-game",
	"matrix-reasoning",
	"same-and-different",
	"trog",
	"mental-rotation",
	"theory-of-mind",
	"child-survey",
	"vocab",
)

NO_APPROVED = "NO APPROVED TRANSLATION"

# Dashboard / languageoptions locale → Crowdin target id (only exception today).
DASHBOARD_LANG_TO_CROWDIN: dict[str, str] = {
	"de-DE": "de",
	"nl-NL": "nl"
}

DEFAULT_DEV_BUCKET = "levante-assets-dev"
DEFAULT_LANGUAGEOPTIONS_BLOB = "translations/dashboard-consolidated-flat/languageoptions.json"


def object_path(task: str, locale_key: str) -> str:
	"""Path inside the bucket or under ``--local-root`` (``translations/itembank/...``)."""
	return f"translations/itembank/{task}/{locale_key}/item-bank-translations.json"


def dashboard_locale_to_crowdin(locale_key: str) -> str:
	return DASHBOARD_LANG_TO_CROWDIN.get(locale_key, locale_key)


def load_language_option_keys(raw: Any) -> list[str]:
	"""Top-level locale keys, or ``.languages`` if present."""
	if isinstance(raw, dict) and "languages" in raw and isinstance(raw["languages"], dict):
		raw = raw["languages"]
	if not isinstance(raw, dict):
		raise ValueError("languageoptions.json must be a JSON object (optionally with a .languages map).")
	return sorted(str(k) for k in raw.keys())


def fetch_languageoptions_json(*, bucket: str, blob_path: str) -> Any:
	client = utils.initialize_gcs()
	b = client.bucket(bucket)
	data = b.blob(blob_path).download_as_bytes()
	return json.loads(data.decode("utf-8"))


def _airtable_task_key(cli_name: str, task_map: dict) -> str:
	"""Resolve ``taskManual`` key: exact match, else case-insensitive (e.g. ``trog`` → ``TROG``)."""
	if cli_name in task_map:
		return cli_name
	for k in task_map:
		if k.lower() == cli_name.lower():
			return k
	raise KeyError(cli_name)


def resolve_task_file_map(selected_tasks: list[str]) -> dict[str, int]:
	"""CLI task name → Crowdin ``fileId`` (keys stay canonical CLI names for output paths)."""
	full = utils.build_task_file_map()
	out: dict[str, int] = {}
	for name in selected_tasks:
		try:
			at_key = _airtable_task_key(name, full)
		except KeyError:
			raise SystemExit(
				f"No Crowdin file id in Airtable for task {name!r}. "
				f"Available taskManual keys: {sorted(full.keys())}"
			)
		# ``split_itembank_fileId`` is a number in Airtable; pyairtable returns int.
		out[name] = int(full[at_key])
	return out


def iter_strings_for_file(client: CrowdinClient, file_id: int, *, page_size: int = 500):
	offset = 0
	while True:
		resp = client.source_strings.list_strings(fileId=file_id, limit=page_size, offset=offset)
		batch = resp.get("data") or []
		for item in batch:
			yield item
		if len(batch) < page_size:
			break
		offset += page_size


def build_translation_map_for_file_language(
	client: CrowdinClient,
	file_id: int,
	crowdin_lang: str,
) -> dict[str, str]:
	"""identifier → approved translation text or ``NO_APPROVED`` placeholder."""
	out: dict[str, str] = {}
	for item in iter_strings_for_file(client, file_id):
		data = item.get("data") or {}
		ident = data.get("identifier")
		if ident is None or ident == "":
			continue
		sid = int(data["id"])
		text = utils.get_approved_translation_text(client, sid, crowdin_lang)
		out[str(ident)] = text if text is not None else NO_APPROVED
	return out


def write_json_local(path: Path, payload: dict[str, str]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def upload_json_bucket(
	bucket_name: str,
	blob_path: str,
	payload: dict[str, str],
) -> None:
	client = utils.initialize_gcs()
	bucket = client.bucket(bucket_name)
	blob = bucket.blob(blob_path)
	blob.upload_from_string(
		json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
		content_type="application/json; charset=utf-8",
	)


def main() -> None:
	p = argparse.ArgumentParser(description=__doc__)
	p.add_argument(
		"--tasks",
		nargs="+",
		metavar="TASK",
		required=True,
		help="'all' or one or more of: " + ", ".join(ITEMBANK_TASK_NAMES),
	)
	p.add_argument(
		"--local",
		action="store_true",
		help="Write under ./translations/itembank/... instead of GCS.",
	)
	p.add_argument(
		"--language-options-bucket",
		default=DEFAULT_DEV_BUCKET,
		help=f"Bucket containing languageoptions.json (default: {DEFAULT_DEV_BUCKET}).",
	)
	p.add_argument(
		"--language-options-blob",
		default=DEFAULT_LANGUAGEOPTIONS_BLOB,
		help="Object path to languageoptions.json (used when --languages is options-file).",
	)
	p.add_argument(
		"--languages",
		nargs="+",
		default=["options-file"],
		metavar="LOCALE",
		help=(
			"Default: options-file — load locale list from languageoptions.json. "
			"Otherwise one or more dashboard locale codes (e.g. es-AR en-US). "
			"options-file must appear alone if used."
		),
	)
	p.add_argument(
		"--output-bucket",
		default=DEFAULT_DEV_BUCKET,
		help=f"Destination bucket when not --local (default: {DEFAULT_DEV_BUCKET}).",
	)
	p.add_argument(
		"--local-root",
		type=Path,
		default=Path("translations"),
		help="Directory that will contain itembank/... when using --local (default: ./translations).",
	)
	args = p.parse_args()

	names = [t.strip() for t in args.tasks]
	if not names or any(not t for t in names):
		p.error("--tasks: each value must be non-empty.")
	if names == ["all"]:
		selected = list(ITEMBANK_TASK_NAMES)
	else:
		bad = [t for t in names if t not in ITEMBANK_TASK_NAMES]
		if bad:
			p.error(f"Unknown task(s): {bad}. Expected 'all' or any of {list(ITEMBANK_TASK_NAMES)}")
		if "all" in names:
			p.error("Use 'all' alone, not mixed with other task names.")
		selected = names

	lang_spec = [x.strip() for x in args.languages]
	if not lang_spec or any(not x for x in lang_spec):
		p.error("--languages: each value must be non-empty.")
	if lang_spec == ["options-file"]:
		print(
			"Loading language keys from gs://{}/{} ...".format(
				args.language_options_bucket,
				args.language_options_blob,
			)
		)
		raw = fetch_languageoptions_json(
			bucket=args.language_options_bucket,
			blob_path=args.language_options_blob,
		)
		locale_keys = load_language_option_keys(raw)
		print(
			f"Locales (from languageoptions): {len(locale_keys)} — "
			f"{', '.join(locale_keys[:12])}{' …' if len(locale_keys) > 12 else ''}"
		)
	else:
		if "options-file" in lang_spec:
			p.error("Use '--languages options-file' alone (default), not mixed with other locales.")
		locale_keys = lang_spec
		print(f"Locales (explicit): {len(locale_keys)} — {', '.join(locale_keys)}")

	task_files = resolve_task_file_map(selected)
	print(f"Tasks → fileId: {task_files}")

	client = CrowdinClient(token=config.LEV_CI, project_id=config.LEV_CI_PID)

	for task, file_id in task_files.items():
		for loc in locale_keys:
			crowdin_lang = dashboard_locale_to_crowdin(loc)
			print(f"Building {task} / {loc} (Crowdin {crowdin_lang}) fileId={file_id} …")
			payload = build_translation_map_for_file_language(client, file_id, crowdin_lang)
			rel = object_path(task, loc)
			if args.local:
				dest = args.local_root / "itembank" / task / loc / "item-bank-translations.json"
				write_json_local(dest, payload)
				print(f"   → {dest.resolve()} ({len(payload)} keys)")
			else:
				upload_json_bucket(args.output_bucket, rel, payload)
				print(f"   → gs://{args.output_bucket}/{rel} ({len(payload)} keys)")

	print("Done.")


if __name__ == "__main__":
	main()
