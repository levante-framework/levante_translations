#!/usr/bin/env python3
"""
Voice Management Utility for PlayHT

This script helps manage voice mappings between readable names and PlayHT voice IDs.
It provides commands to list voices, add mappings, and update the voice cache.

Usage:
    python manage_voices.py list                    # List all available voices
    python manage_voices.py list --language es-CO   # List voices for specific language
    python manage_voices.py add "MyVoice" "s3://..."  # Add custom mapping
    python manage_voices.py update                   # Force update voice cache
    python manage_voices.py find "Salome"          # Find voices matching a pattern
"""

import argparse
import sys
import os
from typing import Optional

# Add the parent directory to the path so we can import voice_mapping
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PlayHt import voice_mapping


def list_voices(language_filter: Optional[str] = None):
    """List all available voices."""
    print("Fetching voice list from PlayHT...")
    voice_mapping.update_voices(force=True)
    
    voices = voice_mapping.list_voices(language_filter)
    
    if not voices:
        print("No voices found.")
        return
    
    print(f"\nFound {len(voices)} voices:")
    print("-" * 80)
    print(f"{'Readable Name':<40} {'Voice ID':<40}")
    print("-" * 80)
    
    for voice in sorted(voices, key=lambda x: x['name']):
        name = voice['name'][:38] + "..." if len(voice['name']) > 38 else voice['name']
        voice_id = voice['id'][:38] + "..." if len(voice['id']) > 38 else voice['id']
        print(f"{name:<40} {voice_id:<40}")


def add_mapping(readable_name: str, voice_id: str):
    """Add a custom voice mapping."""
    print(f"Adding mapping: '{readable_name}' -> '{voice_id}'")
    voice_mapping.add_voice_mapping(readable_name, voice_id)
    print("Mapping added successfully!")


def update_cache():
    """Force update the voice cache."""
    print("Updating voice cache from PlayHT API...")
    voice_mapping.update_voices(force=True)
    print("Voice cache updated successfully!")


def find_voices(pattern: str):
    """Find voices matching a pattern."""
    print(f"Searching for voices matching '{pattern}'...")
    voice_mapping.update_voices()
    
    voices = voice_mapping.list_voices()
    matching_voices = []
    
    for voice in voices:
        if pattern.lower() in voice['name'].lower():
            matching_voices.append(voice)
    
    if not matching_voices:
        print(f"No voices found matching '{pattern}'.")
        return
    
    print(f"\nFound {len(matching_voices)} matching voices:")
    print("-" * 80)
    print(f"{'Readable Name':<40} {'Voice ID':<40}")
    print("-" * 80)
    
    for voice in sorted(matching_voices, key=lambda x: x['name']):
        name = voice['name'][:38] + "..." if len(voice['name']) > 38 else voice['name']
        voice_id = voice['id'][:38] + "..." if len(voice['id']) > 38 else voice['id']
        print(f"{name:<40} {voice_id:<40}")


def test_mapping(readable_name: str):
    """Test if a readable name maps to a voice ID."""
    print(f"Testing mapping for '{readable_name}'...")
    voice_id = voice_mapping.get_voice_id(readable_name)
    
    if voice_id:
        print(f"✓ Found mapping: '{readable_name}' -> '{voice_id}'")
        
        # Try to get the readable name back
        reverse_name = voice_mapping.get_readable_name(voice_id)
        if reverse_name:
            print(f"✓ Reverse mapping: '{voice_id}' -> '{reverse_name}'")
        else:
            print("⚠ No reverse mapping found")
    else:
        print(f"✗ No mapping found for '{readable_name}'")
        print("Available similar names:")
        voices = voice_mapping.list_voices()
        similar = [v['name'] for v in voices if readable_name.lower() in v['name'].lower()]
        for name in similar[:5]:  # Show first 5 similar names
            print(f"  - {name}")


def show_config_voices():
    """Show the voices currently configured in config.py."""
    try:
        import utilities.config as conf
        languages = conf.get_languages()
        
        print("Current voices in config.py:")
        print("-" * 50)
        
        for lang_name, lang_info in languages.items():
            if lang_info['service'] == 'PlayHt':
                voice_name = lang_info['voice']
                lang_code = lang_info['lang_code']
                
                print(f"{lang_name} ({lang_code}): {voice_name}")
                
                # Test if this voice has a mapping
                voice_id = voice_mapping.get_voice_id(voice_name)
                if voice_id:
                    print(f"  ✓ Mapped to: {voice_id[:50]}...")
                else:
                    print(f"  ✗ No mapping found")
                print()
                
    except ImportError:
        print("Could not import utilities.config")


def main():
    parser = argparse.ArgumentParser(description="Manage PlayHT voice mappings")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List available voices')
    list_parser.add_argument('--language', help='Filter by language code (e.g., es-CO)')
    
    # Add command
    add_parser = subparsers.add_parser('add', help='Add a custom voice mapping')
    add_parser.add_argument('readable_name', help='Readable name for the voice')
    add_parser.add_argument('voice_id', help='PlayHT voice ID (S3 URL)')
    
    # Update command
    subparsers.add_parser('update', help='Force update voice cache')
    
    # Find command
    find_parser = subparsers.add_parser('find', help='Find voices matching a pattern')
    find_parser.add_argument('pattern', help='Pattern to search for')
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Test a voice mapping')
    test_parser.add_argument('readable_name', help='Readable name to test')
    
    # Config command
    subparsers.add_parser('config', help='Show voices from config.py')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'list':
            list_voices(args.language)
        elif args.command == 'add':
            add_mapping(args.readable_name, args.voice_id)
        elif args.command == 'update':
            update_cache()
        elif args.command == 'find':
            find_voices(args.pattern)
        elif args.command == 'test':
            test_mapping(args.readable_name)
        elif args.command == 'config':
            show_config_voices()
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 