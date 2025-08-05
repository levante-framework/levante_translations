#!/usr/bin/env python3
"""
Levante Dashboard Deployment Script

Deploys only the itembank_translations.csv file to the Levante dashboard buckets.
This is specifically for the Levante dashboard, not the web dashboard.

Usage:
    python deploy_levante.py -dev              # Deploy to dev environment
    python deploy_levante.py -prod             # Deploy to prod environment  
    python deploy_levante.py -dev --dry-run    # Test deploy to dev
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

try:
    from google.cloud import storage
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False
    print("Warning: google-cloud-storage not available. Install with: pip install google-cloud-storage")

# Configuration
GOOGLE_CREDENTIALS_ENV = 'GOOGLE_APPLICATION_CREDENTIALS_JSON'
DASHBOARD_BUCKET_NAME_DEV = 'levante-dashboard-dev'
DASHBOARD_BUCKET_NAME_PROD = 'levante-dashboard-prod'

class LevanteDeployer:
    """
    Deployment class specifically for Levante dashboard files.
    """
    
    def __init__(self, environment: str = 'dev', google_credentials: str = None):
        """
        Initialize the LevanteDeployer.
        
        Args:
            environment: Target environment ('dev' or 'prod')
            google_credentials: Google Cloud credentials JSON
        """
        self.environment = environment.lower()
        if self.environment not in ['dev', 'prod']:
            raise ValueError("Environment must be 'dev' or 'prod'")
        
        # Initialize GCS client
        self.google_credentials = google_credentials or os.getenv(GOOGLE_CREDENTIALS_ENV)
        
        # Debug output
        if self.google_credentials:
            print(f"✅ Found credentials (length: {len(self.google_credentials)} chars)")
            print(f"   Starts with: {self.google_credentials[:20]}...")
        else:
            print(f"❌ No credentials found in environment variable: {GOOGLE_CREDENTIALS_ENV}")
            print(f"   Available env vars: {[k for k in os.environ.keys() if 'GOOGLE' in k or 'CRED' in k]}")
        
        if not GCS_AVAILABLE:
            raise ImportError("google-cloud-storage is required. Install with: pip install google-cloud-storage")
        
        self.gcs_client = self._initialize_gcs()
        
        # Get bucket name
        self.bucket_name = DASHBOARD_BUCKET_NAME_PROD if self.environment == 'prod' else DASHBOARD_BUCKET_NAME_DEV
        
        print(f"✅ Initialized LevanteDeployer")
        print(f"   Environment: {self.environment}")
        print(f"   Target Bucket: {self.bucket_name}")
        print(f"   GCS Client: {'✅ Ready' if self.gcs_client else '❌ Failed'}")
    
    def _initialize_gcs(self):
        """Initialize Google Cloud Storage client."""
        try:
            if self.google_credentials:
                credentials_dict = json.loads(self.google_credentials)
                return storage.Client.from_service_account_info(credentials_dict)
            else:
                # Try default credentials
                return storage.Client()
        except Exception as e:
            print(f"Warning: Failed to initialize GCS client: {e}")
            return None
    
    def find_itembank_translations(self):
        """
        Find the itembank_translations.csv file.
        
        Returns:
            Path to the file or None if not found
        """
        possible_paths = [
            "translation_text/item_bank_translations.csv",
            "item_bank_translations.csv",
            "itembank_translations.csv",
            "translation_text/itembank_translations.csv"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        return None
    
    def validate_file(self, file_path):
        """
        Validate that the file exists and is readable.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if file is valid, False otherwise
        """
        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            return False
        
        if not os.path.isfile(file_path):
            print(f"❌ Not a file: {file_path}")
            return False
        
        try:
            file_size = os.path.getsize(file_path)
            with open(file_path, 'rb') as f:
                f.read(1)  # Try to read first byte
            
            print(f"✅ File validated: {file_path} ({file_size:,} bytes)")
            return True
            
        except Exception as e:
            print(f"❌ Cannot read file {file_path}: {e}")
            return False
    
    def deploy_itembank_translations(self, dry_run=False):
        """
        Deploy the itembank_translations.csv file to GCS.
        
        Args:
            dry_run: If True, show what would be deployed without uploading
            
        Returns:
            True if deployment successful
        """
        print(f"📊 Deploying itembank_translations.csv to {self.environment} environment...")
        
        # Find the file
        file_path = self.find_itembank_translations()
        if not file_path:
            print("❌ itembank_translations.csv not found!")
            print("   Looked in:")
            print("   - translation_text/item_bank_translations.csv")
            print("   - item_bank_translations.csv") 
            print("   - itembank_translations.csv")
            print("   - translation_text/itembank_translations.csv")
            return False
        
        # Validate file
        if not self.validate_file(file_path):
            return False
        
        if dry_run:
            file_size = os.path.getsize(file_path)
            print(f"\n🧪 DRY RUN - File that would be uploaded to {self.bucket_name}:")
            print(f"   {file_path} → itembank_translations.csv ({file_size:,} bytes)")
            return True
        
        # Upload file
        if not self.gcs_client:
            raise Exception("GCS client not initialized")
        
        try:
            bucket = self.gcs_client.bucket(self.bucket_name)
            blob = bucket.blob('itembank_translations.csv')
            
            # Upload with metadata
            blob.upload_from_filename(file_path, content_type='text/csv')
            
            # Set metadata
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            blob.cache_control = 'public, max-age=1800'  # 30 minutes
            blob.metadata = {
                'deployed_at': timestamp,
                'deployed_by': 'deploy_levante.py',
                'environment': self.environment,
                'original_path': file_path
            }
            blob.patch()
            
            file_size = os.path.getsize(file_path)
            print(f"✅ Uploaded: {file_path} → {self.bucket_name}/itembank_translations.csv ({file_size:,} bytes)")
            return True
            
        except Exception as e:
            print(f"❌ Failed to upload file: {e}")
            return False


def main():
    """Command-line interface for Levante deployment."""
    
    # Parse simple arguments
    if len(sys.argv) < 2:
        print("Usage: python deploy_levante.py [-dev|-prod] [--dry-run]")
        print("Examples:")
        print("  python deploy_levante.py -dev")
        print("  python deploy_levante.py -prod")
        print("  python deploy_levante.py -dev --dry-run")
        sys.exit(1)
    
    # Determine environment
    environment = None
    dry_run = False
    
    for arg in sys.argv[1:]:
        if arg == '-dev':
            environment = 'dev'
        elif arg == '-prod':
            environment = 'prod'
        elif arg == '--dry-run':
            dry_run = True
    
    if not environment:
        print("❌ Environment required: use -dev or -prod")
        sys.exit(1)
    
    try:
        print(f"🚀 Levante Dashboard Deployment")
        print(f"   Target: itembank_translations.csv only")
        print(f"   Environment: {environment}")
        print(f"   Mode: {'DRY RUN' if dry_run else 'DEPLOY'}")
        print("=" * 50)
        
        # Create deployer and run
        deployer = LevanteDeployer(environment=environment)
        success = deployer.deploy_itembank_translations(dry_run=dry_run)
        
        if success:
            if dry_run:
                print(f"\n✅ Dry run completed - ready to deploy to {environment}!")
            else:
                print(f"\n🎉 Successfully deployed itembank_translations.csv to {environment}!")
                print(f"🌐 URL: https://storage.googleapis.com/{deployer.bucket_name}/itembank_translations.csv")
        else:
            print(f"\n❌ Deployment failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹️  Deployment cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Error: {e}")
        print("\n📋 Setup Instructions:")
        print("1. Install dependencies: pip install google-cloud-storage")
        print("2. Set credentials: export GOOGLE_APPLICATION_CREDENTIALS_JSON='...'")
        print("3. Ensure buckets exist in your GCP project")
        print("4. Make sure itembank_translations.csv exists in translation_text/ folder")
        sys.exit(1)

if __name__ == "__main__":
    main()