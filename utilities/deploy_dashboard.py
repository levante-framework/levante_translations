#!/usr/bin/env python3
"""
Deploy Dashboard and Translations to Google Cloud Storage

This script deploys the Levante dashboard files and translation CSV to the appropriate
GCS buckets based on the specified environment (dev/prod).

Features:
- Uploads dashboard HTML, CSS, JS files to dashboard bucket
- Uploads translation CSV to translations bucket  
- Supports dev and prod environments
- Validates files before upload
- Sets appropriate content types and cache headers
- Provides detailed progress reporting

Usage:
    python utilities/deploy_dashboard.py --env dev
    python utilities/deploy_dashboard.py --env prod --dry-run
"""

import os
import sys
import argparse
import mimetypes
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from google.cloud import storage
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False
    print("Warning: google-cloud-storage not available. Install with: pip install google-cloud-storage")

# Import bucket functions directly from buckets module
current_dir = os.path.dirname(os.path.abspath(__file__))
buckets_path = os.path.join(current_dir, 'buckets.py')

# Import bucket configuration constants directly
DASHBOARD_BUCKET_NAME_DEV = 'levante-dashboard-dev'
DASHBOARD_BUCKET_NAME_PROD = 'levante-dashboard-prod'
TRANSLATIONS_BUCKET_NAME_DEV = 'levante-translations-dev'
TRANSLATIONS_BUCKET_NAME_PROD = 'levante-translations-prod'

def get_dashboard_bucket_name(environment: str = 'dev') -> str:
    """Get the dashboard bucket name for the specified environment."""
    if environment.lower() == 'prod':
        return DASHBOARD_BUCKET_NAME_PROD
    else:
        return DASHBOARD_BUCKET_NAME_DEV

def get_translations_bucket_name(environment: str = 'dev') -> str:
    """Get the translations bucket name for the specified environment."""
    if environment.lower() == 'prod':
        return TRANSLATIONS_BUCKET_NAME_PROD
    else:
        return TRANSLATIONS_BUCKET_NAME_DEV

def get_audio_bucket_name(environment: str = 'dev') -> str:
    """Get the audio bucket name for the specified environment."""
    if environment.lower() == 'prod':
        return 'levante-audio-prod'
    else:
        return 'levante-audio-dev'

# Configuration
GOOGLE_CREDENTIALS_ENV = 'GOOGLE_APPLICATION_CREDENTIALS_JSON'

