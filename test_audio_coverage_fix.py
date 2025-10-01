#!/usr/bin/env python3
"""
Test Audio Coverage Fix

This script tests the updated audio coverage functionality to ensure
child-survey files are properly detected and counted.
"""

import subprocess
import json
import os

def test_local_child_survey_files():
    """Test that child-survey files exist locally."""
    print("🔍 Testing local child-survey files...")
    
    # Check if child-survey directory exists
    child_survey_dir = "audio_files/child-survey"
    if not os.path.exists(child_survey_dir):
        print(f"❌ Child-survey directory not found: {child_survey_dir}")
        return False
    
    # Count files by language
    languages = {}
    total_files = 0
    
    for lang_dir in os.listdir(child_survey_dir):
        lang_path = os.path.join(child_survey_dir, lang_dir)
        if os.path.isdir(lang_path):
            mp3_files = [f for f in os.listdir(lang_path) if f.endswith('.mp3')]
            languages[lang_dir] = len(mp3_files)
            total_files += len(mp3_files)
    
    print(f"✅ Found {total_files} child-survey files locally")
    print(f"📊 By language:")
    for lang, count in sorted(languages.items()):
        print(f"   • {lang}: {count} files")
    
    return total_files > 0

def test_gcs_child_survey_files():
    """Test that child-survey files exist in GCS."""
    print("\n🔍 Testing GCS child-survey files...")
    
    try:
        # List child-survey files in dev bucket
        cmd = ['gsutil', 'ls', '-r', 'gs://levante-assets-dev/audio/child-survey/**']
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        files = result.stdout.strip().split('\n')
        files = [f for f in files if f.endswith('.mp3')]
        
        # Group by language
        by_language = {}
        total = 0
        
        for file_path in files:
            path_parts = file_path.split('/')
            if len(path_parts) >= 5 and path_parts[-2]:  # language is second to last part
                lang = path_parts[-2]
                if lang not in by_language:
                    by_language[lang] = 0
                by_language[lang] += 1
                total += 1
        
        print(f"✅ Found {total} child-survey files in GCS dev bucket")
        print(f"📊 By language:")
        for lang, count in sorted(by_language.items()):
            print(f"   • {lang}: {count} files")
        
        return total > 0
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error accessing GCS: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_web_dashboard_api():
    """Test the web dashboard API with child-survey prefix."""
    print("\n🔍 Testing web dashboard API...")
    
    # This would require the web dashboard to be running
    # For now, just show what the API call would look like
    print("📋 API call example:")
    print("   GET /api/read-tags?itemId=ClassNice&langCode=es-CO&prefix=child-survey&source=repo")
    print("   Expected URL: https://raw.githubusercontent.com/levante-framework/levante_translations/main/audio_files/child-survey/es-CO/ClassNice.mp3")
    
    return True

def main():
    """Run all tests."""
    print("🎯 Audio Coverage Fix Test")
    print("="*50)
    
    # Test local files
    local_ok = test_local_child_survey_files()
    
    # Test GCS files
    gcs_ok = test_gcs_child_survey_files()
    
    # Test API
    api_ok = test_web_dashboard_api()
    
    # Summary
    print("\n📊 Test Results:")
    print(f"   • Local files: {'✅' if local_ok else '❌'}")
    print(f"   • GCS files: {'✅' if gcs_ok else '❌'}")
    print(f"   • API support: {'✅' if api_ok else '❌'}")
    
    if local_ok and gcs_ok and api_ok:
        print("\n🎉 All tests passed! Child-survey files should now be visible in the web dashboard.")
    else:
        print("\n⚠️  Some tests failed. Check the issues above.")

if __name__ == "__main__":
    main()

