#!/usr/bin/env python3
"""
Script to set CORS configuration for Levante audio buckets.
Allows web dashboard to access audio files directly from GCS buckets.
"""

import os
import sys
from typing import List, Dict, Optional
from google.cloud import storage
from google.api_core import exceptions

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Project and bucket configurations
PROJECT_ID_DEV = 'hs-levante-admin-dev'
PROJECT_ID_PROD = 'hs-levante-admin-prod'

AUDIO_BUCKET_DEV = 'levante-audio-dev'
AUDIO_BUCKET_PROD = 'levante-audio-prod'

# CORS configuration to allow web dashboard access
CORS_CONFIG = [
    {
        "origin": ["*"],
        "responseHeader": ["Content-Type"],
        "method": ["GET"],
        "maxAgeSeconds": 3600
    }
]


class BucketCORSManager:
    """Class to manage CORS settings for GCS buckets."""
    
    def __init__(self, project_id: str):
        """
        Initialize the GCS client for a specific project.
        
        Args:
            project_id: Google Cloud Project ID
        """
        try:
            self.client = storage.Client(project=project_id)
            self.project_id = project_id
            print(f"Initialized GCS client for project: {self.project_id}")
        except Exception as e:
            print(f"Error initializing GCS client: {e}")
            print("Make sure you have Google Cloud credentials configured.")
            print("Run: gcloud auth application-default login")
            raise
    
    def set_bucket_cors(self, bucket_name: str, cors_config: List[Dict]) -> bool:
        """
        Set CORS configuration for a specific bucket.
        
        Args:
            bucket_name: Name of the GCS bucket
            cors_config: CORS configuration as a list of dictionaries
            
        Returns:
            True if successful, False otherwise
        """
        try:
            bucket = self.client.bucket(bucket_name)
            
            # Check if bucket exists
            if not bucket.exists():
                print(f"❌ Bucket {bucket_name} does not exist in project {self.project_id}")
                return False
            
            # Set CORS configuration
            bucket.cors = cors_config
            bucket.patch()
            
            print(f"✅ CORS configuration set successfully for: {bucket_name}")
            return True
            
        except exceptions.NotFound:
            print(f"❌ Bucket {bucket_name} not found in project {self.project_id}")
            return False
        except exceptions.Forbidden:
            print(f"❌ Insufficient permissions to modify bucket {bucket_name}")
            return False
        except Exception as e:
            print(f"❌ Error setting CORS for bucket {bucket_name}: {e}")
            return False
    
    def get_bucket_cors(self, bucket_name: str) -> Optional[List[Dict]]:
        """
        Get current CORS configuration for a specific bucket.
        
        Args:
            bucket_name: Name of the GCS bucket
            
        Returns:
            CORS configuration as a list of dictionaries, or None if error
        """
        try:
            bucket = self.client.bucket(bucket_name)
            
            # Check if bucket exists
            if not bucket.exists():
                print(f"❌ Bucket {bucket_name} does not exist in project {self.project_id}")
                return None
            
            # Reload to get current configuration
            bucket.reload()
            cors_config = bucket.cors
            
            return cors_config
            
        except exceptions.NotFound:
            print(f"❌ Bucket {bucket_name} not found in project {self.project_id}")
            return None
        except Exception as e:
            print(f"❌ Error getting CORS for bucket {bucket_name}: {e}")
            return None
    
    def verify_cors_config(self, bucket_name: str, expected_config: List[Dict]) -> bool:
        """
        Verify that the CORS configuration matches expected settings.
        
        Args:
            bucket_name: Name of the GCS bucket
            expected_config: Expected CORS configuration
            
        Returns:
            True if configuration matches, False otherwise
        """
        current_config = self.get_bucket_cors(bucket_name)
        
        if current_config is None:
            return False
        
        # Check if configurations match
        if len(current_config) != len(expected_config):
            return False
        
        for i, expected_rule in enumerate(expected_config):
            if i >= len(current_config):
                return False
            
            current_rule = current_config[i]
            
            # Check each field in the CORS rule
            for key, expected_value in expected_rule.items():
                if key not in current_rule or current_rule[key] != expected_value:
                    return False
        
        return True


