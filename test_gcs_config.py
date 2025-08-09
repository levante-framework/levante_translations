#!/usr/bin/env python3
"""
Test script to verify GCS language configuration integration.
Tests both local fallback and GCS bucket loading.
"""

import os
import sys
sys.path.append('utilities')

def test_config_loading():
    print("🔧 Testing Language Configuration Loading")
    print("=" * 50)
    
    # Test 1: Import the updated config
    try:
        from utilities.config import get_languages
        languages = get_languages()
        
        print(f"✅ Successfully loaded language configuration")
        print(f"📊 Found {len(languages)} languages:")
        
        for lang_name, config in languages.items():
            service = config.get('service', 'Unknown')
            voice = config.get('voice', 'Unknown')
            lang_code = config.get('lang_code', 'Unknown')
            print(f"  • {lang_name}: {lang_code} → {service} → {voice}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to load configuration: {e}")
        return False

def test_gcs_direct():
    print("\n🌐 Testing Direct GCS Loading")
    print("=" * 50)
    
    try:
        from utilities.config_from_gcs import load_from_gcs, get_languages_config
        
        # Test direct GCS loading
        remote_config = load_from_gcs()
        if remote_config:
            print(f"✅ Successfully loaded from GCS: {remote_config.get('metadata', {}).get('saved_at', 'Unknown time')}")
            
            if 'languages' in remote_config:
                languages = remote_config['languages']
                print(f"📊 GCS has {len(languages)} languages configured")
                
                for lang_name in languages.keys():
                    print(f"  • {lang_name}")
            else:
                print("⚠️  No 'languages' key in GCS config")
        else:
            print("ℹ️  No remote config found (using local fallback)")
            
        # Test the fallback mechanism
        local_fallback = {
            'English': {'lang_code': 'en', 'service': 'ElevenLabs', 'voice': 'Test Voice'}
        }
        
        final_config = get_languages_config(local_fallback)
        print(f"📋 Final config source: {'GCS' if remote_config else 'Local fallback'}")
        
        return True
        
    except Exception as e:
        print(f"❌ GCS test failed: {e}")
        return False

def test_environment():
    print("\n🔑 Testing Environment")
    print("=" * 50)
    
    has_creds = bool(os.environ.get('GCP_SERVICE_ACCOUNT_JSON'))
    bucket = os.environ.get('AUDIO_DEV_BUCKET', 'levante-audio-dev')
    object_name = os.environ.get('LANGUAGE_CONFIG_OBJECT', 'language_config.json')
    
    print(f"GCP_SERVICE_ACCOUNT_JSON: {'✅ Set' if has_creds else '❌ Not set'}")
    print(f"Target bucket: {bucket}")
    print(f"Target object: {object_name}")
    
    if not has_creds:
        print("ℹ️  To enable GCS loading, set the GCP_SERVICE_ACCOUNT_JSON environment variable")
    
    return has_creds

if __name__ == '__main__':
    print("🧪 Levante Language Configuration Test")
    print("=" * 60)
    
    # Run tests
    env_ok = test_environment()
    config_ok = test_config_loading()
    gcs_ok = test_gcs_direct()
    
    print("\n📋 Test Summary")
    print("=" * 50)
    print(f"Environment: {'✅ Ready' if env_ok else '⚠️  Partial (local only)'}")
    print(f"Config Loading: {'✅ Working' if config_ok else '❌ Failed'}")
    print(f"GCS Integration: {'✅ Working' if gcs_ok else '❌ Failed'}")
    
    if config_ok:
        print("\n🎉 Audio generation scripts will use centralized language configuration!")
        if env_ok:
            print("   📡 Remote GCS config will be used when available")
        else:
            print("   💾 Local fallback config will be used")
    else:
        print("\n⚠️  There may be issues with the configuration system")
    
    print(f"\n💡 Next steps:")
    if not env_ok:
        print("   1. Set GCP_SERVICE_ACCOUNT_JSON environment variable for GCS integration")
    print("   2. Run: python generate_speech.py <language> to test audio generation")
    print("   3. Any changes made via the web dashboard will automatically be used by Python scripts")
