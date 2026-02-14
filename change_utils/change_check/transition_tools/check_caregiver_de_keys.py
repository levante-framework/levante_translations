import csv
import requests

from change_check import utils


URL_MAP = {
	"caregiver-child": "https://storage.googleapis.com/levante-assets-prod/surveys/parent_survey_child.json",
	"caregiver-family": "https://storage.googleapis.com/levante-assets-prod/surveys/parent_survey_family.json",
}


def fetch_and_flatten(survey_key: str):
	"""Fetch survey JSON from prod and return flattened data using utils.flatten_custom."""
	url = URL_MAP[survey_key]
	response = requests.get(url)
	response.raise_for_status()
	data = response.json()
	return utils.flatten_custom(data)


def analyze_language_dict(lang_dict: dict):
	"""
	Given a dict of language -> text, determine:
	- structural issue type (both_keys, deOnly, neither, or None)
	- equality issues where de/de-DE equals default/en/en-US
	"""
	has_de = "de" in lang_dict
	has_de_de = "de-DE" in lang_dict

	issue_type = None
	if has_de and has_de_de:
		issue_type = "both_keys"
	elif not has_de and not has_de_de:
		issue_type = "neither"

	# Equality checks
	equality_matches = []
	for german_key in ("de", "de-DE"):
		if german_key not in lang_dict:
			continue
		german_value = lang_dict.get(german_key)
		for ref_key in ("default", "en", "en-US"):
			if ref_key in lang_dict and lang_dict.get(ref_key) == german_value:
				equality_matches.append((german_key, ref_key))

	return issue_type, equality_matches


def main():
	# CSV 1: structural issues with de / de-DE keys
	structural_filename = "caregiver_de_key_issues.csv"
	# CSV 2: equality issues where de / de-DE equals default/en/en-US
	equality_filename = "caregiver_de_translation_matches.csv"

	structural_rows = []
	equality_rows = []

	for survey_key in ("caregiver-child", "caregiver-family"):
		print(f"Processing survey: {survey_key}")
		flat = fetch_and_flatten(survey_key)

		for flat_key, value in flat.items():
			# We're only interested in entries where the value is a dict of language codes
			if not isinstance(value, dict):
				continue

			issue_type, equality_matches = analyze_language_dict(value)

			# Structural issues CSV
			if issue_type is not None:
				structural_rows.append(
					{
						"survey": survey_key,
						"url_key": survey_key,
						"key": flat_key,
						"issue": issue_type,
						"default": value.get("default", ""),
						"en": value.get("en", ""),
						"en-US": value.get("en-US", ""),
					}
				)

			# Equality issues CSV
			for german_key, ref_key in equality_matches:
				equality_rows.append(
					{
						"survey": survey_key,
						"url_key": survey_key,
						"key": flat_key,
						"german_key": german_key,
						"same_as": ref_key,
						"default": value.get("default", ""),
						"en": value.get("en", ""),
						"en-US": value.get("en-US", ""),
					}
				)

	# Write structural issues CSV
	if structural_rows:
		fieldnames_struct = ["survey", "url_key", "key", "issue", "default", "en", "en-US"]
		with open(structural_filename, "w", newline="", encoding="utf-8") as f:
			writer = csv.DictWriter(f, fieldnames=fieldnames_struct)
			writer.writeheader()
			for row in structural_rows:
				writer.writerow(row)
		print(f"Wrote {len(structural_rows)} rows to {structural_filename}")
	else:
		print("No structural issues found for de / de-DE keys.")

	# Write equality issues CSV
	if equality_rows:
		fieldnames_eq = ["survey", "url_key", "key", "german_key", "same_as", "default", "en", "en-US"]
		with open(equality_filename, "w", newline="", encoding="utf-8") as f:
			writer = csv.DictWriter(f, fieldnames=fieldnames_eq)
			writer.writeheader()
			for row in equality_rows:
				writer.writerow(row)
		print(f"Wrote {len(equality_rows)} rows to {equality_filename}")
	else:
		print("No equality issues found where de / de-DE equals default/en/en-US.")


if __name__ == "__main__":
	main()

