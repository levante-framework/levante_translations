#!/usr/bin/env python3
"""
Check Crowdin Machine Translation configuration.

This script checks if Google Translate (or other MT engines) are configured
in your Crowdin project.

Usage:
    python3 check_crowdin_mt_config.py [--project-id PROJECT_ID]
"""

import argparse
import os
import sys

try:
    import requests
except ImportError:
    print("❌ Error: 'requests' library required. Install with: pip install requests")
    sys.exit(1)

API_BASE = "https://api.crowdin.com/api/v2"


def check_mt_engines(project_id: str, token: str):
    """Check available MT engines in Crowdin project."""
    url = f"{API_BASE}/projects/{project_id}/mt/engines"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        engines = data.get("data", [])
        
        if not engines:
            print("⚠️  No machine translation engines configured")
            print()
            print("📋 To configure Google Translate:")
            print("   1. Go to https://crowdin.com/project/YOUR_PROJECT/settings/machine-translation")
            print("   2. Click 'Add Engine' or 'Configure'")
            print("   3. Select 'Google Translate'")
            print("   4. Enter your Google Cloud API key")
            print("   5. Save the configuration")
            return False
        
        print("✅ Available Machine Translation Engines:")
        print()
        
        google_found = False
        for engine in engines:
            engine_data = engine.get("data", {})
            engine_id = engine_data.get("id", "unknown")
            engine_name = engine_data.get("name", "unknown")
            engine_type = engine_data.get("type", "unknown")
            
            print(f"   • {engine_name} ({engine_id})")
            print(f"     Type: {engine_type}")
            
            if engine_id == "google" or "google" in engine_id.lower():
                google_found = True
                print(f"     ✅ Google Translate is configured!")
            
            print()
        
        if not google_found:
            print("⚠️  Google Translate not found in configured engines")
            print()
            print("📋 To add Google Translate:")
            print("   1. Go to https://crowdin.com/project/YOUR_PROJECT/settings/machine-translation")
            print("   2. Click 'Add Engine'")
            print("   3. Select 'Google Translate'")
            print("   4. Enter your Google Cloud API key")
            print("   5. Save the configuration")
            return False
        
        return True
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print("⚠️  Machine Translation API endpoint not found")
            print("   This might mean MT is not enabled for your project")
        else:
            print(f"❌ HTTP Error: {e.response.status_code}")
            try:
                error_data = e.response.json()
                print(f"   {error_data}")
            except:
                print(f"   {e.response.text[:200]}")
        return False
    except Exception as e:
        print(f"❌ Error checking MT configuration: {e}")
        return False


def get_crowdin_token():
    """Get Crowdin API token from environment or file (matching existing scripts)."""
    token = os.environ.get('CROWDIN_API_TOKEN')
    if token:
        return token.strip()
    
    # Try ~/.crowdin_api_token file (matching existing scripts)
    from pathlib import Path
    token_file = Path.home() / ".crowdin_api_token"
    if token_file.exists():
        return token_file.read_text().strip()
    
    print("❌ Error: CROWDIN_API_TOKEN environment variable or ~/.crowdin_api_token file required")
    sys.exit(1)


def resolve_project_id(identifier_or_id: str, headers: dict) -> str:
    """Resolve project identifier to numeric ID (matching existing scripts)."""
    if identifier_or_id.isdigit():
        return identifier_or_id
    
    # Try to resolve by identifier/name
    url = f"{API_BASE}/projects"
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        projects = response.json().get("data", [])
        for project in projects:
            data = project.get("data", {})
            if data.get("identifier") == identifier_or_id or data.get("name") == identifier_or_id:
                project_id = str(data.get("id"))
                print(f"ℹ️  Resolved '{identifier_or_id}' to project ID: {project_id}")
                return project_id
        print(f"❌ Error: Could not resolve project by identifier/name: {identifier_or_id}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error resolving project ID: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Check Crowdin Machine Translation configuration"
    )
    
    parser.add_argument('--project-id', '-p',
                       help='Crowdin project ID or identifier (or set CROWDIN_PROJECT_ID env var)')
    
    args = parser.parse_args()
    
    token = get_crowdin_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    project_identifier = args.project_id or os.environ.get('CROWDIN_PROJECT_ID')
    if not project_identifier:
        print("❌ Error: Project ID or identifier required")
        print("   Set CROWDIN_PROJECT_ID environment variable or use --project-id")
        print("   Can use project identifier (e.g., 'levantetranslations') or numeric ID")
        sys.exit(1)
    
    project_id = resolve_project_id(project_identifier, headers)
    
    print(f"🔍 Checking MT configuration for project: {project_identifier}")
    if project_id != project_identifier:
        print(f"   (Project ID: {project_id})")
    print()
    
    success = check_mt_engines(project_id, token)
    
    if success:
        print("✅ Google Translate is configured and ready to use!")
        print()
        print("🚀 You can now run:")
        print("   python3 crowdin_pretranslate_esperanto.py")
    else:
        print()
        print("📖 For detailed instructions, see:")
        print("   https://support.crowdin.com/project-settings/machine-translation/")


if __name__ == "__main__":
    main()

