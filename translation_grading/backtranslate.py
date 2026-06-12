#!/usr/bin/env python3
"""Gemini-powered back-translation pass.

For every composite record this asks Gemini to translate the target-language
translation back into natural English, WITHOUT seeing the English source. The
result is shown on the dashboard beside the English source and the translation
so a reviewer can eyeball meaning drift at a glance.

It is resumable (skips ``item_id\\tlang`` keys already done), concurrent, and
flushes incrementally, so it is safe to interrupt and re-run.

Usage (from repo root, GEMINI_API_KEY in env):
    python translation_grading/backtranslate.py \
        --report translation_grading/output/composite-quality-report.csv \
        --out translation_grading/output/backtranslations.json
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gemini_quality_evaluator as gqe  # noqa: E402


def build_prompt(target_lang: str, target_text: str) -> str:
    return (
        "You are a professional translator. Translate the following text into natural, "
        "fluent English. Do not explain, do not add notes, and do not include the original. "
        "Translate faithfully what is actually written (including any errors or odd phrasing) "
        "rather than guessing the intended meaning.\n"
        f"Source language: {target_lang}\n"
        f"Text: \"{target_text}\"\n"
        "Return ONLY JSON: {\"english\": \"the English back-translation\"}"
    )


def parse_response(raw: str) -> str:
    payload = json.loads(gqe.extract_json_text(raw))
    if not isinstance(payload, dict):
        raise ValueError("not a JSON object")
    return str(payload.get("english", "") or "").strip()


def with_retry(fn, *args, max_retries: int = 4, base_delay: float = 2.0):
    attempt = 0
    while True:
        try:
            return fn(*args)
        except (urllib.error.HTTPError, urllib.error.URLError) as exc:
            code = getattr(exc, "code", None)
            if (code in {429, 500, 503} or code is None) and attempt < max_retries:
                time.sleep(min(60.0, base_delay * (2 ** attempt)))
                attempt += 1
                continue
            raise


def backtranslate_one(target_lang: str, target_text: str, api_key: str,
                      model: str, fallback: str) -> str:
    prompt = build_prompt(target_lang, target_text)
    raw = with_retry(gqe.call_gemini, prompt, api_key, model, fallback)
    try:
        return parse_response(raw)
    except (ValueError, KeyError, json.JSONDecodeError):
        strict = prompt + ("\n\nYour previous output was not valid JSON. Output ONLY a single-line "
                           "minified JSON object with all interior quotes escaped.")
        raw = with_retry(gqe.call_gemini, strict, api_key, model, fallback)
        return parse_response(raw)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report", default="translation_grading/output/composite-quality-report.csv")
    p.add_argument("--out", default="translation_grading/output/backtranslations.json")
    p.add_argument("--tiers", default="", help="Comma-separated tiers to limit to (default: all).")
    p.add_argument("--api-key-env", default="GEMINI_API_KEY")
    p.add_argument("--model", default=gqe.DEFAULT_MODEL)
    p.add_argument("--fallback-model", default=gqe.FALLBACK_MODEL)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--flush-every", type=int, default=50)
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args()

    api_key = os.environ.get(args.api_key_env, "").strip()
    if not api_key:
        raise SystemExit(f"{args.api_key_env} is not set.")

    tiers = {t.strip() for t in args.tiers.split(",") if t.strip()}
    with Path(args.report).open("r", encoding="utf-8-sig", newline="") as handle:
        records = [r for r in csv.DictReader(handle)
                   if (not tiers or r.get("flag_tier") in tiers)
                   and (r.get("target_text") or "").strip()]
    if args.limit:
        records = records[: args.limit]

    out_path = Path(args.out)
    done: Dict[str, str] = {}
    if out_path.exists():
        try:
            done = json.loads(out_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            done = {}

    def key(rec: Dict[str, str]) -> str:
        return f"{rec['item_id']}\t{rec['target_lang']}"

    pending = [r for r in records if key(r) not in done]
    print(f"[backtranslate] records={len(records)} already={len(done)} pending={len(pending)} "
          f"model={args.model}", flush=True)

    def flush() -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = out_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(done, ensure_ascii=False, indent=0), encoding="utf-8")
        tmp.replace(out_path)

    processed = 0
    failures = 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futs = {pool.submit(backtranslate_one, r["target_lang"], r["target_text"],
                            api_key, args.model, args.fallback_model): r for r in pending}
        for fut in as_completed(futs):
            rec = futs[fut]
            try:
                done[key(rec)] = fut.result()
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"[backtranslate] failed {key(rec)}: {exc}", flush=True)
            processed += 1
            if processed % args.flush_every < 1:
                flush()
            if processed % 200 < 1 or processed == len(pending):
                print(f"[backtranslate] {processed}/{len(pending)} failures={failures}", flush=True)
    flush()
    print(f"[backtranslate] DONE wrote {len(done)} back-translations -> {out_path} "
          f"(failures={failures})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