class DashboardDeployer:
    """
    Main class for deploying dashboard and translations to GCS.
    """
    
    def __init__(self, environment: str = 'dev', google_credentials: Optional[str] = None):
        """
        Initialize the DashboardDeployer.
        
        Args:
            environment: Target environment ('dev' or 'prod')
            google_credentials: Google Cloud credentials JSON (will check env if not provided)
        """
        self.environment = environment.lower()
        if self.environment not in ['dev', 'prod']:
            raise ValueError("Environment must be 'dev' or 'prod'")
        
        # Initialize GCS client
        self.google_credentials = google_credentials or os.getenv(GOOGLE_CREDENTIALS_ENV)
        
        if not GCS_AVAILABLE:
            raise ImportError("google-cloud-storage is required. Install with: pip install google-cloud-storage")
        
        self.gcs_client = self._initialize_gcs()
        
        # Get bucket names
        self.dashboard_bucket = get_dashboard_bucket_name(self.environment)
        self.translations_bucket = get_translations_bucket_name(self.environment)
        
        print(f"✅ Initialized DashboardDeployer")
        print(f"   Environment: {self.environment}")
        print(f"   Dashboard Bucket: {self.dashboard_bucket}")
        print(f"   Translations Bucket: {self.translations_bucket}")
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
    
    def get_dashboard_files(self) -> List[Tuple[str, str]]:
        """
        Get list of dashboard files to deploy.
        
        Returns:
            List of (local_path, gcs_path) tuples
        """
        files_to_deploy = []
        base_dir = Path(".")
        
        # Dashboard files mapping: local_path -> gcs_path
        dashboard_files = {
            # Main dashboard files (use the consolidated index.html)
            "index.html": "index.html",
            "config.js": "config.js",
            "vercel.json": "vercel.json",
            
            # API directory
            "api/elevenlabs-proxy.js": "api/elevenlabs-proxy.js",
            "api/playht-proxy.js": "api/playht-proxy.js", 
            "api/translate-proxy.js": "api/translate-proxy.js",
            "api/validation-storage.js": "api/validation-storage.js",
            
            # Translation text directory
            "translation_text/complete_translations.csv": "translation_text/complete_translations.csv",
            
            # Package.json for dependencies
            "package.json": "package.json",
        }
        
        # Check for files and add to deployment list
        for local_path, gcs_path in dashboard_files.items():
            full_local_path = base_dir / local_path
            if full_local_path.exists():
                files_to_deploy.append((str(full_local_path), gcs_path))
            else:
                print(f"⚠️  File not found: {local_path}")
        
        # Also check for any additional web-dashboard files if they exist
        web_dashboard_dir = base_dir / "web-dashboard" / "public"
        if web_dashboard_dir.exists():
            print(f"📁 Found web-dashboard/public directory, including additional files...")
            for file_path in web_dashboard_dir.rglob("*"):
                if file_path.is_file():
                    rel_path = file_path.relative_to(web_dashboard_dir)
                    files_to_deploy.append((str(file_path), f"web-dashboard/{rel_path}"))
        
        return files_to_deploy
    
    def get_translation_files(self) -> List[Tuple[str, str]]:
        """
        Get list of translation CSV files to deploy.
        
        Returns:
            List of (local_path, gcs_path) tuples
        """
        files_to_deploy = []
        base_dir = Path(".")
        
        # Translation files to deploy
        translation_files = {
            "translation_master.csv": "translation_master.csv",
            "translation_text/item_bank_translations.csv": "translation_text/item_bank_translations.csv",
            "translation_text/complete_translations.csv": "translation_text/complete_translations.csv",
        }
        
        for local_path, gcs_path in translation_files.items():
            full_local_path = base_dir / local_path
            if full_local_path.exists():
                files_to_deploy.append((str(full_local_path), gcs_path))
            else:
                print(f"⚠️  Translation file not found: {local_path}")
        
        return files_to_deploy
    
    def get_content_type(self, file_path: str) -> str:
        """
        Get the appropriate content type for a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Content type string
        """
        content_type, _ = mimetypes.guess_type(file_path)
        
        # Set specific content types for known files
        if file_path.endswith('.js'):
            return 'application/javascript'
        elif file_path.endswith('.css'):
            return 'text/css'
        elif file_path.endswith('.html'):
            return 'text/html'
        elif file_path.endswith('.csv'):
            return 'text/csv'
        elif file_path.endswith('.json'):
            return 'application/json'
        
        return content_type or 'application/octet-stream'
    
    def get_cache_control(self, file_path: str) -> str:
        """
        Get appropriate cache control headers for a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Cache control string
        """
        if file_path.endswith('.html'):
            # HTML files: short cache
            return 'public, max-age=300'  # 5 minutes
        elif file_path.endswith(('.js', '.css')):
            # Static assets: longer cache
            return 'public, max-age=3600'  # 1 hour
        elif file_path.endswith('.csv'):
            # CSV files: medium cache
            return 'public, max-age=1800'  # 30 minutes
        else:
            # Default: short cache
            return 'public, max-age=600'  # 10 minutes
    
    def upload_files_to_bucket(self, bucket_name: str, files: List[Tuple[str, str]], 
                              file_type: str = "files") -> int:
        """
        Upload files to a specific GCS bucket.
        
        Args:
            bucket_name: Name of the GCS bucket
            files: List of (local_path, gcs_path) tuples
            file_type: Description of file type for logging
            
        Returns:
            Number of files successfully uploaded
        """
        if not self.gcs_client:
            raise Exception("GCS client not initialized")
        
        if not files:
            print(f"⚠️  No {file_type} to upload")
            return 0
        
        print(f"📤 Uploading {len(files)} {file_type} to {bucket_name}...")
        
        try:
            bucket = self.gcs_client.bucket(bucket_name)
            uploaded_count = 0
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            for local_path, gcs_path in files:
                try:
                    # Get file size for reporting
                    file_size = os.path.getsize(local_path)
                    
                    # Create blob
                    blob = bucket.blob(gcs_path)
                    
                    # Set metadata
                    content_type = self.get_content_type(local_path)
                    cache_control = self.get_cache_control(local_path)
                    
                    # Upload with metadata
                    blob.upload_from_filename(
                        local_path,
                        content_type=content_type
                    )
                    
                    # Set additional metadata
                    blob.cache_control = cache_control
                    blob.metadata = {
                        'deployed_at': timestamp,
                        'deployed_by': 'deploy_dashboard.py',
                        'environment': self.environment,
                        'original_path': local_path
                    }
                    blob.patch()
                    
                    uploaded_count += 1
                    
                    if uploaded_count <= 10:  # Show details for first 10 files
                        print(f"   ✅ {os.path.basename(local_path)} ({file_size:,} bytes) → {gcs_path}")
                    elif uploaded_count == 11:
                        print(f"   ... uploading remaining files...")
                    
                except Exception as e:
                    print(f"   ❌ Failed to upload {local_path}: {e}")
            
            print(f"✅ {file_type}: uploaded {uploaded_count}/{len(files)} files to {bucket_name}")
            return uploaded_count
            
        except Exception as e:
            print(f"❌ Failed to upload {file_type} to {bucket_name}: {e}")
            return 0
    
    def validate_files(self, files: List[Tuple[str, str]]) -> bool:
        """
        Validate that all files exist and are readable.
        
        Args:
            files: List of (local_path, gcs_path) tuples
            
        Returns:
            True if all files are valid
        """
        print("🔍 Validating files...")
        
        all_valid = True
        total_size = 0
        
        for local_path, gcs_path in files:
            if not os.path.exists(local_path):
                print(f"❌ File not found: {local_path}")
                all_valid = False
                continue
            
            if not os.path.isfile(local_path):
                print(f"❌ Not a file: {local_path}")
                all_valid = False
                continue
            
            try:
                file_size = os.path.getsize(local_path)
                total_size += file_size
                
                # Check if file is readable
                with open(local_path, 'rb') as f:
                    f.read(1)  # Try to read first byte
                    
            except Exception as e:
                print(f"❌ Cannot read file {local_path}: {e}")
                all_valid = False
        
        if all_valid:
            print(f"✅ All {len(files)} files validated (total size: {total_size:,} bytes)")
        else:
            print("❌ File validation failed")
        
        return all_valid
    
    def deploy_dashboard(self, dry_run: bool = False) -> bool:
        """
        Deploy dashboard files to GCS.
        
        Args:
            dry_run: If True, show what would be deployed without uploading
            
        Returns:
            True if deployment successful
        """
        print(f"🌐 Deploying dashboard to {self.environment} environment...")
        
        # Get files to deploy
        dashboard_files = self.get_dashboard_files()
        
        if not dashboard_files:
            print("❌ No dashboard files found to deploy")
            return False
        
        # Validate files
        if not self.validate_files(dashboard_files):
            return False
        
        if dry_run:
            print(f"\n🧪 DRY RUN - Dashboard files that would be uploaded to {self.dashboard_bucket}:")
            for local_path, gcs_path in dashboard_files:
                file_size = os.path.getsize(local_path)
                print(f"   {local_path} → {gcs_path} ({file_size:,} bytes)")
            return True
        
        # Upload files
        uploaded_count = self.upload_files_to_bucket(
            self.dashboard_bucket, 
            dashboard_files, 
            "dashboard files"
        )
        
        return uploaded_count > 0
    
    def deploy_translations(self, dry_run: bool = False) -> bool:
        """
        Deploy translation CSV files to GCS.
        
        Args:
            dry_run: If True, show what would be deployed without uploading
            
        Returns:
            True if deployment successful
        """
        print(f"📊 Deploying translations to {self.environment} environment...")
        
        # Get files to deploy
        translation_files = self.get_translation_files()
        
        if not translation_files:
            print("❌ No translation files found to deploy")
            return False
        
        # Validate files
        if not self.validate_files(translation_files):
            return False
        
        if dry_run:
            print(f"\n🧪 DRY RUN - Translation files that would be uploaded to {self.translations_bucket}:")
            for local_path, gcs_path in translation_files:
                file_size = os.path.getsize(local_path)
                print(f"   {local_path} → {gcs_path} ({file_size:,} bytes)")
            return True
        
        # Upload files
        uploaded_count = self.upload_files_to_bucket(
            self.translations_bucket, 
            translation_files, 
            "translation files"
        )
        
        return uploaded_count > 0
    
    def deploy_all(self, dry_run: bool = False) -> bool:
        """
        Deploy both dashboard and translations.
        
        Args:
            dry_run: If True, show what would be deployed without uploading
            
        Returns:
            True if both deployments successful
        """
        print(f"🚀 Starting full deployment to {self.environment} environment...")
        print(f"   Timestamp: {datetime.now().isoformat()}")
        
        try:
            # Deploy dashboard
            dashboard_success = self.deploy_dashboard(dry_run)
            
            # Deploy translations
            translations_success = self.deploy_translations(dry_run)
            
            # Summary
            if dry_run:
                print(f"\n🎯 Dry run completed for {self.environment} environment")
                print(f"   Dashboard: {'✅ Ready' if dashboard_success else '❌ Issues found'}")
                print(f"   Translations: {'✅ Ready' if translations_success else '❌ Issues found'}")
            else:
                print(f"\n🎉 Deployment completed!")
                print(f"   Dashboard: {'✅ Success' if dashboard_success else '❌ Failed'}")
                print(f"   Translations: {'✅ Success' if translations_success else '❌ Failed'}")
                
                if dashboard_success and translations_success:
                    print(f"\n🌐 Dashboard URLs:")
                    print(f"   Dashboard: https://storage.googleapis.com/{self.dashboard_bucket}/index.html")
                    print(f"   Translations: https://storage.googleapis.com/{self.translations_bucket}/translation_master.csv")
            
            return dashboard_success and translations_success
            
        except Exception as e:
            print(f"\n❌ Deployment failed: {e}")
            return False


