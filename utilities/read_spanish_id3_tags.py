#!/usr/bin/env python3
"""
Script to read ID3 tags from Spanish audio files and output to CSV.
Reads 10 Spanish audio files and extracts all their ID3v2 tags.
"""

import os
import glob
import pandas as pd

# Import mutagen directly for ID3 tag reading
try:
    from mutagen.id3 import ID3
    from mutagen.mp3 import MP3
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    print("Warning: mutagen not available. Install with: pip install mutagen")

def read_id3_tags_simple(file_path):
    """
    Simple ID3 tag reader without dependencies on utilities module.
    """
    if not MUTAGEN_AVAILABLE:
        return {}
    
    if not os.path.exists(file_path):
        return {}
    
    try:
        audio_file = MP3(file_path, ID3=ID3)
        tags = {}
        
        # Read standard ID3v2 tags
        if audio_file.tags:
            tags['title'] = str(audio_file.tags.get('TIT2', [''])[0]) if audio_file.tags.get('TIT2') else ''
            tags['artist'] = str(audio_file.tags.get('TPE1', [''])[0]) if audio_file.tags.get('TPE1') else ''
            tags['album'] = str(audio_file.tags.get('TALB', [''])[0]) if audio_file.tags.get('TALB') else ''
            tags['date'] = str(audio_file.tags.get('TDRC', [''])[0]) if audio_file.tags.get('TDRC') else ''
            tags['genre'] = str(audio_file.tags.get('TCON', [''])[0]) if audio_file.tags.get('TCON') else ''
            
            # Read comment (if any)
            comment_frames = audio_file.tags.getall('COMM')
            tags['comment'] = str(comment_frames[0].text[0]) if comment_frames else ''
            
            # Read custom fields (TXXX frames)
            txxx_frames = audio_file.tags.getall('TXXX')
            for frame in txxx_frames:
                if frame.desc and frame.text:
                    # Use the description as the field name
                    custom_field_name = frame.desc
                    custom_field_value = str(frame.text[0]) if frame.text else ''
                    tags[custom_field_name] = custom_field_value
        
        return tags
        
    except Exception as e:
        print(f"Error reading ID3 tags from {file_path}: {e}")
        return {}

def read_spanish_audio_tags():
    """
    Read ID3 tags from 10 Spanish audio files and save to CSV.
    """
    
    # Find Spanish audio files (check both es-CO and es directories)
    spanish_patterns = [
        'audio_files/*/es-CO/shared/*.mp3',
        'audio_files/*/es/shared/*.mp3'
    ]
    
    spanish_files = []
    for pattern in spanish_patterns:
        files = glob.glob(pattern)
        spanish_files.extend(files)
    
    print(f"Found {len(spanish_files)} Spanish audio files")
    
    if len(spanish_files) == 0:
        print("No Spanish audio files found!")
        return
    
    # Take only the first 10 files
    files_to_analyze = spanish_files[:10]
    print(f"Analyzing first {len(files_to_analyze)} files...")
    
    # Read tags from each file
    all_tags_data = []
    
    for i, file_path in enumerate(files_to_analyze):
        print(f"Reading tags from: {os.path.basename(file_path)}")
        
        # Read ID3 tags
        tags = read_id3_tags_simple(file_path)
        
        # Add file info to the tags
        tags['file_path'] = file_path
        tags['file_name'] = os.path.basename(file_path)
        tags['file_number'] = i + 1
        
        # Get file size
        try:
            file_size = os.path.getsize(file_path)
            tags['file_size_bytes'] = file_size
        except:
            tags['file_size_bytes'] = 'N/A'
        
        all_tags_data.append(tags)
    
    # Convert to DataFrame
    df = pd.DataFrame(all_tags_data)
    
    # Reorder columns to put file info first
    file_info_cols = ['file_number', 'file_name', 'file_path', 'file_size_bytes']
    other_cols = [col for col in df.columns if col not in file_info_cols]
    df = df[file_info_cols + other_cols]
    
    # Create tests folder if it doesn't exist
    tests_dir = 'tests'
    if not os.path.exists(tests_dir):
        os.makedirs(tests_dir)
        print(f"Created {tests_dir} directory")
    
    # Save to CSV
    output_file = os.path.join(tests_dir, 'spanish_audio_id3_tags.csv')
    df.to_csv(output_file, index=False)
    
    print(f"\nID3 tags saved to: {output_file}")
    print(f"Analyzed {len(files_to_analyze)} files")
    
    # Display summary
    print(f"\nSummary of tags found:")
    for col in df.columns:
        if col not in file_info_cols:
            non_empty = df[col].notna().sum()
            print(f"  {col}: {non_empty}/{len(df)} files have this tag")
    
    # Show first few rows for verification
    print(f"\nSample of the data (first 3 files):")
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    print(df.head(3).to_string())
    
    return output_file

if __name__ == "__main__":
    read_spanish_audio_tags() 