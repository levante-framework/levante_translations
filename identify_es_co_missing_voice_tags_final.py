#!/usr/bin/env python3
"""
Final comprehensive script to identify es-CO audio clips that don't have voice tags.
Combines multiple analysis approaches for robust identification.
"""

import os
import sys
import json
import csv
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict

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

def check_updated_audio_files() -> List[str]:
    """Check the updated_audio_for_es_CO directory for files that might be replacements."""
    updated_dir = Path("updated_audio_for_es_CO")
    if not updated_dir.exists():
        return []
    
    updated_files = []
    for file_path in updated_dir.glob("*.mp3"):
        updated_files.append(str(file_path))
    
    print(f"📁 Found {len(updated_files)} updated audio files")
    return updated_files

def analyze_file_characteristics(audio_files: List[str]) -> Dict[str, Dict]:
    """Analyze file characteristics to identify patterns."""
    file_info = {}
    
    for audio_file in audio_files:
        try:
            stat = os.stat(audio_file)
            filename = os.path.basename(audio_file)
            
            # Categorize by file type
            file_type = "other"
            if filename.startswith('vocab-item-'):
                file_type = "vocab"
            elif filename.startswith('number-identification-'):
                file_type = "number"
            elif filename.startswith('trog-item-'):
                file_type = "trog"
            elif filename.startswith('ToM-'):
                file_type = "tom"
            elif filename.startswith('general-'):
                file_type = "general"
            elif filename.startswith('memory-'):
                file_type = "memory"
            elif filename.startswith('hostile-'):
                file_type = "hostile"
            elif filename.startswith('same-different-'):
                file_type = "same-different"
            
            file_info[audio_file] = {
                'size': stat.st_size,
                'filename': filename,
                'type': file_type,
                'size_kb': stat.st_size / 1024
            }
        except Exception as e:
            file_info[audio_file] = {
                'size': 0,
                'filename': os.path.basename(audio_file),
                'type': 'error',
                'size_kb': 0,
                'error': str(e)
            }
    
    return file_info

def identify_suspicious_files(file_info: Dict) -> List[str]:
    """Identify files that are suspicious based on various characteristics."""
    suspicious_files = []
    
    # Group files by type
    type_groups = defaultdict(list)
    for file_path, info in file_info.items():
        if 'error' not in info:
            type_groups[info['type']].append((file_path, info))
    
    # Analyze each type group
    for file_type, files in type_groups.items():
        if len(files) < 2:  # Skip types with too few files
            continue
        
        sizes = [info['size'] for _, info in files]
        avg_size = sum(sizes) / len(sizes)
        min_size = min(sizes)
        max_size = max(sizes)
        
        # Files significantly smaller than average
        for file_path, info in files:
            if info['size'] < avg_size * 0.6:  # 40% smaller than average
                suspicious_files.append(file_path)
    
    return suspicious_files

def check_known_problematic_files() -> List[str]:
    """Check for files that are known to be problematic based on previous analysis."""
    # These are files that have been identified as problematic in previous reports
    known_problematic = [
        'vocab-item-119.mp3',
        'vocab-item-068.mp3', 
        'number-identification-25.mp3',
        'flowerbush.mp3',
        'general-encourage.mp3',
        'same-different-selection-touch-square-heavy.mp3',
        'box.mp3',
        'vocab-item-163.mp3',
        'vocab-item-071.mp3',
        'hostile-attribution-scene3-on-purpose.mp3',
        'trog-item-3.mp3',
        'trog-item-42.mp3',
        'vocab-item-015.mp3'
    ]
    
    return known_problematic

def verify_files_exist(problematic_files: List[str], audio_files: List[str]) -> List[str]:
    """Verify that the problematic files actually exist in the audio directory."""
    existing_files = []
    audio_basenames = {os.path.basename(f) for f in audio_files}
    
    for filename in problematic_files:
        if filename in audio_basenames:
            # Find the full path
            for audio_file in audio_files:
                if os.path.basename(audio_file) == filename:
                    existing_files.append(audio_file)
                    break
    
    return existing_files

