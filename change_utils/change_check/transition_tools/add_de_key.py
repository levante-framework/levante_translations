import json
from pathlib import Path
from change_check import utils, config


def unflatten_custom(flat_dict):
	"""
	Unflatten a dictionary that was flattened using flatten_custom.
	Reverses the flatten_custom process.
	Keys are in format like: "pages_0_elements_0_html" or "logoPosition"
	"""
	result = {}
	
	for key, value in flat_dict.items():
		# Split the key by underscores
		parts = key.split('_')
		
		# Navigate/create the nested structure
		# Root is always a dict
		current = result
		
		for i, part in enumerate(parts):
			is_last = (i == len(parts) - 1)
			
			# Check if this part is a number (list index)
			if part.isdigit():
				idx = int(part)
				# Current should be a list at this point
				if not isinstance(current, list):
					raise ValueError(f"Expected list at position {i} for key '{key}', but got {type(current).__name__}")
				
				# Extend list if needed
				while len(current) <= idx:
					current.append(None)
				
				if is_last:
					# Last part - set the value
					current[idx] = value
				else:
					# Not last - need to navigate deeper
					next_part = parts[i + 1]
					if next_part.isdigit():
						# Next is a list index, so current[idx] should be a list
						if current[idx] is None or not isinstance(current[idx], list):
							current[idx] = []
					else:
						# Next is a dict key, so current[idx] should be a dict
						if current[idx] is None or not isinstance(current[idx], dict):
							current[idx] = {}
					current = current[idx]
			else:
				# This is a dict key
				if not isinstance(current, dict):
					raise ValueError(f"Expected dict at position {i} for key '{key}', but got {type(current).__name__}")
				
				if is_last:
					# Last part - set the value
					current[part] = value
				else:
					# Not last - need to navigate deeper
					next_part = parts[i + 1]
					if next_part.isdigit():
						# Next is a list index, so current[part] should be a list
						if part not in current or current[part] is None:
							current[part] = []
						elif not isinstance(current[part], list):
							current[part] = []
						current = current[part]
					else:
						# Next is a dict key, so current[part] should be a dict
						if part not in current or current[part] is None:
							current[part] = {}
						elif not isinstance(current[part], dict):
							current[part] = {}
						current = current[part]
	
	return result


def add_de_key_to_flattened(flat_dict):
	"""
	Add a 'de' key with the same value as 'de-DE' wherever 'de-DE' exists
	in translation dictionaries (dicts that have 'default', 'en-US', and 'de-DE' keys).
	"""
	modified = {}
	
	for key, value in flat_dict.items():
		if isinstance(value, dict):
			# Check if this is a translation dict (has default, en-US, de-DE)
			if "default" in value and "en-US" in value and "de-DE" in value:
				# Create a copy and add 'de' key
				new_value = value.copy()
				if "de-DE" in new_value:
					new_value["de"] = new_value["de-DE"]
				modified[key] = new_value
			else:
				# Not a translation dict, keep as is
				modified[key] = value
		else:
			# Not a dict, keep as is
			modified[key] = value
	
	return modified


def main():
	# File paths
	TRANSITION_TOOLS_DIR = Path(__file__).parent
	bucket_name = "levante-assets-draft"
	
	# Files to process
	files_to_process = [
		("caregiver-child", "surveys/caregiver-child-draft.json"),
		("caregiver-family", "surveys/caregiver-family-draft.json"),
	]
	
	# Initialize GCS client
	storage_client = utils.initialize_gcs()
	bucket = storage_client.bucket(bucket_name)
	
	for survey_name, gcs_path in files_to_process:
		print(f"\nProcessing {survey_name}...")
		
		# Download from GCS
		print(f"  Downloading from gs://{bucket_name}/{gcs_path}...")
		blob = bucket.blob(gcs_path)
		if not blob.exists():
			print(f"  ⚠️  File not found: {gcs_path}")
			continue
		
		json_content = blob.download_as_text()
		data = json.loads(json_content)
		
		# Flatten using flatten_custom
		print(f"  Flattening JSON...")
		flat_data = utils.flatten_custom(data)
		print(f"    Found {len(flat_data)} flattened keys")
		
		# Add 'de' key where 'de-DE' exists
		print(f"  Adding 'de' keys...")
		modified_flat = add_de_key_to_flattened(flat_data)
		
		# Count how many 'de' keys were added
		added_count = 0
		for key, value in modified_flat.items():
			if isinstance(value, dict) and "de" in value and "de-DE" in value:
				added_count += 1
		print(f"    Added 'de' key to {added_count} translation objects")
		
		# Unflatten
		print(f"  Unflattening JSON...")
		unflattened_data = unflatten_custom(modified_flat)
		
		# Write locally
		output_file = TRANSITION_TOOLS_DIR / f"{survey_name}-draft-with-de.json"
		print(f"  Writing to {output_file}...")
		with open(output_file, "w", encoding="utf-8") as f:
			json.dump(unflattened_data, f, indent=2, ensure_ascii=False)
		
		print(f"  ✅ Completed {survey_name}")
	
	print(f"\n✅ All files processed!")


if __name__ == "__main__":
	main()
