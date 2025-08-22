#!/usr/bin/env python3
"""
Comprehensive Translation Deployment Script

This script handles the complete deployment of translation-related files:
1. Deploys itembank_translations.csv to levante-dashboard buckets via rsync
2. Mirrors CSV/ICU/XLIFF to levante-assets-* buckets via rsync
3. Syncs audio files to levante-assets-* via rsync
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
import tempfile

# Configuration
AUDIO_SOURCE_DIR = "audio_files"
AUDIO_BUCKET_DIR = "audio"
AUDIO_BUCKET_NAME_DEV = "levante-assets-dev"
AUDIO_BUCKET_NAME_PROD = "levante-assets-prod"
TRANSLATION_BUCKET_DIR = "translations"
ICU_SOURCE_DIR = "xliff/translations-icu"
ICU_BUCKET_DIR = "translations/icu"
XLIFF_BUCKET_DIR = "translations/xliff"
XLIFF_GITHUB_REPO = "levante-framework/levante_translations"
XLIFF_GITHUB_REF = "l10n_pending"
XLIFF_GITHUB_PATH = "translations"
DASHBOARD_BUCKET_NAME_DEV = 'levante-dashboard-dev'
DASHBOARD_BUCKET_NAME_PROD = 'levante-dashboard-prod'

def get_audio_bucket_name(environment: str) -> str:
    """Get the audio bucket name for the specified environment."""
    if environment.lower() == 'prod':
        return AUDIO_BUCKET_NAME_PROD
    else:
        return AUDIO_BUCKET_NAME_DEV

def get_dashboard_bucket_name(environment: str) -> str:
    return DASHBOARD_BUCKET_NAME_PROD if environment.lower() == 'prod' else DASHBOARD_BUCKET_NAME_DEV

def print_header(title: str):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f"🚀 {title}")
    print(f"{'='*60}")

def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n📋 {title}")
    print("-" * 40)

def run_command(cmd: list, description: str, dry_run: bool = False) -> bool:
    """
    Run a shell command with proper error handling.
    
    Args:
        cmd: Command to run as a list
        description: Human-readable description for logging
        dry_run: If True, only show what would be run
        
    Returns:
        True if command succeeded, False otherwise
    """
    cmd_str = ' '.join(cmd)
    
    if dry_run:
        print(f"🧪 DRY RUN - Would execute: {cmd_str}")
        return True
    
    print(f"🔧 {description}...")
    print(f"   Command: {cmd_str}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if result.stdout:
            # Filter out verbose gsutil output, show only important lines
            lines = result.stdout.strip().split('\n')
            important_lines = [line for line in lines if any(keyword in line.lower() 
                             for keyword in ['error', 'failed', 'success', 'completed', 'uploaded', 'copied'])]
            if important_lines:
                for line in important_lines[:5]:  # Show max 5 important lines
                    print(f"   📤 {line}")
            else:
                print(f"   ✅ Command completed successfully")
        
        if result.stderr and result.stderr.strip():
            # Show errors if any
            print(f"   ⚠️  Stderr: {result.stderr.strip()}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed: {description}")
        print(f"   Exit code: {e.returncode}")
        if e.stdout:
            print(f"   Stdout: {e.stdout}")
        if e.stderr:
            print(f"   Stderr: {e.stderr}")
        return False
    except FileNotFoundError:
        print(f"❌ Command not found: {cmd[0]}")
        print(f"   Make sure the command is installed and in your PATH")
        return False

def _split_languages(languages_csv):
    if not languages_csv:
        return []
    return [s.strip() for s in languages_csv.split(',') if s.strip()]

def check_prerequisites(environment: str, deploy_audio: bool) -> bool:
    """
    Check if all prerequisites are met for deployment.
    
    Args:
        environment: Target environment (dev/prod)
        deploy_audio: Whether audio deployment is requested
        
    Returns:
        True if all prerequisites are met
    """
    print_section("Prerequisites Check")
    
    all_good = True
    
    # Check if deploy_levante.py exists
    if not Path("deploy_levante.py").exists():
        print("❌ deploy_levante.py not found in current directory")
        all_good = False
    else:
        print("✅ deploy_levante.py found")
    
    # Check audio directory if audio deployment requested
    if deploy_audio:
        if not Path(AUDIO_SOURCE_DIR).exists():
            print(f"❌ Audio source directory not found: {AUDIO_SOURCE_DIR}")
            all_good = False
        elif not any(Path(AUDIO_SOURCE_DIR).iterdir()):
            print(f"⚠️  Audio source directory is empty: {AUDIO_SOURCE_DIR}")
            print("   This may be expected if no audio has been generated yet")
        else:
            # Count audio files
            audio_count = sum(1 for p in Path(AUDIO_SOURCE_DIR).rglob("*.mp3"))
            print(f"✅ Audio source directory found with {audio_count} MP3 files")
    
    # Check for gsutil if audio deployment requested
    if deploy_audio:
        try:
            result = subprocess.run(["gsutil", "version"], capture_output=True, check=True)
            print("✅ gsutil is available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("❌ gsutil not found. Please install Google Cloud SDK")
            print("   See: https://cloud.google.com/sdk/docs/install")
            all_good = False
    
    # Check credentials
    creds_env = 'GOOGLE_APPLICATION_CREDENTIALS_JSON'
    creds_file_env = 'GOOGLE_APPLICATION_CREDENTIALS'
    
    if os.getenv(creds_env):
        print(f"✅ Found credentials in {creds_env} environment variable")
    elif os.getenv(creds_file_env):
        print(f"✅ Found credentials file in {creds_file_env} environment variable")
    else:
        print(f"⚠️  No Google Cloud credentials found")
        print(f"   Set either {creds_env} or {creds_file_env}")
        print("   CSV deployment may fail without proper credentials")
    
    return all_good

def setup_gsutil_auth() -> None:
    """If creds are provided via GOOGLE_APPLICATION_CREDENTIALS_JSON, write them to a temp file
    and set GOOGLE_APPLICATION_CREDENTIALS so gsutil can authenticate."""
    json_env = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')
    file_env = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    # If a file is specified but missing, fall back to JSON env if available
    if file_env and not os.path.isfile(file_env):
        print(f"⚠️ {file_env} is set but file not found: {file_env}")
        file_env = None
    
    # Prefer existing valid file; otherwise write JSON to temp
    if not file_env and json_env:
        try:
            fd, path = tempfile.mkstemp(prefix='gsa_', suffix='.json')
            with os.fdopen(fd, 'w') as f:
                f.write(json_env)
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = path
            os.environ['CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE'] = path
            print(f"🔐 gsutil auth configured via GOOGLE_APPLICATION_CREDENTIALS -> {path}")
            print(f"🔐 CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE set for gsutil/gcloud -> {path}")
            # Try to activate account with gcloud if available (best-effort)
            try:
                subprocess.run([
                    'gcloud', 'auth', 'activate-service-account', '--key-file', path, '--quiet'
                ], check=False, capture_output=True)
            except Exception:
                pass
        except Exception as e:
            print(f"⚠️ Failed to configure gsutil auth from JSON env: {e}")
    elif file_env:
        # Ensure CLOUDSDK override also points to the same file so gsutil picks it up
        os.environ['CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE'] = file_env
        print(f"🔐 Using GOOGLE_APPLICATION_CREDENTIALS file -> {file_env}")
        print(f"🔐 CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE set -> {file_env}")

def verify_gsutil_auth(bucket_name: str) -> bool:
    """Run a quick auth check against the target bucket. Returns True if access works."""
    print_section("gsutil Auth Check")
    test_uri = f"gs://{bucket_name}"
    try:
        result = subprocess.run([
            'gsutil', 'ls', '-b', test_uri
        ], check=True, capture_output=True, text=True)
        print(f"✅ Auth OK for {test_uri}")
        return True
    except subprocess.CalledProcessError as e:
        print("❌ gsutil auth check failed")
        if e.stderr:
            print(f"   Stderr: {e.stderr.strip()}")
        # Best-effort remediation: try gcloud activation if we wrote creds
        key_file = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if key_file and os.path.isfile(key_file):
            try:
                subprocess.run([
                    'gcloud', 'auth', 'activate-service-account', '--key-file', key_file, '--quiet'
                ], check=False, capture_output=True)
                # Retry once
                retry = subprocess.run([
                    'gsutil', 'ls', '-b', test_uri
                ], check=True, capture_output=True, text=True)
                print(f"✅ Auth OK after activation for {test_uri}")
                return True
            except Exception:
                pass
        print("⚠️ Ensure GOOGLE_APPLICATION_CREDENTIALS_JSON is set (or GOOGLE_APPLICATION_CREDENTIALS points to a valid key file) in CI.")
        return False

def deploy_csv_to_assets(environment: str, dry_run: bool = False, force: bool = False) -> bool:
    """Rsync item-bank-translations.csv into levante-assets-* bucket under translations/."""
    print_section(f"CSV Mirror to Assets ({environment.upper()})")
    local_csv = "translation_text/item_bank_translations.csv"
    if not os.path.exists(local_csv):
        print(f"❌ Local CSV not found: {local_csv}")
        return False
    bucket = get_audio_bucket_name(environment)
    target_prefix = f"gs://{bucket}/{TRANSLATION_BUCKET_DIR}/"
    # Prepare temp dir with desired filename
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_csv = os.path.join(tmpdir, "item-bank-translations.csv")
        try:
            # Copy local CSV to temp with target name
            with open(local_csv, 'rb') as src, open(tmp_csv, 'wb') as dst:
                dst.write(src.read())
        except Exception as e:
            print(f"❌ Failed staging CSV: {e}")
            return False
        if force:
            run_command(["gsutil", "rm", f"{target_prefix}item-bank-translations.csv"], "Remove remote CSV (force)")
        cmd = ["gsutil", "-m", "rsync", "-c", "-r"]
        cmd.extend([f"{tmpdir}/", target_prefix])
        return run_command(cmd, f"Rsync CSV to {target_prefix}", dry_run)

def validate_core_tasks(core_tasks_path: str) -> bool:
    """
    Run core-tasks validation by calling the validate_core_tasks.py script.
    
    Args:
        core_tasks_path: Path to the core-tasks repository
        
    Returns:
        True if validation succeeded
    """
    print_section("Core-Tasks Validation")
    
    # Check if validation script exists
    validation_script = Path("validate_core_tasks.py")
    if not validation_script.exists():
        print("❌ validate_core_tasks.py script not found")
        print("   Core-tasks validation cannot be performed")
        return False
    
    # Build command
    cmd = ["python3", "validate_core_tasks.py", "--core-tasks-path", core_tasks_path, "--headless"]
    
    description = "Validate core-tasks repository with Cypress tests"
    return run_command(cmd, description, dry_run=False)

def deploy_audio(environment: str, dry_run: bool = False, force: bool = False) -> bool:
    """Deploy audio files using gsutil rsync (checksum)."""
    print_section(f"Audio Deployment to {environment.upper()}")
    bucket_name = get_audio_bucket_name(environment)
    source_path = f"{AUDIO_SOURCE_DIR}/"
    target_path = f"gs://{bucket_name}/{AUDIO_BUCKET_DIR}/"
    cmd = ["gsutil", "-m", "rsync", "-c", "-r", "-d"]
    if dry_run:
        cmd.append("-n")
    cmd.extend([source_path, target_path])
    print(f"📁 Source: {source_path}")
    print(f"🪣 Target: {target_path}")
    if dry_run:
        print("🧪 DRY RUN - Audio files that would be synced:")
    return run_command(cmd, f"Sync audio files to {bucket_name}", dry_run)

# =========================
# Promotion (dev → prod)
# =========================

def promote_audio_from_dev_to_prod(languages_csv, dry_run=False):
    """Promote audio from dev to prod using rsync. Optionally restrict to comma-separated languages.

    Always uses rsync with checksum to avoid redundant copies [[memory:6341171]].
    """
    print_section("Promote Audio (DEV → PROD)")
    langs = _split_languages(languages_csv)
    src_bucket = AUDIO_BUCKET_NAME_DEV
    dst_bucket = AUDIO_BUCKET_NAME_PROD
    if langs:
        ok = True
        for lang in langs:
            src = f"gs://{src_bucket}/{AUDIO_BUCKET_DIR}/{lang}/"
            dst = f"gs://{dst_bucket}/{AUDIO_BUCKET_DIR}/{lang}/"
            cmd = ["gsutil", "-m", "rsync", "-c", "-r", src, dst]
            ok = run_command(cmd, f"Rsync audio for {lang} to prod", dry_run) and ok
        return ok
    else:
        src = f"gs://{src_bucket}/{AUDIO_BUCKET_DIR}/"
        dst = f"gs://{dst_bucket}/{AUDIO_BUCKET_DIR}/"
        cmd = ["gsutil", "-m", "rsync", "-c", "-r", src, dst]
        return run_command(cmd, "Rsync ALL audio to prod", dry_run)

def promote_csv_from_dev_to_prod(dry_run=False):
    """Promote CSVs from dev to prod. Mirrors assets/translations via rsync and copies dashboard CSVs.

    - Assets mirror: rsync translations/ folder dev → prod [[memory:6341171]].
    - Dashboard CSVs: copy the two files; rsync cannot target individual files easily.
    """
    print_section("Promote CSV (DEV → PROD)")
    ok = True
    # Assets mirror (translations/)
    src_assets = f"gs://{AUDIO_BUCKET_NAME_DEV}/{TRANSLATION_BUCKET_DIR}/"
    dst_assets = f"gs://{AUDIO_BUCKET_NAME_PROD}/{TRANSLATION_BUCKET_DIR}/"
    cmd_assets = ["gsutil", "-m", "rsync", "-c", "-r", src_assets, dst_assets]
    ok = run_command(cmd_assets, "Rsync translations mirror to prod", dry_run) and ok

    # Dashboard bucket CSVs (two canonical names)
    for filename in ["itembank_translations.csv", "item-bank-translations.csv"]:
        src = f"gs://{DASHBOARD_BUCKET_NAME_DEV}/{filename}"
        dst = f"gs://{DASHBOARD_BUCKET_NAME_PROD}/{filename}"
        # Use cp with -n to avoid overwrite; small exception to rsync rule for single files
        cmd = ["gsutil", "cp", "-n", src, dst]
        ok = run_command(cmd, f"Copy dashboard CSV {filename} to prod", dry_run) and ok
    return ok

def promote_icu_from_dev_to_prod(languages_csv, dry_run=False):
    """Promote ICU JSONs from dev to prod. If languages specified, copy only those; else rsync all."""
    print_section("Promote ICU JSON (DEV → PROD)")
    langs = _split_languages(languages_csv)
    src_root = f"gs://{AUDIO_BUCKET_NAME_DEV}/{ICU_BUCKET_DIR}/"
    dst_root = f"gs://{AUDIO_BUCKET_NAME_PROD}/{ICU_BUCKET_DIR}/"
    if langs:
        ok = True
        for lang in langs:
            src = f"{src_root}{lang}.json"
            dst = f"{dst_root}{lang}.json"
            cmd = ["gsutil", "cp", "-n", src, dst]
            ok = run_command(cmd, f"Copy ICU {lang}.json to prod", dry_run) and ok
        return ok
    else:
        cmd = ["gsutil", "-m", "rsync", "-c", "-r", src_root, dst_root]
        return run_command(cmd, "Rsync ALL ICU JSON to prod", dry_run)

def promote_xliff_from_dev_to_prod(languages_csv, dry_run=False):
    """Promote XLIFFs from dev to prod. If languages specified, copy only matching files; else rsync all.

    Matching rule for subset: files starting with "<lang>" (e.g., es-AR*.xliff).
    """
    print_section("Promote XLIFF (DEV → PROD)")
    langs = _split_languages(languages_csv)
    src_root = f"gs://{AUDIO_BUCKET_NAME_DEV}/{XLIFF_BUCKET_DIR}/"
    dst_root = f"gs://{AUDIO_BUCKET_NAME_PROD}/{XLIFF_BUCKET_DIR}/"
    if langs:
        ok = True
        for lang in langs:
            # Use wildcard for language-prefixed files
            src = f"{src_root}{lang}*.xliff"
            cmd = ["gsutil", "cp", "-n", src, dst_root]
            ok = run_command(cmd, f"Copy XLIFF for {lang} to prod", dry_run) and ok
        return ok
    else:
        cmd = ["gsutil", "-m", "rsync", "-c", "-r", src_root, dst_root]
        return run_command(cmd, "Rsync ALL XLIFF to prod", dry_run)

# NEW: ICU JSON sync to assets bucket

def deploy_icu_to_assets(environment: str, dry_run: bool = False, force: bool = False) -> bool:
    """Sync ICU JSON files to levante-assets-* bucket under translations/icu/."""
    print_section(f"ICU JSON Mirror to Assets ({environment.upper()})")
    if not Path(ICU_SOURCE_DIR).exists():
        print(f"⚠️ ICU directory not found: {ICU_SOURCE_DIR}")
        return False
    bucket_name = get_audio_bucket_name(environment)
    source_path = f"{ICU_SOURCE_DIR}/"
    target_path = f"gs://{bucket_name}/{ICU_BUCKET_DIR}/"
    if force:
        run_command(["gsutil", "-m", "rm", "-r", target_path], "Remove remote ICU dir (force)")
    cmd = ["gsutil", "-m", "rsync", "-c", "-r", "-d"]
    if dry_run:
        cmd.append("-n")
    cmd.extend([source_path, target_path])
    print(f"📁 Source: {source_path}")
    print(f"🪣 Target: {target_path}")
    if dry_run:
        print("🧪 DRY RUN - ICU JSON files that would be synced:")
    return run_command(cmd, f"Sync ICU JSON to {target_path}", dry_run)

# NEW: Fetch XLIFF from GitHub and mirror to assets bucket

def deploy_xliff_to_assets_from_github(environment: str, dry_run: bool = False, force: bool = False) -> bool:
    """Fetch XLIFF files from GitHub and rsync to gs://levante-assets-*/translations/xliff/."""
    print_section(f"XLIFF Mirror to Assets from GitHub ({environment.upper()})")
    try:
        sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "xliff"))
        from xliff.convert_xliff_to_icu import list_xliff_files, build_raw_url, fetch_text  # type: ignore
    except Exception:
        try:
            from xliff.convert_xliff_to_icu import list_xliff_files, build_raw_url, fetch_text  # type: ignore
        except Exception as e:
            print(f"❌ Could not import XLIFF helpers: {e}")
            return False
    try:
        import os as _os
        token = _os.environ.get("GITHUB_TOKEN")
        files = list_xliff_files(XLIFF_GITHUB_REPO, XLIFF_GITHUB_REF, XLIFF_GITHUB_PATH, token)
    except Exception as e:
        print(f"❌ Failed listing GitHub XLIFF files: {e}")
        return False
    if not files:
        print("⚠️ No XLIFF files found in GitHub translations folder.")
        return False
    bucket_name = get_audio_bucket_name(environment)
    target_path = f"gs://{bucket_name}/{XLIFF_BUCKET_DIR}/"
    with tempfile.TemporaryDirectory() as tmpdir:
        for fi in files:
            name = fi.get("name")
            if not name or not name.lower().endswith(".xliff"):
                continue
            url = fi.get("download_url") or build_raw_url(XLIFF_GITHUB_REPO, XLIFF_GITHUB_REF, XLIFF_GITHUB_PATH, name)
            try:
                content = fetch_text(url, token)
            except Exception as e:
                print(f"   ❌ Fetch failed for {name}: {e}")
                continue
            local_path = os.path.join(tmpdir, name)
            with open(local_path, "w", encoding="utf-8") as f:
                f.write(content)
        if force:
            run_command(["gsutil", "-m", "rm", "-r", target_path], "Remove remote XLIFF dir (force)")
        cmd = ["gsutil", "-m", "rsync", "-c", "-r", "-d", f"{tmpdir}/", target_path]
        return run_command(cmd, f"Rsync XLIFF to {target_path}", dry_run)

