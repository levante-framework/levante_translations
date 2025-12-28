import argparse
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .validator import validate_audio_file, validate_many


def _expand_inputs(paths_or_globs: List[str]) -> List[str]:
    paths: List[str] = []
    for item in paths_or_globs:
        p = Path(item)
        if any(ch in item for ch in ["*", "?", "["]):
            for match in p.parent.glob(p.name):
                if match.is_file():
                    paths.append(str(match))
        elif p.is_dir():
            for match in p.rglob("*.mp3"):
                paths.append(str(match))
            for match in p.rglob("*.wav"):
                paths.append(str(match))
            for match in p.rglob("*.m4a"):
                paths.append(str(match))
        elif p.is_file():
            paths.append(str(p))
    # De-duplicate while preserving order
    seen = set()
    uniq: List[str] = []
    for x in paths:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


def _get_validation_bucket() -> str:
    return os.environ.get("DASHBOARD_DATA_BUCKET", "levante-dashboard-dev")


def _get_validation_prefix() -> str:
    prefix = os.environ.get("VALIDATION_DATA_PREFIX", "data/")
    return prefix if prefix.endswith("/") else f"{prefix}/"


def _has_gsutil() -> bool:
    return shutil.which("gsutil") is not None


def _publish_validation_file(local_path: Path) -> bool:
    if not local_path or not local_path.exists():
        print("⚠️  Validation file not found; skipping publish.")
        return False

    bucket = _get_validation_bucket()
    prefix = _get_validation_prefix()

    if not bucket:
        print("⚠️  DASHBOARD_DATA_BUCKET not set; skipping publish.")
        return False

    if not _has_gsutil():
        print("⚠️  gsutil not available; skipping publish.")
        return False

    dest_uri = f"gs://{bucket}/{prefix}"
    print(f"☁️  Publishing validation report to {dest_uri}{local_path.name}")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            staged = Path(tmpdir) / local_path.name
            shutil.copy2(local_path, staged)
            cmd = [
                "gsutil",
                "-m",
                "rsync",
                "-c",
                "-r",
                f"{tmpdir}/",
                dest_uri,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print("❌ Failed to publish validation report to GCS.")
                if result.stderr:
                    print(result.stderr.strip())
                elif result.stdout:
                    print(result.stdout.strip())
                return False
    except Exception as exc:
        print(f"❌ Publish failed: {exc}")
        return False

    print("✅ Validation report published to dashboard data bucket.")
    return True


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate audio against expected text using ASR and metrics.")
    parser.add_argument("inputs", nargs="+", help="Audio files, directories, or globs (e.g., 'data/*.mp3')")
    parser.add_argument("--expected", help="Expected/original text. If omitted, will try to read from ID3.")
    parser.add_argument("--id3-key", help="Preferred ID3 TXXX key that stores the expected text.")
    parser.add_argument("--language", help="Force language code for ASR (e.g., 'en', 'es', 'fr').")
    parser.add_argument("--backend", choices=["whisper", "google"], default="whisper")
    parser.add_argument("--model-size", default="base", help="Whisper model size (tiny, base, small, medium, large)")
    parser.add_argument("--no-quality", action="store_true", help="Skip audio quality assessment.")
    parser.add_argument("--output", help="Path to write results as JSON (list) or JSONL if ends with .jsonl")
    parser.add_argument("--web-dashboard", action="store_true", help="Save results to web-dashboard/data/ for UI viewing")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON to stdout")
    parser.add_argument("--progress", action="store_true", help="Print progress while validating many files")
    parser.add_argument(
        "--skip-publish",
        action="store_true",
        help="Skip uploading validation results to the dashboard bucket (publish is enabled by default)",
    )

    args = parser.parse_args(argv)

    audio_paths = _expand_inputs(args.inputs)
    if not audio_paths:
        print("No audio files found.")
        return 2

    include_quality = not args.no_quality

    if len(audio_paths) == 1:
        result = validate_audio_file(
            audio_file_path=audio_paths[0],
            expected_text=args.expected,
            language=args.language,
            backend=args.backend,
            model_size=args.model_size,
            include_quality=include_quality,
            id3_preferred_key=args.id3_key,
        )
        results = [result]
    else:
        if args.progress:
            print(f"Validating {len(audio_paths)} files...", flush=True)
        results = validate_many(
            audio_paths=audio_paths,
            expected_texts=[args.expected] * len(audio_paths) if args.expected else None,
            language=args.language,
            backend=args.backend,
            model_size=args.model_size,
            include_quality=include_quality,
            id3_preferred_key=args.id3_key,
            progress=args.progress,
        )

    out_path: Optional[Path] = None

    if args.web_dashboard:
        # Save to web-dashboard/public/data/ with easy-to-read date (served by dashboard)
        date_str = datetime.now().strftime("%b-%d-%Y")  # e.g., Oct-07-2025
        lang = (args.language or "unknown").strip() or "unknown"
        out_name = f"validation-{lang}-{date_str}.json"
        out_path = Path("web-dashboard/public/data") / out_name
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(results if len(audio_paths) > 1 else results[0], f, ensure_ascii=False, indent=2)
        print(f"Results saved to: {out_path}")
    elif args.output:
        out_path = Path(args.output)
        if out_path.suffix.lower() == ".jsonl":
            with out_path.open("w", encoding="utf-8") as f:
                for r in results:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        else:
            with out_path.open("w", encoding="utf-8") as f:
                json.dump(results if len(audio_paths) > 1 else results[0], f, ensure_ascii=False, indent=2 if args.pretty else None)
    else:
        print(json.dumps(results if len(audio_paths) > 1 else results[0], ensure_ascii=False, indent=2 if args.pretty else None))

    if args.web_dashboard and out_path and not args.skip_publish:
        _publish_validation_file(out_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
