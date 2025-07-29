#!/usr/bin/env python3
"""
Script to consolidate audio files from all dev task buckets into the dev audio bucket.
Copies files from task-specific buckets and organizes them by language (en, es, de, fr, nl, etc.).
"""

import os
import sys
import shutil
import glob
from typing import List, Dict

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

# Base directory for audio files (adjust as needed)
AUDIO_BASE_DIR = 'audio_files'


def get_task_audio_files(task_name: str) -> Dict[str, List[str]]:
    """
    Get all audio files for a specific task, organized by language.
    
    Args:
        task_name: Name of the task (folder name in audio_files)
        
    Returns:
        Dictionary mapping language codes to lists of audio file paths
    """
    files_by_language = {}
    
    for lang_code in LANGUAGE_CODES:
        # Pattern to find audio files for this task and language
        pattern = os.path.join(AUDIO_BASE_DIR, task_name, lang_code, 'shared', '*.mp3')
        audio_files = glob.glob(pattern)
        
        if audio_files:
            files_by_language[lang_code] = audio_files
            print(f"  Found {len(audio_files)} files for {task_name}/{lang_code}")
    
    return files_by_language


def create_consolidated_structure(target_base_dir: str) -> Dict[str, str]:
    """
    Create the consolidated directory structure for the audio bucket.
    
    Args:
        target_base_dir: Base directory for the consolidated audio bucket
        
    Returns:
        Dictionary mapping language codes to their target directories
    """
    target_dirs = {}
    
    for lang_code in LANGUAGE_CODES:
        target_dir = os.path.join(target_base_dir, lang_code, 'shared')
        os.makedirs(target_dir, exist_ok=True)
        target_dirs[lang_code] = target_dir
        print(f"Created directory: {target_dir}")
    
    return target_dirs


def copy_audio_files(source_files: List[str], target_dir: str, task_prefix: str = None) -> int:
    """
    Copy audio files to the target directory.
    
    Args:
        source_files: List of source file paths
        target_dir: Target directory path
        task_prefix: Optional prefix to add to filename to avoid conflicts
        
    Returns:
        Number of files successfully copied
    """
    copied_count = 0
    
    for source_file in source_files:
        try:
            filename = os.path.basename(source_file)
            
            # Add task prefix if provided to avoid filename conflicts
            if task_prefix:
                name, ext = os.path.splitext(filename)
                filename = f"{task_prefix}_{name}{ext}"
            
            target_file = os.path.join(target_dir, filename)
            
            # Check if file already exists and is identical
            if os.path.exists(target_file):
                if os.path.getsize(source_file) == os.path.getsize(target_file):
                    print(f"    Skipping {filename} (already exists with same size)")
                    continue
                else:
                    # File exists but different size - add task prefix to avoid overwrite
                    if not task_prefix:
                        name, ext = os.path.splitext(filename)
                        task_name = source_file.split(os.sep)[-4]  # Extract task name from path
                        filename = f"{task_name}_{name}{ext}"
                        target_file = os.path.join(target_dir, filename)
            
            # Copy the file
            shutil.copy2(source_file, target_file)
            copied_count += 1
            print(f"    Copied: {filename}")
            
        except Exception as e:
            print(f"    Error copying {source_file}: {e}")
    
    return copied_count


