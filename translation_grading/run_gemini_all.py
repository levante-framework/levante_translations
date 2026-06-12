#!/usr/bin/env python3
"""Resumable, task-aware Gemini evaluation over ALL translation pairs.

Wraps ``gemini_quality_evaluator`` to add the robustness a full multi-thousand
pair run needs:
  * resume   - skips ``(identifier, language)`` pairs already in the output CSV
  * flushing - rewrites the output CSV every ``--flush-every`` results so a crash
               or interruption never loses completed work
  * resilient - a per-item Gemini failure is recorded and skipped, never aborts

Usage (from repo root, with GEMINI_API_KEY in the environment):
    python translation_grading/run_gemini_all.py \
        --input-csv translation_grading/output/complete_translations.csv \
        --output-csv translation_grading/output/translation_quality_results.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Dict, List, Sequence, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gemini_quality_evaluator as gqe  # noqa: E402


def with_retry(fn: Callable, *args, max_retries: int = 5, base_delay: float = 2.0):
    """Run ``fn`` retrying transient Gemini failures (429/500/503) with backoff."""
    attempt = 0
    while True:
        try:
            return fn(*args)
        except urllib.error.HTTPError as exc:
            if exc.code in {429, 500, 503} and attempt < max_retries:
                time.sleep(min(60.0, base_delay * (2 ** attempt)))
                attempt += 1
                continue
            raise
        except urllib.error.URLError:
            if attempt < max_retries:
                time.sleep(min(60.0, base_delay * (2 ** attempt)))
                attempt += 1
                continue
            raise


FIELDS = ["identifier", "language", "score", "errors_json", "notes",
          "template_used", "human_review", "screenshot_names"]


def load_done(path: Path) -> Tuple[List[dict], Set[Tuple[str, str]]]:
    rows: List[dict] = []
    done: Set[Tuple[str, str]] = set()
    if not path.exists():
        return rows, done
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append(row)
            done.add((str(row.get("identifier", "")), str(row.get("language", ""))))
    return rows, done


def flush(path: Path, rows: Sequence[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-csv", default="translation_grading/output/complete_translations.csv")
    p.add_argument("--output-csv", default="translation_grading/output/translation_quality_results.csv")
    p.add_argument("--source-col", default="en")
    p.add_argument("--target-cols", default="de,nl,es-CO,fr-CA,es-AR,en-GB,pt-PT,pt-BR")
    p.add_argument("--api-key-env", default="GEMINI_API_KEY")
    p.add_argument("--model", default=gqe.DEFAULT_MODEL)
    p.add_argument("--fallback-model", default=gqe.FALLBACK_MODEL)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--workers", type=int, default=8, help="Concurrent Gemini requests.")
    p.add_argument("--flush-every", type=int, default=25)
    args = p.parse_args()

    api_key = os.environ.get(args.api_key_env, "").strip()
    if not api_key:
        raise SystemExit(f"{args.api_key_env} is not set.")

    out_path = Path(args.output_csv)
    results, done = load_done(out_path)

    items = gqe.load_items(Path(args.input_csv), args.source_col,
                           gqe.csv_list(args.target_cols), args.limit)
    pending = [it for it in items if (it.identifier, it.target_lang) not in done]
    print(f"[gemini-all] total={len(items)} done={len(done)} pending={len(pending)} "
          f"model={args.model}", flush=True)

    # Batch OBJECT_NAMING (vocab) pairs; single-call everything else.
    object_items = [it for it in pending
                    if it.template_key == "OBJECT_NAMING" and not it.screenshots]
    object_ids = {id(it) for it in object_items}
    groups: Dict[Tuple[str, str], List[gqe.EvaluationItem]] = {}
    for it in object_items:
        groups.setdefault((it.target_lang,
                           gqe.construct_context_for(it.labels, it.template_key)), []).append(it)

    processed = 0
    failures = 0
    total = len(pending)
    single_items = [it for it in pending if id(it) not in object_ids]
    batches = [batch for group in sorted(groups) for batch in gqe.chunks(groups[group], gqe.BATCH_SIZE)]

    def run_batch(batch: Sequence[gqe.EvaluationItem]) -> List[dict]:
        evals = with_retry(gqe.evaluate_object_batch, batch, api_key, args.model, args.fallback_model)
        return [gqe.result_row(it, ev) for it, ev in zip(batch, evals)]

    def run_single(it: gqe.EvaluationItem) -> List[dict]:
        ev = with_retry(gqe.evaluate_single, it, api_key, args.model, args.fallback_model)
        return [gqe.result_row(it, ev)]

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {}
        for batch in batches:
            futures[pool.submit(run_batch, batch)] = ("batch", len(batch), batch)
        for it in single_items:
            futures[pool.submit(run_single, it)] = ("item", 1, it)

        for fut in as_completed(futures):
            kind, n, payload = futures[fut]
            try:
                results.extend(fut.result())
            except Exception as exc:  # noqa: BLE001 - record and continue
                failures += n
                label = (payload[0].identifier if kind == "batch" and payload
                         else getattr(payload, "identifier", "?"))
                print(f"[gemini-all] {kind} failed ({label}, n={n}): {exc}", flush=True)
            processed += n
            if processed % args.flush_every < n:
                flush(out_path, results)
            if processed % 100 < n or processed >= total:
                print(f"[gemini-all] {processed}/{total} failures={failures}", flush=True)

    flush(out_path, results)
    print(f"[gemini-all] DONE wrote {len(results)} rows to {out_path} "
          f"(processed={processed}, failures={failures})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
