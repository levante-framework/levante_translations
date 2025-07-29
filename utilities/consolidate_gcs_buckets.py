#!/usr/bin/env python3
"""
Script to consolidate audio files from all dev task buckets into the dev audio bucket.
Copies files from Google Cloud Storage task-specific buckets and organizes them by language.
Uses simplified structure: language/filename.mp3 (no "shared" subfolder)
"""

import os
import sys
from typing import List, Dict, Optional
from google.cloud import storage
from google.api_core import exceptions

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import bucket constants directly
TASK_BUCKET_NAMES_DEV = {
    'intro': 'levante-intro-dev',
    'vocab': 'levante-vocabulary-dev',
    'memorygame': 'levante-memory-dev',
    'roarinference': 'roar-inference',
    'adultreasoning': 'levante-math-dev',
    'heartsandflowers': 'levante-hearts-and-flowers-dev',
    'egmamath': 'levante-math-dev',
    'matrixreasoning': 'levante-pattern-matching-dev',
    'samedifferentselection': 'levante-same-different-dev',
    'trog': 'levante-sentence-understanding-dev',
    'mentalrotation': 'levante-shape-rotation-dev',
    'theoryofmind': 'levante-stories-dev',
    'shared': 'levante-tasks-shared-dev',
}

AUDIO_BUCKET_NAME_DEV = 'levante-audio-dev'

# Language codes to consolidate
LANGUAGE_CODES = ['en', 'en-US', 'es', 'es-CO', 'de', 'de-DE', 'fr', 'fr-CA', 'nl', 'nl-NL']


