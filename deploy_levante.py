#!/usr/bin/env python3
"""
Levante Translations Deployment Script

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
import subprocess
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
                print(f"🔧 Initializing GCS client with service account credentials...")
                credentials_dict = json.loads(self.google_credentials)
                client = storage.Client.from_service_account_info(credentials_dict)
                print(f"✅ GCS client initialized successfully with project: {credentials_dict.get('project_id', 'unknown')}")
                return client
            else:
                print(f"🔧 No explicit credentials found, trying default credentials...")
                client = storage.Client()
                print(f"✅ GCS client initialized with default credentials")
                return client
        except Exception as e:
            print(f"❌ Failed to initialize GCS client: {e}")
            print(f"   Error type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
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
        
        # Fetch + normalize latest translations (identifier->item_id, labels/label->task)
        print("📥 Fetching and normalizing latest translations...")
        try:
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            from utilities.get_translations_csv_merged import get_translations
            if not get_translations(force=True):
                print("❌ Failed to fetch latest translations - using local copy")
            else:
                print("✅ Successfully updated to latest translations")
        except Exception as e:
            print(f"⚠️  Warning: Could not fetch latest translations: {e}")
            print("   Using local copy...")
        
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
            print(f"   {file_path} → item-bank-translations.csv ({file_size:,} bytes)")
            return True
        
        # Upload file
        if not self.gcs_client:
            raise Exception("GCS client not initialized")
        
        print(f"🔧 About to upload using GCS client...")
        print(f"   Client project: {getattr(self.gcs_client, 'project', 'unknown')}")
        print(f"   Target bucket: {self.bucket_name}")
        
        try:
            bucket = self.gcs_client.bucket(self.bucket_name)
            blob = bucket.blob('item-bank-translations.csv')
            print(f"   Blob created: {blob.name} in bucket {bucket.name}")
            
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
            print(f"✅ Uploaded: {file_path} → {self.bucket_name}/item-bank-translations.csv ({file_size:,} bytes)")
            return True
            
        except Exception as e:
            print(f"❌ Failed to upload file: {e}")
            return False


def main():
    """Command-line interface for Levante deployment."""
    
    # Parse simple arguments
    if len(sys.argv) < 2:
        print("Usage: python deploy_levante.py [-dev|-prod] [--dry-run] [--validate]")
        print("Examples:")
        print("  python deploy_levante.py -dev")
        print("  python deploy_levante.py -prod")
        print("  python deploy_levante.py -dev --dry-run")
        print("  python deploy_levante.py -dev --validate")
        sys.exit(1)
    
    # Determine environment
    environment = None
    dry_run = False
    validate_core_tasks = False
    
    for arg in sys.argv[1:]:
        if arg == '-dev':
            environment = 'dev'
        elif arg == '-prod':
            environment = 'prod'
        elif arg == '--dry-run':
            dry_run = True
        elif arg == '--validate':
            validate_core_tasks = True
    
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
                if validate_core_tasks:
                    print("🧪 Would also validate core-tasks repository after deployment")
            else:
                print(f"\n🎉 Successfully deployed itembank_translations.csv to {environment}!")
                print(f"🌐 URL: https://storage.googleapis.com/{deployer.bucket_name}/item-bank-translations.csv")
                
                # Run core-tasks validation if requested
                if validate_core_tasks:
                    print(f"\n📋 Running core-tasks validation (quick test)...")
                    validation_cmd = ["python3", "validate_core_tasks.py", "--quick"]
                    try:
                        result = subprocess.run(validation_cmd, check=True, capture_output=True, text=True)
                        print(f"✅ Core-tasks validation passed!")
                    except subprocess.CalledProcessError as e:
                        print(f"❌ Core-tasks validation failed!")
                        print(f"   Exit code: {e.returncode}")
                        print(f"   💡 For faster testing, you can run individual tests:")
                        print(f"      python3 validate_core_tasks_single.py --list")
                        if e.stdout:
                            print(f"   Output: {e.stdout}")
                        if e.stderr:
                            print(f"   Error: {e.stderr}")
                        sys.exit(1)
                    except FileNotFoundError:
                        print(f"❌ validate_core_tasks.py script not found")
                        print("   Please ensure the validation script is in the current directory")
                        sys.exit(1)
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