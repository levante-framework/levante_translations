#!/usr/bin/env python3
"""
Google Cloud Service Account Creation Script

Creates a service account with proper permissions for Levante dashboard deployment.
This script automates the process described in create_dashboard_service_account.md.

Usage:
    python utilities/create_service_account.py --project-id YOUR_PROJECT_ID
    python utilities/create_service_account.py --project-id YOUR_PROJECT_ID --prod
    python utilities/create_service_account.py --project-id YOUR_PROJECT_ID --both
"""

import argparse
import subprocess
import sys
import os
import json
from pathlib import Path

def run_command(cmd, description, capture_output=False):
    """Run a shell command and handle errors."""
    print(f"🔧 {description}...")
    print(f"   Command: {' '.join(cmd)}")
    
    try:
        if capture_output:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        else:
            subprocess.run(cmd, check=True)
            print(f"   ✅ Success")
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Failed: {e}")
        if capture_output and e.stderr:
            print(f"   Error: {e.stderr}")
        return None

def check_gcloud_auth():
    """Check if gcloud is authenticated and configured."""
    print("🔍 Checking gcloud authentication...")
    
    try:
        # Check if authenticated
        result = subprocess.run(['gcloud', 'auth', 'list', '--filter=status:ACTIVE', '--format=value(account)'], 
                              capture_output=True, text=True, check=True)
        if not result.stdout.strip():
            print("❌ No active gcloud authentication found")
            print("   Please run: gcloud auth login")
            return False
        
        print(f"   ✅ Authenticated as: {result.stdout.strip()}")
        
        # Check current project
        result = subprocess.run(['gcloud', 'config', 'get-value', 'project'], 
                              capture_output=True, text=True, check=True)
        if result.stdout.strip():
            print(f"   ✅ Current project: {result.stdout.strip()}")
        else:
            print("   ⚠️ No default project set")
            
        return True
        
    except subprocess.CalledProcessError:
        print("❌ gcloud CLI not found or not working")
        print("   Please install gcloud CLI: https://cloud.google.com/sdk/docs/install")
        return False

def create_service_account(project_id, environment='dev'):
    """Create service account for the specified environment."""
    
    # Configuration
    sa_name = f"levante-dashboard-writer-{environment}"
    sa_email = f"{sa_name}@{project_id}.iam.gserviceaccount.com"
    bucket_name = f"levante-dashboard-{environment}"
    key_filename = f"levante-dashboard-{environment}-key.json"
    
    print(f"\n🚀 Creating service account for {environment.upper()} environment")
    print(f"   Service Account: {sa_name}")
    print(f"   Email: {sa_email}")
    print(f"   Target Bucket: {bucket_name}")
    print(f"   Key File: {key_filename}")
    
    # Step 1: Create service account (or use existing)
    cmd = [
        'gcloud', 'iam', 'service-accounts', 'create', sa_name,
        '--display-name', f'Levante Dashboard Writer ({environment.upper()})',
        '--description', f'Service account for writing to levante-dashboard-{environment} bucket',
        '--project', project_id
    ]
    
    result = run_command(cmd, f"Creating service account '{sa_name}'", capture_output=True)
    if result is None:
        # Check if it failed because service account already exists
        check_cmd = ['gcloud', 'iam', 'service-accounts', 'describe', sa_email, '--project', project_id]
        existing = run_command(check_cmd, f"Checking if service account exists", capture_output=True)
        if existing is None:
            print(f"   ❌ Failed to create service account and it doesn't exist")
            return False
        else:
            print(f"   ⚠️ Service account already exists, will use existing one")
    
    # Step 2: Grant bucket permissions
    cmd = [
        'gsutil', 'iam', 'ch', f'serviceAccount:{sa_email}:objectAdmin', f'gs://{bucket_name}'
    ]
    
    if run_command(cmd, f"Granting permissions to bucket '{bucket_name}'") is None:
        print(f"   ⚠️ Bucket permission failed. Trying project-level permissions...")
        
        # Fallback to project-level permissions
        cmd = [
            'gcloud', 'projects', 'add-iam-policy-binding', project_id,
            '--member', f'serviceAccount:{sa_email}',
            '--role', 'roles/storage.objectAdmin'
        ]
        
        if run_command(cmd, f"Granting project-level storage permissions") is None:
            return False
    
    # Step 3: Create and download key
    cmd = [
        'gcloud', 'iam', 'service-accounts', 'keys', 'create', key_filename,
        '--iam-account', sa_email,
        '--project', project_id
    ]
    
    if run_command(cmd, f"Creating service account key") is None:
        return False
    
    # Step 4: Verify key file and show contents
    if os.path.exists(key_filename):
        print(f"\n✅ Service account created successfully!")
        print(f"   📧 Email: {sa_email}")
        print(f"   🔑 Key file: {key_filename}")
        print(f"   🪣 Target bucket: gs://{bucket_name}")
        
        # Show the JSON content for GitHub secret
        try:
            with open(key_filename, 'r') as f:
                key_content = f.read()
                print(f"\n📋 GitHub Secret Content (copy this to GOOGLE_APPLICATION_CREDENTIALS_JSON):")
                print("=" * 80)
                print(key_content)
                print("=" * 80)
        except Exception as e:
            print(f"   ⚠️ Could not read key file: {e}")
        
        return True
    else:
        print(f"   ❌ Key file {key_filename} was not created")
        return False