def main():
    """Command-line interface for the dashboard deployer."""
    parser = argparse.ArgumentParser(
        description="Deploy Levante dashboard and translations to GCS buckets"
    )
    parser.add_argument(
        '--env', '--environment',
        choices=['dev', 'prod'],
        default='dev',
        help="Target environment (default: dev)"
    )
    parser.add_argument(
        '--dashboard-only',
        action='store_true',
        help="Deploy only dashboard files"
    )
    parser.add_argument(
        '--translations-only',
        action='store_true',
        help="Deploy only translation files"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Show what would be deployed without uploading"
    )
    parser.add_argument(
        '--google-credentials',
        help=f"Google Cloud credentials JSON (or set {GOOGLE_CREDENTIALS_ENV} env var)"
    )
    
    args = parser.parse_args()
    
    try:
        # Create deployer instance
        deployer = DashboardDeployer(
            environment=args.env,
            google_credentials=args.google_credentials
        )
        
        # Determine what to deploy
        if args.dashboard_only:
            success = deployer.deploy_dashboard(args.dry_run)
        elif args.translations_only:
            success = deployer.deploy_translations(args.dry_run)
        else:
            success = deployer.deploy_all(args.dry_run)
        
        if success:
            print(f"\n✅ Operation completed successfully!")
            sys.exit(0)
        else:
            print(f"\n❌ Operation failed!")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n⏹️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()