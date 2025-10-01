#!/usr/bin/env python3
"""
Deploy Survey Audio Files to GCS Buckets

This script deploys the newly generated survey audio files to both dev and prod environments.
It uses rsync to efficiently sync only the survey audio files to the appropriate GCS buckets.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

# Configuration
AUDIO_SOURCE_DIR = "audio_files"
AUDIO_BUCKET_DIR = "audio"
BUCKET_NAME_DEV = "levante-assets-dev"
BUCKET_NAME_PROD = "levante-assets-prod"

def run_command(cmd, description, dry_run=False):
    """Run a command and return success status."""
    print(f"🔄 {description}")
    print(f"   Command: {' '.join(cmd)}")
    
    if dry_run:
        print("   🧪 DRY RUN - Would execute:")
        print(f"   {' '.join(cmd)}")
        return True
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"   ✅ Success")
        if result.stdout:
            print(f"   Output: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Failed with exit code {e.returncode}")
        if e.stderr:
            print(f"   Error: {e.stderr.strip()}")
        return False

def deploy_survey_audio_to_bucket(bucket_name, environment, dry_run=False, force=False):
    """Deploy survey audio files to a specific GCS bucket."""
    print(f"\n🎯 Deploying Survey Audio to {environment.upper()}")
    print("="*60)
    
    # Check if source directories exist
    es_co_dir = f"{AUDIO_SOURCE_DIR}/es-CO"
    child_survey_dir = f"{AUDIO_SOURCE_DIR}/child-survey/es-CO"
    
    if not os.path.exists(es_co_dir):
        print(f"❌ Source directory not found: {es_co_dir}")
        return False
    
    if not os.path.exists(child_survey_dir):
        print(f"❌ Child survey directory not found: {child_survey_dir}")
        return False
    
    # Count files to deploy
    es_co_files = [f for f in os.listdir(es_co_dir) if f.endswith('.mp3')]
    child_survey_files = [f for f in os.listdir(child_survey_dir) if f.endswith('.mp3')]
    
    print(f"📊 Files to deploy:")
    print(f"   • Standard es-CO: {len(es_co_files)} files")
    print(f"   • Child survey: {len(child_survey_files)} files")
    
    success = True
    
    # Deploy standard es-CO audio files
    print(f"\n📁 Deploying standard es-CO audio files...")
    source_path = f"{es_co_dir}/"
    target_path = f"gs://{bucket_name}/{AUDIO_BUCKET_DIR}/es-CO/"
    
    cmd = ["gsutil", "-m", "rsync", "-c", "-r"]
    if force:
        cmd.append("-u")  # Update only newer files
    cmd.extend([source_path, target_path])
    
    if not run_command(cmd, f"Sync es-CO audio to {bucket_name}", dry_run):
        success = False
    
    # Deploy child-survey audio files
    print(f"\n📁 Deploying child-survey audio files...")
    source_path = f"{child_survey_dir}/"
    target_path = f"gs://{bucket_name}/{AUDIO_BUCKET_DIR}/child-survey/es-CO/"
    
    cmd = ["gsutil", "-m", "rsync", "-c", "-r"]
    if force:
        cmd.append("-u")  # Update only newer files
    cmd.extend([source_path, target_path])
    
    if not run_command(cmd, f"Sync child-survey audio to {bucket_name}", dry_run):
        success = False
    
    return success

def verify_deployment(bucket_name, environment, dry_run=False):
    """Verify the deployment by listing files in the bucket."""
    print(f"\n🔍 Verifying deployment in {environment.upper()}")
    print("="*60)
    
    if dry_run:
        print("🧪 DRY RUN - Skipping verification")
        return True
    
    # List standard es-CO files
    print(f"📋 Standard es-CO files in {bucket_name}:")
    cmd = ["gsutil", "ls", f"gs://{bucket_name}/{AUDIO_BUCKET_DIR}/es-CO/"]
    run_command(cmd, f"List es-CO files in {bucket_name}", dry_run=False)
    
    # List child-survey files
    print(f"\n📋 Child-survey files in {bucket_name}:")
    cmd = ["gsutil", "ls", f"gs://{bucket_name}/{AUDIO_BUCKET_DIR}/child-survey/es-CO/"]
    run_command(cmd, f"List child-survey files in {bucket_name}", dry_run=False)
    
    return True

def main():
    """Main deployment function."""
    parser = argparse.ArgumentParser(description='Deploy survey audio files to GCS buckets')
    parser.add_argument('--environment', '-e', choices=['dev', 'prod', 'both'], 
                       default='both', help='Target environment(s)')
    parser.add_argument('--dry-run', '-n', action='store_true',
                       help='Show what would be deployed without actually deploying')
    parser.add_argument('--force', '-f', action='store_true',
                       help='Force update files even if they exist')
    
    args = parser.parse_args()
    
    print("🚀 Survey Audio Deployment Script")
    print("="*60)
    print(f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 Target: {args.environment}")
    print(f"🧪 Dry run: {args.dry_run}")
    print(f"💪 Force: {args.force}")
    print("="*60)
    
    success = True
    
    if args.environment in ['dev', 'both']:
        print(f"\n🔧 Deploying to DEV environment...")
        if not deploy_survey_audio_to_bucket(BUCKET_NAME_DEV, 'dev', args.dry_run, args.force):
            success = False
        if not verify_deployment(BUCKET_NAME_DEV, 'dev', args.dry_run):
            success = False
    
    if args.environment in ['prod', 'both']:
        print(f"\n🔧 Deploying to PROD environment...")
        if not deploy_survey_audio_to_bucket(BUCKET_NAME_PROD, 'prod', args.dry_run, args.force):
            success = False
        if not verify_deployment(BUCKET_NAME_PROD, 'prod', args.dry_run):
            success = False
    
    print("\n" + "="*60)
    if success:
        print("✅ Survey audio deployment completed successfully!")
        print(f"📁 Files deployed to:")
        if args.environment in ['dev', 'both']:
            print(f"   • Dev: gs://{BUCKET_NAME_DEV}/{AUDIO_BUCKET_DIR}/es-CO/")
            print(f"   • Dev: gs://{BUCKET_NAME_DEV}/{AUDIO_BUCKET_DIR}/child-survey/es-CO/")
        if args.environment in ['prod', 'both']:
            print(f"   • Prod: gs://{BUCKET_NAME_PROD}/{AUDIO_BUCKET_DIR}/es-CO/")
            print(f"   • Prod: gs://{BUCKET_NAME_PROD}/{AUDIO_BUCKET_DIR}/child-survey/es-CO/")
    else:
        print("❌ Survey audio deployment failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()

