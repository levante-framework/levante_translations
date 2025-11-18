#!/usr/bin/env python3
"""
Use Crowdin's pre-translate feature with Google Translate to populate Portuguese translations.

This script uses Crowdin's built-in machine translation (Google Translate) to automatically
populate Portuguese translations, which is cleaner than manually translating and uploading.

Usage:
    python3 crowdin_pretranslate_portuguese.py [--project-id PROJECT_ID] [--dry-run]
    
Environment variables:
    CROWDIN_API_TOKEN: Crowdin API token (required)
    CROWDIN_PROJECT_ID: Crowdin project ID (or use --project-id)
"""

import argparse
import os
import sys
import time
import json
from typing import Dict, List, Optional

# Prefer requests if available
try:
    import requests
except ImportError:
    requests = None
    print("❌ Error: 'requests' library required. Install with: pip install requests")
    sys.exit(1)

import urllib.request
import urllib.parse
import urllib.error

API_BASE = "https://api.crowdin.com/api/v2"


def get_crowdin_token() -> str:
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


def get_headers(token: str) -> Dict[str, str]:
    """Create API headers."""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


def resolve_project_id(identifier_or_id: str, headers: Dict[str, str]) -> str:
    """Resolve project identifier to numeric ID (matching existing scripts)."""
    if identifier_or_id.isdigit():
        return identifier_or_id
    
    # Try to resolve by identifier/name
    url = f"{API_BASE}/projects"
    try:
        response = make_request("GET", url, headers)
        projects = response.get("data", [])
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


def make_request(method: str, url: str, headers: Dict[str, str], data: Optional[Dict] = None) -> Dict:
    """Make HTTP request to Crowdin API."""
    if requests:
        if data:
            response = requests.request(method, url, headers=headers, json=data, timeout=60)
        else:
            response = requests.request(method, url, headers=headers, timeout=60)
        response.raise_for_status()
        return response.json()
    else:
        # Fallback to urllib
        req_data = None
        if data:
            req_data = json.dumps(data).encode('utf-8')
            headers = {**headers, 'Content-Type': 'application/json'}
        
        req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode())


def check_language_exists(project_id: str, headers: Dict[str, str], lang_code: str) -> bool:
    """Check if target language exists in Crowdin project."""
    # Get project to check target languages (matching existing scripts)
    url = f"{API_BASE}/projects/{project_id}"
    
    try:
        response = make_request("GET", url, headers)
        project_data = response.get("data", {})
        target_languages = project_data.get("targetLanguages") or project_data.get("targetLanguageIds") or []
        
        # Check if language exists
        for lang in target_languages:
            lang_id = lang.get("id") if isinstance(lang, dict) else lang
            if lang_id == lang_code:
                return True
        
        return False
    except Exception as e:
        print(f"⚠️  Warning: Could not check languages: {e}")
        return False


def add_language_to_project(project_id: str, headers: Dict[str, str], lang_code: str) -> bool:
    """Add a language to the Crowdin project."""
    # Try using the project settings endpoint to add target languages
    url = f"{API_BASE}/projects/{project_id}"
    
    # First get current target languages
    try:
        response = make_request("GET", url, headers)
        project_data = response.get("data", {})
        current_langs = project_data.get("targetLanguageIds") or []
        
        # Check if already exists
        if lang_code in current_langs:
            print(f"ℹ️  Language '{lang_code}' already exists in project")
            return True
        
        # Add the new language
        current_langs.append(lang_code)
        
        # Update project with new language list
        update_data = {
            "targetLanguageIds": current_langs
        }
        
        print(f"➕ Adding language '{lang_code}' to Crowdin project...")
        # Use PATCH to update project settings
        if requests:
            patch_response = requests.patch(url, headers=headers, json=update_data, timeout=30)
            patch_response.raise_for_status()
            print(f"✅ Language '{lang_code}' added successfully")
            return True
        else:
            # Fallback for urllib
            import json
            req = urllib.request.Request(url, data=json.dumps(update_data).encode('utf-8'), headers=headers, method='PATCH')
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    print(f"✅ Language '{lang_code}' added successfully")
                    return True
            return False
            
    except Exception as e:
        if hasattr(e, 'response') and e.response:
            try:
                if hasattr(e.response, 'json'):
                    error_data = e.response.json()
                else:
                    error_data = json.loads(e.response.read().decode())
                if 'already exists' in str(error_data).lower() or 'already added' in str(error_data).lower():
                    print(f"ℹ️  Language '{lang_code}' already exists in project")
                    return True
            except:
                pass
        print(f"❌ Error adding language: {e}")
        print(f"   Note: You may need to add '{lang_code}' manually in Crowdin project settings")
        return False