# NEW: CSV upload to levante-dashboard bucket via rsync

def deploy_csv_to_dashboard(environment: str, dry_run: bool = False, force: bool = False) -> bool:
    print_section(f"CSV Deployment to {environment.upper()} (Dashboard)")
    local_csv = "translation_text/item_bank_translations.csv"
    if not os.path.exists(local_csv):
        print(f"❌ Local CSV not found: {local_csv}")
        return False
    bucket = get_dashboard_bucket_name(environment)
    target_root = f"gs://{bucket}/"
    with tempfile.TemporaryDirectory() as tmpdir:
        # Stage BOTH filenames commonly referenced by downstream consumers
        tmp_csv_underscore = os.path.join(tmpdir, "itembank_translations.csv")
        tmp_csv_hyphen = os.path.join(tmpdir, "item-bank-translations.csv")
        try:
            with open(local_csv, 'rb') as src:
                data = src.read()
            with open(tmp_csv_underscore, 'wb') as dst1:
                dst1.write(data)
            with open(tmp_csv_hyphen, 'wb') as dst2:
                dst2.write(data)
        except Exception as e:
            print(f"❌ Failed staging CSV: {e}")
            return False
        if force:
            run_command(["gsutil", "rm", f"{target_root}itembank_translations.csv"], "Remove remote dashboard CSV (underscore, force)")
            run_command(["gsutil", "rm", f"{target_root}item-bank-translations.csv"], "Remove remote dashboard CSV (hyphen, force)")
        cmd = ["gsutil", "-m", "rsync", "-c", "-r", f"{tmpdir}/", target_root]
        return run_command(cmd, f"Rsync CSV files to {target_root}", dry_run)

