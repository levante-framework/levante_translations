#!/usr/bin/env python3
"""
Check es-CO audio files in production for missing voice tags.

This script:
1. Lists all es-CO audio files in levante-assets-prod
2. Downloads each file temporarily
3. Checks ID3 tags for voice information
4. Reports files missing voice tags
"""

import os
import tempfile
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Tuple
import pandas as pd

# Try to import mutagen for ID3 tag reading
try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, TXXX
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    print("⚠️  mutagen not available. Install with: pip install mutagen")

def run_gsutil_command(cmd: List[str]) -> Tuple[bool, str]:
    """Run a gsutil command and return success status and output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr

def get_es_co_audio_files() -> List[str]:
    """Get list of all es-CO audio files in production."""
    print("🔍 Fetching es-CO audio files from production...")
    
    cmd = ["gsutil", "ls", "gs://levante-assets-prod/audio/es-CO/*.mp3"]
    success, output = run_gsutil_command(cmd)
    
    if not success:
        print(f"❌ Error listing files: {output}")
        return []
    
    files = [line.strip() for line in output.split('\n') if line.strip()]
    print(f"📁 Found {len(files)} es-CO audio files")
    return files

def download_file_temporarily(gcs_path: str) -> str:
    """Download a file from GCS to a temporary location."""
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_file:
        temp_path = tmp_file.name
    
    cmd = ["gsutil", "cp", gcs_path, temp_path]
    success, output = run_gsutil_command(cmd)
    
    if not success:
        print(f"❌ Error downloading {gcs_path}: {output}")
        return None
    
    return temp_path

def read_id3_tags(file_path: str) -> Dict[str, str]:
    """Read ID3 tags from an MP3 file."""
    if not MUTAGEN_AVAILABLE:
        return {}
    
    try:
        audio_file = MP3(file_path, ID3=ID3)
        if audio_file.tags is None:
            return {}
        
        tags = {}
        
        # Read standard tags
        if 'TIT2' in audio_file.tags:
            tags['title'] = str(audio_file.tags['TIT2'])
        if 'TPE1' in audio_file.tags:
            tags['artist'] = str(audio_file.tags['TPE1'])
        if 'TALB' in audio_file.tags:
            tags['album'] = str(audio_file.tags['TALB'])
        
        # Read custom TXXX frames
        for frame in audio_file.tags.getall('TXXX'):
            if hasattr(frame, 'desc') and frame.desc:
                tags[frame.desc.lower()] = str(frame.text[0]) if getattr(frame, 'text', None) else None
        
        return tags
    except Exception as e:
        print(f"⚠️  Error reading ID3 tags from {file_path}: {e}")
        return {}

def check_voice_tag(file_path: str) -> Tuple[bool, str, Dict[str, str]]:
    """Check if a file has voice tag and return details."""
    tags = read_id3_tags(file_path)
    
    voice = tags.get('voice', '').strip()
    has_voice = bool(voice)
    
    return has_voice, voice, tags

def main():
    """Main function to check es-CO files for voice tags."""
    print("🎵 Checking es-CO audio files for voice tags in production...")
    print("=" * 60)
    
    if not MUTAGEN_AVAILABLE:
        print("❌ Cannot proceed without mutagen. Please install it first.")
        return
    
    # Get list of es-CO files
    es_co_files = get_es_co_audio_files()
    if not es_co_files:
        print("❌ No es-CO files found or error occurred")
        return
    
    files_without_voice = []
    files_with_voice = []
    error_files = []
    
    print(f"\n🔍 Checking {len(es_co_files)} files for voice tags...")
    
    for i, gcs_path in enumerate(es_co_files, 1):
        filename = os.path.basename(gcs_path)
        print(f"[{i:3d}/{len(es_co_files)}] {filename}", end=" ... ")
        
        # Download file temporarily
        temp_path = download_file_temporarily(gcs_path)
        if not temp_path:
            error_files.append(gcs_path)
            print("❌ Download failed")
            continue
        
        try:
            # Check for voice tag
            has_voice, voice, tags = check_voice_tag(temp_path)
            
            if has_voice:
                files_with_voice.append({
                    'file': filename,
                    'gcs_path': gcs_path,
                    'voice': voice,
                    'tags': tags
                })
                print(f"✅ Voice: {voice}")
            else:
                files_without_voice.append({
                    'file': filename,
                    'gcs_path': gcs_path,
                    'tags': tags
                })
                print("❌ No voice tag")
        
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_path)
            except:
                pass
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    print(f"Total files checked: {len(es_co_files)}")
    print(f"Files with voice tags: {len(files_with_voice)}")
    print(f"Files without voice tags: {len(files_without_voice)}")
    print(f"Files with errors: {len(error_files)}")
    
    if files_without_voice:
        print(f"\n❌ FILES WITHOUT VOICE TAGS ({len(files_without_voice)}):")
        print("-" * 40)
        for item in files_without_voice:
            print(f"  • {item['file']}")
            # Show what tags are available
            if item['tags']:
                available_tags = list(item['tags'].keys())
                print(f"    Available tags: {', '.join(available_tags)}")
            else:
                print(f"    No ID3 tags found")
    
    if files_with_voice:
        print(f"\n✅ FILES WITH VOICE TAGS ({len(files_with_voice)}):")
        print("-" * 40)
        voice_summary = {}
        for item in files_with_voice:
            voice = item['voice']
            if voice not in voice_summary:
                voice_summary[voice] = 0
            voice_summary[voice] += 1
        
        for voice, count in voice_summary.items():
            print(f"  • {voice}: {count} files")
    
    if error_files:
        print(f"\n⚠️  FILES WITH ERRORS ({len(error_files)}):")
        print("-" * 40)
        for gcs_path in error_files:
            print(f"  • {os.path.basename(gcs_path)}")
    
    # Save detailed report
    if files_without_voice:
        report_file = "es_co_files_without_voice_tags.txt"
        with open(report_file, 'w') as f:
            f.write("ES-CO Audio Files Without Voice Tags\n")
            f.write("=" * 50 + "\n\n")
            for item in files_without_voice:
                f.write(f"File: {item['file']}\n")
                f.write(f"GCS Path: {item['gcs_path']}\n")
                f.write(f"Available tags: {list(item['tags'].keys())}\n")
                f.write("-" * 30 + "\n")
        
        print(f"\n📄 Detailed report saved to: {report_file}")

if __name__ == "__main__":
    main()
