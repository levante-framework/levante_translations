#!/usr/bin/env python3
"""
Audio backup script.

Creates a durable, independent backup of the approved audio source-of-truth
(`gs://levante-assets-dev/audio`) into a versioned backup bucket
(`gs://hs-levante-admin-dev-backups/audio` by default).

Design notes:
- The sync is APPEND-ONLY: we deliberately do NOT pass gsutil's `-d` flag, so a
  deletion in the source bucket never deletes the corresponding backup object.
- The backup bucket has Object Versioning enabled, so overwrites in the source
  are preserved in the backup as noncurrent versions (retained per the bucket's
  lifecycle policy). Together these protect against accidental delete AND
  accidental overwrite.
- This replaces the practice of committing `audio_files/` to git as a backup.

Auth: reuses the same credentials handling as deploy_translations.py. Set
`GOOGLE_APPLICATION_CREDENTIALS_JSON` (JSON string) or
`GOOGLE_APPLICATION_CREDENTIALS` (path to key file).
"""

import os
import sys
import argparse
import subprocess
from datetime import datetime, timezone

# Reuse the battle-tested auth helpers from the deploy script.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from deploy_translations import setup_gsutil_auth, verify_gsutil_auth
except Exception:  # pragma: no cover - fallback if import path differs
    setup_gsutil_auth = None
    verify_gsutil_auth = None

DEFAULT_SOURCE_BUCKET = os.environ.get("AUDIO_DEV_BUCKET", "levante-assets-dev")
DEFAULT_SOURCE_PREFIX = "audio"
DEFAULT_BACKUP_BUCKET = os.environ.get("AUDIO_BACKUP_BUCKET", "hs-levante-admin-dev-backups")
DEFAULT_BACKUP_PREFIX = "audio"


def _log(msg: str) -> None:
    print(msg, flush=True)


def run_backup(
    source_bucket: str,
    source_prefix: str,
    backup_bucket: str,
    backup_prefix: str,
    dry_run: bool,
) -> bool:
    source_uri = f"gs://{source_bucket}/{source_prefix}".rstrip("/") + "/"
    backup_uri = f"gs://{backup_bucket}/{backup_prefix}".rstrip("/") + "/"

    _log("=" * 60)
    _log("🗄️  Audio Backup")
    _log("=" * 60)
    _log(f"   Source: {source_uri}")
    _log(f"   Backup: {backup_uri}")
    _log(f"   Mode:   {'DRY RUN' if dry_run else 'RUN'} (append-only, no deletes)")
    _log(f"   Time:   {datetime.now(timezone.utc).isoformat()}")

    if setup_gsutil_auth is not None:
        setup_gsutil_auth()
    if verify_gsutil_auth is not None and not verify_gsutil_auth(backup_bucket):
        _log("❌ Could not authenticate to the backup bucket. Aborting.")
        return False

    # -m: parallel, -r: recursive, -c: checksum compare (don't trust mtime).
    # NOTE: intentionally NO -d, so source deletions never delete backup objects.
    # -q (real runs only): suppress the progress UI, which throws a cosmetic
    #    "Exception in UIThread" and can abort the run when stdout is redirected
    #    (e.g. in CI logs). Errors are still reported.
    cmd = ["gsutil"]
    if not dry_run:
        cmd.append("-q")
    cmd += ["-m", "rsync", "-r", "-c"]
    if dry_run:
        cmd.append("-n")
    cmd += [source_uri, backup_uri]

    _log(f"\n$ {' '.join(cmd)}\n")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        _log(f"❌ Backup rsync failed (exit {e.returncode}).")
        return False

    _log("\n✅ Backup completed successfully." if not dry_run else "\n✅ Dry run completed.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Back up approved dev audio to a versioned backup bucket.")
    parser.add_argument("--source-bucket", default=DEFAULT_SOURCE_BUCKET,
                        help=f"Source bucket (default: {DEFAULT_SOURCE_BUCKET})")
    parser.add_argument("--source-prefix", default=DEFAULT_SOURCE_PREFIX,
                        help=f"Source prefix/folder (default: {DEFAULT_SOURCE_PREFIX})")
    parser.add_argument("--backup-bucket", default=DEFAULT_BACKUP_BUCKET,
                        help=f"Backup bucket (default: {DEFAULT_BACKUP_BUCKET})")
    parser.add_argument("--backup-prefix", default=DEFAULT_BACKUP_PREFIX,
                        help=f"Backup prefix/folder (default: {DEFAULT_BACKUP_PREFIX})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be copied without writing anything.")
    args = parser.parse_args()

    ok = run_backup(
        source_bucket=args.source_bucket,
        source_prefix=args.source_prefix,
        backup_bucket=args.backup_bucket,
        backup_prefix=args.backup_prefix,
        dry_run=args.dry_run,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