def get_pre_translate_engines(project_id: str, headers: Dict[str, str]) -> List[str]:
    """Get available machine translation engines for the project."""
    url = f"{API_BASE}/projects/{project_id}/mt/engines"
    
    try:
        response = make_request("GET", url, headers)
        engines = response.get("data", [])
        
        available_engines = []
        for engine in engines:
            engine_id = engine.get("data", {}).get("id")
            if engine_id:
                available_engines.append(engine_id)
        
        return available_engines
    except Exception as e:
        print(f"⚠️  Warning: Could not fetch MT engines: {e}")
        # Return common engine IDs
        return ["google", "google_automl", "microsoft"]


def pre_translate(
    project_id: str,
    headers: Dict[str, str],
    target_lang: str,
    engine: str = "google",
    dry_run: bool = False
) -> Optional[str]:
    """Trigger pre-translation using machine translation."""
    
    url = f"{API_BASE}/projects/{project_id}/pre-translations"
    
    # Pre-translate configuration
    # Simplified request with only required/valid fields
    # engineId must be an integer (e.g., 568372 for Google Translate)
    try:
        engine_id = int(engine)
    except ValueError:
        print(f"❌ Error: engine ID must be an integer, got: {engine}")
        print(f"   Use --engine 568372 for Google Translate")
        return None
    
    data = {
        "languageIds": [target_lang],
        "method": "mt",  # Use machine translation method
        "engineId": engine_id,
        "autoApproveOption": "none"  # Don't auto-approve, let translators review
    }
    
    if dry_run:
        print("🔍 DRY RUN - Would trigger pre-translation with:")
        print(f"   Language: {target_lang}")
        print(f"   Engine: {engine}")
        print(f"   Config: {json.dumps(data, indent=2)}")
        return None
    
    try:
        print(f"🚀 Starting pre-translation for '{target_lang}' using {engine}...")
        response = make_request("POST", url, headers, data)
        
        pre_translate_id = response.get("data", {}).get("identifier")
        
        if pre_translate_id:
            print(f"✅ Pre-translation started successfully")
            print(f"📋 Pre-translation ID: {pre_translate_id}")
            return pre_translate_id
        else:
            print(f"⚠️  Warning: Pre-translation started but no ID returned")
            return None
            
    except Exception as e:
        if hasattr(e, 'response') and e.response:
            try:
                error_data = e.response.json()
                print(f"❌ Error details: {json.dumps(error_data, indent=2)}")
            except:
                print(f"❌ Error response: {e.response.text[:500]}")
        else:
            print(f"❌ Error starting pre-translation: {e}")
        return None


def check_pre_translate_status(project_id: str, headers: Dict[str, str], pre_translate_id: str) -> Optional[str]:
    """Check the status of a pre-translation job."""
    url = f"{API_BASE}/projects/{project_id}/pre-translations/{pre_translate_id}"
    
    try:
        response = make_request("GET", url, headers)
        status = response.get("data", {}).get("status")
        return status
    except Exception as e:
        print(f"⚠️  Warning: Could not check pre-translation status: {e}")
        return None


def wait_for_pre_translate(project_id: str, headers: Dict[str, str], pre_translate_id: str, timeout: int = 300) -> bool:
    """Wait for pre-translation to complete."""
    print(f"⏳ Waiting for pre-translation to complete...")
    print(f"   (This may take a few minutes)")
    
    start_time = time.time()
    last_status = None
    
    while time.time() - start_time < timeout:
        status = check_pre_translate_status(project_id, headers, pre_translate_id)
        
        if status != last_status:
            if status == "finished":
                print(f"✅ Pre-translation completed successfully!")
                return True
            elif status == "failed":
                print(f"❌ Pre-translation failed")
                return False
            elif status:
                print(f"   Status: {status}")
                last_status = status
        
        time.sleep(5)  # Check every 5 seconds
    
    print(f"⏱️  Timeout waiting for pre-translation (waited {timeout} seconds)")
    print(f"   Check status manually in Crowdin dashboard")
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Use Crowdin's pre-translate with Google Translate to populate Portuguese",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 crowdin_pretranslate_portuguese.py
  python3 crowdin_pretranslate_portuguese.py --project-id 123456
  python3 crowdin_pretranslate_portuguese.py --dry-run
  python3 crowdin_pretranslate_portuguese.py --lang pt-BR --engine google
  
