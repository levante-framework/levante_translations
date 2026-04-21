"""
Build per-task, per-language flat JSON maps from Crowdin (approved translations only).

Unless ``--languages`` lists explicit locale codes, use ``--languages options-file`` or
``--languages all`` (same meaning) to read locale keys from ``languageoptions.json``
(default: dev assets bucket). Maps them to
Crowdin language ids (``de-DE`` → ``de`` is the only special case), pulls strings from
the hardcoded task → file id map (:data:`~change_check.utils.ITEMBANK_TASK_FILE_MAP`), and writes
``item-bank-translations.json`` for each (task, language) pair under ``gs://levante-assets-draft/``
by default (override with ``--output-bucket``).

With ``--ignore-hidden-strings true``, source strings whose Crowdin payload has ``isHidden`` are
omitted from generated JSON (they do not appear as keys). Output folders use app-facing names
(``egma-math``, ``memory-game``) where they differ from Crowdin task slugs ``math`` / ``memory``.

With ``--preserve-from``, when Crowdin has no **approved** translation for a string, the build can
fill from production ``levante-assets-prod`` data so live text is kept until Crowdin approves a
replacement: either ``itembanktranslations-csv`` (flat
``translations/item-bank-translations.csv``) or ``itembank-json`` (per-task JSON under
``translations/itembank/<task-folder>/<locale>/``). Preflight fails if required prod objects are
missing.

Writes ``itembank_build_summary.json`` (override with ``--summary-json``) with per-locale counts and
``slack_mrkdwn`` for CI notifications.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from crowdin_api import CrowdinClient

from change_check import config, utils

NO_APPROVED = "NO APPROVED TRANSLATION"

# Default path for CI / Slack (written at end of each successful run).
DEFAULT_SUMMARY_JSON = Path("itembank_build_summary.json")


@dataclass(frozen=True)
class FileLanguageBuildStats:
	"""Per (Crowdin file × locale): how many identifiers used placeholder vs prod legacy."""

	no_approved: int  # JSON value exactly ``NO_APPROVED``
	preserved: int  # no Crowdin approval; non-empty legacy text used

# Dashboard / languageoptions locale → Crowdin target id (de and nl only exceptions).
DASHBOARD_LANG_TO_CROWDIN: dict[str, str] = {
	"de-DE": "de",
	"nl-NL": "nl"
}

# Default bucket for reading languageoptions.json (dev consolidated dashboard assets).
DEFAULT_LANGUAGEOPTIONS_BUCKET = "levante-assets-dev"
DEFAULT_LANGUAGEOPTIONS_BLOB = "translations/dashboard-consolidated-flat/languageoptions.json"
# Default bucket for uploaded itembank JSON (dev GCP project; draft staging bucket).
DEFAULT_OUTPUT_BUCKET = "levante-assets-draft"

# Production bucket for legacy translations when using ``--preserve-from``.
DEFAULT_LEGACY_BUCKET = "levante-assets-prod"
DEFAULT_LEGACY_CSV_BLOB = "translations/item-bank-translations.csv"

# Dashboard / languageoptions locale key → CSV column when the names differ (e.g. ``en-US`` → ``en``).
# Locales not listed here still match if ``languageoptions`` uses the same string as a CSV header
# (case-insensitive), e.g. ``de`` or ``es-AR``.
LOCALE_KEY_TO_LEGACY_CSV_COLUMN: dict[str, str] = {
	"en-US": "en",
	"de-DE": "de",
	"nl-NL": "nl",
	"es-CO": "es-CO",
	"es-AR": "es-AR",
}

PRESERVE_FROM_CHOICES = ("itembanktranslations-csv", "itembank-json")

# Task slugs from ``ITEMBANK_TASK_FILE_MAP`` → folder name under ``translations/itembank/<folder>/``.
# Consumers (e.g. apps) expect egma-math / memory-game, not Crowdin slug math / memory.
ITEMBANK_OUTPUT_FOLDER_BY_TASK: dict[str, str] = {
	"math": "egma-math",
	"memory": "memory-game",
}


def output_folder_for_task(task_slug: str) -> str:
	"""Bucket/local folder segment for ``task_slug`` (defaults to slug when unmapped)."""
	return ITEMBANK_OUTPUT_FOLDER_BY_TASK.get(task_slug, task_slug)


def object_path(task: str, locale_key: str) -> str:
	"""Path inside the bucket or under ``--local-root`` (``translations/itembank/...``)."""
	folder = output_folder_for_task(task)
	return f"translations/itembank/{folder}/{locale_key}/item-bank-translations.json"


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


def gcs_blob_exists(bucket_name: str, blob_path: str) -> bool:
	client = utils.initialize_gcs()
	return client.bucket(bucket_name).blob(blob_path).exists()


def preflight_legacy_csv(*, bucket: str, blob_path: str) -> None:
	if not gcs_blob_exists(bucket, blob_path):
		raise SystemExit(
			f"Legacy CSV fallback: required object missing: gs://{bucket}/{blob_path}"
		)


def preflight_legacy_json(
	*,
	bucket: str,
	task_files: dict[str, int],
	locale_keys: list[str],
) -> None:
	missing: list[str] = []
	for task in task_files:
		folder = output_folder_for_task(task)
		for loc in locale_keys:
			rel = object_path(task, loc)
			if not gcs_blob_exists(bucket, rel):
				missing.append(f"gs://{bucket}/{rel}")
	if missing:
		raise SystemExit(
			"Legacy JSON fallback: one or more required prod files are missing:\n"
			+ "\n".join(missing)
		)


def build_legacy_maps_from_csv(
	*,
	bucket: str,
	blob_path: str,
	locale_keys: list[str],
) -> dict[str, dict[str, str]]:
	"""
	``locale_key`` → ``identifier`` → non-empty legacy text from the flat prod CSV.

	Only locales listed in ``LOCALE_KEY_TO_LEGACY_CSV_COLUMN`` participate.
	"""
	client = utils.initialize_gcs()
	text = client.bucket(bucket).blob(blob_path).download_as_bytes().decode("utf-8-sig")
	reader = csv.DictReader(io.StringIO(text))
	if not reader.fieldnames:
		raise SystemExit(f"Legacy CSV {blob_path!r}: empty or missing header row")

	headers_lower: dict[str, str] = {}
	for f in reader.fieldnames:
		if f is None:
			continue
		fs = f.strip()
		if fs:
			headers_lower[fs.lower()] = fs

	def col(name: str) -> str | None:
		return headers_lower.get(name.strip().lower())

	item_h = col("item_id") or col("itemid")
	if not item_h:
		raise SystemExit(
			f"Legacy CSV {blob_path!r}: no item_id column (expected a header like item_id)"
		)

	def header_for_locale(loc: str) -> str | None:
		"""CSV row key for this dashboard locale: explicit map, else a column named like ``loc``."""
		logical = LOCALE_KEY_TO_LEGACY_CSV_COLUMN.get(loc)
		if logical:
			found = col(logical)
			if found:
				return found
		return col(loc)

	col_headers: dict[str, str] = {}
	for loc in locale_keys:
		h = header_for_locale(loc)
		if h:
			col_headers[loc] = h

	if not col_headers:
		raise SystemExit(
			f"Legacy CSV {blob_path!r}: no locale in this run maps to a CSV column. "
			f"Locales in this build: {locale_keys!r}. "
			f"CSV headers: {list(reader.fieldnames)!r}. "
			f"Add a header matching each locale, or extend LOCALE_KEY_TO_LEGACY_CSV_COLUMN "
			f"(e.g. en-US→en when options use en-US but CSV column is en)."
		)

	legacy: dict[str, dict[str, str]] = {loc: {} for loc in col_headers}

	for row in reader:
		ident = (row.get(item_h) or "").strip()
		if not ident:
			continue
		for loc, h in col_headers.items():
			val = (row.get(h) or "").strip()
			if val:
				legacy[loc][ident] = val

	return legacy


def load_legacy_json_map(*, bucket: str, task: str, locale_key: str) -> dict[str, str]:
	"""identifier → text from prod per-task JSON (must exist if caller ran preflight)."""
	rel = object_path(task, locale_key)
	client = utils.initialize_gcs()
	raw = client.bucket(bucket).blob(rel).download_as_bytes()
	data = json.loads(raw.decode("utf-8"))
	if not isinstance(data, dict):
		raise SystemExit(f"Legacy JSON gs://{bucket}/{rel}: expected a JSON object at top level")
	out: dict[str, str] = {}
	for k, v in data.items():
		if v is None:
			continue
		s = str(v).strip()
		if s:
			out[str(k)] = s
	return out


def _airtable_task_key(cli_name: str, task_map: dict) -> str:
	"""Resolve ``taskManual`` key: exact match, else case-insensitive; ``…-dx`` suffixes match the base name."""
	if cli_name in task_map:
		return cli_name
	for k in task_map:
		if k.lower() == cli_name.lower():
			return k
	norm = utils.normalize_task_manual_key(cli_name)
	if norm and norm != cli_name:
		if norm in task_map:
			return norm
		for k in task_map:
			if k.lower() == norm.lower():
				return k
	raise KeyError(cli_name)


def resolve_task_file_map(task_map: dict[str, Any], selected_tasks: list[str]) -> dict[str, int]:
	"""CLI task token → Crowdin ``fileId`` (dict keys are canonical task slugs from ``normalize_task_manual_key``)."""
	out: dict[str, int] = {}
	for name in selected_tasks:
		try:
			at_key = _airtable_task_key(name, task_map)
		except KeyError:
			raise SystemExit(
				f"No file id configured for task {name!r}. "
				f"Available task slugs: {sorted(task_map.keys())}"
			)
		out[at_key] = int(task_map[at_key])
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


def _crowdin_string_is_hidden(data: dict) -> bool:
	"""Whether Crowdin marks this source string hidden (editor / visibility flag)."""
	v = data.get("isHidden")
	if v is True:
		return True
	if isinstance(v, str) and v.strip().lower() in ("true", "1", "yes"):
		return True
	return False


def build_translation_map_for_file_language(
	client: CrowdinClient,
	file_id: int,
	crowdin_lang: str,
	*,
	ignore_hidden_strings: bool = False,
	legacy_by_identifier: Optional[dict[str, str]] = None,
) -> tuple[dict[str, str], FileLanguageBuildStats]:
	"""identifier → final JSON value; stats count placeholder vs preserved legacy rows."""
	out: dict[str, str] = {}
	legacy = legacy_by_identifier or {}
	no_approved = 0
	preserved = 0
	for item in iter_strings_for_file(client, file_id):
		data = item.get("data") or {}
		if ignore_hidden_strings and _crowdin_string_is_hidden(data):
			continue
		ident = data.get("identifier")
		if ident is None or ident == "":
			continue
		sid = int(data["id"])
		ident_s = str(ident)
		text = utils.get_approved_translation_text(client, sid, crowdin_lang)
		if text is not None:
			out[ident_s] = text
			continue
		fallback = legacy.get(ident_s)
		if fallback is not None and str(fallback).strip() != "":
			out[ident_s] = str(fallback).strip()
			preserved += 1
		else:
			out[ident_s] = NO_APPROVED
			no_approved += 1
	return out, FileLanguageBuildStats(no_approved=no_approved, preserved=preserved)


def _format_slack_build_stats_mrkdwn(
	per_language: dict[str, dict[str, int]],
	totals: dict[str, int],
) -> str:
	"""Slack mrkdwn section: per-language and run-wide counts."""
	lines = [
		"*Build statistics* (this run, all tasks × locales)",
		f"• _No approved in Crowdin_ — JSON value is exactly `{NO_APPROVED}`: *{totals['no_approved']}* strings",
		f"• _Preserved from prod_ — no Crowdin approval, legacy text used: *{totals['preserved']}* strings",
		"",
	]
	nonzero = [
		(loc, per_language[loc])
		for loc in sorted(per_language)
		if per_language[loc]["no_approved"] or per_language[loc]["preserved"]
	]
	if not nonzero:
		lines.append("_Every string in this run had an approved Crowdin translation._")
	else:
		lines.append("*Per language* (only locales with at least one gap or preserved row):")
		for loc, row in nonzero:
			lines.append(
				f"• *{loc}*: {row['no_approved']} no approved, {row['preserved']} preserved"
			)
	return "\n".join(lines)


def write_build_summary_json(
	path: Path,
	*,
	per_language: dict[str, dict[str, int]],
	totals: dict[str, int],
) -> None:
	"""Summary for Slack / dashboards; safe to parse with ``jq`` in GitHub Actions."""
	payload = {
		"per_language": {k: dict(v) for k, v in sorted(per_language.items())},
		"totals": dict(totals),
		"slack_mrkdwn": _format_slack_build_stats_mrkdwn(per_language, totals),
		"no_approved_token": NO_APPROVED,
	}
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
	print(f"Wrote build summary for Slack: {path.resolve()}")


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
		help=(
			"'all' or one or more task slugs (see change_check.utils.ITEMBANK_TASK_FILE_MAP); "
			"matching is case-insensitive; …-dx suffixes map to the base name."
		),
	)
	p.add_argument(
		"--local",
		action="store_true",
		help="Write under ./translations/itembank/... instead of GCS.",
	)
	p.add_argument(
		"--language-options-bucket",
		default=DEFAULT_LANGUAGEOPTIONS_BUCKET,
		help=f"Bucket containing languageoptions.json (default: {DEFAULT_LANGUAGEOPTIONS_BUCKET}).",
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
			"Default: options-file — load every locale key from languageoptions.json "
			"(same as 'all' alone). Otherwise one or more explicit dashboard locale codes "
			"(e.g. es-AR en-US). options-file and all must not be mixed with other values."
		),
	)
	p.add_argument(
		"--output-bucket",
		default=DEFAULT_OUTPUT_BUCKET,
		help=f"Destination bucket when not --local (default: {DEFAULT_OUTPUT_BUCKET}).",
	)
	p.add_argument(
		"--local-root",
		type=Path,
		default=Path("translations"),
		help="Directory that will contain itembank/... when using --local (default: ./translations).",
	)
	p.add_argument(
		"--ignore-hidden-strings",
		required=True,
		choices=("true", "false"),
		help="If true, skip Crowdin source strings with isHidden when writing JSON (omit their keys).",
	)
	p.add_argument(
		"--preserve-from",
		choices=list(PRESERVE_FROM_CHOICES),
		default=None,
		help=(
			"When set, strings with no approved Crowdin translation use prod legacy text until one is "
			"approved: itembanktranslations-csv reads the flat CSV; itembank-json reads per-task JSON "
			"under translations/itembank/<folder>/<locale>/. Preflight fails if required gs:// objects "
			"are missing."
		),
	)
	p.add_argument(
		"--legacy-bucket",
		default=DEFAULT_LEGACY_BUCKET,
		help=f"GCS bucket for --preserve-from reads (default: {DEFAULT_LEGACY_BUCKET}).",
	)
	p.add_argument(
		"--legacy-csv-blob",
		default=DEFAULT_LEGACY_CSV_BLOB,
		help=f"Object path for CSV preserve mode (default: {DEFAULT_LEGACY_CSV_BLOB}).",
	)
	p.add_argument(
		"--summary-json",
		type=Path,
		default=DEFAULT_SUMMARY_JSON,
		help=(
			f"Write per-language gap counts and slack_mrkdwn here after a successful run "
			f"(default: {DEFAULT_SUMMARY_JSON}). Use /dev/null path to skip."
		),
	)
	args = p.parse_args()
	ignore_hidden_strings = args.ignore_hidden_strings == "true"

	task_map = utils.build_task_file_map()
	available = sorted(task_map.keys())

	names = [t.strip() for t in args.tasks]
	if not names or any(not t for t in names):
		p.error("--tasks: each value must be non-empty.")
	if names == ["all"]:
		selected = list(available)
	else:
		if "all" in names:
			p.error("Use 'all' alone, not mixed with other task names.")
		bad: list[str] = []
		for t in names:
			try:
				_airtable_task_key(t, task_map)
			except KeyError:
				bad.append(t)
		if bad:
			p.error(
				f"Unknown task(s): {bad!r}. Use 'all' or any configured task slug: {available}"
			)
		selected = names

	lang_spec = [x.strip() for x in args.languages]
	if not lang_spec or any(not x for x in lang_spec):
		p.error("--languages: each value must be non-empty.")
	load_from_options_file = lang_spec in (["options-file"], ["all"])
	if load_from_options_file:
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
		if "options-file" in lang_spec or "all" in lang_spec:
			p.error(
				"Use '--languages options-file' or '--languages all' alone for languageoptions.json, "
				"not mixed with other locale codes."
			)
		locale_keys = lang_spec
		print(f"Locales (explicit): {len(locale_keys)} — {', '.join(locale_keys)}")

	task_files = resolve_task_file_map(task_map, selected)
	print(f"Tasks → fileId: {task_files}")

	client = CrowdinClient(token=config.LEV_CI, project_id=config.LEV_CI_PID)

	if ignore_hidden_strings:
		print("Mode: omitting Crowdin strings with isHidden=true from output JSON.")
	legacy_csv_maps: dict[str, dict[str, str]] | None = None
	legacy_json_cache: dict[tuple[str, str], dict[str, str]] = {}

	if args.preserve_from == "itembanktranslations-csv":
		preflight_legacy_csv(bucket=args.legacy_bucket, blob_path=args.legacy_csv_blob)
		legacy_csv_maps = build_legacy_maps_from_csv(
			bucket=args.legacy_bucket,
			blob_path=args.legacy_csv_blob,
			locale_keys=locale_keys,
		)
		summary = ", ".join(f"{loc}:{len(m)}" for loc, m in sorted(legacy_csv_maps.items()))
		print(
			f"Legacy CSV: gs://{args.legacy_bucket}/{args.legacy_csv_blob} "
			f"(identifiers per mapped locale: {summary})"
		)
	elif args.preserve_from == "itembank-json":
		preflight_legacy_json(
			bucket=args.legacy_bucket,
			task_files=task_files,
			locale_keys=locale_keys,
		)
		print(
			f"Legacy JSON preflight OK: gs://{args.legacy_bucket}/translations/itembank/ "
			f"({len(task_files)} tasks × {len(locale_keys)} locale files)"
		)

	per_language: dict[str, dict[str, int]] = defaultdict(lambda: {"no_approved": 0, "preserved": 0})
	totals: dict[str, int] = {"no_approved": 0, "preserved": 0}

	for task, file_id in task_files.items():
		out_folder = output_folder_for_task(task)
		for loc in locale_keys:
			crowdin_lang = dashboard_locale_to_crowdin(loc)
			legacy_by_id: dict[str, str] | None = None
			if args.preserve_from == "itembanktranslations-csv" and legacy_csv_maps is not None:
				legacy_by_id = legacy_csv_maps.get(loc)
			elif args.preserve_from == "itembank-json":
				cache_key = (task, loc)
				if cache_key not in legacy_json_cache:
					legacy_json_cache[cache_key] = load_legacy_json_map(
						bucket=args.legacy_bucket,
						task=task,
						locale_key=loc,
					)
				legacy_by_id = legacy_json_cache[cache_key]

			print(f"Building {task} / {loc} (Crowdin {crowdin_lang}) fileId={file_id} …")
			payload, st = build_translation_map_for_file_language(
				client,
				file_id,
				crowdin_lang,
				ignore_hidden_strings=ignore_hidden_strings,
				legacy_by_identifier=legacy_by_id,
			)
			per_language[loc]["no_approved"] += st.no_approved
			per_language[loc]["preserved"] += st.preserved
			totals["no_approved"] += st.no_approved
			totals["preserved"] += st.preserved
			rel = object_path(task, loc)
			if args.local:
				dest = args.local_root / "itembank" / out_folder / loc / "item-bank-translations.json"
				write_json_local(dest, payload)
				print(f"   → {dest.resolve()} ({len(payload)} keys)")
			else:
				upload_json_bucket(args.output_bucket, rel, payload)
				print(f"   → gs://{args.output_bucket}/{rel} ({len(payload)} keys)")

	summary_path = args.summary_json
	if str(summary_path).replace("\\", "/") not in ("/dev/null", "nul"):
		write_build_summary_json(summary_path, per_language=dict(per_language), totals=totals)
	print(
		f"Totals — no approved (placeholder): {totals['no_approved']}; "
		f"preserved from prod: {totals['preserved']}"
	)
	print("Done.")


if __name__ == "__main__":
	main()
