#!/usr/bin/env python3
"""
crowdin_xliff_manager.py

Manage XLIFF files in Crowdin projects - upload, download, and sync.

This tool helps migrate from CSV to XLIFF workflow by:
1. Uploading XLIFF files to Crowdin
2. Downloading translated XLIFF files from Crowdin  
3. Managing file structure and language mappings
4. Preserving translation states and metadata

Usage:
    # Upload XLIFF files to Crowdin
    python utilities/crowdin_xliff_manager.py upload --project-id 756721 --source-dir xliff-migration-test/

    # Download translated XLIFF files from Crowdin
    python utilities/crowdin_xliff_manager.py download --project-id 756721 --output-dir xliff-from-crowdin/

    # Sync: upload source files and download translations
    python utilities/crowdin_xliff_manager.py sync --project-id 756721 --source-dir xliff/ --output-dir xliff/

Requires CROWDIN_API_TOKEN environment variable or ~/.crowdin_api_token file.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import requests

API_BASE = "https://api.crowdin.com/api/v2"

def get_crowdin_token() -> str:
    """Get Crowdin API token from environment or file."""
    # Try environment variable first
    token = os.environ.get('CROWDIN_API_TOKEN')
    if token:
        return token.strip()
    
    # Try token file
    token_file = Path.home() / '.crowdin_api_token'
    if token_file.exists():
        return token_file.read_text().strip()
    
    raise ValueError("Crowdin API token not found. Set CROWDIN_API_TOKEN environment variable or create ~/.crowdin_api_token file")

def make_request(method: str, url: str, headers: Dict[str, str], **kwargs) -> requests.Response:
    """Make HTTP request with error handling."""
    try:
        response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        print(f"❌ API request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                print(f"   Error details: {error_data}")
            except:
                print(f"   Response: {e.response.text[:200]}")
        raise

def list_project_files(project_id: str, headers: Dict[str, str]) -> List[Dict]:
    """List all files in a Crowdin project."""
    url = f"{API_BASE}/projects/{project_id}/files"
    response = make_request("GET", url, headers, params={"limit": 500})
    return response.json().get("data", [])

def list_project_languages(project_id: str, headers: Dict[str, str]) -> List[Dict]:
    """List all target languages in a Crowdin project."""
    url = f"{API_BASE}/projects/{project_id}/languages"
    response = make_request("GET", url, headers)
    return response.json().get("data", [])

def upload_xliff_file(project_id: str, headers: Dict[str, str], file_path: str, 
                     crowdin_path: str, update_existing: bool = True) -> Optional[Dict]:
    """Upload an XLIFF file to Crowdin via storage + file create/update."""
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return None
    
    # First, check if file already exists
    existing_files = list_project_files(project_id, headers)
    existing_file = None
    for file_data in existing_files:
        if file_data["data"]["path"] == crowdin_path:
            existing_file = file_data["data"]
            break
    
    if existing_file and update_existing:
        # Update existing file via storage
        file_id = existing_file["id"]
        storage_id = upload_to_storage(headers, file_path, file_name_override=os.path.basename(crowdin_path))
        url = f"{API_BASE}/projects/{project_id}/files/{file_id}"
        payload = {"storageId": storage_id}
        response = make_request("PUT", url, headers, json=payload)
        print(f"✅ Updated: {crowdin_path}")
        return response.json().get("data")
        
    elif not existing_file:
        # Create new file
        url = f"{API_BASE}/projects/{project_id}/files"
        storage_id = upload_to_storage(headers, file_path, file_name_override=os.path.basename(crowdin_path))
        # Crowdin will respect directories in "name" (e.g., surveys/myfile.xliff)
        payload = {"storageId": storage_id, "name": crowdin_path.lstrip('/')}
        response = make_request("POST", url, headers, json=payload)
        print(f"✅ Created: {crowdin_path}")
        return response.json().get("data")
    else:
        print(f"⚠️  File exists, skipping: {crowdin_path}")
        return existing_file

def download_xliff_file(project_id: str, headers: Dict[str, str], file_id: str, 
                       language_id: str, output_path: str, *, format: str = "xliff") -> bool:
    """Download a translated XLIFF file from Crowdin.

    Note: Some projects with non-XLIFF sources require an explicit format parameter.
    """
    
    # Build request (POST) to obtain a downloadable URL for this file/language
    build_url = f"{API_BASE}/projects/{project_id}/translations/builds/files/{file_id}"
    payload = {"targetLanguageId": language_id, "format": format}
    
    try:
        build_resp = make_request("POST", build_url, headers, json=payload)
        build_data = build_resp.json().get("data", {})
        download_url = build_data.get("url")
        if not download_url:
            print(f"❌ No download URL for file {file_id} lang {language_id}")
            return False
        # Download the file bytes
        bin_resp = requests.get(download_url, timeout=60)
        bin_resp.raise_for_status()
        # Save to file
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(bin_resp.content)
        print(f"✅ Downloaded: {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to download {output_path}: {e}")
        return False

def upload_xliff_directory(project_id: str, headers: Dict[str, str], source_dir: str, 
                          crowdin_base_path: str = "/translations/") -> Dict[str, str]:
    """Upload all XLIFF files from a directory to Crowdin."""
    
    source_path = Path(source_dir)
    if not source_path.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")
    
    uploaded_files = {}
    xliff_files = list(source_path.glob("*.xliff")) + list(source_path.glob("*.xlf"))
    
    if not xliff_files:
        print(f"No XLIFF files found in {source_dir}")
        return uploaded_files
    
    print(f"Uploading {len(xliff_files)} XLIFF files to Crowdin project {project_id}")
    
    for xliff_file in xliff_files:
        crowdin_path = crowdin_base_path + xliff_file.name
        
        try:
            result = upload_xliff_file(project_id, headers, str(xliff_file), crowdin_path)
            if result:
                uploaded_files[str(xliff_file)] = crowdin_path
        except Exception as e:
            print(f"❌ Failed to upload {xliff_file.name}: {e}")
    
    return uploaded_files

def download_xliff_translations(project_id: str, headers: Dict[str, str], output_dir: str,
                               file_pattern: str = "*", languages: Optional[List[str]] = None) -> Dict[str, List[str]]:
    """Download all translated XLIFF files from Crowdin."""
    
    # Get project files and languages (if not provided)
    files = list_project_files(project_id, headers)
    if languages is None:
        lang_rows = list_project_languages(project_id, headers)
        languages = [row["data"]["id"] for row in lang_rows]
    
    # Pick all files matching the pattern (default all), regardless of source format
    matched_files = []
    for file_data in files:
        file_info = file_data["data"]
        if file_pattern == "*" or Path(file_info["path"]).match(file_pattern):
            matched_files.append(file_info)
    
    if not matched_files:
        print("No files found in Crowdin project")
        return {}
    
    print(f"Downloading translations for {len(matched_files)} files in {len(languages)} languages (as XLIFF)")
    
    downloaded_files = {}
    
    for file_info in matched_files:
        file_id = file_info["id"]
        file_name = os.path.basename(file_info["path"])
        base_name = os.path.splitext(file_name)[0]
        
        file_downloads = []
        
        for lang_id in languages:
            
            # Create output filename: <source_base>-<langId>.xliff
            output_filename = f"{base_name}-{lang_id}.xliff"
            output_path = os.path.join(output_dir, output_filename)
            
            if download_xliff_file(project_id, headers, file_id, lang_id, output_path, format="xliff"):
                file_downloads.append(output_path)
        
        if file_downloads:
            downloaded_files[file_name] = file_downloads
    
    return downloaded_files


def find_file_by_path(project_id: str, headers: Dict[str, str], crowdin_path: str) -> Optional[Dict]:
    """Return file info for a given Crowdin path, if it exists."""
    files = list_project_files(project_id, headers)
    for file_data in files:
        data = file_data["data"]
        if data.get("path") == crowdin_path:
            return data
    return None


def upload_to_storage(headers: Dict[str, str], file_path: str, file_name_override: Optional[str] = None) -> int:
    """Upload a local file to Crowdin storage and return storageId."""
    url = f"{API_BASE}/storages"
    fname = file_name_override or os.path.basename(file_path)
    with open(file_path, 'rb') as f:
        storage_headers = {
            "Authorization": headers["Authorization"],
            "Crowdin-API-FileName": fname,
        }
        resp = make_request("POST", url, storage_headers, data=f)
        return resp.json()["data"]["id"]


def import_translations_for_file(project_id: str, headers: Dict[str, str], *, crowdin_file_path: str, local_xliff_path: str, target_language_id: str, import_eq_suggestions: bool = False) -> bool:
    """Import translations XLIFF into a specific Crowdin file and language."""
    # Resolve fileId
    file_info = find_file_by_path(project_id, headers, crowdin_file_path)
    if not file_info:
        print(f"❌ File not found in project {project_id}: {crowdin_file_path}")
        return False
    file_id = file_info["id"]

    # Upload to storage
    storage_id = upload_to_storage(headers, local_xliff_path)

    # Import translations
    url = f"{API_BASE}/projects/{project_id}/translations"
    payload = {
        "storageId": storage_id,
        "fileId": file_id,
        "languageId": target_language_id,
    }
    resp = make_request("POST", url, headers, json=payload)
    if resp.ok:
        print(f"✅ Imported translations for {target_language_id} from {os.path.basename(local_xliff_path)}")
        return True
    return False


def import_translations_directory(project_id: str, headers: Dict[str, str], *, crowdin_file_path: str, source_dir: str) -> Dict[str, bool]:
    """Import all XLIFF files in a directory as translations for a single Crowdin file.

    Expects files named like: <base>-<langId>.xliff
    """
    results: Dict[str, bool] = {}
    # Determine enabled target languages in the project
    try:
        langs_resp = list_project_languages(project_id, headers)
        enabled_lang_ids = {row["data"]["id"] for row in langs_resp}
    except Exception:
        enabled_lang_ids = set()
    for path in Path(source_dir).glob("*.xliff"):
        name = path.name
        # Skip obvious source-only files
        if "source-" in name:
            continue
        # Extract langId from filename patterns like itembank-es-CO.xliff
        base = os.path.splitext(name)[0]
        lang_id = base
        # Strip common prefixes
        for prefix in ("itembank-", "surveys-", "translations-"):
            if lang_id.startswith(prefix):
                lang_id = lang_id[len(prefix):]
                break
        if enabled_lang_ids and lang_id not in enabled_lang_ids:
            print(f"Skipping {name} (language '{lang_id}' not enabled in project)")
            results[lang_id] = False
            continue
        print(f"Importing {name} as language '{lang_id}' → {crowdin_file_path}")
        try:
            ok = import_translations_for_file(
                project_id,
                headers,
                crowdin_file_path=crowdin_file_path,
                local_xliff_path=str(path),
                target_language_id=lang_id,
            )
        except Exception as e:
            print(f"Error importing {name} for '{lang_id}': {e}")
            ok = False
        results[lang_id] = ok
    return results

def main():
    parser = argparse.ArgumentParser(
        description="Manage XLIFF files in Crowdin projects",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload XLIFF files to Crowdin
  python utilities/crowdin_xliff_manager.py upload --project-id 756721 --source-dir xliff-export/
  
  # Download translated XLIFF files
  python utilities/crowdin_xliff_manager.py download --project-id 756721 --output-dir xliff-downloads/
  
  # Full sync: upload sources, download translations
  python utilities/crowdin_xliff_manager.py sync --project-id 756721 --source-dir xliff/ --output-dir xliff/
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Upload command
    upload_parser = subparsers.add_parser('upload', help='Upload XLIFF files to Crowdin')
    upload_parser.add_argument('--project-id', required=True, help='Crowdin project ID')
    upload_parser.add_argument('--source-dir', required=True, help='Directory containing XLIFF files to upload')
    upload_parser.add_argument('--crowdin-path', default='/translations/', help='Base path in Crowdin project')
    
    # Download command
    download_parser = subparsers.add_parser('download', help='Download translated XLIFF files from Crowdin')
    download_parser.add_argument('--project-id', required=True, help='Crowdin project ID')
    download_parser.add_argument('--output-dir', required=True, help='Directory to save downloaded XLIFF files')
    download_parser.add_argument('--file-pattern', default='*', help='Glob to filter source files (default: all)')
    
    # Sync command
    sync_parser = subparsers.add_parser('sync', help='Upload sources and download translations')
    sync_parser.add_argument('--project-id', required=True, help='Crowdin project ID')
    sync_parser.add_argument('--source-dir', required=True, help='Directory containing source XLIFF files')
    sync_parser.add_argument('--output-dir', required=True, help='Directory to save translated XLIFF files')

    # Import translations command
    import_parser = subparsers.add_parser('import_translations', help='Import XLIFF translations into a specific Crowdin file path')
    import_parser.add_argument('--project-id', required=True, help='Crowdin project ID')
    import_parser.add_argument('--crowdin-file-path', required=True, help='Crowdin file path (e.g., /item-bank-translations.xlsx)')
    import_parser.add_argument('--source-dir', required=True, help='Directory with XLIFF files named <base>-<langId>.xliff')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        token = get_crowdin_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        if args.command == 'upload':
            uploaded = upload_xliff_directory(args.project_id, headers, args.source_dir, args.crowdin_path)
            print(f"\n✅ Successfully uploaded {len(uploaded)} XLIFF files")
            
        elif args.command == 'download':
            downloaded = download_xliff_translations(args.project_id, headers, args.output_dir, file_pattern=args.file_pattern)
            total_files = sum(len(files) for files in downloaded.values())
            print(f"\n✅ Successfully downloaded {total_files} translated XLIFF files")
        
        elif args.command == 'import_translations':
            # Import translations from a directory into a specific Crowdin file path
            results = import_translations_directory(args.project_id, headers, crowdin_file_path=args.crowdin_file_path, source_dir=args.source_dir)
            ok_count = sum(1 for v in results.values() if v)
            print(f"\n✅ Imported {ok_count}/{len(results)} languages into {args.crowdin_file_path}")
            
        elif args.command == 'sync':
            print("🔄 Starting XLIFF sync...")
            
            # Upload sources
            uploaded = upload_xliff_directory(args.project_id, headers, args.source_dir)
            print(f"📤 Uploaded {len(uploaded)} source files")
            
            # Wait a moment for Crowdin to process
            if uploaded:
                print("⏳ Waiting for Crowdin to process uploads...")
                time.sleep(5)
            
            # Download translations
            downloaded = download_xliff_translations(args.project_id, headers, args.output_dir)
            total_files = sum(len(files) for files in downloaded.values())
            print(f"📥 Downloaded {total_files} translated files")
            
            print(f"\n✅ Sync complete!")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