This script:
1. Adds Portuguese (pt) to your Crowdin project if not already present
2. Triggers pre-translation using Google Translate
3. Waits for completion and reports status

Note: Google Translate must be configured in your Crowdin project settings.
        """
    )
    
    parser.add_argument('--project-id', '-p',
                       help='Crowdin project ID (or set CROWDIN_PROJECT_ID env var)')
    parser.add_argument('--lang', '-l',
                       default='pt-PT',
                       help='Target language code (default: pt-PT for Portuguese)')
    parser.add_argument('--engine', '-e',
                       default='568372',
                       help='Machine translation engine ID (default: 568372 for Google Translate)')
    parser.add_argument('--dry-run',
                       action='store_true',
                       help='Dry run mode - show what would be done without actually doing it')
    parser.add_argument('--no-wait',
                       action='store_true',
                       help='Don\'t wait for pre-translation to complete')
    
    args = parser.parse_args()
    
    # Get API token
    token = get_crowdin_token()
    headers = get_headers(token)
    
    # Get project ID (can be identifier like "levantetranslations" or numeric ID)
    project_identifier = args.project_id or os.environ.get('CROWDIN_PROJECT_ID')
    if not project_identifier:
        print("❌ Error: Project ID or identifier required")
        print("   Set CROWDIN_PROJECT_ID environment variable or use --project-id")
        print("   Can use project identifier (e.g., 'levantetranslations') or numeric ID")
        sys.exit(1)
    
    # Resolve project ID if it's an identifier (matching existing scripts)
    project_id = resolve_project_id(project_identifier, headers)
    
    target_lang = args.lang
    engine = args.engine
    
    print(f"🌍 Crowdin Pre-Translate for {target_lang}")
    print(f"📋 Project: {project_identifier}")
    if project_id != project_identifier:
        print(f"   (Project ID: {project_id})")
    print(f"🔧 Engine: {engine}")
    print(f"🔑 Using API token: {token[:10]}...")
    print()
    
    # Check if language exists
    language_exists = check_language_exists(project_id, headers, target_lang)
    
    if not language_exists:
        print(f"⚠️  Language '{target_lang}' is not yet added to the Crowdin project")
        print(f"   Please add '{target_lang}' (Portuguese) manually in Crowdin project settings:")
        print(f"   1. Go to your Crowdin project: https://crowdin.com/project/levantetranslations/settings#target-languages")
        print(f"   2. Click 'Add Target Language'")
        print(f"   3. Search for and select 'Portuguese'")
        print(f"   4. Then run this script again")
        sys.exit(1)
    
    print(f"✅ Language '{target_lang}' is already in the project")
    print()
    
    # Check available engines
    if not args.dry_run:
        available_engines = get_pre_translate_engines(project_id, headers)
        if available_engines:
            print(f"📊 Available MT engines: {', '.join(available_engines)}")
            if engine not in available_engines:
                print(f"⚠️  Warning: Engine '{engine}' not in available engines")
                print(f"   Using anyway - Crowdin may reject if not configured")
        print()
    
    # Trigger pre-translation
    pre_translate_id = pre_translate(project_id, headers, target_lang, engine, args.dry_run)
    
    if args.dry_run:
        print()
        print("🔍 Dry run complete - no changes made")
        return
    
    if not pre_translate_id:
        print("❌ Failed to start pre-translation")
        sys.exit(1)
    
    print()
    
    # Wait for completion if requested
    if not args.no_wait:
        success = wait_for_pre_translate(project_id, headers, pre_translate_id)
        if success:
            print()
            print("🎉 Pre-translation completed!")
            print(f"📋 Review translations in Crowdin dashboard:")
            print(f"   https://crowdin.com/project/YOUR_PROJECT/translations#{target_lang}")
        else:
            print()
            print("⚠️  Pre-translation may still be in progress")
            print(f"📋 Check status in Crowdin dashboard")
    else:
        print()
        print("⏭️  Not waiting for completion")
        print(f"📋 Check status in Crowdin dashboard:")
        print(f"   Pre-translation ID: {pre_translate_id}")


if __name__ == "__main__":
    main()