def test_service_account(key_filename, bucket_name):
    """Test the service account permissions."""
    print(f"\n🧪 Testing service account permissions...")
    
    # Set environment variable
    env = os.environ.copy()
    env['GOOGLE_APPLICATION_CREDENTIALS'] = key_filename
    
    # Test bucket access
    cmd = ['gsutil', 'ls', f'gs://{bucket_name}']
    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
        print(f"   ✅ Can access bucket gs://{bucket_name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Cannot access bucket: {e}")
        if e.stderr:
            print(f"   Error: {e.stderr}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Create Google Cloud service account for Levante dashboard')
    parser.add_argument('--project-id', required=True, help='Google Cloud project ID')
    parser.add_argument('--prod', action='store_true', help='Create for production environment')
    parser.add_argument('--both', action='store_true', help='Create for both dev and prod environments')
    parser.add_argument('--test', action='store_true', help='Test service account after creation')
    
    args = parser.parse_args()
    
    print("🔧 Levante Dashboard Service Account Creator")
    print("=" * 50)
    
    # Check prerequisites
    if not check_gcloud_auth():
        sys.exit(1)
    
    # Set project
    cmd = ['gcloud', 'config', 'set', 'project', args.project_id]
    if run_command(cmd, f"Setting project to {args.project_id}") is None:
        sys.exit(1)
    
    success = True
    
    # Create service accounts
    if args.both:
        environments = ['dev', 'prod']
    elif args.prod:
        environments = ['prod']
    else:
        environments = ['dev']
    
    for env in environments:
        if not create_service_account(args.project_id, env):
            success = False
        
        # Test if requested
        if args.test and success:
            key_filename = f"levante-dashboard-{env}-key.json"
            bucket_name = f"levante-dashboard-{env}"
            test_service_account(key_filename, bucket_name)
    
    if success:
        print(f"\n🎉 All done! Service account(s) created successfully.")
        print(f"\n📝 Next steps:")
        print(f"   1. Copy the JSON content above")
        print(f"   2. Go to GitHub repository → Settings → Secrets and variables → Actions")
        print(f"   3. Add secret: GOOGLE_APPLICATION_CREDENTIALS_JSON")
        print(f"   4. Paste the JSON content as the value")
        print(f"   5. Test automatic deployment!")
    else:
        print(f"\n❌ Some operations failed. Check the errors above.")
        sys.exit(1)

if __name__ == '__main__':
    main()