import csv
import os
from collections import defaultdict


def split_corpus_by_task_dir(csv_filename="corpus_all.csv", output_dir="corpus_by_task"):
	"""
	Split corpus_all.csv into separate files based on task_id.
	
	Args:
		csv_filename: Path to the corpus_all.csv file
		output_dir: Directory to write task-specific CSV files
	"""
	if not os.path.exists(csv_filename):
		raise FileNotFoundError(f"Corpus file not found: {csv_filename}")
	
	# Create output directory if it doesn't exist
	os.makedirs(output_dir, exist_ok=True)
	
	# Group rows by task_id
	task_id_groups = defaultdict(list)
	field_names = None
	
	print(f"Reading {csv_filename}...")
	with open(csv_filename, 'r', encoding='utf-8') as csvfile:
		reader = csv.DictReader(csvfile)
		field_names = reader.fieldnames
		
		for row in reader:
			task_id = row.get("task_id", "").strip()
			if not task_id:
				task_id = "_no_task_id"
			
			task_id_groups[task_id].append(row)
	
	print(f"Found {len(task_id_groups)} unique task_id values")
	
	# Write separate CSV files for each task_id
	sorted_field_names = sorted(field_names) if field_names else []
	
	for task_id, rows in task_id_groups.items():
		# Sanitize task_id for filename
		safe_filename = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in task_id)
		output_filename = os.path.join(output_dir, f"{safe_filename}.csv")
		
		print(f"Writing {len(rows)} rows to {output_filename}...")
		with open(output_filename, 'w', encoding='utf-8', newline='') as outfile:
			writer = csv.DictWriter(outfile, fieldnames=sorted_field_names, extrasaction='ignore')
			writer.writeheader()
			
			for row in rows:
				ordered_row = {field: row.get(field, "") for field in sorted_field_names}
				writer.writerow(ordered_row)
		
		# Verify file was created
		if os.path.exists(output_filename):
			file_size = os.path.getsize(output_filename)
			print(f"  ✅ Created: {os.path.abspath(output_filename)} ({file_size} bytes)")
		else:
			print(f"  ⚠️  WARNING: File was not created: {output_filename}")
	
	print(f"\n✅ Successfully created {len(task_id_groups)} task-specific CSV files in {output_dir}/")


def main():
	"""Main function for console script entry point."""
	import sys
	
	# Allow custom input/output paths
	csv_file = sys.argv[1] if len(sys.argv) > 1 else "corpus_all.csv"
	output_dir = sys.argv[2] if len(sys.argv) > 2 else "corpus_by_task"
	
	split_corpus_by_task_dir(csv_file, output_dir)


if __name__ == "__main__":
	main()
