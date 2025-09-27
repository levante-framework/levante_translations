#!/usr/bin/env python3
"""
Script to extract ID3 data for all vocab audio clips in es-CO and save to CSV.
Uses multiple methods to read ID3 tags for comprehensive data extraction.
"""

import os
import sys
import json
import csv
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import time

def get_vocab_audio_files() -> List[str]:
    """Get all vocab-item audio files from the es-CO directory."""
    audio_dir = Path("audio_files/es-CO")
    if not audio_dir.exists():
        print(f"❌ Directory {audio_dir} does not exist")
        return []
    
    vocab_files = []
    for file_path in audio_dir.glob("vocab-item-*.mp3"):
        vocab_files.append(str(file_path))
    
    # Sort by item number for consistent ordering
    vocab_files.sort(key=lambda x: int(os.path.basename(x).split('-')[2].split('.')[0]))
    
    print(f"📁 Found {len(vocab_files)} vocab-item audio files")
    return vocab_files

def extract_id3_with_ffprobe(audio_file: str) -> Dict:
    """Extract ID3 data using ffprobe."""
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json', 
            '-show_format', '-show_streams', audio_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            return {'error': f"ffprobe failed: {result.stderr}"}
        
        data = json.loads(result.stdout)
        format_tags = data.get('format', {}).get('tags', {})
        
        # Extract relevant ID3 fields
        id3_data = {
            'title': format_tags.get('title', ''),
            'artist': format_tags.get('artist', ''),
            'album': format_tags.get('album', ''),
            'genre': format_tags.get('genre', ''),
            'voice': format_tags.get('voice', ''),
            'service': format_tags.get('service', ''),
            'lang_code': format_tags.get('lang_code', ''),
            'text': format_tags.get('text', ''),
            'created': format_tags.get('created', ''),
            'copyright': format_tags.get('copyright', ''),
            'comment': format_tags.get('comment', ''),
            'date': format_tags.get('date', ''),
            'year': format_tags.get('date', ''),
            'track': format_tags.get('track', ''),
            'disc': format_tags.get('disc', ''),
            'composer': format_tags.get('composer', ''),
            'publisher': format_tags.get('publisher', ''),
            'encoder': format_tags.get('encoder', ''),
            'bitrate': data.get('format', {}).get('bit_rate', ''),
            'duration': data.get('format', {}).get('duration', ''),
            'size': data.get('format', {}).get('size', ''),
            'format_name': data.get('format', {}).get('format_name', ''),
            'format_long_name': data.get('format', {}).get('format_long_name', ''),
            'sample_rate': '',
            'channels': '',
            'codec': ''
        }
        
        # Extract stream information
        streams = data.get('streams', [])
        if streams:
            stream = streams[0]  # First audio stream
            id3_data['sample_rate'] = stream.get('sample_rate', '')
            id3_data['channels'] = stream.get('channels', '')
            id3_data['codec'] = stream.get('codec_name', '')
        
        # Check for TXXX (user defined text) frames
        for key, value in format_tags.items():
            if key.startswith('TXXX:'):
                field_name = key.replace('TXXX:', '').lower()
                if field_name not in id3_data:
                    id3_data[f'txxx_{field_name}'] = value
        
        return id3_data
        
    except subprocess.TimeoutExpired:
        return {'error': 'ffprobe timeout'}
    except json.JSONDecodeError:
        return {'error': 'Invalid JSON from ffprobe'}
    except Exception as e:
        return {'error': f"ffprobe error: {str(e)}"}

