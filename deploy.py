#!/usr/bin/env python3
"""
Simple Deploy Script for Levante Dashboard and Translations

This is a simplified interface to the main deployment functionality.
Deploys dashboard files and translation CSV to GCS buckets.

Usage:
    python deploy.py -dev          # Deploy to dev environment
    python deploy.py -prod         # Deploy to prod environment  
    python deploy.py -dev --dry-run    # Test deploy to dev
"""

import sys
import os
from utilities.deploy_dashboard import DashboardDeployer

def main():
    """Simple command-line interface for deployment."""
    
    # Parse simple arguments
    if len(sys.argv) < 2:
        print("Usage: python deploy.py [-dev|-prod] [--dry-run]")
        print("Examples:")
        print("  python deploy.py -dev")
        print("  python deploy.py -prod")
        print("  python deploy.py -dev --dry-run")
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
        print(f"   Environment: {environment}")
        print(f"   Mode: {'DRY RUN' if dry_run else 'DEPLOY'}")
        print("=" * 50)
        
        # Create deployer and run
        deployer = DashboardDeployer(environment=environment)
        success = deployer.deploy_all(dry_run=dry_run)
        
        if success:
            if dry_run:
                print(f"\n✅ Dry run completed - ready to deploy to {environment}!")
            else:
                print(f"\n🎉 Successfully deployed to {environment} environment!")
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
        sys.exit(1)

if __name__ == "__main__":
    main()