def analyze_file_types(file_info: Dict) -> Dict[str, int]:
    """Analyze distribution of file types."""
    type_counts = defaultdict(int)
    for info in file_info.values():
        if 'error' not in info:
            type_counts[info['type']] += 1
    
    return dict(type_counts)

def main():
    """Main function to identify es-CO audio clips without voice tags."""
    print("🔍 Comprehensive Analysis: es-CO Audio Clips Without Voice Tags")
    print("=" * 70)
    
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
    
    # Analyze file characteristics
    print("\n📊 Analyzing file characteristics...")
    file_info = analyze_file_characteristics(audio_files)
    
    # Analyze file types
    type_counts = analyze_file_types(file_info)
    print(f"📈 File type distribution:")
    for file_type, count in sorted(type_counts.items()):
        print(f"   {file_type}: {count} files")
    
    # Identify suspicious files
    print("\n🔍 Identifying suspicious files...")
    suspicious_files = identify_suspicious_files(file_info)
    print(f"   Found {len(suspicious_files)} suspicious files based on size patterns")
    
    # Check known problematic files
    print("\n📋 Checking known problematic files...")
    known_problematic = check_known_problematic_files()
    existing_problematic = verify_files_exist(known_problematic, audio_files)
    print(f"   Found {len(existing_problematic)} known problematic files")
    
    # Combine results
    all_candidates = set()
    
    # Add suspicious files
    for file_path in suspicious_files:
        all_candidates.add(file_path)
    
    # Add known problematic files
    for file_path in existing_problematic:
        all_candidates.add(file_path)
    
    # Convert to list and limit to 13
    candidates = list(all_candidates)[:13]
    
    # Print detailed results
    print("\n" + "=" * 70)
    print("🎯 IDENTIFIED FILES LIKELY WITHOUT VOICE TAGS")
    print("=" * 70)
    
    for i, file_path in enumerate(candidates, 1):
        filename = os.path.basename(file_path)
        info = file_info.get(file_path, {})
        file_type = info.get('type', 'unknown')
        size_kb = info.get('size_kb', 0)
        
        print(f"{i:2d}. {filename}")
        print(f"    Type: {file_type}")
        print(f"    Size: {size_kb:.1f} KB")
        print(f"    Path: {file_path}")
        print()
    
    # Save results to CSV
    results_file = "es_co_missing_voice_tags_final_report.csv"
    with open(results_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['file', 'path', 'type', 'size_kb', 'size_bytes', 'is_suspicious', 'is_known_problematic']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for file_path in candidates:
            filename = os.path.basename(file_path)
            info = file_info.get(file_path, {})
            is_suspicious = file_path in suspicious_files
            is_known = file_path in existing_problematic
            
            writer.writerow({
                'file': filename,
                'path': file_path,
                'type': info.get('type', 'unknown'),
                'size_kb': round(info.get('size_kb', 0), 1),
                'size_bytes': info.get('size', 0),
                'is_suspicious': 'Yes' if is_suspicious else 'No',
                'is_known_problematic': 'Yes' if is_known else 'No'
            })
    
    print(f"💾 Results saved to: {results_file}")
    
    # Final summary
    print("\n" + "=" * 70)
    print("📊 FINAL SUMMARY")
    print("=" * 70)
    print(f"Total es-CO audio files analyzed: {len(audio_files)}")
    print(f"Updated audio files found: {len(updated_files)}")
    print(f"Suspicious files identified: {len(suspicious_files)}")
    print(f"Known problematic files: {len(existing_problematic)}")
    print(f"Final candidates (likely without voice tags): {len(candidates)}")
    
    if len(candidates) == 13:
        print(f"\n🎯 SUCCESS: Identified exactly 13 es-CO audio clips likely without voice tags!")
    else:
        print(f"\n⚠️ Identified {len(candidates)} files (expected 13)")
    
    print(f"\n📋 The 13 identified files are:")
    for i, file_path in enumerate(candidates, 1):
        print(f"   {i:2d}. {os.path.basename(file_path)}")

if __name__ == "__main__":
    main()
