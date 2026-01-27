#!/usr/bin/env python3
"""
Test Child Survey Audio Counting

This script tests the child-survey audio file counting across all language subdirectories.
"""

import subprocess
import json

def count_child_survey_files(bucket_name, environment='dev'):
    """Count child-survey files across all language subdirectories."""
    print(f"🔍 Counting child-survey files in {bucket_name}...")
    
    try:
        # List all files in child-survey directory (including subdirectories)
        cmd = ['gsutil', 'ls', '-r', f'gs://{bucket_name}/audio/child-survey/**']
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        files = result.stdout.strip().split('\n')
        files = [f for f in files if f.endswith('.mp3')]
        
        # Group by language
        by_language = {}
        total = 0
        
        for file_path in files:
            # Extract language from path like: gs://bucket/audio/child-survey/es-CO/filename.mp3
            path_parts = file_path.split('/')
            if len(path_parts) >= 5 and path_parts[-2]:  # language is second to last part
                lang = path_parts[-2]
                if lang not in by_language:
                    by_language[lang] = 0
                by_language[lang] += 1
                total += 1
        
        print(f"✅ Found {total} child-survey audio files")
        print(f"📊 By language:")
        for lang, count in sorted(by_language.items()):
            print(f"   • {lang}: {count} files")
        
        return total, by_language
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running gsutil: {e}")
        print(f"   stderr: {e.stderr}")
        return 0, {}
    except Exception as e:
        print(f"❌ Error: {e}")
        return 0, {}

def main():
    """Test child-survey counting for both environments."""
    print("🎯 Child Survey Audio Counting Test")
    print("="*50)
    
    # Test draft (dev staging) environment
    print("\n🔧 Testing DRAFT environment...")
    dev_total, dev_by_lang = count_child_survey_files('levante-assets-draft', 'draft')
    
    # Test prod environment  
    print("\n🔧 Testing PROD environment...")
    prod_total, prod_by_lang = count_child_survey_files('levante-assets-prod', 'prod')
    
    # Summary
    print("\n📊 Summary:")
    print(f"   • Draft total: {dev_total} files")
    print(f"   • Prod total: {prod_total} files")
    
    # Check if es-CO has the expected 25 files
    expected_es_co = 25
    dev_es_co = dev_by_lang.get('es-CO', 0)
    prod_es_co = prod_by_lang.get('es-CO', 0)
    
    print(f"\n🎯 es-CO Survey Files:")
    print(f"   • Draft: {dev_es_co} files (expected: {expected_es_co})")
    print(f"   • Prod: {prod_es_co} files (expected: {expected_es_co})")
    
    if dev_es_co == expected_es_co and prod_es_co == expected_es_co:
        print("✅ es-CO child-survey files are correctly deployed!")
    else:
        print("⚠️  es-CO child-survey files may be missing or incorrectly counted")

if __name__ == "__main__":
    main()
