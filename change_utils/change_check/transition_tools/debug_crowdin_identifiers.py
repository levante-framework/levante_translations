import argparse
import csv
import json
import os
import requests

from crowdin_api import CrowdinClient

from change_check import config, utils
from change_check.platform_update import update_survey


def fetch_strings_for_file(client, file_id, limit=100):
	"""Yield all string records for a given file_id."""
	offset = 0
	while True:
		resp = client.source_strings.list_strings(fileId=file_id, limit=limit, offset=offset)
		data = resp.get("data", [])
		if not data:
			break
		for item in data:
			yield item
		if len(data) < limit:
			break
		offset += limit


def debug_identifier(client, file_id: int, identifier: str) -> bool:
	print(f"\n===== Identifier: {identifier} (fileId={file_id}) =====")

	# 1) Run the same query pattern used by getStringID
	resp = client.source_strings.list_strings(fileId=file_id, filter=identifier, scope="identifier")
	api_data = resp.get("data", [])
	print(f"API list_strings(filter=..., scope='identifier') returned {len(api_data)} record(s).")

	for entry in api_data:
		data = entry.get("data", {})
		print(
			"  MATCH:",
			f"id={data.get('id')},",
			f"identifier={repr(data.get('identifier'))},",
			f"text={repr(data.get('text'))}",
		)

	# 2) If nothing came back, manually scan all strings in the file
	if not api_data:
		print("No direct API matches. Scanning all strings in file for possible clues...")
		all_items = list(fetch_strings_for_file(client, file_id))

		# Exact identifier matches (in case of subtle differences like whitespace / case)
		exact_matches = [
			it for it in all_items if (it.get("data", {}) or {}).get("identifier") == identifier
		]
		if exact_matches:
			print(f"  Found {len(exact_matches)} exact identifier match(es) when scanning all strings:")
			for it in exact_matches:
				d = it["data"]
				print(
					"    EXACT:",
					f"id={d.get('id')},",
					f"identifier={repr(d.get('identifier'))},",
					f"text={repr(d.get('text'))}",
				)
		else:
			print("  No exact identifier matches found when scanning all strings.")

		# Substring matches in identifier or text, to see if UI search is more lenient
		substring_matches = []
		for it in all_items:
			d = it.get("data", {}) or {}
			ident = d.get("identifier") or ""
			text = d.get("text") or ""
			if identifier in ident or identifier in text:
				substring_matches.append(it)

		if substring_matches:
			print(
				f"  Found {len(substring_matches)} substring match(es) "
				f"(identifier/text contains the query):"
			)
			for it in substring_matches[:20]:
				d = it["data"]
				print(
					"    SUBSTR:",
					f"id={d.get('id')},",
					f"identifier={repr(d.get('identifier'))},",
					f"text={repr(d.get('text'))}",
				)
			if len(substring_matches) > 20:
				print(f"    ... {len(substring_matches) - 20} more substring matches not shown")
		else:
			print("  No substring matches found in identifier or text.")

		# Indicate failure to find a usable stringId via primary API call
		return False

	# If we got here, the primary API call returned at least one match
	return True


def main():
	parser = argparse.ArgumentParser(
		description=(
			"Debug why certain identifiers in a Crowdin file "
			"do not return string IDs via list_strings(filter=..., scope='identifier')."
		)
	)
	parser.add_argument(
		"--file-id",
		type=int,
		default=782,
		help="Crowdin fileId to inspect (default: 782)",
	)
	parser.add_argument(
		"--from-prod",
		nargs="+",
		help=(
			"Optional survey keys (as in update_survey.urlMap) whose prod JSON flattened keys "
			"will be used as additional identifiers to debug."
		),
	)
	parser.add_argument(
		"identifiers",
		nargs="*",
		help="One or more identifier strings to debug.",
	)
	args = parser.parse_args()

	client = CrowdinClient(token=config.LEV_CI, project_id=config.LEV_CI_PID)

	# Start with identifiers passed on the command line
	identifiers = list(args.identifiers or [])

	# Optionally extend with flattened keys from prod JSON for given surveys
	if args.from_prod:
		for survey_key in args.from_prod:
			if survey_key not in update_survey.urlMap:
				print(f"⚠️  Skipping unknown survey key '{survey_key}' (not in update_survey.urlMap).")
				continue
			print(f"Fetching and flattening prod JSON for survey '{survey_key}'...")
			url = update_survey.urlMap[survey_key]
			resp = requests.get(url)
			resp.raise_for_status()
			data = resp.json()
			flat = utils.flatten_custom(data)
			# Write flattened keys/values to a local JSON file for inspection
			out_name = f"prod_flat_{survey_key}.json"
			with open(out_name, "w", encoding="utf-8") as f:
				json.dump(flat, f, ensure_ascii=False, indent=2)
			print(f"  Wrote flattened prod JSON for '{survey_key}' to {out_name}")
			identifiers.extend(flat.keys())

	# Require at least one identifier source
	if not identifiers:
		print("No identifiers provided and no --from-prod surveys specified; nothing to debug.")
		return

	# De-duplicate while preserving order
	seen = set()
	unique_identifiers = []
	for ident in identifiers:
		if ident not in seen:
			seen.add(ident)
			unique_identifiers.append(ident)

	failed = []
	for ident in unique_identifiers:
		ok = debug_identifier(client, args.file_id, ident)
		if not ok:
			failed.append({"identifier": ident})

	# Write failed identifiers to CSV, if any
	if failed:
		out_name = "crowdin_failed_identifiers.csv"
		with open(out_name, "w", newline="", encoding="utf-8") as f:
			writer = csv.DictWriter(f, fieldnames=["identifier"])
			writer.writeheader()
			for row in failed:
				writer.writerow(row)
		print(f"\nWrote {len(failed)} failed identifier(s) to {out_name}")


if __name__ == "__main__":
	main()