def main():
    """Main function to handle command line arguments and orchestrate deployment."""
    parser = argparse.ArgumentParser(
        description='Deploy translation CSV and audio files to GCS buckets',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python deploy_translations.py                    # Deploy both to dev (default)
    python deploy_translations.py dev                # Deploy both to dev
    python deploy_translations.py prod               # Deploy both to prod  
    python deploy_translations.py dev --dry-run      # Test deployment
    python deploy_translations.py dev --csv-only     # Deploy only CSV
    python deploy_translations.py dev --audio-only   # Deploy only audio
    python deploy_translations.py dev --force        # Force re-upload by removing remote targets
        """
    )
    
    parser.add_argument(
        'environment',
        nargs='?',
        default='dev',
        choices=['dev', 'prod'],
        help='Target environment (default: dev)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deployed without actually uploading'
    )
    
    parser.add_argument(
        '--csv-only',
        action='store_true',
        help='Deploy only the CSV file, skip audio files'
    )
    
    parser.add_argument(
        '--audio-only',
        action='store_true',
        help='Deploy only audio files, skip CSV file'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force uploads (use cp instead of rsync)'
    )

    # Promotion options (dev → prod)
    parser.add_argument(
        '--promote',
        action='store_true',
        help='Promote from dev buckets to prod buckets (blocks direct local→prod uploads)'
    )
    parser.add_argument(
        '--languages',
        help='Comma-separated language codes to restrict promotion (applies to audio/ICU/XLIFF)'
    )
    parser.add_argument(
        '--skip-icu',
        action='store_true',
        help='When promoting CSV/translations, skip ICU JSON'
    )
    parser.add_argument(
        '--skip-xliff',
        action='store_true',
        help='When promoting CSV/translations, skip XLIFF files'
    )
    
    parser.add_argument(
        '--validate-core-tasks',
        action='store_true',
        help='Run core-tasks Cypress tests after deployment to validate everything works'
    )
    
    parser.add_argument(
        '--core-tasks-path',
        default='../core-tasks',
        help='Path to core-tasks repository (default: ../core-tasks)'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.csv_only and args.audio_only:
        print("❌ Error: Cannot use both --csv-only and --audio-only")
        return 1
    
    # Determine what to deploy/promote
    deploy_csv_flag = not args.audio_only
    deploy_audio_flag = not args.csv_only
    
    # Print header
    deployment_type = []
    if deploy_csv_flag:
        deployment_type.append("CSV")
    if deploy_audio_flag:
        deployment_type.append("Audio")
    
    mode = "DRY RUN" if args.dry_run else "DEPLOY"
    title = f"Translation Deployment - {'/'.join(deployment_type)} to {args.environment.upper()} ({mode})"
    print_header(title)
    
    print(f"🎯 Environment: {args.environment}")
    print(f"📊 Deploy CSV: {'Yes' if deploy_csv_flag else 'No'}")
    print(f"🎵 Deploy Audio: {'Yes' if deploy_audio_flag else 'No'}")
    print(f"🧪 Dry Run: {'Yes' if args.dry_run else 'No'}")
    print(f"🔄 Force Re-upload: {'Yes' if args.force else 'No'}")
    
    # If targeting prod without --promote, block direct uploads
    if args.environment == 'prod' and not args.promote:
        print("\n❌ Direct local→prod deployments are disabled. Use --promote to sync from dev to prod.")
        return 1

    # Promotion path: dev → prod
    if args.promote:
        print_header(f"Promotion (DEV → PROD) - {'Audio' if deploy_audio_flag and not deploy_csv_flag else 'CSV+Translations' if deploy_csv_flag and not deploy_audio_flag else 'Audio + CSV/Translations'} ({'DRY RUN' if args.dry_run else 'RUN'})")
        setup_gsutil_auth()
        overall_ok = True
        if deploy_audio_flag:
            overall_ok = promote_audio_from_dev_to_prod(args.languages, args.dry_run) and overall_ok
        if deploy_csv_flag:
            overall_ok = promote_csv_from_dev_to_prod(args.dry_run) and overall_ok
            if not args.skip_icu:
                overall_ok = promote_icu_from_dev_to_prod(args.languages, args.dry_run) and overall_ok
            if not args.skip_xliff:
                overall_ok = promote_xliff_from_dev_to_prod(args.languages, args.dry_run) and overall_ok
        print_section("Promotion Summary")
        print("✅ Success" if overall_ok else "❌ Failed")
        return 0 if overall_ok else 1

    # Local → dev path (or local → prod if allowed with --promote, which we already handled)

    # Fetch the latest translations from l10n_pending branch
    if deploy_csv_flag:
        print("\n📥 Fetching and normalizing latest translations...")
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
    
    # Check prerequisites
    if not check_prerequisites(args.environment, deploy_audio_flag):
        print("\n❌ Prerequisites check failed. Please resolve the issues above.")
        return 1

    # Ensure gsutil can authenticate if only JSON env is present
    setup_gsutil_auth()

    # Track success
    csv_success = True
    audio_success = True
    validation_success = True
    
    # Deploy CSV
    if deploy_csv_flag:
        # Upload CSV to levante-dashboard bucket via rsync
        csv_success = deploy_csv_to_dashboard(args.environment, args.dry_run, args.force)
        # Mirror to levante-assets-*/translations/ if primary CSV deploy succeeded
        if csv_success:
            _ = deploy_csv_to_assets(args.environment, args.dry_run, args.force)
            # Also mirror ICU JSONs
            _ = deploy_icu_to_assets(args.environment, args.dry_run, args.force)
            # And fetch+mirror XLIFF files from GitHub
            _ = deploy_xliff_to_assets_from_github(args.environment, args.dry_run, args.force)
        if not csv_success:
            print(f"\n❌ CSV deployment failed!")
    
    # Deploy Audio  
    if deploy_audio_flag:
        audio_success = deploy_audio(args.environment, args.dry_run, args.force)
        if not audio_success:
            print(f"\n❌ Audio deployment failed!")
    
    # Validate core-tasks (only if deployments succeeded and not in dry-run)
    if args.validate_core_tasks and csv_success and audio_success and not args.dry_run:
        validation_success = validate_core_tasks(args.core_tasks_path)
        if not validation_success:
            print(f"\n❌ Core-tasks validation failed!")
    elif args.validate_core_tasks and args.dry_run:
        print_section("Core-Tasks Validation")
        print("🧪 DRY RUN - Would validate core-tasks repository after deployment")
        print(f"   Command: python3 validate_core_tasks.py --core-tasks-path {args.core_tasks_path} --headless")
    
    # Final results
    print_section("Deployment Summary")
    
    if deploy_csv_flag:
        status = "✅ Success" if csv_success else "❌ Failed"
        print(f"CSV Deployment: {status}")
    
    if deploy_audio_flag:
        status = "✅ Success" if audio_success else "❌ Failed"
        print(f"Audio Deployment: {status}")
    
    if args.validate_core_tasks:
        if args.dry_run:
            print(f"Core-Tasks Validation: 🧪 Would run")
        else:
            status = "✅ Success" if validation_success else "❌ Failed"
            print(f"Core-Tasks Validation: {status}")
    
    overall_success = csv_success and audio_success and validation_success
    
    if overall_success:
        print(f"\n🎉 All deployments completed successfully!")
        if not args.dry_run:
            print(f"\n🌐 Resources deployed to {args.environment} environment:")
            if deploy_csv_flag:
                print(f"   📊 CSV (dashboard): gs://{get_dashboard_bucket_name(args.environment)}/itembank_translations.csv")
                print(f"   📊 CSV (assets mirror): gs://{get_audio_bucket_name(args.environment)}/{TRANSLATION_BUCKET_DIR}/item-bank-translations.csv")
                print(f"   📄 ICU JSON (assets mirror): gs://{get_audio_bucket_name(args.environment)}/{ICU_BUCKET_DIR}/")
                print(f"   📦 XLIFF (assets mirror): gs://{get_audio_bucket_name(args.environment)}/{XLIFF_BUCKET_DIR}/")
            if deploy_audio_flag:
                print(f"   🎵 Audio: gs://{get_audio_bucket_name(args.environment)}/{AUDIO_BUCKET_DIR}/")
    else:
        print(f"\n💥 Some deployments failed. Check the logs above for details.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())