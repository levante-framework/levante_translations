import csv
import json
from pathlib import Path
from change_check import utils, config


def get_translation_value(flat_data, flat_key, lang_code):
	"""Get translation value for a given flattened key and language code."""
	if not flat_key or flat_key not in flat_data:
		return None
	
	value = flat_data[flat_key]
	
	# If the value is a dict (translation object), get the language code from it
	if isinstance(value, dict):
		return value.get(lang_code)
	
	# If it's not a dict, it's probably not a translation object
	return None


def main():
	# File paths
	caregiver_file = "caregiver-family-draft-with-de.json"
	parent_file = "surveybackup/parent_survey_family.json"
	output_csv = "caregiver_family_backup_comparison.csv"
	
	# Check if files exist
	#if not caregiver_file.exists():
	#	raise FileNotFoundError(f"Caregiver file not found: {caregiver_file}")
	#if not parent_file.exists():
	#	raise FileNotFoundError(f"Parent file not found: {parent_file}")
	
	# Load and flatten caregiver file
	print(f"Loading and flattening caregiver file: {caregiver_file}...")
	with open(caregiver_file, "r", encoding="utf-8") as f:
		caregiver_data = json.load(f)
	caregiver_flat = utils.flatten_custom(caregiver_data)
	print(f"  Found {len(caregiver_flat)} flattened keys in caregiver file")
	
	# Load and flatten parent file
	print(f"Loading and flattening parent file: {parent_file}...")
	with open(parent_file, "r", encoding="utf-8") as f:
		parent_data = json.load(f)
	parent_flat = utils.flatten_custom(parent_data)
	print(f"  Found {len(parent_flat)} flattened keys in parent file")
	
	# Get all keys that exist in both files
	common_keys = set(caregiver_flat.keys()) & set(parent_flat.keys())
	print(f"  Found {len(common_keys)} common keys")
	
	# Comparison rules: (caregiver_lang, parent_lang, description)
	comparisons = [
		("es-CO", "es", "caregiver es-CO vs parent es"),
		("es-CO", "es-CO", "caregiver es-CO vs parent es-CO"),
		("en-US", "default", "caregiver en-US vs parent default"),
		("en-US", "en", "caregiver en-US vs parent en"),
		("en-US", "en-US", "caregiver en-US vs parent en-US"),
	]
	
	# Collect differences
	differences = []
	
	print("\nComparing translations...")
	for key in sorted(common_keys):
		caregiver_value = caregiver_flat.get(key)
		parent_value = parent_flat.get(key)
		
		# Skip if either value is not a dict (not a translation object)
		if not isinstance(caregiver_value, dict) or not isinstance(parent_value, dict):
			continue
		
		# Perform each comparison
		for caregiver_lang, parent_lang, description in comparisons:
			caregiver_text = get_translation_value(caregiver_flat, key, caregiver_lang)
			parent_text = get_translation_value(parent_flat, key, parent_lang)
			
			# Skip if caregiver doesn't have the language
			if caregiver_text is None:
				continue
			
			# Skip if parent doesn't have the language (for conditional comparisons)
			if parent_text is None:
				continue
			
			# Compare values
			if caregiver_text != parent_text:
				differences.append({
					"key": key,
					"comparison": description,
					"caregiver_lang": caregiver_lang,
					"parent_lang": parent_lang,
					"caregiver_value": caregiver_text,
					"parent_value": parent_text,
				})
	
	print(f"  Found {len(differences)} differences")
	
	# Write to CSV
	if differences:
		print(f"\nWriting differences to {output_csv}...")
		fieldnames = ["key", "comparison", "caregiver_lang", "parent_lang", "caregiver_value", "parent_value"]
		with open(output_csv, "w", newline="", encoding="utf-8") as f:
			writer = csv.DictWriter(f, fieldnames=fieldnames)
			writer.writeheader()
			writer.writerows(differences)
		print(f"✅ Wrote {len(differences)} differences to {output_csv}")
	else:
		print("\n✅ No differences found!")


if __name__ == "__main__":
	main()