class GCSBucketConsolidator:
    """Class to handle Google Cloud Storage bucket consolidation operations."""
    
    def __init__(self, project_id: Optional[str] = None):
        """
        Initialize the GCS client.
        
        Args:
            project_id: Google Cloud Project ID. If None, uses default from environment.
        """
        try:
            if project_id:
                self.client = storage.Client(project=project_id)
            else:
                self.client = storage.Client()
            self.project_id = self.client.project
            print(f"Initialized GCS client for project: {self.project_id}")
        except Exception as e:
            print(f"Error initializing GCS client: {e}")
            print("Make sure you have Google Cloud credentials configured.")
            print("Run: gcloud auth application-default login")
            raise
    
    def list_bucket_files(self, bucket_name: str, prefix: str = "") -> List[str]:
        """
        List all files in a GCS bucket with optional prefix.
        
        Args:
            bucket_name: Name of the GCS bucket
            prefix: Optional prefix to filter files
            
        Returns:
            List of blob names (file paths) in the bucket
        """
        try:
            bucket = self.client.bucket(bucket_name)
            blobs = bucket.list_blobs(prefix=prefix)
            return [blob.name for blob in blobs if blob.name.endswith('.mp3')]
        except exceptions.NotFound:
            print(f"Warning: Bucket {bucket_name} not found")
            return []
        except Exception as e:
            print(f"Error listing files in bucket {bucket_name}: {e}")
            return []
    
    def copy_blob(self, source_bucket_name: str, source_blob_name: str, 
                  dest_bucket_name: str, dest_blob_name: str) -> bool:
        """
        Copy a blob from one bucket to another, only if source is newer than destination.
        
        Args:
            source_bucket_name: Source bucket name
            source_blob_name: Source blob (file) name
            dest_bucket_name: Destination bucket name
            dest_blob_name: Destination blob (file) name
            
        Returns:
            True if successful, False otherwise
        """
        try:
            source_bucket = self.client.bucket(source_bucket_name)
            source_blob = source_bucket.blob(source_blob_name)
            dest_bucket = self.client.bucket(dest_bucket_name)
            dest_blob = dest_bucket.blob(dest_blob_name)
            
            # Check if source blob exists
            if not source_blob.exists():
                print(f"    Warning: Source file {source_blob_name} does not exist")
                return False
            
            # Refresh source blob to get current metadata
            source_blob.reload()
            
            # Check if destination blob already exists
            if dest_blob.exists():
                # Refresh destination blob to get current metadata
                dest_blob.reload()
                
                # Compare modification times
                source_updated = source_blob.updated
                dest_updated = dest_blob.updated
                
                if source_updated <= dest_updated:
                    print(f"    Skipping {dest_blob_name} (destination is newer or same age)")
                    return True
                else:
                    print(f"    Updating {dest_blob_name} (source is newer: {source_updated} > {dest_updated})")
            else:
                print(f"    New file: {dest_blob_name}")
            
            # Copy the blob
            source_bucket.copy_blob(source_blob, dest_bucket, dest_blob_name)
            print(f"    Copied: {source_blob_name} -> {dest_blob_name}")
            return True
            
        except Exception as e:
            print(f"    Error copying {source_blob_name}: {e}")
            return False
    
    def get_language_files(self, bucket_name: str) -> Dict[str, List[str]]:
        """
        Get all audio files from a bucket, organized by language.
        Looks for files in both old (language/shared/) and new (language/) structures.
        
        Args:
            bucket_name: Name of the GCS bucket
            
        Returns:
            Dictionary mapping language codes to lists of file paths
        """
        files_by_language = {}
        
        for lang_code in LANGUAGE_CODES:
            # Look for files in the new simplified structure: language/
            prefix_new = f"{lang_code}/"
            files_new = self.list_bucket_files(bucket_name, prefix_new)
            
            # Look for files in the old structure: language/shared/
            prefix_old = f"{lang_code}/shared/"
            files_old = self.list_bucket_files(bucket_name, prefix_old)
            
            # Combine files from both structures
            all_files = files_new + files_old
            
            if all_files:
                files_by_language[lang_code] = all_files
                print(f"  Found {len(all_files)} files for {bucket_name}/{lang_code} (new: {len(files_new)}, old: {len(files_old)})")
        
        return files_by_language
    
    def ensure_bucket_exists(self, bucket_name: str) -> bool:
        """
        Ensure a bucket exists, create if it doesn't.
        
        Args:
            bucket_name: Name of the bucket to check/create
            
        Returns:
            True if bucket exists or was created, False otherwise
        """
        try:
            bucket = self.client.bucket(bucket_name)
            if not bucket.exists():
                print(f"Creating bucket: {bucket_name}")
                bucket = self.client.create_bucket(bucket_name)
            return True
        except Exception as e:
            print(f"Error with bucket {bucket_name}: {e}")
            return False
    
    def consolidate_buckets(self, target_bucket_name: str = None, 
                           add_task_prefix: bool = False, 
                           dry_run: bool = False,
                           force_copy: bool = False) -> None:
        """
        Main function to consolidate audio files from all dev task buckets.
        Files are organized as: language/filename.mp3 (no "shared" subfolder)
        
        Args:
            target_bucket_name: Name of target bucket (defaults to AUDIO_BUCKET_NAME_DEV)
            add_task_prefix: Whether to add task name prefix to avoid filename conflicts
            dry_run: If True, only show what would be copied without actually copying
            force_copy: If True, copy all files regardless of timestamps
        """
        if not target_bucket_name:
            target_bucket_name = AUDIO_BUCKET_NAME_DEV
        
        print(f"Starting GCS bucket consolidation to: {target_bucket_name}")
        print(f"Using simplified structure: language/filename.mp3 (no 'shared' subfolder)")
        print(f"Add task prefix: {add_task_prefix}")
        print(f"Dry run: {dry_run}")
        print(f"Force copy (ignore timestamps): {force_copy}")
        print("-" * 60)
        
        # Ensure target bucket exists
        if not dry_run and not self.ensure_bucket_exists(target_bucket_name):
            print(f"Failed to ensure target bucket {target_bucket_name} exists")
            return
        
        total_files_copied = 0
        total_files_skipped = 0
        total_files_updated = 0
        total_files_new = 0
        total_tasks_processed = 0
        
        # Process each task bucket
        for task_name, bucket_name in TASK_BUCKET_NAMES_DEV.items():
            print(f"\nProcessing task: {task_name} (bucket: {bucket_name})")
            
            # Get audio files for this task
            files_by_language = self.get_language_files(bucket_name)
            
            if not files_by_language:
                print(f"  No audio files found in bucket: {bucket_name}")
                continue
            
            total_tasks_processed += 1
            task_files_copied = 0
            task_files_skipped = 0
            task_files_updated = 0
            task_files_new = 0
            
            # Copy files for each language
            for lang_code, audio_files in files_by_language.items():
                print(f"  Processing {len(audio_files)} files for language: {lang_code}")
                
                for source_file in audio_files:
                    # Extract filename from the full path
                    filename = os.path.basename(source_file)
                    
                    # Add task prefix if requested
                    if add_task_prefix:
                        name, ext = os.path.splitext(filename)
                        filename = f"{task_name}_{name}{ext}"
                    
                    # Construct destination path: lang_code/filename (no "shared" subfolder)
                    dest_path = f"{lang_code}/{filename}"
                    
                    if dry_run:
                        print(f"    Would copy: {bucket_name}/{source_file} -> {target_bucket_name}/{dest_path}")
                        task_files_copied += 1
                    else:
                        # Check if we should use force copy mode
                        if force_copy:
                            # Force copy mode - use the original simple copy logic
                            if self.copy_blob_force(bucket_name, source_file, target_bucket_name, dest_path):
                                task_files_copied += 1
                                task_files_new += 1  # Count as new since we're forcing
                        else:
                            # Normal copy with timestamp checking
                            result = self.copy_blob_with_status(bucket_name, source_file, target_bucket_name, dest_path)
                            if result['copied']:
                                task_files_copied += 1
                                if result['status'] == 'new':
                                    task_files_new += 1
                                elif result['status'] == 'updated':
                                    task_files_updated += 1
                            elif result['status'] == 'skipped':
                                task_files_skipped += 1
            
            # Update totals
            total_files_copied += task_files_copied
            total_files_skipped += task_files_skipped
            total_files_updated += task_files_updated
            total_files_new += task_files_new
            
            print(f"  Task {task_name} results: {task_files_copied} copied, {task_files_skipped} skipped")
            if not force_copy and not dry_run:
                print(f"    (New: {task_files_new}, Updated: {task_files_updated})")
        
        print("\n" + "=" * 60)
        print(f"Consolidation {'simulation' if dry_run else 'operation'} completed!")
        print(f"Tasks processed: {total_tasks_processed}")
        
        if dry_run:
            print(f"Total files that would be copied: {total_files_copied}")
        else:
            print(f"Total files copied: {total_files_copied}")
            if not force_copy:
                print(f"  New files: {total_files_new}")
                print(f"  Updated files: {total_files_updated}")
                print(f"  Skipped files (up to date): {total_files_skipped}")
        
        print(f"Target bucket: {target_bucket_name}")
        print(f"Structure: language/filename.mp3 (simplified, no 'shared' subfolder)")
    
    def copy_blob_force(self, source_bucket_name: str, source_blob_name: str, 
                       dest_bucket_name: str, dest_blob_name: str) -> bool:
        """
        Force copy a blob without timestamp checking (original simple logic).
        
        Args:
            source_bucket_name: Source bucket name
            source_blob_name: Source blob (file) name
            dest_bucket_name: Destination bucket name
            dest_blob_name: Destination blob (file) name
            
        Returns:
            True if successful, False otherwise
        """
        try:
            source_bucket = self.client.bucket(source_bucket_name)
            source_blob = source_bucket.blob(source_blob_name)
            dest_bucket = self.client.bucket(dest_bucket_name)
            
            # Check if destination blob already exists
            dest_blob = dest_bucket.blob(dest_blob_name)
            if dest_blob.exists():
                print(f"    Overwriting: {dest_blob_name}")
            else:
                print(f"    New file: {dest_blob_name}")
            
            # Copy the blob
            source_bucket.copy_blob(source_blob, dest_bucket, dest_blob_name)
            print(f"    Copied: {source_blob_name} -> {dest_blob_name}")
            return True
            
        except Exception as e:
            print(f"    Error copying {source_blob_name}: {e}")
            return False
    
    def copy_blob_with_status(self, source_bucket_name: str, source_blob_name: str, 
                             dest_bucket_name: str, dest_blob_name: str) -> dict:
        """
        Copy a blob with detailed status information.
        
        Args:
            source_bucket_name: Source bucket name
            source_blob_name: Source blob (file) name
            dest_bucket_name: Destination bucket name
            dest_blob_name: Destination blob (file) name
            
        Returns:
            dict: {'copied': bool, 'status': str} where status is 'new', 'updated', 'skipped', or 'error'
        """
        try:
            source_bucket = self.client.bucket(source_bucket_name)
            source_blob = source_bucket.blob(source_blob_name)
            dest_bucket = self.client.bucket(dest_bucket_name)
            dest_blob = dest_bucket.blob(dest_blob_name)
            
            # Check if source blob exists
            if not source_blob.exists():
                print(f"    Warning: Source file {source_blob_name} does not exist")
                return {'copied': False, 'status': 'error'}
            
            # Refresh source blob to get current metadata
            source_blob.reload()
            
            # Check if destination blob already exists
            if dest_blob.exists():
                # Refresh destination blob to get current metadata
                dest_blob.reload()
                
                # Compare modification times
                source_updated = source_blob.updated
                dest_updated = dest_blob.updated
                
                if source_updated <= dest_updated:
                    print(f"    Skipping {dest_blob_name} (destination is newer or same age)")
                    return {'copied': False, 'status': 'skipped'}
                else:
                    print(f"    Updating {dest_blob_name} (source is newer: {source_updated} > {dest_updated})")
                    # Copy the blob
                    source_bucket.copy_blob(source_blob, dest_bucket, dest_blob_name)
                    print(f"    Updated: {source_blob_name} -> {dest_blob_name}")
                    return {'copied': True, 'status': 'updated'}
            else:
                print(f"    New file: {dest_blob_name}")
                # Copy the blob
                source_bucket.copy_blob(source_blob, dest_bucket, dest_blob_name)
                print(f"    Copied: {source_blob_name} -> {dest_blob_name}")
                return {'copied': True, 'status': 'new'}
            
        except Exception as e:
            print(f"    Error copying {source_blob_name}: {e}")
            return {'copied': False, 'status': 'error'}
    
    def list_consolidation_summary(self, target_bucket_name: str = None) -> None:
        """
        List summary of consolidated files by language.
        
        Args:
            target_bucket_name: Name of target bucket to analyze
        """
        if not target_bucket_name:
            target_bucket_name = AUDIO_BUCKET_NAME_DEV
        
        print(f"Consolidation summary for bucket: {target_bucket_name}")
        print("Structure: language/filename.mp3 (simplified)")
        print("-" * 40)
        
        total_files = 0
        
        for lang_code in LANGUAGE_CODES:
            # Look for files directly in the language folder (simplified structure)
            prefix = f"{lang_code}/"
            files = self.list_bucket_files(target_bucket_name, prefix)
            # Filter out any files that might be in subdirectories
            files = [f for f in files if f.count('/') == 1 and f.endswith('.mp3')]
            file_count = len(files)
            total_files += file_count
            
            if file_count > 0:
                print(f"  {lang_code}: {file_count} files")
        
        print(f"\nTotal files in consolidated bucket: {total_files}")
    
    def clean_consolidated_bucket(self, target_bucket_name: str = None, 
                                 confirm: bool = False) -> None:
        """
        Clean/remove all files from the consolidated audio bucket.
        
        Args:
            target_bucket_name: Name of target bucket to clean
            confirm: Whether to skip confirmation prompt
        """
        if not target_bucket_name:
            target_bucket_name = AUDIO_BUCKET_NAME_DEV
        
        if not confirm:
            response = input(f"Are you sure you want to delete all files from bucket {target_bucket_name}? (yes/no): ")
            if response.lower() != 'yes':
                print("Operation cancelled.")
                return
        
        try:
            bucket = self.client.bucket(target_bucket_name)
            blobs = bucket.list_blobs()
            
            deleted_count = 0
            for blob in blobs:
                blob.delete()
                deleted_count += 1
                print(f"Deleted: {blob.name}")
            
            print(f"Successfully deleted {deleted_count} files from bucket: {target_bucket_name}")
            
        except exceptions.NotFound:
            print(f"Bucket {target_bucket_name} not found.")
        except Exception as e:
            print(f"Error cleaning bucket: {e}")


