#!/usr/bin/env python3
"""Automatic plain-language explanation pass for flagged translations.

For every record the composite metric flags as ``likely_bad`` (optionally also
``review``), this asks Gemini to synthesize ALL of the automated signals into a
short, human-readable verdict: why it was flagged (or whether it looks like a
false alarm), a concrete suggested correction, and a confidence in the flag.

It is resumable (skips ``item_id\\tlang`` keys already explained), concurrent,
and flushes incrementally, so it is safe to interrupt and re-run.

Usage (from repo root, GEMINI_API_KEY in env):
    python translation_grading/explain_flagged.py \
        --report translation_grading/output/composite-quality-report.csv \
        --out translation_grading/output/flagged_explanations.json
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


SYSTEM = (
    "You are a senior translation QA lead for LEVANTE, an international study that measures "
    "cognitive development in children ages 5-12. Prompts are short, spoken aloud to children, "
    "and contain no technical jargon. Proper names may be localized. Informal address is required "
    "(tu/du/jij/vos), never formal. You are triaging translations that automated signals flagged "
    "as likely problematic, and writing a concise explanation a human reviewer can act on."
)

REASON_GLOSSARY = {
    "gemini:critical": "an LLM judge found a construct-critical error",
    "backtranslation:critical": "a round-trip backtranslation diverged critically from the source",
    "vlm:cross_lang_outlier": "a simulated child (VLM) failed this item in this language while succeeding in others",
    "vlm:incorrect": "a simulated child (VLM) picked the wrong answer (and could solve the item in English)",
    "oracle:incorrect": "a deterministic oracle QA agent got the item wrong",
    "uncorroborated_critical": "a single LLM critical with no corroborating signal",
}


def build_prompt(rec: Dict[str, str], gem: Dict[str, str]) -> str:
    reasons = [r for r in (rec.get("reasons", "") or "").split(";") if r]

    def gloss(r: str) -> str:
        meaning = REASON_GLOSSARY.get(r, "")
        return f"  - {r}: {meaning}" if meaning else f"  - {r}"

    reason_lines = "\n".join(gloss(r) for r in reasons) or "  - (low composite score)"
    signal_bits = []
    if gem.get("score"):
        signal_bits.append(f"Gemini rubric score: {gem.get('score')}/5 (severity: {rec.get('gemini_severity') or 'none'})")
    if gem.get("errors_json") and gem.get("errors_json") not in ("[]", ""):
        signal_bits.append(f"Gemini errors: {gem.get('errors_json')}")
    if gem.get("notes"):
        signal_bits.append(f"Gemini notes: {gem.get('notes')}")
    if rec.get("comet_raw"):
        signal_bits.append(f"COMET QE (reference-free, ~0-1): {rec.get('comet_raw')}")
    if rec.get("backtranslation_q"):
        signal_bits.append(f"Backtranslation quality (0-1): {rec.get('backtranslation_q')}")
    if rec.get("vlm_correct") not in (None, ""):
        ol = " and a cross-language outlier" if rec.get("vlm_lang_outlier") else ""
        signal_bits.append(f"VLM answered {'correctly' if rec.get('vlm_correct') == '1' else 'incorrectly'}{ol}")
    signal_block = "\n".join(f"  - {b}" for b in signal_bits) or "  - (none)"

    return (
        f"{SYSTEM}\n\n"
        f"Task type: {rec.get('task') or 'unknown'}\n"
        f"Target language: {rec.get('target_lang')}\n"
        f"Composite quality score (0=worst, 1=best): {rec.get('quality_score') or 'n/a'}\n"
        f"English source: \"{rec.get('source_text', '')}\"\n"
        f"Translation: \"{rec.get('target_text', '')}\"\n\n"
        f"Why the automated system flagged it:\n{reason_lines}\n\n"
        f"Underlying signals:\n{signal_block}\n\n"
        "Write a verdict for a human reviewer. Be specific and concrete. Decide whether the flag is "
        "correct. Use verdict 'confirmed' if the translation really is problematic, 'false_alarm' if "
        "the translation is actually acceptable and the flag is wrong, or 'uncertain' if you cannot "
        "tell. Reserve 'false_alarm' for cases where the translation is genuinely fine.\n"
        "Return ONLY JSON: {\"verdict\": \"confirmed|false_alarm|uncertain\", "
        "\"explanation\": \"1-3 sentences on what is (or isn't) wrong\", "
        "\"suggested_fix\": \"a concrete corrected translation or '' if none needed\", "
        "\"flag_confidence\": \"high|medium|low\"}"
    )


def parse_response(raw: str) -> Dict[str, str]:
    payload = json.loads(gqe.extract_json_text(raw))
    if not isinstance(payload, dict):
        raise ValueError("not a JSON object")
    conf = str(payload.get("flag_confidence", "") or "").strip().lower()
    if conf not in {"high", "medium", "low"}:
        conf = "medium"
    verdict = str(payload.get("verdict", "") or "").strip().lower()
    if verdict not in {"confirmed", "false_alarm", "uncertain"}:
        verdict = "uncertain"
    return {
        "verdict": verdict,
        "explanation": str(payload.get("explanation", "") or "").strip(),
        "suggested_fix": str(payload.get("suggested_fix", "") or "").strip(),
        "flag_confidence": conf,
    }


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


def explain_one(rec: Dict[str, str], gem: Dict[str, str], api_key: str,
                model: str, fallback: str) -> Dict[str, str]:
    prompt = build_prompt(rec, gem)
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
    p.add_argument("--gemini-results", default="translation_grading/output/translation_quality_results.csv")
    p.add_argument("--out", default="translation_grading/output/flagged_explanations.json")
    p.add_argument("--tiers", default="likely_bad", help="Comma-separated tiers to explain (e.g. likely_bad,review).")
    p.add_argument("--api-key-env", default="GEMINI_API_KEY")
    p.add_argument("--model", default=gqe.DEFAULT_MODEL)
    p.add_argument("--fallback-model", default=gqe.FALLBACK_MODEL)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--flush-every", type=int, default=20)
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args()

    api_key = os.environ.get(args.api_key_env, "").strip()
    if not api_key:
        raise SystemExit(f"{args.api_key_env} is not set.")

    tiers = {t.strip() for t in args.tiers.split(",") if t.strip()}
    with Path(args.report).open("r", encoding="utf-8-sig", newline="") as handle:
        flagged = [r for r in csv.DictReader(handle) if r.get("flag_tier") in tiers]
    if args.limit:
        flagged = flagged[: args.limit]

    gem_map: Dict[str, Dict[str, str]] = {}
    gpath = Path(args.gemini_results)
    if gpath.exists():
        with gpath.open("r", encoding="utf-8-sig", newline="") as handle:
            for r in csv.DictReader(handle):
                gem_map[f"{r['identifier']}\t{r['language']}"] = r

    out_path = Path(args.out)
    explanations: Dict[str, Dict[str, str]] = {}
    if out_path.exists():
        try:
            explanations = json.loads(out_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            explanations = {}

    def key(rec: Dict[str, str]) -> str:
        return f"{rec['item_id']}\t{rec['target_lang']}"

    pending = [r for r in flagged if key(r) not in explanations]
    print(f"[explain] flagged={len(flagged)} already={len(explanations)} pending={len(pending)} "
          f"model={args.model}", flush=True)

    def flush() -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = out_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(explanations, ensure_ascii=False, indent=0), encoding="utf-8")
        tmp.replace(out_path)

    processed = 0
    failures = 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futs = {pool.submit(explain_one, r, gem_map.get(key(r), {}), api_key,
                            args.model, args.fallback_model): r for r in pending}
        for fut in as_completed(futs):
            rec = futs[fut]
            try:
                explanations[key(rec)] = fut.result()
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"[explain] failed {key(rec)}: {exc}", flush=True)
            processed += 1
            if processed % args.flush_every < 1:
                flush()
            if processed % 50 < 1 or processed == len(pending):
                print(f"[explain] {processed}/{len(pending)} failures={failures}", flush=True)
    flush()
    print(f"[explain] DONE wrote {len(explanations)} explanations -> {out_path} (failures={failures})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