def consolidate_audio_buckets(target_bucket_name: str = None, add_task_prefix: bool = False):
    """
    Main function to consolidate audio files from all dev task buckets.
    
    Args:
        target_bucket_name: Name of target bucket (defaults to AUDIO_BUCKET_NAME_DEV)
        add_task_prefix: Whether to add task name prefix to avoid filename conflicts
    """
    if not target_bucket_name:
        target_bucket_name = AUDIO_BUCKET_NAME_DEV
    
    print(f"Starting audio consolidation to bucket: {target_bucket_name}")
    print(f"Source base directory: {AUDIO_BASE_DIR}")
    print(f"Add task prefix: {add_task_prefix}")
    print("-" * 60)
    
    # Create target directory structure
    target_base_dir = os.path.join(AUDIO_BASE_DIR, target_bucket_name)
    target_dirs = create_consolidated_structure(target_base_dir)
    
    total_files_copied = 0
    total_tasks_processed = 0
    
    # Process each task bucket
    for task_name, bucket_name in TASK_BUCKET_NAMES_DEV.items():
        print(f"\nProcessing task: {task_name} (bucket: {bucket_name})")
        
        # Check if task directory exists in audio_files
        task_dir = os.path.join(AUDIO_BASE_DIR, task_name)
        if not os.path.exists(task_dir):
            print(f"  Warning: Task directory {task_dir} not found, skipping...")
            continue
        
        # Get audio files for this task
        files_by_language = get_task_audio_files(task_name)
        
        if not files_by_language:
            print(f"  No audio files found for task: {task_name}")
            continue
        
        total_tasks_processed += 1
        task_files_copied = 0
        
        # Copy files for each language
        for lang_code, audio_files in files_by_language.items():
            if lang_code in target_dirs:
                target_dir = target_dirs[lang_code]
                task_prefix = task_name if add_task_prefix else None
                
                copied_count = copy_audio_files(audio_files, target_dir, task_prefix)
                task_files_copied += copied_count
                total_files_copied += copied_count
        
        print(f"  Copied {task_files_copied} files from {task_name}")
    
    print("\n" + "=" * 60)
    print(f"Consolidation completed!")
    print(f"Tasks processed: {total_tasks_processed}")
    print(f"Total files copied: {total_files_copied}")
    print(f"Target bucket: {target_bucket_name}")
    print(f"Target directory: {target_base_dir}")


def list_consolidation_summary(target_bucket_name: str = None):
    """
    List summary of consolidated files by language.
    
    Args:
        target_bucket_name: Name of target bucket to analyze
    """
    if not target_bucket_name:
        target_bucket_name = AUDIO_BUCKET_NAME_DEV
    
    target_base_dir = os.path.join(AUDIO_BASE_DIR, target_bucket_name)
    
    print(f"Consolidation summary for: {target_bucket_name}")
    print("-" * 40)
    
    total_files = 0
    
    for lang_code in LANGUAGE_CODES:
        lang_dir = os.path.join(target_base_dir, lang_code, 'shared')
        if os.path.exists(lang_dir):
            audio_files = glob.glob(os.path.join(lang_dir, '*.mp3'))
            file_count = len(audio_files)
            total_files += file_count
            
            if file_count > 0:
                print(f"  {lang_code}: {file_count} files")
    
    print(f"\nTotal files in consolidated bucket: {total_files}")


def clean_consolidated_bucket(target_bucket_name: str = None, confirm: bool = False):
    """
    Clean/remove the consolidated audio bucket directory.
    
    Args:
        target_bucket_name: Name of target bucket to clean
        confirm: Whether to skip confirmation prompt
    """
    if not target_bucket_name:
        target_bucket_name = AUDIO_BUCKET_NAME_DEV
    
    target_base_dir = os.path.join(AUDIO_BASE_DIR, target_bucket_name)
    
    if not os.path.exists(target_base_dir):
        print(f"Target directory {target_base_dir} does not exist.")
        return
    
    if not confirm:
        response = input(f"Are you sure you want to delete {target_base_dir}? (yes/no): ")
        if response.lower() != 'yes':
            print("Operation cancelled.")
            return
    
    try:
        shutil.rmtree(target_base_dir)
        print(f"Successfully removed: {target_base_dir}")
    except Exception as e:
        print(f"Error removing directory: {e}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Consolidate audio files from task buckets")
    parser.add_argument('--action', choices=['consolidate', 'summary', 'clean'], 
                       default='consolidate', help='Action to perform')
    parser.add_argument('--target-bucket', type=str, 
                       help=f'Target bucket name (default: {AUDIO_BUCKET_NAME_DEV})')
    parser.add_argument('--add-prefix', action='store_true', 
                       help='Add task name prefix to filenames to avoid conflicts')
    parser.add_argument('--confirm-clean', action='store_true',
                       help='Skip confirmation when cleaning')
    
    args = parser.parse_args()
    
    if args.action == 'consolidate':
        consolidate_audio_buckets(args.target_bucket, args.add_prefix)
    elif args.action == 'summary':
        list_consolidation_summary(args.target_bucket)
    elif args.action == 'clean':
        clean_consolidated_bucket(args.target_bucket, args.confirm_clean)
    
    print("\nScript completed!") 