def extract_id3_with_eyeD3(audio_file: str) -> Dict:
    """Extract ID3 data using eyeD3."""
    try:
        cmd = ['eyeD3', '--json', audio_file]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            return {'error': f"eyeD3 failed: {result.stderr}"}
        
        data = json.loads(result.stdout)
        
        # Extract relevant fields
        id3_data = {
            'title': data.get('title', ''),
            'artist': data.get('artist', ''),
            'album': data.get('album', ''),
            'genre': data.get('genre', ''),
            'voice': data.get('voice', ''),
            'service': data.get('service', ''),
            'lang_code': data.get('lang_code', ''),
            'text': data.get('text', ''),
            'created': data.get('created', ''),
            'copyright': data.get('copyright', ''),
            'comment': data.get('comment', ''),
            'date': data.get('date', ''),
            'year': data.get('year', ''),
            'track': data.get('track', ''),
            'disc': data.get('disc', ''),
            'composer': data.get('composer', ''),
            'publisher': data.get('publisher', ''),
            'encoder': data.get('encoder', ''),
            'bitrate': data.get('bitrate', ''),
            'duration': data.get('duration', ''),
            'size': data.get('size', ''),
            'format_name': data.get('format_name', ''),
            'format_long_name': data.get('format_long_name', ''),
            'sample_rate': data.get('sample_rate', ''),
            'channels': data.get('channels', ''),
            'codec': data.get('codec', '')
        }
        
        # Extract user defined text frames
        if 'user_defined_text' in data:
            for frame in data['user_defined_text']:
                field_name = frame.get('description', '').lower()
                if field_name:
                    id3_data[f'udt_{field_name}'] = frame.get('text', '')
        
        return id3_data
        
    except subprocess.TimeoutExpired:
        return {'error': 'eyeD3 timeout'}
    except json.JSONDecodeError:
        return {'error': 'Invalid JSON from eyeD3'}
    except Exception as e:
        return {'error': f"eyeD3 error: {str(e)}"}

