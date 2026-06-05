#!/usr/bin/env python3
"""
Tiered translation grading for Levante translations.

This pipeline lives in levante_translations because it evaluates the same
Crowdin/XLIFF-derived translation sources used by the back-translation and
XCOMET/COMET tooling in this repo.

Stages:
1. Cross-lingual consistency outlier detection (LaBSE / multilingual-e5).
2. Optional reference-free QE scoring (COMET-Kiwi / xCOMET via unbabel-comet).
3. Optional Gemini LLM-as-judge on flagged rows.
4. CSV + JSON + Markdown triage reports.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import statistics
import urllib.error
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np


CROWDIN_API_BASE = "https://api.crowdin.com/api/v2"
DEFAULT_CROWDIN_PROJECT_ID = "756721"
HTML_TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


@dataclass
class RowTranslation:
    item_id: str
    row_index: int
    source_text: str
    target_lang: str
    target_text: str
    source_path: str = ""
    ambiguity_note: str = ""
    scores: Dict[str, float] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)
    needs_review: bool = False
    review_reasons: List[str] = field(default_factory=list)
    metadata: Dict[str, object] = field(default_factory=dict)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run tiered translation grading.")
    parser.add_argument(
        "--input-mode",
        default="csv",
        choices=["csv", "crowdin-api", "crowdin-zip", "dashboard-endpoint"],
        help="Translation source mode.",
    )
    parser.add_argument("--input-csv", default="", help="CSV path for --input-mode csv.")
    parser.add_argument("--crowdin-zip", default="", help="Crowdin export ZIP for --input-mode crowdin-zip.")
    parser.add_argument("--crowdin-project-id", default=DEFAULT_CROWDIN_PROJECT_ID)
    parser.add_argument("--dashboard-base-url", default="https://levante-cockpit.vercel.app")
    parser.add_argument("--item-id-col", default="item_id")
    parser.add_argument("--source-col", default="en")
    parser.add_argument("--target-cols", default="", help="Comma-separated target columns; auto-detect if empty.")
    parser.add_argument("--ignore-cols", default="")
    parser.add_argument("--ambiguity-col", default="")
    parser.add_argument("--max-pairs", type=int, default=0, help="Limit source-target pairs (0 = all).")
    parser.add_argument("--strip-html", action="store_true")

    parser.add_argument("--embedding-model", default="sentence-transformers/LaBSE")
    parser.add_argument("--embedding-device", default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--embedding-batch-size", type=int, default=128)
    parser.add_argument("--consistency-threshold", type=float, default=0.78)

    parser.add_argument("--run-comet", action="store_true")
    parser.add_argument("--comet-model", default="Unbabel/wmt22-cometkiwi-da")
    parser.add_argument("--comet-batch-size", type=int, default=32)
    parser.add_argument("--comet-threshold", type=float, default=0.62)

    parser.add_argument("--run-llm-judge", action="store_true")
    parser.add_argument("--gemini-api-key-env", default="GEMINI_API_KEY")
    parser.add_argument("--gemini-model", default="gemini-2.5-pro")
    parser.add_argument("--gemini-threshold", type=float, default=75.0)
    parser.add_argument("--llm-only-flagged", action="store_true")
    parser.add_argument("--llm-max-calls", type=int, default=0)

    parser.add_argument("--output-csv", default="translation_grading/output/translation-grading-report.csv")
    parser.add_argument("--summary-json", default="translation_grading/output/translation-grading-summary.json")
    parser.add_argument("--report-md", default="translation_grading/output/translation-grading-flag-report.md")
    return parser.parse_args()


def parse_csv_list(raw: str) -> List[str]:
    return [c.strip() for c in str(raw or "").split(",") if c.strip()]


def normalize_text(value: str, strip_html: bool = False) -> str:
    text = str(value or "")
    if strip_html:
        text = HTML_TAG_RE.sub(" ", text)
    return SPACE_RE.sub(" ", text).strip()


def normalize_lang_code(value: str) -> str:
    raw = str(value or "").strip().replace("_", "-")
    if not raw:
        return ""
    aliases = {
        "de-de": "de",
        "en-us": "en-US",
        "en-gb": "en-GB",
        "en-gh": "en-GH",
        "es-co": "es-CO",
        "es-ar": "es-AR",
        "fr-ca": "fr-CA",
        "pt-br": "pt-BR",
        "pt-pt": "pt-PT",
    }
    return aliases.get(raw.lower(), raw)


def auto_target_cols(
    fieldnames: Iterable[str],
    source_col: str,
    id_col: str,
    ambiguity_col: str,
    ignore_cols: Sequence[str],
) -> List[str]:
    ignored = {source_col, id_col, ambiguity_col, *ignore_cols}
    ignored = {c for c in ignored if c}
    out: List[str] = []
    for name in fieldnames:
        n = str(name or "").strip()
        if not n or n in ignored or n.startswith("_"):
            continue
        if re.fullmatch(r"[a-z]{2}(?:-[A-Za-z0-9]{2,8})?", n):
            out.append(n)
    return out


def get_crowdin_token() -> str:
    token = os.environ.get("CROWDIN_API_TOKEN", "").strip() or os.environ.get("CROWDIN_TOKEN", "").strip()
    if token:
        return token
    token_path = Path.home() / ".crowdin_api_token"
    if token_path.exists():
        return token_path.read_text(encoding="utf-8").strip()
    raise RuntimeError("Crowdin token not found. Set CROWDIN_API_TOKEN or create ~/.crowdin_api_token.")


def fetch_json(url: str, *, method: str = "GET", headers: Dict[str, str] | None = None, body: bytes | None = None, timeout: int = 120) -> dict:
    req = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {details}") from exc


def fetch_crowdin_project_zip(project_id: str) -> bytes:
    token = get_crowdin_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    build_url = f"{CROWDIN_API_BASE}/projects/{project_id}/translations/builds"
    payload = json.dumps({"exportApprovedOnly": True}).encode("utf-8")
    build = fetch_json(build_url, method="POST", headers=headers, body=payload)
    build_id = build.get("data", {}).get("id")
    if not build_id:
        raise RuntimeError(f"Crowdin build response missing id: {build}")

    status_url = f"{build_url}/{build_id}"
    for _ in range(40):
        status = fetch_json(status_url, headers=headers)
        state = str(status.get("data", {}).get("status", "")).lower()
        if state == "finished":
            break
        if state in {"failed", "cancelled"}:
            raise RuntimeError(f"Crowdin build {state}")
        import time

        time.sleep(2)
    else:
        raise RuntimeError("Crowdin build did not finish in time.")

    download = fetch_json(f"{status_url}/download", headers=headers)
    zip_url = str(download.get("data", {}).get("url", "")).strip()
    if not zip_url:
        raise RuntimeError(f"Crowdin download response missing URL: {download}")
    with urllib.request.urlopen(zip_url, timeout=180) as resp:
        return resp.read()


def fetch_dashboard_crowdin_zip(base_url: str) -> bytes:
    endpoint = f"{base_url.rstrip('/')}/api/crowdin-approved-translations"
    payload = fetch_json(endpoint)
    zip_url = str(payload.get("zipUrl", "")).strip()
    if not zip_url:
        raise RuntimeError(f"Dashboard endpoint did not return zipUrl: {payload}")
    with urllib.request.urlopen(zip_url, timeout=180) as resp:
        return resp.read()


def parse_crowdin_csv_bytes(payload: bytes) -> List[dict]:
    text = payload.decode("utf-8-sig", errors="replace")
    return [{str(k): (v if v is not None else "") for k, v in row.items()} for row in csv.DictReader(io.StringIO(text))]


def infer_lang_from_path(path: str) -> str:
    parts = [p for p in str(path or "").replace("\\", "/").split("/") if p]
    for part in parts:
        if re.fullmatch(r"[a-z]{2}(?:-[A-Za-z0-9]{2,8})?", part):
            return normalize_lang_code(part)
    return ""


def parse_xliff_bytes(payload: bytes, zip_path: str) -> List[dict]:
    try:
        root = ET.fromstring(payload)
    except Exception:
        return []
    rows: List[dict] = []
    for unit in root.iter():
        tag = str(unit.tag)
        if not (tag.endswith("trans-unit") or tag.endswith("unit")):
            continue
        unit_id = str(unit.attrib.get("id") or unit.attrib.get("resname") or "").strip()
        source = ""
        target = ""
        for child in unit.iter():
            child_tag = str(child.tag)
            if child_tag.endswith("source") and not source:
                source = "".join(child.itertext()).strip()
            elif child_tag.endswith("target") and not target:
                target = "".join(child.itertext()).strip()
        if source or target:
            rows.append({"item_id": f"{zip_path}::{unit_id or len(rows)}", "en": source, "_xliff_target": target, "_path": zip_path})
    return rows


def merge_crowdin_zip(zip_bytes: bytes) -> List[dict]:
    merged: Dict[str, dict] = {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for info in zf.infolist():
            name = str(info.filename or "")
            lower = name.lower()
            if info.is_dir() or "/archive/" in lower:
                continue
            if not (lower.endswith(".csv") or lower.endswith(".xlf") or lower.endswith(".xliff")):
                continue
            data = zf.read(info)
            if lower.endswith(".csv"):
                for idx, row in enumerate(parse_crowdin_csv_bytes(data)):
                    rid = str(row.get("item_id") or row.get("identifier") or row.get("id") or f"{name}::{idx}").strip()
                    if not rid:
                        continue
                    row["_path"] = name
                    merged[rid] = {**merged.get(rid, {}), **row}
            else:
                lang = infer_lang_from_path(name)
                for row in parse_xliff_bytes(data, name):
                    rid = str(row.get("item_id", "")).strip()
                    if not rid:
                        continue
                    existing = merged.get(rid, {})
                    existing["item_id"] = existing.get("item_id") or rid
                    existing["en"] = existing.get("en") or row.get("en", "")
                    if lang and row.get("_xliff_target"):
                        existing[lang] = row["_xliff_target"]
                    existing["_path"] = existing.get("_path") or name
                    merged[rid] = existing
    return list(merged.values())


def load_source_rows(args: argparse.Namespace) -> List[dict]:
    if args.input_mode == "csv":
        if not args.input_csv:
            raise ValueError("--input-csv is required for --input-mode csv")
        with Path(args.input_csv).expanduser().open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    if args.input_mode == "crowdin-zip":
        if not args.crowdin_zip:
            raise ValueError("--crowdin-zip is required for --input-mode crowdin-zip")
        return merge_crowdin_zip(Path(args.crowdin_zip).expanduser().read_bytes())
    if args.input_mode == "crowdin-api":
        return merge_crowdin_zip(fetch_crowdin_project_zip(args.crowdin_project_id))
    if args.input_mode == "dashboard-endpoint":
        return merge_crowdin_zip(fetch_dashboard_crowdin_zip(args.dashboard_base_url))
    raise ValueError(f"Unsupported input mode: {args.input_mode}")


def materialize_pairs(args: argparse.Namespace) -> Tuple[List[RowTranslation], List[str]]:
    source_rows = load_source_rows(args)
    if not source_rows:
        raise RuntimeError("No source rows loaded.")
    fieldnames = sorted({k for row in source_rows for k in row.keys()})
    target_cols = parse_csv_list(args.target_cols) or auto_target_cols(
        fieldnames,
        source_col=args.source_col,
        id_col=args.item_id_col,
        ambiguity_col=args.ambiguity_col,
        ignore_cols=parse_csv_list(args.ignore_cols) + ["identifier", "labels", "contentType", "_path", "_sourcePaths", "_xliff_target"],
    )
    if not target_cols:
        raise RuntimeError("No target language columns detected.")

    pairs: List[RowTranslation] = []
    for idx, row in enumerate(source_rows, start=2):
        source = normalize_text(row.get(args.source_col, ""), strip_html=args.strip_html)
        item_id = normalize_text(row.get(args.item_id_col, ""), strip_html=False) or normalize_text(row.get("identifier", ""), strip_html=False) or f"row-{idx}"
        if not source:
            continue
        ambiguity = normalize_text(row.get(args.ambiguity_col, ""), strip_html=args.strip_html) if args.ambiguity_col else ""
        source_path = normalize_text(row.get("_path", ""), strip_html=False)
        for lang in target_cols:
            target = normalize_text(row.get(lang, ""), strip_html=args.strip_html)
            if not target:
                continue
            pairs.append(RowTranslation(item_id=item_id, row_index=idx, source_text=source, target_lang=lang, target_text=target, source_path=source_path, ambiguity_note=ambiguity))
            if args.max_pairs > 0 and len(pairs) >= args.max_pairs:
                return pairs, target_cols
    return pairs, target_cols


def maybe_prefix_e5(model_name: str, texts: Sequence[str], prefix: str) -> List[str]:
    if "e5" not in str(model_name or "").lower():
        return list(texts)
    return [f"{prefix}: {text}" for text in texts]


def cosine(u: np.ndarray, v: np.ndarray) -> float:
    denom = float(np.linalg.norm(u) * np.linalg.norm(v))
    return 0.0 if denom == 0 else float(np.dot(u, v) / denom)


def run_consistency_stage(rows: List[RowTranslation], args: argparse.Namespace) -> None:
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as exc:
        print(f"[consistency] skipped: sentence-transformers unavailable ({exc})")
        return
    if not rows:
        return
    device = None if args.embedding_device == "auto" else args.embedding_device
    model = SentenceTransformer(args.embedding_model, device=device)
    target_inputs = maybe_prefix_e5(args.embedding_model, [r.target_text for r in rows], "passage")
    source_inputs = maybe_prefix_e5(args.embedding_model, [r.source_text for r in rows], "query")
    target_emb = model.encode(target_inputs, batch_size=args.embedding_batch_size, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=True)
    source_emb = model.encode(source_inputs, batch_size=args.embedding_batch_size, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=True)
    per_item: Dict[str, List[int]] = {}
    for idx, row in enumerate(rows):
        per_item.setdefault(row.item_id, []).append(idx)
    for indices in per_item.values():
        for idx in indices:
            row = rows[idx]
            others = [target_emb[j] for j in indices if j != idx]
            if others:
                score = cosine(target_emb[idx], np.mean(np.array(others), axis=0))
                basis = "target-centroid"
            else:
                score = cosine(target_emb[idx], source_emb[idx])
                basis = "source-fallback"
            row.scores["consistency"] = score
            row.metadata["consistency_basis"] = basis
            if score < args.consistency_threshold:
                row.needs_review = True
                row.review_reasons.append(f"consistency<{args.consistency_threshold:.2f}")


def run_comet_stage(rows: List[RowTranslation], args: argparse.Namespace) -> None:
    if not args.run_comet or not rows:
        return
    try:
        from comet import download_model, load_from_checkpoint
    except Exception as exc:
        print(f"[comet] skipped: unbabel-comet unavailable ({exc})")
        return
    model_path = download_model(args.comet_model)
    model = load_from_checkpoint(model_path)
    samples = [{"src": r.source_text, "mt": r.target_text} for r in rows]
    try:
        pred = model.predict(samples, batch_size=args.comet_batch_size, progress_bar=True)
    except TypeError:
        pred = model.predict(samples, batch_size=args.comet_batch_size, gpus=0, progress_bar=True)
    scores = list(pred.get("scores") or [])
    if len(scores) != len(rows):
        print("[comet] skipped: prediction count did not match row count")
        return
    for row, score in zip(rows, scores):
        score_f = float(score)
        row.scores["comet"] = score_f
        if score_f < args.comet_threshold:
            row.needs_review = True
            row.review_reasons.append(f"comet<{args.comet_threshold:.2f}")


def build_llm_prompt(row: RowTranslation) -> str:
    context = row.ambiguity_note or "Preserve the intended meaning, pragmatic force, and naturalness for Levante benchmark content."
    return (
        "You are an expert translation quality assessor using MQM-style severity.\n"
        "Evaluate source and target directly. Return strict JSON only.\n\n"
        f"Source (English): {row.source_text}\n"
        f"Target ({row.target_lang}): {row.target_text}\n"
        f"Context: {context}\n\n"
        "Return JSON with keys: adequacy, fluency, naturalness, ambiguity_preservation, "
        "final_score, severity, issues, rationale_short. Severity must be critical, major, minor, or none."
    )


def call_gemini(prompt: str, model: str, api_key: str) -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=90) as resp:
        parsed = json.loads(resp.read().decode("utf-8"))
    text = parsed.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
    if not text:
        raise RuntimeError("Gemini returned empty response.")
    return json.loads(text)


def run_llm_judge_stage(rows: List[RowTranslation], args: argparse.Namespace) -> None:
    if not args.run_llm_judge or not rows:
        return
    api_key = os.environ.get(args.gemini_api_key_env, "").strip()
    if not api_key:
        print(f"[llm] skipped: {args.gemini_api_key_env} is not set")
        return
    calls = 0
    for row in rows:
        if args.llm_only_flagged and not row.needs_review:
            continue
        if args.llm_max_calls > 0 and calls >= args.llm_max_calls:
            break
        try:
            judged = call_gemini(build_llm_prompt(row), args.gemini_model, api_key)
        except Exception as exc:
            row.notes.append(f"llm_error:{exc}")
            continue
        calls += 1
        row.metadata["llm"] = judged
        score = float(judged.get("final_score", 0.0) or 0.0)
        severity = str(judged.get("severity", "none")).strip().lower().replace("_", "-")
        row.scores["llm_final"] = score
        if score < args.gemini_threshold:
            row.needs_review = True
            row.review_reasons.append(f"llm<{args.gemini_threshold:.1f}")
        if severity in {"critical", "major"}:
            row.needs_review = True
            row.review_reasons.append(f"llm_severity:{severity}")


def metric_summary(values: Sequence[float]) -> Dict[str, object]:
    if not values:
        return {"count": 0}
    arr = np.array(values, dtype=np.float32)
    return {
        "count": len(values),
        "mean": round(float(statistics.mean(values)), 4),
        "median": round(float(statistics.median(values)), 4),
        "min": round(float(min(values)), 4),
        "max": round(float(max(values)), 4),
        "p10": round(float(np.percentile(arr, 10)), 4),
        "p90": round(float(np.percentile(arr, 90)), 4),
    }


def summarize(rows: List[RowTranslation]) -> Dict[str, object]:
    flagged = [r for r in rows if r.needs_review]
    by_language: Dict[str, Dict[str, int]] = {}
    for row in rows:
        bucket = by_language.setdefault(row.target_lang, {"total": 0, "flagged": 0})
        bucket["total"] += 1
        if row.needs_review:
            bucket["flagged"] += 1
    return {
        "rows_total": len(rows),
        "rows_flagged": len(flagged),
        "flag_rate": round((len(flagged) / len(rows)) if rows else 0.0, 4),
        "consistency": metric_summary([r.scores["consistency"] for r in rows if "consistency" in r.scores]),
        "comet": metric_summary([r.scores["comet"] for r in rows if "comet" in r.scores]),
        "llm_final": metric_summary([r.scores["llm_final"] for r in rows if "llm_final" in r.scores]),
        "by_language": by_language,
    }


def write_outputs(rows: List[RowTranslation], args: argparse.Namespace) -> None:
    csv_path = Path(args.output_csv)
    json_path = Path(args.summary_json)
    md_path = Path(args.report_md)
    for path in (csv_path, json_path, md_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "item_id",
        "source_path",
        "target_lang",
        "source_text",
        "target_text",
        "consistency_score",
        "comet_score",
        "llm_final_score",
        "llm_severity",
        "llm_issues",
        "llm_rationale_short",
        "needs_review",
        "review_reasons",
        "notes",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            llm = row.metadata.get("llm")
            llm_severity = ""
            llm_issues = ""
            llm_rationale_short = ""
            if isinstance(llm, dict):
                llm_severity = str(llm.get("severity", "") or "")
                issues = llm.get("issues", "")
                if isinstance(issues, list):
                    llm_issues = " | ".join(str(x) for x in issues if str(x).strip())
                else:
                    llm_issues = str(issues or "")
                llm_rationale_short = str(llm.get("rationale_short", "") or "")
            writer.writerow({
                "item_id": row.item_id,
                "source_path": row.source_path,
                "target_lang": row.target_lang,
                "source_text": row.source_text,
                "target_text": row.target_text,
                "consistency_score": row.scores.get("consistency", ""),
                "comet_score": row.scores.get("comet", ""),
                "llm_final_score": row.scores.get("llm_final", ""),
                "llm_severity": llm_severity,
                "llm_issues": llm_issues,
                "llm_rationale_short": llm_rationale_short,
                "needs_review": "yes" if row.needs_review else "no",
                "review_reasons": ";".join(sorted(set(row.review_reasons))),
                "notes": ";".join(row.notes),
            })
    payload = {
        "summary": summarize(rows),
        "rows": [
            {
                "itemId": r.item_id,
                "sourcePath": r.source_path,
                "targetLang": r.target_lang,
                "scores": r.scores,
                "needsReview": r.needs_review,
                "reviewReasons": sorted(set(r.review_reasons)),
                "metadata": r.metadata,
            }
            for r in rows
        ],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown_report(rows, md_path)
    print(f"Report CSV: {csv_path}")
    print(f"Summary JSON: {json_path}")
    print(f"Flag report: {md_path}")


def write_markdown_report(rows: List[RowTranslation], out_path: Path) -> None:
    from collections import Counter

    flagged = [r for r in rows if r.needs_review]
    reason_counts = Counter(reason for r in flagged for reason in sorted(set(r.review_reasons)))
    severity_counts = Counter()
    for row in rows:
        llm = row.metadata.get("llm")
        if isinstance(llm, dict):
            sev = str(llm.get("severity", "none")).strip().lower().replace("_", " ").replace("-", " ")
            severity_counts[sev or "none"] += 1
    lines = [
        "# Translation Grading Flag Report",
        "",
        f"- Total pairs: **{len(rows)}**",
        f"- Flagged pairs: **{len(flagged)}** ({(100 * len(flagged) / max(1, len(rows))):.2f}%)",
        "",
        "## Flag Reasons",
        "",
    ]
    if reason_counts:
        lines.extend([f"- `{reason}`: **{count}**" for reason, count in reason_counts.most_common()])
    else:
        lines.append("- No rows flagged.")
    lines.extend(["", "## Gemini Severity Counts", ""])
    if severity_counts:
        lines.extend([f"- `{severity}`: **{count}**" for severity, count in severity_counts.most_common()])
    else:
        lines.append("- Gemini stage not run or returned no severities.")
    lines.extend(["", "## By Language", ""])
    summary = summarize(rows)
    for lang, stats in sorted(summary["by_language"].items()):
        total = stats["total"]
        count = stats["flagged"]
        lines.append(f"- `{lang}`: {count} / {total} ({(100 * count / max(1, total)):.2f}%)")

    lines.extend(["", "## Flagged Row Details", ""])
    if not flagged:
        lines.append("- No flagged rows.")
    else:
        lines.append("| item_id | lang | reasons | llm_severity | llm_rationale_short | llm_issues |")
        lines.append("|---|---|---|---|---|---|")
        for row in flagged:
            llm = row.metadata.get("llm")
            if isinstance(llm, dict):
                severity = str(llm.get("severity", "") or "")
                rationale = str(llm.get("rationale_short", "") or "")
                issues = llm.get("issues", "")
                if isinstance(issues, list):
                    issues_text = " ; ".join(str(x) for x in issues if str(x).strip())
                else:
                    issues_text = str(issues or "")
            else:
                severity = ""
                rationale = ""
                issues_text = ""
            reasons = ";".join(sorted(set(row.review_reasons)))
            lines.append(
                f"| {row.item_id} | {row.target_lang} | {reasons} | {severity} | {rationale} | {issues_text} |"
            )
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    rows, target_cols = materialize_pairs(args)
    if not rows:
        print("No source-target pairs found.")
        return 1
    print(f"Loaded {len(rows)} source-target pairs across {len(target_cols)} target columns.")
    run_consistency_stage(rows, args)
    run_comet_stage(rows, args)
    run_llm_judge_stage(rows, args)
    write_outputs(rows, args)
    summary = summarize(rows)
    print(f"Flagged: {summary['rows_flagged']} / {summary['rows_total']} ({summary['flag_rate'] * 100:.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
