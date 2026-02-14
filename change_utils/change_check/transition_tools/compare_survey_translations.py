import argparse
import csv
import json
from pathlib import Path
from change_check import utils

# Language codes to compare
LANG_CODES = ["default", "en", "en-US", "de", "de-DE", "es", "es-CO"]


def get_translation_value(flat_data, flat_key, lang_code):
	"""Get translation value for a given flattened key and language code."""
	if not flat_key:
		return "missing key"
	
	if flat_key not in flat_data:
		return "missing key"
	
	value = flat_data[flat_key]
	
	# If the value is a dict (translation object), get the language code from it
	if isinstance(value, dict):
		# Check if the dict has the language code
		if lang_code in value:
			return value[lang_code]
		else:
			return "missing key"
	
	# If it's not a dict, it's probably not a translation object
	return "missing key"


def main():
	# Parse command line arguments
	parser = argparse.ArgumentParser(description="Compare translations between old and new survey JSON files")
	parser.add_argument(
		"--type",
		required=True,
		choices=["child", "family"],
		help="Survey type: 'child' or 'family'"
	)
	args = parser.parse_args()
	
	# Set up file paths based on survey type
	TRANSITION_TOOLS_DIR = Path(__file__).parent
	NEW_JSON = TRANSITION_TOOLS_DIR / f"parent_survey_{args.type}_NEW.json"
	OLD_JSON = TRANSITION_TOOLS_DIR / f"parent_survey_{args.type}_OLD.json"
	MAPPING_CSV = TRANSITION_TOOLS_DIR.parent.parent / "archive" / "transition_sot" / "surveys" / "maps" / f"surveyShorteningMap_{args.type}.csv"
	OUTPUT_CSV = TRANSITION_TOOLS_DIR / f"survey_translation_comparison_{args.type}.csv"
	
	# Load and flatten NEW JSON
	print(f"Loading and flattening {NEW_JSON}...")
	with open(NEW_JSON, "r", encoding="utf-8") as f:
		new_data = json.load(f)
	new_flat = utils.flatten_custom(new_data)
	print(f"  Found {len(new_flat)} flattened keys in NEW file")
	
	# Load and flatten OLD JSON
	print(f"Loading and flattening {OLD_JSON}...")
	with open(OLD_JSON, "r", encoding="utf-8") as f:
		old_data = json.load(f)
	old_flat = utils.flatten_custom(old_data)
	print(f"  Found {len(old_flat)} flattened keys in OLD file")
	
	# Load mapping CSV - use oldString to match, not keys
	print(f"Loading mapping CSV {MAPPING_CSV}...")
	new_to_old_string = {}  # Maps newFlatKey -> oldString (from CSV)
	with open(MAPPING_CSV, "r", encoding="utf-8") as f:
		reader = csv.DictReader(f)
		for row in reader:
			new_key = row.get("newFlatKey", "").strip()
			old_string = row.get("oldString", "").strip()
			if new_key and old_string:
				new_to_old_string[new_key] = old_string
	print(f"  Found {len(new_to_old_string)} mappings")
	
	# Build a mapping from newFlatKey to old flattened key by matching string values
	# For each new key, find the old key that has a matching string value
	new_to_old_flat_key = {}
	
	# Create a reverse lookup: string value -> list of old flattened keys that contain it
	old_string_to_keys = {}
	for old_key, old_value in old_flat.items():
		if isinstance(old_value, dict):
			# Check all language codes in the dict for matching strings
			for lang_code, string_value in old_value.items():
				if string_value and isinstance(string_value, str):
					string_normalized = string_value.strip()
					if string_normalized:
						if string_normalized not in old_string_to_keys:
							old_string_to_keys[string_normalized] = []
						old_string_to_keys[string_normalized].append(old_key)
	
	print(f"  Built index of {len(old_string_to_keys)} unique string values in old JSON")
	
	# Match new keys to old keys based on oldString from mapping
	for new_key, old_string in new_to_old_string.items():
		old_string_normalized = old_string.strip()
		if old_string_normalized in old_string_to_keys:
			# Found matching string - use the first matching old key
			# (if multiple, prefer the one that's most similar to the new key structure)
			matching_old_keys = old_string_to_keys[old_string_normalized]
			if matching_old_keys:
				# Prefer exact match or shortest key
				best_match = min(matching_old_keys, key=len)
				new_to_old_flat_key[new_key] = best_match
	
	matched_count = len(new_to_old_flat_key)
	print(f"  Matched {matched_count} new keys to old keys based on string values (out of {len(new_to_old_string)} mappings)")
	
	# Build comparison rows
	print("Building comparison...")
	rows = []
	
	# Process each new flattened key
	for new_flat_key in sorted(new_flat.keys()):
		# Skip keys that aren't translation objects (non-dict values)
		if not isinstance(new_flat[new_flat_key], dict):
			continue
		
		# Find corresponding old flattened key by matching string values
		old_flat_key = new_to_old_flat_key.get(new_flat_key, "")
		
		# Build row
		row = {
			"old_flat_key": old_flat_key,
			"new_flat_key": new_flat_key,
		}
		
		# Get translations for each language code
		for lang_code in LANG_CODES:
			# Get old translation
			if old_flat_key:
				old_value = get_translation_value(old_flat, old_flat_key, lang_code)
			else:
				old_value = "missing key"
			
			# Get new translation
			new_value = get_translation_value(new_flat, new_flat_key, lang_code)
			
			# Column names - handle special cases
			if lang_code == "default":
				old_col = "oldDefault"
				new_col = "newDefault"
			elif lang_code == "es-CO":
				old_col = "oldesCO"
				new_col = "newesCO"
			else:
				# Keep original case and hyphens for en-US and de-DE
				old_col = f"old{lang_code}"
				new_col = f"new{lang_code}"
			
			row[old_col] = old_value
			row[new_col] = new_value
		
		rows.append(row)
	
	# Write CSV
	print(f"Writing {len(rows)} rows to {OUTPUT_CSV}...")
	# Build fieldnames matching the column name logic
	fieldnames = ["old_flat_key", "new_flat_key"]
	for lang_code in LANG_CODES:
		if lang_code == "default":
			fieldnames.extend(["oldDefault", "newDefault"])
		elif lang_code == "es-CO":
			fieldnames.extend(["oldesCO", "newesCO"])
		else:
			# Keep original case and hyphens for en-US and de-DE
			fieldnames.extend([f"old{lang_code}", f"new{lang_code}"])
	
	with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
		writer = csv.DictWriter(f, fieldnames=fieldnames)
		writer.writeheader()
		for row in rows:
			writer.writerow(row)
	
	print(f"✅ Comparison complete! Output written to {OUTPUT_CSV}")


if __name__ == "__main__":
	main()
