#!/usr/bin/env python3
"""
Simple script to upload the edited item-bank-translations.csv back to the GCS bucket.
"""

import os
import subprocess
import sys
from datetime import datetime

def backup_original():
    """Create a backup of the original file in the bucket"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"item-bank-translations-backup-{timestamp}.csv"
    
    print(f"Creating backup: {backup_name}")
    
    # Copy current version to backup
    cmd = [
        "gsutil", "cp",
        "gs://levante-dashboard-prod/item-bank-translations.csv",
        f"gs://levante-dashboard-prod/{backup_name}"
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"✓ Backup created successfully: {backup_name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to create backup: {e}")
        print(f"Error output: {e.stderr}")
        return False

def upload_csv():
    """Upload the local CSV file to the bucket"""
    local_file = "item-bank-translations.csv"
    
    if not os.path.exists(local_file):
        print(f"✗ Local file {local_file} not found!")
        return False
    
    print(f"Uploading {local_file} to gs://levante-dashboard-prod/item-bank-translations.csv")
    
    # Upload the file
    cmd = [
        "gsutil", "cp",
        local_file,
        "gs://levante-dashboard-prod/item-bank-translations.csv"
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✓ File uploaded successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to upload file: {e}")
        print(f"Error output: {e.stderr}")
        return False

def main():
    print("Item Bank Translations Upload Script")
    print("====================================")
    print()
    
    # Check if local file exists
    if not os.path.exists("item-bank-translations.csv"):
        print("✗ Local file 'item-bank-translations.csv' not found!")
        print("Please make sure you have the file in the current directory.")
        sys.exit(1)
    
    # Show file info
    print(f"Local file size: {os.path.getsize('item-bank-translations.csv')} bytes")
    
    # Confirm with user
    response = input("\nDo you want to proceed with uploading? This will replace the file in the bucket. (y/N): ")
    if response.lower() != 'y':
        print("Upload cancelled.")
        sys.exit(0)
    
    # Create backup first
    if not backup_original():
        print("Failed to create backup. Aborting upload for safety.")
        sys.exit(1)
    
    # Upload the file
    if upload_csv():
        print("\n✓ Upload completed successfully!")
        print("The file has been updated in gs://levante-dashboard-prod/item-bank-translations.csv")
    else:
        print("\n✗ Upload failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
