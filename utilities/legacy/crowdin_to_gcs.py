#!/usr/bin/env python3
"""
Crowdin to Google Cloud Storage (GCS) Downloader
Downloads translation files from Crowdin and uploads them to GCS dev buckets.

This utility provides functionality to:
1. Download translation files/bundles from Crowdin using their API
2. Process and organize the downloaded files
3. Upload the files to appropriate GCS dev buckets for the LEVANTE project

Required dependencies:
- crowdin-api-client
- google-cloud-storage
- requests
"""

import os
import sys
import tempfile
import zipfile
import shutil
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from crowdin_api import CrowdinClient
    CROWDIN_AVAILABLE = True
except ImportError:
    CROWDIN_AVAILABLE = False
    print("Warning: crowdin-api-client not available. Install with: pip install crowdin-api-client")

try:
    from google.cloud import storage
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False
    print("Warning: google-cloud-storage not available. Install with: pip install google-cloud-storage")

from utilities.legacy.buckets import get_bucket_name, get_all_task_names, AUDIO_BUCKET_NAME_DEV
try:
    # For XLIFF normalization (fill empty targets when src==trg)
    from utilities.crowdin_xliff_manager import _normalize_xliff_fill_targets_when_same_language  # type: ignore
except Exception:
    _normalize_xliff_fill_targets_when_same_language = None

# Configuration constants
DEFAULT_BUNDLE_ID = 18  # From crowdin.yml
CROWDIN_PROJECT_ID_ENV = 'CROWDIN_PROJECT_ID'
CROWDIN_TOKEN_ENV = 'CROWDIN_TOKEN'
GOOGLE_CREDENTIALS_ENV = 'GOOGLE_APPLICATION_CREDENTIALS_JSON'

