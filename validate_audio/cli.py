import argparse
import json
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
        results = validate_many(
            audio_paths=audio_paths,
            expected_texts=[args.expected] * len(audio_paths) if args.expected else None,
            language=args.language,
            backend=args.backend,
            model_size=args.model_size,
            include_quality=include_quality,
            id3_preferred_key=args.id3_key,
        )

    if args.web_dashboard:
        # Save to web-dashboard/data/ with timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        lang = args.language or "unknown"
        out_path = Path("web-dashboard/data") / f"validation_results_{lang}_{timestamp}.json"
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

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
