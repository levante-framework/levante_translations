#!/usr/bin/env python3
"""
Simple script to identify es-CO audio clips that don't have voice tags.
Uses the existing web dashboard API approach for consistency.
"""

import os
import sys
import json
import requests
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import csv

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

def check_voice_tag_via_api(audio_file: str, base_url: str = "http://localhost:3000") -> Tuple[bool, Optional[str], str]:
    """
    Check if an audio file has a voice tag using the web dashboard API.
    Returns (has_voice_tag, voice_value, error_message)
    """
    try:
        # Construct the API URL for reading tags
        # The API expects a URL parameter, so we need to construct a file URL
        filename = os.path.basename(audio_file)
        api_url = f"{base_url}/api/read-tags"
        
        # Try different URL patterns that the API might accept
        url_candidates = [
            f"file://{os.path.abspath(audio_file)}",
            f"gs://levante-assets-dev/audio/es-CO/{filename}",
            f"gs://levante-assets/audio/es-CO/{filename}",
            f"https://storage.googleapis.com/levante-assets-dev/audio/es-CO/{filename}",
            f"https://storage.googleapis.com/levante-assets/audio/es-CO/{filename}"
        ]
        
        for url in url_candidates:
            try:
                response = requests.get(api_url, params={'url': url}, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    if 'id3Tags' in data:
                        voice_tag = data['id3Tags'].get('voice', 'Not available')
                        has_voice = voice_tag != 'Not available' and voice_tag.strip() != ''
                        return has_voice, voice_tag if has_voice else None, ""
            except requests.RequestException:
                continue
        
        return False, None, "API not accessible or file not found in any location"
        
    except Exception as e:
        return False, None, f"Error: {str(e)}"

def check_voice_tag_local(audio_file: str) -> Tuple[bool, Optional[str], str]:
    """
    Check if an audio file has a voice tag by reading it locally.
    This is a simplified approach that looks for common voice tag patterns.
    """
    try:
        # Read the file and look for ID3 tags
        with open(audio_file, 'rb') as f:
            # Read the first 10KB to look for ID3v2 tags
            header = f.read(10240)
            
            # Look for ID3v2 header
            if header.startswith(b'ID3'):
                # This is a very basic check - in a real implementation,
                # you'd want to use a proper ID3 library
                return False, None, "Basic ID3 detection not implemented"
            else:
                # Look for ID3v1 tags at the end
                f.seek(-128, 2)  # Go to last 128 bytes
                id3v1 = f.read(128)
                if id3v1.startswith(b'TAG'):
                    # ID3v1 tag found, but it doesn't have custom voice field
                    return False, None, "ID3v1 tags don't support custom voice field"
                else:
                    return False, None, "No ID3 tags found"
                    
    except Exception as e:
        return False, None, f"Error reading file: {str(e)}"

def main():
    """Main function to identify es-CO audio clips without voice tags."""
    print("🔍 Identifying es-CO audio clips without voice tags...")
    print("=" * 60)
    
    # Get all es-CO audio files
    audio_files = get_es_co_audio_files()
    if not audio_files:
        print("❌ No es-CO audio files found")
        return
    
    # Check each file for voice tags
    files_without_voice_tags = []
    files_with_voice_tags = []
    error_files = []
    
    total_files = len(audio_files)
    
    for i, audio_file in enumerate(audio_files, 1):
        filename = os.path.basename(audio_file)
        print(f"📄 [{i}/{total_files}] Checking {filename}...")
        
        # Try API first, then fallback to local check
        has_voice, voice_value, error = check_voice_tag_via_api(audio_file)
        
        if error and "API not accessible" in error:
            # Fallback to local check
            has_voice, voice_value, error = check_voice_tag_local(audio_file)
        
        if error:
            error_files.append({
                'file': filename,
                'path': audio_file,
                'error': error
            })
            print(f"   ❌ Error: {error}")
        elif has_voice:
            files_with_voice_tags.append({
                'file': filename,
                'path': audio_file,
                'voice': voice_value
            })
            print(f"   ✅ Has voice tag: '{voice_value}'")
        else:
            files_without_voice_tags.append({
                'file': filename,
                'path': audio_file,
                'voice': voice_value or 'None'
            })
            print(f"   ❌ No voice tag")
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    print(f"Total files checked: {total_files}")
    print(f"Files with voice tags: {len(files_with_voice_tags)}")
    print(f"Files without voice tags: {len(files_without_voice_tags)}")
    print(f"Files with errors: {len(error_files)}")
    
    # Print files without voice tags
    if files_without_voice_tags:
        print(f"\n❌ FILES WITHOUT VOICE TAGS ({len(files_without_voice_tags)}):")
        print("-" * 40)
        for item in files_without_voice_tags:
            print(f"  • {item['file']}")
    
    # Print files with errors
    if error_files:
        print(f"\n⚠️ FILES WITH ERRORS ({len(error_files)}):")
        print("-" * 40)
        for item in error_files:
            print(f"  • {item['file']}: {item['error']}")
    
    # Save results to CSV
    results_file = "es_co_missing_voice_tags_simple_report.csv"
    with open(results_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['file', 'path', 'has_voice_tag', 'voice_value', 'status']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for item in files_without_voice_tags:
            writer.writerow({
                'file': item['file'],
                'path': item['path'],
                'has_voice_tag': 'No',
                'voice_value': item['voice'],
                'status': 'Missing voice tag'
            })
        
        for item in files_with_voice_tags:
            writer.writerow({
                'file': item['file'],
                'path': item['path'],
                'has_voice_tag': 'Yes',
                'voice_value': item['voice'],
                'status': 'Has voice tag'
            })
        
        for item in error_files:
            writer.writerow({
                'file': item['file'],
                'path': item['path'],
                'has_voice_tag': 'Unknown',
                'voice_value': 'N/A',
                'status': f"Error: {item['error']}"
            })
    
    print(f"\n💾 Results saved to: {results_file}")
    
    # Check if we found exactly 13 files without voice tags
    if len(files_without_voice_tags) == 13:
        print(f"\n🎯 SUCCESS: Found exactly 13 es-CO audio clips without voice tags!")
    elif len(files_without_voice_tags) > 13:
        print(f"\n⚠️ Found {len(files_without_voice_tags)} files without voice tags (expected 13)")
    else:
        print(f"\n⚠️ Found {len(files_without_voice_tags)} files without voice tags (expected 13)")

if __name__ == "__main__":
    main()
