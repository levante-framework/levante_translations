#!/usr/bin/env python3
"""
convert_xliff_to_icu.py

Fetch all .xliff files from the levante_translations repository translations folder
and output one ICU-style JSON file per language code.

- Default source: repo=levante-framework/levante_translations, ref=l10n_pending, path=translations/
- Output: ICU JSON written to --output-dir (defaults to xliff/translations-icu under this repo)

ICU JSON format: a flat mapping of string identifiers to translated strings.
If a <trans-unit> has a <target>, it is used; otherwise falls back to <source>.

Usage:
  python xliff/convert_xliff_to_icu.py [--repo levante-framework/levante_translations] \
      [--ref l10n_pending] [--path translations] [--output-dir xliff/translations-icu]

Optionally set GITHUB_TOKEN in the environment to increase rate limits.
"""

import argparse
import json
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

import requests
import xml.etree.ElementTree as ET

GITHUB_API = "https://api.github.com"
RAW_BASE = "https://raw.githubusercontent.com"


def get_env(name: str, default: Optional[str] = None) -> Optional[str]:
	return os.environ.get(name, default)


def list_xliff_files(repo: str, ref: str, path: str, token: Optional[str]) -> List[Dict[str, str]]:
	"""List XLIFF files in a GitHub repo folder using the contents API."""
	url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
	headers = {"Accept": "application/vnd.github.v3+json"}
	if token:
		headers["Authorization"] = f"Bearer {token}"
	params = {"ref": ref}
	resp = requests.get(url, headers=headers, params=params, timeout=30)
	resp.raise_for_status()
	items = resp.json()
	files = []
	for it in items:
		if it.get("type") == "file" and it.get("name", "").lower().endswith(".xliff"):
			files.append({
				"name": it["name"],
				"download_url": it.get("download_url")
			})
	return files


def build_raw_url(repo: str, ref: str, path: str, filename: str) -> str:
	return f"{RAW_BASE}/{repo}/{ref}/{path.rstrip('/')}/{filename}"


def fetch_text(url: str, token: Optional[str]) -> str:
	headers = {}
	if token and "api.github.com" in url:
		headers["Authorization"] = f"Bearer {token}"
	resp = requests.get(url, headers=headers, timeout=60)
	resp.raise_for_status()
	return resp.text


def extract_text_with_placeholders(element: Optional[ET.Element]) -> str:
	"""Extract text from an XML element, preserving a minimal placeholder marker for <x>, <ph> nodes.
	This is a simple, conservative approach suitable for common UI strings.
	"""
	if element is None:
		return ""
	parts: List[str] = []

	def walk(node: ET.Element):
		if node.text:
			parts.append(node.text)
		for child in list(node):
			tag = re.sub(r"^\{.*\}", "", child.tag).lower()
			if tag in {"x", "ph"}:
				# Try to name the placeholder; fall back to a generic token
				name = child.attrib.get("id") or child.attrib.get("ctype") or child.attrib.get("equiv-text")
				name = re.sub(r"[^A-Za-z0-9_]+", "_", name) if name else "PH"
				parts.append(f"{{{name}}}")
			else:
				walk(child)
			if child.tail:
				parts.append(child.tail)

	walk(element)
	return "".join(parts).strip()


def parse_xliff(xliff_text: str, fallback_lang: Optional[str] = None, stats: Optional[Dict[str, int]] = None) -> Tuple[str, Dict[str, str]]:
	"""Parse XLIFF 1.2 text and return (language_code, mapping of key->string).
	Optionally track stats on which key source was used.
	"""
	try:
		tree = ET.fromstring(xliff_text)
	except ET.ParseError as exc:
		raise ValueError(f"Invalid XLIFF: {exc}")

	lang_code = fallback_lang or ""
	strings: Dict[str, str] = {}

	for file_el in tree.findall(".//file") + tree.findall(".//{*}file"):
		target_lang = file_el.attrib.get("target-language") or file_el.attrib.get("targetLanguage")
		if target_lang:
			lang_code = target_lang
		for tu in file_el.findall(".//trans-unit") + file_el.findall(".//{*}trans-unit"):
			# Prefer resname over id as requested
			key = (
				tu.attrib.get("resname")
				or tu.attrib.get("resName")
				or tu.attrib.get("id")
				or tu.attrib.get("resId")
			)
			key_source = "resname" if (tu.attrib.get("resname") or tu.attrib.get("resName")) else ("id" if (tu.attrib.get("id") or tu.attrib.get("resId")) else "source")
			if not key:
				# Attempt to use <source> text as a key in absence of attributes
				src_el = tu.find("source") or tu.find("{*}source")
				key = extract_text_with_placeholders(src_el)[:100] if src_el is not None else None
			if not key:
				continue
			target_el = tu.find("target") or tu.find("{*}target")
			text = extract_text_with_placeholders(target_el)
			if not text:
				src_el = tu.find("source") or tu.find("{*}source")
				text = extract_text_with_placeholders(src_el)
			strings[key] = text
			if stats is not None:
				stats[key_source] = stats.get(key_source, 0) + 1

	if not lang_code:
		# Try to infer from <xliff> or fall back to provided
		xliff_lang = tree.attrib.get("target-language") or tree.attrib.get("srcLang")
		if xliff_lang:
			lang_code = xliff_lang
	if not lang_code:
		lang_code = fallback_lang or "unknown"

	return lang_code, strings


