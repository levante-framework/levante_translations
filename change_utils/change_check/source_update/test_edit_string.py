#!/usr/bin/env python3
"""
Test script for editing source strings in Crowdin.
This script allows safe testing of the edit_string functionality before using it in production.

Usage:
    python test_edit_string.py --string-id <stringId> --new-text "New text here" [--dry-run]
"""

from crowdin_api import CrowdinClient
from change_check import config
import argparse


def main():
	CLI = argparse.ArgumentParser(
		description="Test editing a source string in Crowdin",
		formatter_class=argparse.RawDescriptionHelpFormatter,
		epilog="""
Examples:
  # Dry run - see what would change without making changes
  python test_edit_string.py --string-id 12345 --new-text "Updated text" --dry-run
  
  # Actually make the change
  python test_edit_string.py --string-id 12345 --new-text "Updated text"
  
  # Just view the current string without changing it
  python test_edit_string.py --string-id 12345
		"""
	)
	
	CLI.add_argument(
		"--string-id",
		type=int,
		required=True,
		help="Crowdin string ID to edit"
	)
	
	CLI.add_argument(
		"--new-text",
		type=str,
		help="New text to set for the source string"
	)
	
	CLI.add_argument(
		"--dry-run",
		action="store_true",
		help="Show what would change without making the actual change"
	)
	
	args = CLI.parse_args()
	
	# Initialize Crowdin client
	levanteMain = CrowdinClient(token=config.LEV_CI, project_id=config.LEV_CI_PID)
	
	# Get current string
	try:
		current_string = levanteMain.source_strings.get_string(stringId=args.string_id)
		string_data = current_string["data"]
		
		current_text = string_data.get("text", "")
		current_identifier = string_data.get("identifier", "")
		file_id = string_data.get("fileId")
		
		print(f"📋 Current String Information:")
		print(f"   String ID: {args.string_id}")
		print(f"   Identifier: {current_identifier}")
		print(f"   File ID: {file_id}")
		print(f"   Current Text: {current_text}")
		print()
		
		if not args.new_text:
			print("ℹ️  No --new-text provided. Use --new-text to specify the new text.")
			print("   Add --dry-run to see what would change without making changes.")
			return
		
		new_text = args.new_text
		
		if current_text == new_text:
			print("⚠️  New text is the same as current text. No change needed.")
			return
		
		print(f"📝 Proposed Change:")
		print(f"   FROM: {current_text}")
		print(f"   TO:   {new_text}")
		print()
		
		if args.dry_run:
			print("🏃 DRY RUN MODE - No changes will be made")
			print("   Remove --dry-run to apply the change")
		else:
			# Confirm before making change
			response = input("⚠️  Are you sure you want to update this string? (yes/no): ")
			if response.lower() != "yes":
				print("❌ Update cancelled")
				return
			
			try:
				# Make the actual change
				# The edit_string method expects a list of patch operations
				# Using JSON Patch format as per Crowdin API v2
				patch_request = [{
					"op": "replace",
					"path": "/text",
					"value": new_text
				}]
				levanteMain.source_strings.edit_string(
					stringId=args.string_id,
					data=patch_request
				)
				print(f"✅ Successfully updated string {args.string_id}")
				print(f"   New text: {new_text}")
			except Exception as e:
				print(f"❌ Failed to update string: {e}")
				print(f"   Error type: {type(e).__name__}")
				raise
		
	except Exception as e:
		print(f"❌ Error: {e}")
		raise


if __name__ == "__main__":
	main()