def extract_id3_with_node_id3(audio_file: str) -> Dict:
    """Extract ID3 data using Node.js ID3 reader (mimics web dashboard approach)."""
    try:
        script_content = f"""
const NodeID3 = require('node-id3');
const fs = require('fs');

try {{
    const buffer = fs.readFileSync('{audio_file}');
    const tags = NodeID3.read(buffer);
    
    const result = {{
        title: tags.title || '',
        artist: tags.artist || '',
        album: tags.album || '',
        genre: tags.genre || '',
        voice: tags.voice || '',
        service: tags.service || '',
        lang_code: tags.lang_code || '',
        text: tags.text || '',
        created: tags.created || '',
        copyright: tags.copyright || '',
        comment: tags.comment ? tags.comment.text || tags.comment : '',
        date: tags.date || '',
        year: tags.year || '',
        track: tags.track || '',
        disc: tags.disc || '',
        composer: tags.composer || '',
        publisher: tags.publisher || '',
        encoder: tags.encoder || '',
        bitrate: tags.bitrate || '',
        duration: tags.duration || '',
        size: tags.size || '',
        format_name: tags.format_name || '',
        format_long_name: tags.format_long_name || '',
        sample_rate: tags.sample_rate || '',
        channels: tags.channels || '',
        codec: tags.codec || '',
        error: null
    }};
    
    // Extract user defined text frames
    if (tags.userDefinedText) {{
        tags.userDefinedText.forEach(frame => {{
            const fieldName = frame.description ? frame.description.toLowerCase() : 'unknown';
            result[`udt_${{fieldName}}`] = frame.value || '';
        }});
    }}
    
    console.log(JSON.stringify(result));
}} catch (error) {{
    console.log(JSON.stringify({{
        error: error.message
    }}));
}}
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(script_content)
            temp_script = f.name
        
        try:
            result = subprocess.run(['node', temp_script], capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return {'error': f"Node.js script failed: {result.stderr}"}
            
            data = json.loads(result.stdout)
            return data
            
        finally:
            os.unlink(temp_script)
            
    except subprocess.TimeoutExpired:
        return {'error': 'Node.js script timeout'}
    except json.JSONDecodeError:
        return {'error': 'Invalid JSON from Node.js script'}
    except Exception as e:
        return {'error': f"Node.js error: {str(e)}"}

def extract_id3_data(audio_file: str) -> Dict:
    """Extract ID3 data using multiple methods and combine results."""
    filename = os.path.basename(audio_file)
    
    # Try multiple methods
    methods = [
        ("NodeID3", extract_id3_with_node_id3),
        ("ffprobe", extract_id3_with_ffprobe),
        ("eyeD3", extract_id3_with_eyeD3)
    ]
    
    combined_data = {
        'filename': filename,
        'filepath': audio_file,
        'extraction_method': '',
        'extraction_error': ''
    }
    
    for method_name, method_func in methods:
        try:
            data = method_func(audio_file)
            if 'error' not in data:
                # Success - use this data
                combined_data.update(data)
                combined_data['extraction_method'] = method_name
                return combined_data
            else:
                print(f"⚠️ {method_name} failed for {filename}: {data['error']}")
        except Exception as e:
            print(f"⚠️ {method_name} exception for {filename}: {str(e)}")
    
    # If all methods failed
    combined_data['extraction_error'] = 'All extraction methods failed'
    return combined_data

def main():
    """Main function to extract ID3 data for all vocab audio clips."""
    print("🔍 Extracting ID3 data for es-CO vocab audio clips...")
    print("=" * 60)
    
    # Get all vocab audio files
    vocab_files = get_vocab_audio_files()
    if not vocab_files:
        print("❌ No vocab audio files found")
        return
    
    # Extract ID3 data for each file
    all_data = []
    total_files = len(vocab_files)
    
    for i, audio_file in enumerate(vocab_files, 1):
        filename = os.path.basename(audio_file)
        print(f"📄 [{i}/{total_files}] Processing {filename}...")
        
        id3_data = extract_id3_data(audio_file)
        all_data.append(id3_data)
        
        # Show progress every 10 files
        if i % 10 == 0:
            print(f"   Progress: {i}/{total_files} files processed")
    
    # Save to CSV
    if all_data:
        # Get all possible field names
        all_fields = set()
        for data in all_data:
            all_fields.update(data.keys())
        
        # Sort fields for consistent column order
        field_order = [
            'filename', 'filepath', 'extraction_method', 'extraction_error',
            'title', 'artist', 'album', 'genre', 'voice', 'service', 'lang_code', 'text',
            'created', 'copyright', 'comment', 'date', 'year', 'track', 'disc',
            'composer', 'publisher', 'encoder', 'bitrate', 'duration', 'size',
            'format_name', 'format_long_name', 'sample_rate', 'channels', 'codec'
        ]
        
        # Add any additional fields found
        for field in sorted(all_fields):
            if field not in field_order:
                field_order.append(field)
        
        # Write CSV
        csv_file = "es_co_vocab_id3_data.csv"
        with open(csv_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=field_order)
            writer.writeheader()
            
            for data in all_data:
                # Ensure all fields are present
                row = {field: data.get(field, '') for field in field_order}
                writer.writerow(row)
        
        print(f"\n💾 ID3 data saved to: {csv_file}")
        
        # Print summary
        successful_extractions = len([d for d in all_data if not d.get('extraction_error')])
        failed_extractions = len([d for d in all_data if d.get('extraction_error')])
        
        print(f"\n📊 EXTRACTION SUMMARY")
        print("=" * 60)
        print(f"Total files processed: {total_files}")
        print(f"Successful extractions: {successful_extractions}")
        print(f"Failed extractions: {failed_extractions}")
        
        if failed_extractions > 0:
            print(f"\n❌ Files with extraction errors:")
            for data in all_data:
                if data.get('extraction_error'):
                    print(f"   • {data['filename']}: {data['extraction_error']}")
        
        # Show voice tag statistics
        files_with_voice = len([d for d in all_data if d.get('voice') and d.get('voice').strip()])
        files_without_voice = len([d for d in all_data if not d.get('voice') or not d.get('voice').strip()])
        
        print(f"\n🎤 VOICE TAG STATISTICS")
        print("=" * 60)
        print(f"Files with voice tags: {files_with_voice}")
        print(f"Files without voice tags: {files_without_voice}")
        
        if files_without_voice > 0:
            print(f"\n❌ Files without voice tags:")
            for data in all_data:
                if not data.get('voice') or not data.get('voice').strip():
                    print(f"   • {data['filename']}")
    
    else:
        print("❌ No data extracted")

if __name__ == "__main__":
    main()