class CrowdinToGCS:
    """
    Main class for downloading files from Crowdin and uploading to GCS.
    """
    
    def __init__(self, 
                 crowdin_token: Optional[str] = None,
                 crowdin_project_id: Optional[str] = None,
                 google_credentials: Optional[str] = None,
                 bundle_id: int = DEFAULT_BUNDLE_ID):
        """
        Initialize the CrowdinToGCS instance.
        
        Args:
            crowdin_token: Crowdin API token (will check env if not provided)
            crowdin_project_id: Crowdin project ID (will check env if not provided)
            google_credentials: Google Cloud credentials JSON (will check env if not provided)
            bundle_id: Crowdin bundle ID to download (default from crowdin.yml)
        """
        self.bundle_id = bundle_id
        self.temp_dir = None
        
        # Initialize Crowdin client
        self.crowdin_token = crowdin_token or os.getenv(CROWDIN_TOKEN_ENV)
        self.crowdin_project_id = crowdin_project_id or os.getenv(CROWDIN_PROJECT_ID_ENV)
        
        if not self.crowdin_token or not self.crowdin_project_id:
            raise ValueError(f"Crowdin credentials required. Set {CROWDIN_TOKEN_ENV} and {CROWDIN_PROJECT_ID_ENV} environment variables or pass directly.")
        
        if not CROWDIN_AVAILABLE:
            raise ImportError("crowdin-api-client is required. Install with: pip install crowdin-api-client")
        
        self.crowdin_client = CrowdinClient(
            token=self.crowdin_token,
            project_id=int(self.crowdin_project_id)
        )
        
        # Initialize GCS client
        self.google_credentials = google_credentials or os.getenv(GOOGLE_CREDENTIALS_ENV)
        
        if not GCS_AVAILABLE:
            raise ImportError("google-cloud-storage is required. Install with: pip install google-cloud-storage")
        
        self.gcs_client = self._initialize_gcs()
        
        print(f"✅ Initialized CrowdinToGCS")
        print(f"   Crowdin Project ID: {self.crowdin_project_id}")
        print(f"   Bundle ID: {self.bundle_id}")
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
    
    def download_bundle(self) -> str:
        """
        Download a bundle from Crowdin.
        
        Returns:
            Path to the downloaded zip file
            
        Raises:
            Exception: If download fails
        """
        print(f"📥 Starting bundle download from Crowdin...")
        print(f"   Project ID: {self.crowdin_project_id}")
        print(f"   Bundle ID: {self.bundle_id}")
        
        try:
            # Build the bundle
            print("🔨 Building bundle...")
            build_response = self.crowdin_client.bundles.build_bundle(
                bundleId=self.bundle_id
            )
            
            if not build_response or 'data' not in build_response:
                raise Exception("Failed to build bundle - no response data")
            
            build_id = build_response['data']['id']
            print(f"   Build ID: {build_id}")
            
            # Wait for build completion and get download URL
            print("⏳ Waiting for build completion...")
            build_status = None
            max_attempts = 30
            attempt = 0
            
            while attempt < max_attempts:
                build_status = self.crowdin_client.bundles.check_bundle_build_status(
                    bundleId=self.bundle_id,
                    buildId=build_id
                )
                
                if build_status and 'data' in build_status:
                    status = build_status['data'].get('status', 'unknown')
                    print(f"   Status: {status} (attempt {attempt + 1}/{max_attempts})")
                    
                    if status == 'finished':
                        break
                    elif status == 'failed':
                        raise Exception("Bundle build failed")
                
                attempt += 1
                if attempt < max_attempts:
                    import time
                    time.sleep(2)  # Wait 2 seconds between checks
            
            if attempt >= max_attempts:
                raise Exception("Bundle build timeout")
            
            # Download the bundle
            print("💾 Downloading bundle...")
            download_response = self.crowdin_client.bundles.download_bundle(
                bundleId=self.bundle_id,
                buildId=build_id
            )
            
            if not download_response or 'data' not in download_response:
                raise Exception("Failed to get download URL")
            
            download_url = download_response['data']['url']
            print(f"   Download URL obtained: {download_url[:50]}...")
            
            # Create temp directory and download file
            self.temp_dir = tempfile.mkdtemp(prefix='crowdin_download_')
            zip_path = os.path.join(self.temp_dir, f'bundle_{self.bundle_id}.zip')
            
            # Download the actual file
            import requests
            response = requests.get(download_url)
            response.raise_for_status()
            
            with open(zip_path, 'wb') as f:
                f.write(response.content)
            
            file_size = os.path.getsize(zip_path)
            print(f"✅ Bundle downloaded successfully!")
            print(f"   File: {zip_path}")
            print(f"   Size: {file_size:,} bytes")
            
            return zip_path
            
        except Exception as e:
            print(f"❌ Failed to download bundle: {e}")
            raise
    
    def extract_bundle(self, zip_path: str) -> str:
        """
        Extract the downloaded bundle.
        
        Args:
            zip_path: Path to the zip file
            
        Returns:
            Path to the extracted directory
        """
        print(f"📂 Extracting bundle...")
        
        extract_dir = os.path.join(self.temp_dir, 'extracted')
        os.makedirs(extract_dir, exist_ok=True)
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_file:
                zip_file.extractall(extract_dir)
            
            # List extracted contents
            extracted_files = []
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    rel_path = os.path.relpath(os.path.join(root, file), extract_dir)
                    extracted_files.append(rel_path)
            
            print(f"✅ Extracted {len(extracted_files)} files:")
            for file_path in extracted_files[:10]:  # Show first 10 files
                print(f"   {file_path}")
            if len(extracted_files) > 10:
                print(f"   ... and {len(extracted_files) - 10} more files")
            
            # Normalize any XLIFF files: if srcLang == trgLang and target is empty/needs-translation,
            # fill target content from source so downstream processing sees usable text.
            if _normalize_xliff_fill_targets_when_same_language is not None:
                try:
                    for root_dir, _dirs, files in os.walk(extract_dir):
                        for fname in files:
                            if fname.lower().endswith('.xliff'):
                                path = os.path.join(root_dir, fname)
                                try:
                                    with open(path, 'rb') as f:
                                        data = f.read()
                                    new_data = _normalize_xliff_fill_targets_when_same_language(data)
                                    if new_data != data:
                                        with open(path, 'wb') as f:
                                            f.write(new_data)
                                except Exception:
                                    # Best-effort normalization; continue on errors
                                    pass
                except Exception:
                    pass

            return extract_dir
            
        except Exception as e:
            print(f"❌ Failed to extract bundle: {e}")
            raise
    
    def organize_files_by_task(self, extract_dir: str) -> Dict[str, List[str]]:
        """
        Organize extracted files by task for uploading to appropriate buckets.
        
        Args:
            extract_dir: Path to extracted files
            
        Returns:
            Dictionary mapping task names to lists of file paths
        """
        print(f"🗂️  Organizing files by task...")
        
        task_files = {}
        all_tasks = set(get_all_task_names())
        
        # Walk through all extracted files
        for root, dirs, files in os.walk(extract_dir):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, extract_dir)
                
                # Try to determine task from file path
                path_parts = rel_path.split(os.sep)
                identified_task = None
                
                # Look for task names in the path
                for part in path_parts:
                    part_lower = part.lower()
                    for task in all_tasks:
                        if task.lower() in part_lower or part_lower in task.lower():
                            identified_task = task
                            break
                    if identified_task:
                        break
                
                # If no specific task identified, use 'shared'
                if not identified_task:
                    identified_task = 'shared'
                
                if identified_task not in task_files:
                    task_files[identified_task] = []
                
                task_files[identified_task].append(file_path)
        
        # Summary
        print(f"✅ Organized files by task:")
        for task, files in task_files.items():
            bucket_name = get_bucket_name(task, 'dev')
            print(f"   {task}: {len(files)} files → {bucket_name}")
        
        return task_files
    
    def upload_to_gcs(self, task_files: Dict[str, List[str]], extract_dir: str) -> Dict[str, int]:
        """
        Upload organized files to appropriate GCS buckets.
        
        Args:
            task_files: Dictionary mapping tasks to file lists
            extract_dir: Base directory of extracted files
            
        Returns:
            Dictionary with upload results (task -> number of files uploaded)
        """
        if not self.gcs_client:
            raise Exception("GCS client not initialized")
        
        print(f"☁️  Starting upload to GCS buckets...")
        
        upload_results = {}
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        for task, file_paths in task_files.items():
            bucket_name = get_bucket_name(task, 'dev')
            if not bucket_name:
                print(f"⚠️  Skipping {task}: no bucket configured")
                continue
            
            print(f"📤 Uploading {len(file_paths)} files to {bucket_name}...")
            
            try:
                bucket = self.gcs_client.bucket(bucket_name)
                uploaded_count = 0
                
                for file_path in file_paths:
                    # Calculate relative path for GCS object name
                    rel_path = os.path.relpath(file_path, extract_dir)
                    
                    # Create GCS object name with timestamp prefix
                    gcs_object_name = f"crowdin_downloads/{timestamp}/{rel_path}"
                    
                    # Upload file
                    blob = bucket.blob(gcs_object_name)
                    blob.upload_from_filename(file_path)
                    uploaded_count += 1
                    
                    if uploaded_count <= 5:  # Show details for first 5 files
                        print(f"   ✅ {rel_path} → {gcs_object_name}")
                    elif uploaded_count == 6:
                        print(f"   ... uploading remaining files...")
                
                upload_results[task] = uploaded_count
                print(f"✅ {task}: uploaded {uploaded_count} files to {bucket_name}")
                
            except Exception as e:
                print(f"❌ Failed to upload {task} files to {bucket_name}: {e}")
                upload_results[task] = 0
        
        return upload_results
    
    def cleanup(self):
        """Clean up temporary files."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            print(f"🗑️  Cleaned up temporary directory: {self.temp_dir}")
    
    def download_and_upload(self) -> Dict[str, int]:
        """
        Complete workflow: download from Crowdin and upload to GCS.
        
        Returns:
            Dictionary with upload results
        """
        print(f"🚀 Starting Crowdin to GCS workflow...")
        print(f"   Timestamp: {datetime.now().isoformat()}")
        
        try:
            # Step 1: Download bundle
            zip_path = self.download_bundle()
            
            # Step 2: Extract bundle
            extract_dir = self.extract_bundle(zip_path)
            
            # Step 3: Organize files by task
            task_files = self.organize_files_by_task(extract_dir)
            
            # Step 4: Upload to GCS
            upload_results = self.upload_to_gcs(task_files, extract_dir)
            
            # Summary
            total_files = sum(upload_results.values())
            print(f"\n🎉 Workflow completed successfully!")
            print(f"   Total files uploaded: {total_files}")
            print(f"   Tasks processed: {len(upload_results)}")
            
            return upload_results
            
        except Exception as e:
            print(f"\n❌ Workflow failed: {e}")
            raise
        finally:
            self.cleanup()


def main():
    """Command-line interface for the Crowdin to GCS downloader."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Download translation files from Crowdin and upload to GCS dev buckets"
    )
    parser.add_argument(
        '--bundle-id', 
        type=int, 
        default=DEFAULT_BUNDLE_ID,
        help=f"Crowdin bundle ID to download (default: {DEFAULT_BUNDLE_ID})"
    )
    parser.add_argument(
        '--crowdin-token',
        help=f"Crowdin API token (or set {CROWDIN_TOKEN_ENV} env var)"
    )
    parser.add_argument(
        '--crowdin-project-id',
        help=f"Crowdin project ID (or set {CROWDIN_PROJECT_ID_ENV} env var)"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Download and organize files but don't upload to GCS"
    )
    
    args = parser.parse_args()
    
    try:
        # Create downloader instance
        downloader = CrowdinToGCS(
            crowdin_token=args.crowdin_token,
            crowdin_project_id=args.crowdin_project_id,
            bundle_id=args.bundle_id
        )
        
        if args.dry_run:
            print("🧪 DRY RUN MODE - No files will be uploaded to GCS")
            # Only download and organize
            zip_path = downloader.download_bundle()
            extract_dir = downloader.extract_bundle(zip_path)
            task_files = downloader.organize_files_by_task(extract_dir)
            print("\n📋 Summary of what would be uploaded:")
            for task, files in task_files.items():
                bucket_name = get_bucket_name(task, 'dev')
                print(f"   {task}: {len(files)} files → {bucket_name}")
        else:
            # Full workflow
            results = downloader.download_and_upload()
            print(f"\n📊 Final Results:")
            for task, count in results.items():
                print(f"   {task}: {count} files uploaded")
    
    except KeyboardInterrupt:
        print("\n⏹️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()