def sanitize_lang_code(code: str) -> str:
	return code.replace("_", "-").strip()


def write_icu_json(out_dir: str, lang_code: str, data: Dict[str, str], overwrite: bool = False) -> str:
	os.makedirs(out_dir, exist_ok=True)
	lang_code = sanitize_lang_code(lang_code)
	out_path = os.path.join(out_dir, f"{lang_code}.json")
	# Merge unless overwrite requested
	if not overwrite and os.path.exists(out_path):
		try:
			with open(out_path, "r", encoding="utf-8") as f:
				existing = json.load(f)
		except Exception:
			existing = {}
		existing.update(data)
		data = existing
	with open(out_path, "w", encoding="utf-8") as f:
		json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
	return out_path


def infer_lang_from_filename(filename: str) -> Optional[str]:
	# e.g., messages-es-CO.xliff or es-CO.xliff
	m = re.search(r"([A-Za-z]{2}(?:[-_][A-Za-z]{2})?)\.xliff$", filename)
	return m.group(1).replace("_", "-") if m else None


def main(argv: Optional[List[str]] = None) -> int:
	parser = argparse.ArgumentParser(description="Convert XLIFF files to ICU JSON by language")
	parser.add_argument("--repo", default="levante-framework/levante_translations", help="GitHub repo owner/name")
	parser.add_argument("--ref", default="l10n_pending", help="Git ref/branch/tag")
	parser.add_argument("--path", default="translations", help="Path within repo containing .xliff files")
	parser.add_argument("--output-dir", default=os.path.join(os.path.dirname(__file__), "translations-icu"), help="Directory to write ICU JSON files")
	parser.add_argument("--languages", nargs="*", default=None, help="Optional list of language codes (filter)")
	parser.add_argument("--overwrite", action="store_true", help="Overwrite output JSON instead of merging with existing")
	parser.add_argument("--verbose", action="store_true", help="Print diagnostics about key sources (resname/id/source)")
	args = parser.parse_args(argv)

	token = get_env("GITHUB_TOKEN")

	try:
		files = list_xliff_files(args.repo, args.ref, args.path, token)
	except Exception as e:
		print(f"Error listing XLIFF files: {e}", file=sys.stderr)
		return 1

	if not files:
		print("No .xliff files found in the specified path/ref.")
		return 0

	# Accumulate by language
	lang_to_strings: Dict[str, Dict[str, str]] = {}
	lang_to_stats: Dict[str, Dict[str, int]] = {}

	for fi in files:
		name = fi["name"]
		download_url = fi.get("download_url") or build_raw_url(args.repo, args.ref, args.path, name)
		try:
			xliff_text = fetch_text(download_url, token)
		except Exception as e:
			print(f"Warning: failed to fetch {name}: {e}", file=sys.stderr)
			continue
		fallback_lang = infer_lang_from_filename(name)
		try:
			stats = {}
			lang_code, strings = parse_xliff(xliff_text, fallback_lang=fallback_lang, stats=stats)
		except Exception as e:
			print(f"Warning: failed to parse {name}: {e}", file=sys.stderr)
			continue
		lang_code = sanitize_lang_code(lang_code)
		if args.languages and lang_code not in args.languages and sanitize_lang_code(fallback_lang or "") not in (args.languages):
			continue
		lang_to_strings.setdefault(lang_code, {}).update(strings)
		if args.verbose:
			acc = lang_to_stats.setdefault(lang_code, {"resname": 0, "id": 0, "source": 0})
			for k, v in stats.items():
				acc[k] = acc.get(k, 0) + v

	# Write per-language ICU JSON
	written = []
	for lang, data in sorted(lang_to_strings.items()):
		out_path = write_icu_json(args.output_dir, lang, data, overwrite=args.overwrite)
		written.append((lang, out_path, len(data)))

	for lang, path_out, count in written:
		print(f"Wrote {count} entries -> {path_out}")
		if args.verbose and lang in lang_to_stats:
			st = lang_to_stats[lang]
			print(f"  Key sources: resname={st.get('resname',0)}, id={st.get('id',0)}, source={st.get('source',0)}")

	return 0


if __name__ == "__main__":
	sys.exit(main())
