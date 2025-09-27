#!/usr/bin/env python3
"""
Script to identify es-CO audio clips that don't have voice tags.
This script scans all es-CO audio files and checks their ID3 metadata for voice tags.
"""

import os
import sys
import json
import subprocess
import tempfile
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

def check_voice_tag_with_ffprobe(audio_file: str) -> Tuple[bool, Optional[str], str]:
    """
    Check if an audio file has a voice tag using ffprobe.
    Returns (has_voice_tag, voice_value, error_message)
    """
    try:
        # Use ffprobe to extract metadata
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json', 
            '-show_format', '-show_streams', audio_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            return False, None, f"ffprobe failed: {result.stderr}"
        
        data = json.loads(result.stdout)
        
        # Check format tags
        format_tags = data.get('format', {}).get('tags', {})
        
        # Look for voice tag in various possible locations
        voice_tag = None
        
        # Check standard voice field
        if 'voice' in format_tags:
            voice_tag = format_tags['voice']
        # Check user defined text fields
        elif 'TXXX:voice' in format_tags:
            voice_tag = format_tags['TXXX:voice']
        # Check for any TXXX field with voice description
        for key, value in format_tags.items():
            if key.startswith('TXXX:') and 'voice' in key.lower():
                voice_tag = value
                break
        
        has_voice = voice_tag is not None and voice_tag.strip() != '' and voice_tag != 'Not available'
        
        return has_voice, voice_tag, ""
        
    except subprocess.TimeoutExpired:
        return False, None, "ffprobe timeout"
    except json.JSONDecodeError:
        return False, None, "Invalid JSON from ffprobe"
    except Exception as e:
        return False, None, f"Error: {str(e)}"

def check_voice_tag_with_eyeD3(audio_file: str) -> Tuple[bool, Optional[str], str]:
    """
    Check if an audio file has a voice tag using eyeD3.
    Returns (has_voice_tag, voice_value, error_message)
    """
    try:
        # Use eyeD3 to extract metadata
        cmd = ['eyeD3', '--json', audio_file]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            return False, None, f"eyeD3 failed: {result.stderr}"
        
        data = json.loads(result.stdout)
        
        # Check for voice tag in various locations
        voice_tag = None
        
        # Check standard tags
        if 'voice' in data:
            voice_tag = data['voice']
        # Check user defined text frames
        elif 'user_defined_text' in data:
            for frame in data['user_defined_text']:
                if frame.get('description', '').lower() == 'voice':
                    voice_tag = frame.get('text', '')
                    break
        
        has_voice = voice_tag is not None and voice_tag.strip() != '' and voice_tag != 'Not available'
        
        return has_voice, voice_tag, ""
        
    except subprocess.TimeoutExpired:
        return False, None, "eyeD3 timeout"
    except json.JSONDecodeError:
        return False, None, "Invalid JSON from eyeD3"
    except Exception as e:
        return False, None, f"Error: {str(e)}"

def check_voice_tag_with_node_id3(audio_file: str) -> Tuple[bool, Optional[str], str]:
    """
    Check if an audio file has a voice tag using Node.js ID3 reader.
    This mimics the web dashboard's approach.
    """
    try:
        # Create a temporary Node.js script to read ID3 tags
        script_content = f"""
const NodeID3 = require('node-id3');
const fs = require('fs');

try {{
    const buffer = fs.readFileSync('{audio_file}');
    const tags = NodeID3.read(buffer);
    
    let voice = null;
    
    // Check standard voice field
    if (tags.voice) {{
        voice = tags.voice;
    }}
    // Check user defined text fields
    else if (tags.userDefinedText) {{
        const voiceFrame = tags.userDefinedText.find(t => t.description === 'voice');
        if (voiceFrame) {{
            voice = voiceFrame.value;
        }}
    }}
    
    const hasVoice = voice && voice.trim() !== '' && voice !== 'Not available';
    
    console.log(JSON.stringify({{
        hasVoice: hasVoice,
        voice: voice,
        error: null
    }}));
}} catch (error) {{
    console.log(JSON.stringify({{
        hasVoice: false,
        voice: null,
        error: error.message
    }}));
}}
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(script_content)
            temp_script = f.name
        
        try:
            # Run the Node.js script
            result = subprocess.run(['node', temp_script], capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return False, None, f"Node.js script failed: {result.stderr}"
            
            data = json.loads(result.stdout)
            return data.get('hasVoice', False), data.get('voice'), data.get('error', '')
            
        finally:
            os.unlink(temp_script)
            
    except subprocess.TimeoutExpired:
        return False, None, "Node.js script timeout"
    except json.JSONDecodeError:
        return False, None, "Invalid JSON from Node.js script"
    except Exception as e:
        return False, None, f"Error: {str(e)}"

def check_voice_tag(audio_file: str) -> Tuple[bool, Optional[str], str]:
    """
    Check if an audio file has a voice tag using multiple methods.
    Returns (has_voice_tag, voice_value, error_message)
    """
    # Try multiple methods in order of preference
    methods = [
        ("NodeID3", check_voice_tag_with_node_id3),
        ("ffprobe", check_voice_tag_with_ffprobe),
        ("eyeD3", check_voice_tag_with_eyeD3)
    ]
    
    for method_name, method_func in methods:
        try:
            has_voice, voice_value, error = method_func(audio_file)
            if error == "":  # Success
                return has_voice, voice_value, ""
            else:
                print(f"⚠️ {method_name} failed for {os.path.basename(audio_file)}: {error}")
        except Exception as e:
            print(f"⚠️ {method_name} exception for {os.path.basename(audio_file)}: {str(e)}")
    
    return False, None, "All methods failed"

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
        
        has_voice, voice_value, error = check_voice_tag(audio_file)
        
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
    results_file = "es_co_missing_voice_tags_report.csv"
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
