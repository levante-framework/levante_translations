from pyairtable import Api
from change_check import config
from change_check import utils
import csv
import argparse
import io
from collections import defaultdict


def main():
	CLI = argparse.ArgumentParser(description="Build corpus CSV file from Airtable corpus table")
	CLI.add_argument(
		"--tasks",
		nargs="+",
		required=True,
		help="List of tasks to process. Use 'all' to process all tasks. Valid tasks: adult-reasoning, child-survey, math, hostile-attribution, matrix-reasoning, mental-rotation, same-different-selection, theory-of-mind, trog, vocab"
	)
	args = CLI.parse_args()
	
	# Mapping from CLI task names to task_id values
	task_name_to_id = {
		"adult-reasoning": "adult-reasoning",
		"child-survey": "child-survey",
		"math": "egma-math",
		"hostile-attribution": "hostile-attribution",
		"matrix-reasoning": "matrix-reasoning",
		"mental-rotation": "mental-rotation",
		"same-different-selection": "same-different-selection",
		"theory-of-mind": "theory-of-mind",
		"trog": "trog",
		"vocab": "vocab"
	}
	
	valid_task_names = set(task_name_to_id.keys())
	valid_task_names.add("all")
	
	# Validate task names
	if "all" in args.tasks and len(args.tasks) > 1:
		raise ValueError("Cannot specify 'all' with other task names. Use '--tasks all' to process all tasks.")
	
	invalid_tasks = [task for task in args.tasks if task not in valid_task_names]
	if invalid_tasks:
		raise ValueError(f"Invalid task name(s): {invalid_tasks}. Valid tasks are: {', '.join(sorted(valid_task_names))}")
	
	# Connect to Airtable
	airtableLevante = Api(config.LEV_AT_PAT)
	corpus_table = airtableLevante.table(config.LEV_AT_BASE, config.LEV_AT_CORPUSTABLE)
	
	# Field names to extract (in the order specified)
	field_names = [
		"corpus_file_name", "task_id", "task_dir", "answer", "assessment_stage",
		"audio_file", "block_index", "chance_level", "d", "difficulty", "image",
		"item", "item_id", "item_uid", "orig_item_num", "prompt", "randomize",
		"required_selections", "response_alternatives", "source", "task",
		"time_limit", "trial_num", "trial_type"
	]
	
	# Fetch all records (only the fields we need for efficiency)
	print("Fetching records from Airtable corpus table...")
	all_records = corpus_table.all(fields=field_names)
	print(f"Found {len(all_records)} records")
	
	# Extract data and validate consistency
	rows = []
	validation_errors = []
	corpus_metadata = {}  # Track corpus_file_name -> (task_id, task_dir)
	
	for record in all_records:
		fields = record["fields"]
		
		# Extract all fields (use empty string for missing fields)
		row = {}
		for field_name in field_names:
			value = fields.get(field_name, "")
			# Handle list values (e.g., from linked records) - take first value or convert to string
			if isinstance(value, list):
				row[field_name] = value[0] if value else ""
			else:
				row[field_name] = value
		
		rows.append(row)
		
		# Validate consistency: for each corpus_file_name, task_id and task_dir should be the same
		corpus_name = row.get("corpus_file_name", "")
		task_id = row.get("task_id", "")
		task_dir = row.get("task_dir", "")
		
		if corpus_name:  # Only validate if corpus_file_name exists
			if corpus_name in corpus_metadata:
				# Check if task_id and task_dir match
				expected_task_id, expected_task_dir = corpus_metadata[corpus_name]
				if task_id != expected_task_id or task_dir != expected_task_dir:
					validation_errors.append({
						"corpus_file_name": corpus_name,
						"expected": (expected_task_id, expected_task_dir),
						"found": (task_id, task_dir)
					})
			else:
				# First time seeing this corpus_file_name, store its task_id and task_dir
				corpus_metadata[corpus_name] = (task_id, task_dir)
	
	# Print validation warnings if any
	if validation_errors:
		print(f"\n⚠️  WARNING: Found {len(validation_errors)} validation errors:")
		for error in validation_errors:
			print(f"   Corpus '{error['corpus_file_name']}': expected (task_id={error['expected'][0]}, task_dir={error['expected'][1]}), "
			      f"found (task_id={error['found'][0]}, task_dir={error['found'][1]})")
	else:
		print("✅ Validation passed: All corpus_file_name entries have consistent task_id and task_dir")
	
	# Group rows by task_id (skip rows with empty task_id)
	task_id_groups = defaultdict(list)
	skipped_rows = 0
	for row in rows:
		task_id = row.get("task_id", "").strip()
		if not task_id:
			skipped_rows += 1
			continue
		task_id_groups[task_id].append(row)
	
	if skipped_rows > 0:
		print(f"\n⚠️  Skipped {skipped_rows} row(s) with empty task_id")
	print(f"\nFound {len(task_id_groups)} unique task_id values")
	
	# Filter task_id_groups based on --tasks argument
	if "all" in args.tasks:
		print(f"Processing all {len(task_id_groups)} tasks")
	else:
		# Convert task names to task_id values
		selected_task_ids = {task_name_to_id[task] for task in args.tasks}
		# Filter to only include selected tasks
		task_id_groups = {task_id: rows for task_id, rows in task_id_groups.items() if task_id in selected_task_ids}
		print(f"Filtered to {len(task_id_groups)} task(s): {', '.join(sorted(task_id_groups.keys()))}")
	
	# Fields to keep for each split file
	fields_to_keep = [
		"answer", "assessment_stage", "audio_file", "block_index", "chance_level",
		"difficulty", "item_id", "item_uid", "required_selections", "response_alternatives",
		"time_limit", "trial_num", "trial_type"
	]
	
	# Initialize GCS client (uses config.GOOGLE_APPLICATION_CREDENTIALS_JSON_DEV)
	storage_client = utils.initialize_gcs()
	bucket_name = "levante-assets-draft"
	bucket = storage_client.bucket(bucket_name)
	
	# Process and upload each task_id group
	for task_id, task_rows in task_id_groups.items():
		# Process rows: filter fields, handle difficulty/d, add downex
		processed_rows = []
		for row in task_rows:
			# Start with filtered fields
			processed_row = {}
			for field in fields_to_keep:
				processed_row[field] = row.get(field, "")
			
			# If difficulty is empty, use value from d field
			difficulty_value = processed_row.get("difficulty", "")
			# Convert to string and check if it's empty (handles None, float, etc.)
			difficulty_str = str(difficulty_value) if difficulty_value is not None else ""
			if not difficulty_str.strip():
				processed_row["difficulty"] = row.get("d", "")
			
			# Add downex column: True if "downex" appears in item, item_id, or item_uid
			item = str(row.get("item", "")).lower()
			item_id = str(row.get("item_id", "")).lower()
			item_uid = str(row.get("item_uid", "")).lower()
			processed_row["downex"] = "downex" in item or "downex" in item_id or "downex" in item_uid
			
			processed_rows.append(processed_row)
		
		# Sort field names alphabetically (including downex)
		all_fields = fields_to_keep + ["downex"]
		sorted_field_names = sorted(all_fields)
		
		# Create CSV content in memory
		csv_buffer = io.StringIO()
		writer = csv.DictWriter(csv_buffer, fieldnames=sorted_field_names, extrasaction='ignore')
		writer.writeheader()
		
		for processed_row in processed_rows:
			# Ensure all fields are present in the correct order
			ordered_row = {field: processed_row.get(field, "") for field in sorted_field_names}
			writer.writerow(ordered_row)
		
		# Get CSV content as string
		csv_content = csv_buffer.getvalue()
		csv_buffer.close()
		
		# Sanitize task_id for filename
		safe_filename = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in task_id)
		
		# Upload to GCS
		gcs_path = f"corpus/{safe_filename}.csv"
		blob = bucket.blob(gcs_path)
		blob.upload_from_string(csv_content, content_type="text/csv")
		
		print(f"✅ Uploaded {len(processed_rows)} rows to gs://{bucket_name}/{gcs_path}")
	
	print(f"\n✅ Successfully uploaded {len(task_id_groups)} task-specific CSV files to gs://{bucket_name}/corpus/")


if __name__ == "__main__":
	main()