def main():
    """Main function with command line argument parsing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Consolidate audio files from GCS task buckets")
    parser.add_argument('--action', choices=['consolidate', 'summary', 'clean'], 
                       default='consolidate', help='Action to perform')
    parser.add_argument('--target-bucket', type=str, 
                       help=f'Target bucket name (default: {AUDIO_BUCKET_NAME_DEV})')
    parser.add_argument('--add-prefix', action='store_true', 
                       help='Add task name prefix to filenames to avoid conflicts')
    parser.add_argument('--confirm-clean', action='store_true',
                       help='Skip confirmation when cleaning')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be copied without actually copying')
    parser.add_argument('--force-copy', action='store_true',
                       help='Force copy files regardless of timestamp checks')
    parser.add_argument('--project-id', type=str,
                       help='Google Cloud Project ID (if not using default)')
    
    args = parser.parse_args()
    
    try:
        # Initialize the consolidator
        consolidator = GCSBucketConsolidator(project_id=args.project_id)
        
        if args.action == 'consolidate':
            consolidator.consolidate_buckets(
                target_bucket_name=args.target_bucket, 
                add_task_prefix=args.add_prefix,
                dry_run=args.dry_run,
                force_copy=args.force_copy
            )
        elif args.action == 'summary':
            consolidator.list_consolidation_summary(args.target_bucket)
        elif args.action == 'clean':
            consolidator.clean_consolidated_bucket(args.target_bucket, args.confirm_clean)
        
        print("\nScript completed!")
        
    except Exception as e:
        print(f"Script failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main()) 