def set_cors_for_environment(environment: str, buckets_only: List[str] = None) -> bool:
    """
    Set CORS configuration for all buckets in a specific environment.
    
    Args:
        environment: 'dev' or 'prod'
        buckets_only: Optional list of specific bucket names to update
        
    Returns:
        True if all operations successful, False otherwise
    """
    if environment.lower() == 'prod':
        project_id = PROJECT_ID_PROD
        audio_bucket = AUDIO_BUCKET_PROD
        env_name = "PRODUCTION"
    else:
        project_id = PROJECT_ID_DEV
        audio_bucket = AUDIO_BUCKET_DEV
        env_name = "DEVELOPMENT"
    
    print(f"\n🌐 Setting CORS configuration for {env_name} environment")
    print(f"Project: {project_id}")
    print("-" * 60)
    
    try:
        cors_manager = BucketCORSManager(project_id)
        
        # Determine which buckets to update
        buckets_to_update = [audio_bucket]
        
        if buckets_only:
            # Filter to only specified buckets
            buckets_to_update = [b for b in buckets_to_update if b in buckets_only]
            if not buckets_to_update:
                print(f"⚠️  None of the specified buckets found in {env_name} environment")
                return False
        
        all_successful = True
        
        for bucket_name in buckets_to_update:
            print(f"\n📦 Processing bucket: {bucket_name}")
            
            # Set CORS configuration
            success = cors_manager.set_bucket_cors(bucket_name, CORS_CONFIG)
            if not success:
                all_successful = False
                continue
            
            # Verify the configuration was set correctly
            print("🔍 Verifying CORS configuration...")
            if cors_manager.verify_cors_config(bucket_name, CORS_CONFIG):
                print("✅ CORS configuration verified successfully")
            else:
                print("⚠️  CORS configuration verification failed")
                all_successful = False
        
        return all_successful
        
    except Exception as e:
        print(f"❌ Error setting CORS for {env_name} environment: {e}")
        return False


def show_cors_config(environment: str, bucket_name: str = None) -> None:
    """
    Display current CORS configuration for buckets.
    
    Args:
        environment: 'dev' or 'prod'
        bucket_name: Optional specific bucket name to check
    """
    if environment.lower() == 'prod':
        project_id = PROJECT_ID_PROD
        default_bucket = AUDIO_BUCKET_PROD
        env_name = "PRODUCTION"
    else:
        project_id = PROJECT_ID_DEV
        default_bucket = AUDIO_BUCKET_DEV
        env_name = "DEVELOPMENT"
    
    print(f"\n📋 CORS Configuration for {env_name} environment")
    print(f"Project: {project_id}")
    print("-" * 60)
    
    try:
        cors_manager = BucketCORSManager(project_id)
        
        buckets_to_check = [bucket_name] if bucket_name else [default_bucket]
        
        for bucket in buckets_to_check:
            print(f"\n📦 Bucket: {bucket}")
            cors_config = cors_manager.get_bucket_cors(bucket)
            
            if cors_config is None:
                print("❌ Could not retrieve CORS configuration")
                continue
            
            if not cors_config:
                print("⚠️  No CORS configuration set")
                continue
            
            print("✅ Current CORS configuration:")
            for i, rule in enumerate(cors_config):
                print(f"  Rule {i + 1}:")
                for key, value in rule.items():
                    print(f"    {key}: {value}")
                
    except Exception as e:
        print(f"❌ Error retrieving CORS configuration: {e}")


def main():
    """Main function with command line argument parsing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Set CORS configuration for Levante audio buckets")
    parser.add_argument('--action', choices=['set', 'show'], 
                       default='set', help='Action to perform (default: set)')
    parser.add_argument('--environment', choices=['dev', 'prod', 'both'], 
                       default='both', help='Target environment(s) (default: both)')
    parser.add_argument('--bucket', type=str,
                       help='Specific bucket name (for show action)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making changes')
    
    args = parser.parse_args()
    
    if args.dry_run and args.action == 'set':
        print("🔍 DRY RUN MODE - No changes will be made")
        print("\nWould set the following CORS configuration:")
        import json
        print(json.dumps(CORS_CONFIG, indent=2))
        
        environments = ['dev', 'prod'] if args.environment == 'both' else [args.environment]
        for env in environments:
            bucket_name = AUDIO_BUCKET_PROD if env == 'prod' else AUDIO_BUCKET_DEV
            project_id = PROJECT_ID_PROD if env == 'prod' else PROJECT_ID_DEV
            print(f"\nWould update bucket: {bucket_name} in project: {project_id}")
        
        return 0
    
    try:
        if args.action == 'show':
            if args.environment == 'both':
                show_cors_config('dev')
                show_cors_config('prod')
            else:
                show_cors_config(args.environment, args.bucket)
        
        elif args.action == 'set':
            success = True
            
            if args.environment == 'both':
                print("🚀 Setting CORS configuration for both environments...")
                success &= set_cors_for_environment('dev')
                success &= set_cors_for_environment('prod')
            else:
                success = set_cors_for_environment(args.environment)
            
            if success:
                print("\n🎉 All CORS configurations set successfully!")
                print("\n📝 CORS Configuration Applied:")
                import json
                print(json.dumps(CORS_CONFIG, indent=2))
                print("\n💡 This allows web browsers to access audio files directly from GCS buckets.")
            else:
                print("\n⚠️  Some CORS configurations failed. Check the output above for details.")
                return 1
        
        return 0
        
    except KeyboardInterrupt:
        print("\n⏹️  Operation cancelled by user")
        return 1
    except Exception as e:
        print(f"\n❌ Script failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())