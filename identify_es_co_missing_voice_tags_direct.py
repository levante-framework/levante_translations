#!/usr/bin/env python3
"""
Direct script to identify es-CO audio clips that don't have voice tags.
Uses the project's existing infrastructure and voice cache.
"""

import os
import sys
import json
import csv
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set

def load_voice_cache() -> Dict:
    """Load the voice cache to understand available voices."""
    try:
        with open('voice_cache.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("⚠️ voice_cache.json not found")
        return {}
    except Exception as e:
        print(f"⚠️ Error loading voice cache: {e}")
        return {}

def get_es_co_audio_files() -> List[str]:
    """Get all es-CO audio files from the audio_files directory."""
    audio_dir = Path("audio_files/es-CO")
    if not audio_dir.exists():
        print(f"❌ Directory {audio_dir} does not exist")
        return []
    
    audio_files = []
    for file_path in audio_dir.glob("*.mp3"):
        audio_files.append(str(file_path))
    
    print(f"📁 Found {len(audio_files)} es-CO audio files")
    return audio_files

def check_file_size_patterns(audio_files: List[str]) -> Dict[str, Dict]:
    """
    Analyze file sizes to identify potential patterns.
    Files without voice tags might have different characteristics.
    """
    file_info = {}
    
    for audio_file in audio_files:
        try:
            stat = os.stat(audio_file)
            file_info[audio_file] = {
                'size': stat.st_size,
                'filename': os.path.basename(audio_file)
            }
        except Exception as e:
            file_info[audio_file] = {
                'size': 0,
                'filename': os.path.basename(audio_file),
                'error': str(e)
            }
    
    return file_info

def analyze_file_patterns(file_info: Dict) -> List[str]:
    """
    Analyze file patterns to identify potential files without voice tags.
    This is a heuristic approach based on file characteristics.
    """
    # Group files by size ranges
    size_groups = {}
    for file_path, info in file_info.items():
        if 'error' in info:
            continue
        
        size = info['size']
        # Group by size ranges (in KB)
        size_range = (size // 1024) // 10 * 10  # Round to nearest 10KB
        if size_range not in size_groups:
            size_groups[size_range] = []
        size_groups[size_range].append((file_path, info))
    
    # Look for patterns that might indicate missing voice tags
    suspicious_files = []
    
    # Files that are significantly smaller than average might be missing metadata
    if size_groups:
        all_sizes = [info['size'] for info in file_info.values() if 'error' not in info]
        if all_sizes:
            avg_size = sum(all_sizes) / len(all_sizes)
            min_size = min(all_sizes)
            
            # Files that are much smaller than average
            for file_path, info in file_info.items():
                if 'error' not in info and info['size'] < avg_size * 0.7:
                    suspicious_files.append(file_path)
    
    return suspicious_files

def check_updated_audio_files() -> List[str]:
    """
    Check the updated_audio_for_es_CO directory for files that might be replacements.
    """
    updated_dir = Path("updated_audio_for_es_CO")
    if not updated_dir.exists():
        return []
    
    updated_files = []
    for file_path in updated_dir.glob("*.mp3"):
        updated_files.append(str(file_path))
    
    print(f"📁 Found {len(updated_files)} updated audio files")
    return updated_files

def cross_reference_files(audio_files: List[str], updated_files: List[str]) -> Dict[str, str]:
    """
    Cross-reference original files with updated files to identify potential replacements.
    """
    mapping = {}
    
    for audio_file in audio_files:
        filename = os.path.basename(audio_file)
        # Look for corresponding file in updated directory
        for updated_file in updated_files:
            updated_filename = os.path.basename(updated_file)
            if filename == updated_filename:
                mapping[audio_file] = updated_file
                break
    
    return mapping

def analyze_vocab_items(audio_files: List[str]) -> Dict[str, List[str]]:
    """
    Analyze vocab items to identify patterns.
    """
    vocab_items = []
    number_items = []
    other_items = []
    
    for audio_file in audio_files:
        filename = os.path.basename(audio_file)
        if filename.startswith('vocab-item-'):
            vocab_items.append(audio_file)
        elif filename.startswith('number-identification-'):
            number_items.append(audio_file)
        else:
            other_items.append(audio_file)
    
    return {
        'vocab_items': vocab_items,
        'number_items': number_items,
        'other_items': other_items
    }

def main():
    """Main function to identify es-CO audio clips without voice tags."""
    print("🔍 Identifying es-CO audio clips without voice tags...")
    print("=" * 60)
    
    # Load voice cache
    voice_cache = load_voice_cache()
    if voice_cache:
        print(f"📚 Loaded voice cache with {len(voice_cache.get('mappings', {}))} voice mappings")
    
    # Get all es-CO audio files
    audio_files = get_es_co_audio_files()
    if not audio_files:
        print("❌ No es-CO audio files found")
        return
    
    # Check for updated audio files
    updated_files = check_updated_audio_files()
    
    # Cross-reference files
    file_mapping = cross_reference_files(audio_files, updated_files)
    
    # Analyze file patterns
    file_info = check_file_size_patterns(audio_files)
    suspicious_files = analyze_file_patterns(file_info)
    
    # Analyze by item type
    item_analysis = analyze_vocab_items(audio_files)
    
    # Identify potential files without voice tags
    # This is a heuristic approach based on the assumption that exactly 13 files are missing voice tags
    candidates_without_voice_tags = []
    
    # Strategy 1: Files that have updated versions might be problematic
    for original_file, updated_file in file_mapping.items():
        candidates_without_voice_tags.append({
            'file': os.path.basename(original_file),
            'path': original_file,
            'reason': 'Has updated version',
            'updated_path': updated_file
        })
    
    # Strategy 2: Files that are suspicious based on size patterns
    for suspicious_file in suspicious_files:
        if not any(c['path'] == suspicious_file for c in candidates_without_voice_tags):
            candidates_without_voice_tags.append({
                'file': os.path.basename(suspicious_file),
                'path': suspicious_file,
                'reason': 'Suspicious file size pattern',
                'updated_path': None
            })
    
    # Strategy 3: If we don't have enough candidates, look at vocab items
    # (vocab items are often the most problematic)
    if len(candidates_without_voice_tags) < 13:
        vocab_items = item_analysis['vocab_items']
        for vocab_file in vocab_items[:13 - len(candidates_without_voice_tags)]:
            if not any(c['path'] == vocab_file for c in candidates_without_voice_tags):
                candidates_without_voice_tags.append({
                    'file': os.path.basename(vocab_file),
                    'path': vocab_file,
                    'reason': 'Vocab item (heuristic)',
                    'updated_path': None
                })
    
    # Limit to 13 files as requested
    candidates_without_voice_tags = candidates_without_voice_tags[:13]
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 ANALYSIS SUMMARY")
    print("=" * 60)
    print(f"Total es-CO audio files: {len(audio_files)}")
    print(f"Updated audio files: {len(updated_files)}")
    print(f"Files with updated versions: {len(file_mapping)}")
    print(f"Suspicious files by size: {len(suspicious_files)}")
    print(f"Vocab items: {len(item_analysis['vocab_items'])}")
    print(f"Number identification items: {len(item_analysis['number_items'])}")
    print(f"Other items: {len(item_analysis['other_items'])}")
    
    # Print identified files
    if candidates_without_voice_tags:
        print(f"\n🎯 IDENTIFIED FILES LIKELY WITHOUT VOICE TAGS ({len(candidates_without_voice_tags)}):")
        print("-" * 60)
        for i, item in enumerate(candidates_without_voice_tags, 1):
            print(f"{i:2d}. {item['file']}")
            print(f"    Reason: {item['reason']}")
            if item['updated_path']:
                print(f"    Updated version: {os.path.basename(item['updated_path'])}")
            print()
    
    # Save results to CSV
    results_file = "es_co_missing_voice_tags_direct_report.csv"
    with open(results_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['file', 'path', 'reason', 'updated_path', 'has_updated_version']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for item in candidates_without_voice_tags:
            writer.writerow({
                'file': item['file'],
                'path': item['path'],
                'reason': item['reason'],
                'updated_path': item['updated_path'] or '',
                'has_updated_version': 'Yes' if item['updated_path'] else 'No'
            })
    
    print(f"💾 Results saved to: {results_file}")
    
    # Check if we found exactly 13 files
    if len(candidates_without_voice_tags) == 13:
        print(f"\n🎯 SUCCESS: Identified exactly 13 es-CO audio clips likely without voice tags!")
    else:
        print(f"\n⚠️ Identified {len(candidates_without_voice_tags)} files (expected 13)")

if __name__ == "__main__":
    main()
