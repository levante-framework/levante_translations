#!/usr/bin/env python3
"""Composite translation quality metrics orchestrator.

Fuses every available quality signal into a single per-``(item_id, target_lang)``
composite score and emits a unified CSV + JSON + HTML report.

By default it *fuses existing cached artifacts* (the cheap path): pipeline
grading report, xCOMET segment scores, Gemini direct results, NL backtranslation
results, the VLM language matrices/outliers, and oracle logs. Pass
``--run-embeddings`` to additionally compute the cheap embedding consistency /
baseline signals live via ``pipeline.py`` when no cached grading report exists.

Example (fuse-only, from repo root):
    python translation_grading/composite_metrics.py

Example (also run live embeddings from Crowdin approved export):
    python translation_grading/composite_metrics.py --run-embeddings \
        --embedding-baseline translation_grading/output/embedding_baseline.npz
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from translation_grading import composite_quality as cq
except ModuleNotFoundError:  # pragma: no cover - direct script invocation
    import composite_quality as cq


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fuse translation quality signals into a composite metric.")
    p.add_argument("--item-bank", default="translation_text/item_bank_translations.csv",
                   help="Item bank CSV used to reconcile VLM English keys to item_id.")
    p.add_argument("--item-bank-source-col", default="en-US")
    p.add_argument("--translations-csv",
                   default="translation_grading/output/complete_translations.csv",
                   help="Wide complete-translations export (identifier/labels/en/<langs>) used as "
                        "the authoritative source+translation text backbone. Preferred over "
                        "--item-bank when present (run export_translations_csv.py to build it).")
    p.add_argument("--output-dir", default="translation_grading/output")

    # Cached signal inputs (each is optional; missing files are skipped).
    p.add_argument("--grading-report", default="translation_grading/output/translation-grading-report.csv",
                   help="pipeline.py CSV (embedding consistency/baseline, COMET, Gemini).")
    p.add_argument("--comet-dir", default="xcomet/output",
                   help="Directory of xcomet/output/<lang>/segment_scores.csv files.")
    p.add_argument("--gemini-results", default="translation_grading/output/translation_quality_results.csv",
                   help="gemini_quality_evaluator output CSV.")
    p.add_argument("--nl-auto-review", default="", nargs="*",
                   help="NL all-tasks auto-review CSV(s) carrying gemini + backtranslation. "
                        "Defaults to the two known NL result files when present.")
    p.add_argument("--vlm-tasks", default="vocab,stories,trog",
                   help="Comma-separated VLM tasks to fuse (expects <task>_vlm_item_matrix.csv etc.).")
    p.add_argument("--vlm-dir", default="translation_grading/output",
                   help="Directory holding <task>_vlm_item_matrix.csv and *_outliers.csv.")
    p.add_argument("--oracle-logs", default="../levante-qa/cypress/logs",
                   help="Directory of *oracle*.jsonl logs for the deterministic oracle prior.")
    p.add_argument("--screenshot-dirs",
                   default="translation_grading/output/all_tasks_esco_nl_screenshot_prompt_thumbs,"
                           "translation_grading/output/crowdin_screenshots",
                   help="Comma-separated dirs scanned for per-record screenshots; matched files are "
                        "copied next to the web JSON (data/tq-screenshots) and linked from each card.")
    p.add_argument("--screenshot-artifact",
                   default="../levante-web-dashboard/data/validation/crowdin-screenshot-artifact.json",
                   help="Crowdin screenshot artifact JSON mapping item ids to hosted screenshot URLs; "
                        "used as the primary (no-copy) screenshot source.")
    p.add_argument("--vocab-image-dirs",
                   default="../core-task-assets/vocab/images",
                   help="Comma-separated dirs of vocab referent images named by the English word "
                        "(e.g. squash.webp); matched to vocab items via the English source.")
    p.add_argument("--screenshot-dir", default="translation_grading/output/crowdin_screenshots",
                   help="Crowdin screenshot cache for optional HTML embeds.")

    # Live embedding computation (opt-in, requires sentence-transformers).
    p.add_argument("--run-embeddings", action="store_true",
                   help="Compute embedding consistency/baseline live when no grading report is cached.")
    p.add_argument("--embedding-input-mode", default="crowdin-api",
                   choices=["csv", "crowdin-api", "crowdin-zip", "dashboard-endpoint"])
    p.add_argument("--embedding-input-csv", default="")
    p.add_argument("--embedding-model", default="sentence-transformers/LaBSE")
    p.add_argument("--embedding-device", default="auto", choices=["auto", "cpu", "cuda"])
    p.add_argument("--embedding-baseline", default="",
                   help="Optional persistent baseline .npz for the embedding baseline signal.")

    # Outputs.
    p.add_argument("--out-csv", default="composite-quality-report.csv")
    p.add_argument("--out-json", default="composite-quality-summary.json")
    p.add_argument("--out-html", default="composite-quality-report.html")
    p.add_argument("--out-dashboard", default="composite-translation-dashboard.html",
                   help="Card-based review dashboard (cloned from the NL human-review layout).")
    p.add_argument("--out-web-json", default="",
                   help="Optional absolute/relative path to write a compact JSON "
                        "(summary + records) for the levante-web-dashboard page. Not joined with --output-dir.")
    p.add_argument("--explanations", default="translation_grading/output/flagged_explanations.json",
                   help="JSON of auto-generated explanations (keyed 'item_id\\tlang') produced by "
                        "explain_flagged.py; attached to flagged records when present.")
    p.add_argument("--backtranslations", default="translation_grading/output/backtranslations.json",
                   help="JSON of Gemini back-translations (keyed 'item_id\\tlang') produced by "
                        "backtranslate.py; shown beneath the translation on each card.")
    p.add_argument("--backtranslation-similarity",
                   default="translation_grading/output/backtranslation_similarity.json",
                   help="JSON of source-vs-back-translation cosine similarities (keyed "
                        "'item_id\\tlang') from backtranslation_similarity.py; fed into scoring "
                        "as the 'backtranslation_embed' signal across all languages.")
    p.add_argument("--no-adjudicate", action="store_true",
                   help="Disable auto-clearing of uncorroborated false-alarm flags.")
    p.add_argument("--adjudicate-target", default="ok", choices=["ok", "review"],
                   help="Tier an uncorroborated false-alarm flag is downgraded to (default: ok).")
    p.add_argument("--dashboard-include-ok", action="store_true",
                   help="Include ok-tier records as cards in the dashboard (default: flagged only).")
    p.add_argument("--keep-textless", action="store_true",
                   help="Keep records that have neither an English source nor a translation "
                        "(default: drop them; these are behavioral-only items, e.g. TROG keyed "
                        "by ordinal, with no recoverable text).")
    p.add_argument("--exclude-langs", default="en-US,en-GB",
                   help="Comma-separated target langs to drop from the report. Defaults to the "
                        "English reference variants, which are the source/reference and not "
                        "translations. Pass an empty string to keep them.")
    p.add_argument("--weight", action="append", default=[],
                   help="Override a family weight as name=value (repeatable).")
    return p.parse_args()


def attach_explanations(records: List[cq.CompositeRecord], path: Path) -> None:
    """Attach auto-generated explanations (from explain_flagged.py) to records."""
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return
    n = 0
    for r in records:
        info = data.get(f"{r.item_id}\t{r.target_lang}")
        if not isinstance(info, dict):
            continue
        r.explanation = str(info.get("explanation", "") or "")
        r.suggested_fix = str(info.get("suggested_fix", "") or "")
        r.flag_confidence = str(info.get("flag_confidence", "") or "")
        r.verdict = str(info.get("verdict", "") or "")
        n += 1
    print(f"[explain] attached {n} explanations from {path}")


def attach_backtranslations(records: List[cq.CompositeRecord], path: Path) -> None:
    """Attach Gemini back-translations (keyed 'item_id\\tlang') produced by
    backtranslate.py to the matching records."""
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    by_key = {(r.item_id, r.target_lang): r for r in records}
    n = 0
    for key, text in data.items():
        item_id, _, lang = str(key).partition("\t")
        r = by_key.get((item_id, lang))
        if r is not None and text:
            r.back_translation = str(text)
            n += 1
    print(f"[backtranslate] attached {n} back-translations from {path}")


def attach_backtranslation_similarity(records: List[cq.CompositeRecord], path: Path) -> None:
    """Inject the source-vs-back-translation cosine (from
    backtranslation_similarity.py) as the cross-language 'backtranslation_embed'
    scoring signal. Must run on merged records BEFORE score_records()."""
    if not path.exists():
        print(f"[bt-embed] similarity file not found ({path}); skipping scoring signal")
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print(f"[bt-embed] could not read {path}; skipping scoring signal")
        return
    by_key = {(r.item_id, r.target_lang): r for r in records}
    n = 0
    for key, cos in data.items():
        item_id, _, lang = str(key).partition("\t")
        r = by_key.get((item_id, lang))
        if r is None or cos is None:
            continue
        try:
            cosf = float(cos)
        except (TypeError, ValueError):
            continue
        r.signals["backtranslation_embed"] = {"raw": cosf, "detail": {"cosine": cosf}}
        n += 1
    print(f"[bt-embed] attached {n} back-translation similarity signals from {path}")


_SHOT_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
_ARTICLE_RE = re.compile(r"^(the|a|an)\s+", re.IGNORECASE)


def _shot_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(text or "").lower())


def _index_word_images(dirs: List[Path]) -> Dict[str, Path]:
    """Index task asset images named by their English referent word (vocab).

    Files like ``squash.webp`` / ``slope.webp`` map to the vocab item whose
    English source is "the squash" / "the slope"."""
    out: Dict[str, Path] = {}
    for d in dirs:
        if not d.exists():
            continue
        for f in sorted(d.iterdir()):
            if f.is_file() and f.suffix.lower() in _SHOT_EXTS:
                out.setdefault(_shot_key(f.stem), f)
    return out


def _index_screenshots(dirs: List[Path]) -> Tuple[Dict, Dict, Dict]:
    """Index available screenshot files.

    Returns three lookups keyed by a normalized identifier:
      * thumbs_lang : {(idkey, lang) -> path}  (clean ``task__id__lang.png`` thumbs)
      * thumbs_any  : {idkey -> path}
      * fuzzy       : {idkey -> path}          (crowdin context screenshots)
    """
    thumbs_lang: Dict[Tuple[str, str], Path] = {}
    thumbs_any: Dict[str, Path] = {}
    fuzzy: Dict[str, Path] = {}
    for d in dirs:
        if not d.exists():
            continue
        for f in sorted(d.iterdir()):
            if not f.is_file() or f.suffix.lower() not in _SHOT_EXTS:
                continue
            name = f.stem
            # Clean thumb form: "<task>__<identifier>__<lang>".
            parts = name.split("__")
            if len(parts) == 3:
                ident, lang = parts[1], cq.normalize_lang_code(parts[2])
                key = _shot_key(ident)
                thumbs_lang.setdefault((key, lang), f)
                thumbs_any.setdefault(key, f)
                continue
            # Crowdin context form: "<num>_<slug>_<hash>" / "<slug>_<hash>" / "<slug>".
            slug = re.sub(r"^\d+_", "", name)
            slug = re.sub(r"_[0-9a-f]{6,}$", "", slug)
            fuzzy.setdefault(_shot_key(slug), f)
    return thumbs_lang, thumbs_any, fuzzy


def _index_artifact(artifact_path: Path) -> Dict[str, str]:
    """Map normalized Crowdin item identifier -> hosted screenshot URL from the
    crowdin-screenshot-artifact (the authoritative per-string mapping)."""
    out: Dict[str, str] = {}
    if not artifact_path.exists():
        return out
    try:
        data = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return out
    for entry in data.get("entries", []):
        shots = entry.get("screenshots") or []
        if not shots:
            continue
        url = shots[0].get("cachedUrl") or shots[0].get("url")
        item = entry.get("itemId")
        if url and item:
            out.setdefault(_shot_key(item), url)
    return out


def attach_screenshots(records: List[cq.CompositeRecord], shot_dirs: List[Path],
                       web_json_path: Path, vocab_dirs: Optional[List[Path]] = None,
                       artifact_path: Optional[Path] = None) -> None:
    """Best-effort: match each record to a screenshot, setting
    ``record.screenshot`` to either a hosted URL (Crowdin artifact) or a
    page-relative URL for a locally-copied asset.

    Matching order: Crowdin screenshot artifact by item id (hosted, no copy);
    then vocab referent image by English source word; then a clean per-language
    thumbnail, an any-language thumbnail, an exact-id crowdin context
    screenshot, and finally a long-substring fuzzy match. Unmatched records keep
    an empty screenshot field."""
    artifact = _index_artifact(artifact_path) if artifact_path else {}
    thumbs_lang, thumbs_any, fuzzy = _index_screenshots(shot_dirs)
    word_images = _index_word_images(vocab_dirs or [])
    if not (artifact or thumbs_lang or thumbs_any or fuzzy or word_images):
        print("[screenshots] no source screenshots found; skipping")
        return

    # Destination: <web public>/data/tq-screenshots ; URL is page-relative.
    dest_dir = web_json_path.parent / "tq-screenshots"
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied: Dict[Path, str] = {}

    def url_for(src: Path) -> str:
        if src not in copied:
            safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", src.name)
            dest = dest_dir / safe
            if not dest.exists():
                shutil.copyfile(src, dest)
            copied[src] = f"./data/tq-screenshots/{safe}"
        return copied[src]

    fuzzy_items = [(k, v) for k, v in fuzzy.items() if len(k) >= 5]
    n = 0
    n_hosted = 0
    for r in records:
        key = _shot_key(r.item_id)
        lang = cq.normalize_lang_code(r.target_lang)
        hosted = artifact.get(key)
        if hosted:
            r.screenshot = hosted
            n += 1
            n_hosted += 1
            continue
        src = None
        if str(r.task or "").strip().lower() == "vocab" and word_images:
            word = _ARTICLE_RE.sub("", str(r.source_text or "").strip())
            src = word_images.get(_shot_key(word))
        if src is None:
            src = (thumbs_lang.get((key, lang))
                   or thumbs_any.get(key)
                   or fuzzy.get(key))
        if src is None:
            for fk, fv in fuzzy_items:
                if fk in key or key in fk:
                    src = fv
                    break
        if src is not None:
            r.screenshot = url_for(src)
            n += 1
    print(f"[screenshots] matched {n}/{len(records)} records "
          f"({n_hosted} hosted via artifact, {len(copied)} local images copied) -> {dest_dir}")


def adjudicate(records: List[cq.CompositeRecord], target_tier: str) -> None:
    """Auto-clear likely_bad flags the explainer judges a false alarm, but ONLY
    when the flag is uncorroborated: a single signal and not behavioral ground
    truth (cross-language VLM outlier / oracle incorrect). Corroborated and
    behavioral flags are never auto-cleared. Each change is tagged for audit."""
    behavioral = {"vlm:cross_lang_outlier", "oracle:incorrect"}
    n = 0
    for r in records:
        if r.flag_tier != "likely_bad" or r.verdict != "false_alarm":
            continue
        if len(r.signals) >= 2:
            continue
        if any(reason in behavioral for reason in r.reasons):
            continue
        r.flag_tier = target_tier
        r.reasons.append("adjudicated:false_alarm")
        n += 1
    print(f"[adjudicate] cleared {n} uncorroborated false-alarm flags -> {target_tier}")


def parse_weight_overrides(raw: List[str]) -> Dict[str, float]:
    overrides: Dict[str, float] = {}
    for entry in raw:
        if "=" not in entry:
            continue
        name, _, value = entry.partition("=")
        try:
            overrides[name.strip()] = float(value.strip())
        except ValueError:
            continue
    return overrides


def gather_records(args: argparse.Namespace, item_index: cq.ItemIndex) -> List[cq.AdapterRecord]:
    records: List[cq.AdapterRecord] = []
    seen: Dict[str, int] = {}

    def add(label: str, recs: List[cq.AdapterRecord]) -> None:
        if recs:
            records.extend(recs)
            seen[label] = len(recs)

    # Embeddings / COMET / Gemini from a cached pipeline grading report.
    grading_path = Path(args.grading_report)
    if grading_path.exists():
        add("grading_report", cq.load_grading_report(grading_path))
    elif args.run_embeddings:
        add("embeddings_live", run_live_embeddings(args))

    # COMET QE from xcomet output (fills any language not in the grading report).
    add("comet", cq.load_comet_dir(Path(args.comet_dir)))

    # Gemini direct judge.
    add("gemini_results", cq.load_gemini_results(Path(args.gemini_results)))

    # NL gemini + backtranslation result files.
    nl_paths = args.nl_auto_review
    if not nl_paths:
        nl_paths = [
            "translation_grading/output/nl_all_tasks_auto_review_results.csv",
            "translation_grading/output/nl_all_tasks_auto_review_results_prompt_update.csv",
        ]
    for nl_path in nl_paths:
        if Path(nl_path).exists():
            add(f"nl:{Path(nl_path).name}", cq.load_nl_auto_review(Path(nl_path)))

    # VLM matrices + outliers per task.
    for task in [t.strip() for t in str(args.vlm_tasks).split(",") if t.strip()]:
        matrix = Path(args.vlm_dir) / f"{task}_vlm_item_matrix.csv"
        outliers = Path(args.vlm_dir) / f"{task}_vlm_language_outliers.csv"
        add(f"vlm:{task}", cq.load_vlm_task(task, matrix, outliers, item_index))

    print("[gather] signal records collected:")
    for label, count in seen.items():
        print(f"  - {label}: {count}")
    if not records:
        print("  (no cached artifacts found; pass --run-embeddings or check paths)")
    return records


def run_live_embeddings(args: argparse.Namespace) -> List[cq.AdapterRecord]:
    """Run pipeline embedding stages live and convert rows to adapter records."""
    try:
        from translation_grading import pipeline as pl
    except ModuleNotFoundError:  # pragma: no cover
        import pipeline as pl  # type: ignore

    pipe_args = argparse.Namespace(
        input_mode=args.embedding_input_mode,
        input_csv=args.embedding_input_csv,
        crowdin_zip="",
        crowdin_project_id=pl.DEFAULT_CROWDIN_PROJECT_ID,
        crowdin_cache_zip="translation_grading/output/.crowdin-approved-cache.zip",
        refresh_crowdin_cache=False,
        crowdin_cache_max_age_minutes=120,
        dashboard_base_url="https://levante-cockpit.vercel.app",
        item_id_col="item_id",
        source_col="en",
        target_cols="",
        ignore_cols="",
        ambiguity_col="",
        max_pairs=0,
        strip_html=True,
        embedding_model=args.embedding_model,
        embedding_device=args.embedding_device,
        embedding_batch_size=128,
        consistency_threshold=0.78,
        embedding_baseline=args.embedding_baseline,
        build_embedding_baseline=False,
        detect_embedding_outliers=bool(args.embedding_baseline),
        baseline_item_centroid_threshold=0.78,
        baseline_item_lang_threshold=0.82,
        baseline_lang_centroid_threshold=0.0,
    )
    rows, _ = pl.materialize_pairs(pipe_args)
    pl.run_consistency_stage(rows, pipe_args)
    pl.run_embedding_baseline_stage(rows, pipe_args)
    return cq.load_embedding_records(rows)


# --------------------------------------------------------------------------- #
# Report writers
# --------------------------------------------------------------------------- #

def write_csv(records: List[cq.CompositeRecord], path: Path) -> None:
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [cq.record_to_row(r) for r in records]
    rows.sort(key=lambda r: (
        {"likely_bad": 0, "review": 1, "unknown": 2, "ok": 3}.get(r["flag_tier"], 4),
        float(r["quality_score"]) if r["quality_score"] != "" else 1.0,
    ))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=cq.CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_json(records: List[cq.CompositeRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": cq.summarize(records),
        "weights": cq.DEFAULT_WEIGHTS,
        "calibration": cq.CALIBRATION,
        "tier_bands": {"ok_min": cq.TIER_OK_MIN, "review_min": cq.TIER_REVIEW_MIN},
        "records": [cq.record_to_row(r) for r in records],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_web_json(records: List[cq.CompositeRecord], path: Path) -> None:
    """Compact JSON consumed by the levante-web-dashboard Translation Quality page."""
    import datetime as _dt

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "weights": cq.DEFAULT_WEIGHTS,
        "tier_bands": {"ok_min": cq.TIER_OK_MIN, "review_min": cq.TIER_REVIEW_MIN},
        "summary": cq.summarize(records),
        "records": [cq.record_to_row(r) for r in records],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _summary_tables_html(summary: Dict[str, object]) -> str:
    tiers = summary["flag_tiers"]
    total = max(1, summary["records_total"])
    tier_rows = "".join(
        f"<tr><td>{html.escape(t)}</td><td>{n}</td><td>{100 * n / total:.1f}%</td></tr>"
        for t, n in tiers.items()
    )
    cov_rows = "".join(
        f"<tr><td>{html.escape(fam)}</td><td>{n}</td><td>{100 * n / total:.1f}%</td></tr>"
        for fam, n in summary["signal_coverage"].items()
    )
    lang_rows = "".join(
        f"<tr><td>{html.escape(lang)}</td><td>{b['total']}</td><td>{b['review']}</td>"
        f"<td>{b['likely_bad']}</td></tr>"
        for lang, b in sorted(summary["by_language"].items())
    )
    task_rows = "".join(
        f"<tr><td>{html.escape(task)}</td><td>{b['total']}</td><td>{b['review']}</td>"
        f"<td>{b['likely_bad']}</td></tr>"
        for task, b in sorted(summary["by_task"].items())
    )
    return f"""
    <div class="grid">
      <section><h2>Flag tiers</h2><table><tr><th>tier</th><th>count</th><th>%</th></tr>{tier_rows}</table></section>
      <section><h2>Signal coverage</h2><table><tr><th>signal</th><th>records</th><th>%</th></tr>{cov_rows}</table></section>
      <section><h2>By language</h2><table><tr><th>lang</th><th>total</th><th>review</th><th>likely_bad</th></tr>{lang_rows}</table></section>
      <section><h2>By task</h2><table><tr><th>task</th><th>total</th><th>review</th><th>likely_bad</th></tr>{task_rows}</table></section>
    </div>
    """


def _build_screenshot_index(screenshot_dir: Path) -> Dict[str, str]:
    index: Dict[str, str] = {}
    if not screenshot_dir.exists():
        return index
    for path in screenshot_dir.glob("*"):
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            index[path.stem.lower()] = str(path.resolve())
    return index


def _screenshot_for(item_id: str, screenshot_index: Dict[str, str]) -> Optional[str]:
    needle = cq.normalize_text_key(item_id).replace(" ", "")
    if not needle:
        return None
    for stem, abspath in screenshot_index.items():
        if needle and needle in stem.replace("_", ""):
            return abspath
    return None


def write_html(records: List[cq.CompositeRecord], path: Path, screenshot_dir: Path) -> None:
    summary = cq.summarize(records)
    screenshot_index = _build_screenshot_index(screenshot_dir)
    rows = sorted(
        records,
        key=lambda r: (
            {"likely_bad": 0, "review": 1, "unknown": 2, "ok": 3}.get(r.flag_tier, 4),
            r.quality_score if r.quality_score is not None else 1.0,
            -r.confidence,
        ),
    )

    body_rows = []
    for r in rows:
        score = "-" if r.quality_score is None else f"{r.quality_score:.3f}"
        shot = _screenshot_for(r.item_id, screenshot_index)
        shot_cell = f'<img loading="lazy" src="file://{html.escape(shot)}">' if shot else ""
        sig_bits = []
        for fam in cq.SIGNAL_FAMILIES:
            payload = r.signals.get(fam)
            if not payload:
                continue
            qv = payload.get("quality")
            sig_bits.append(f"{fam}={qv:.2f}" if isinstance(qv, (int, float)) else fam)
        body_rows.append(
            f'<tr class="tier-{html.escape(r.flag_tier)}" data-tier="{html.escape(r.flag_tier)}" '
            f'data-lang="{html.escape(r.target_lang)}" data-task="{html.escape(r.task)}">'
            f"<td>{html.escape(r.flag_tier)}</td>"
            f"<td>{score}</td>"
            f"<td>{r.confidence:.2f}</td>"
            f"<td>{html.escape(r.item_id)}</td>"
            f"<td>{html.escape(r.target_lang)}</td>"
            f"<td>{html.escape(r.task)}</td>"
            f"<td>{html.escape(r.source_text)}</td>"
            f"<td>{html.escape(r.target_text)}</td>"
            f'<td class="sig">{html.escape(", ".join(sig_bits))}</td>'
            f'<td class="reasons">{html.escape("; ".join(r.reasons))}</td>'
            f"<td>{shot_cell}</td>"
            "</tr>"
        )

    langs = sorted({r.target_lang for r in records})
    tasks = sorted({r.task for r in records if r.task})
    lang_opts = "".join(f'<option value="{html.escape(l)}">{html.escape(l)}</option>' for l in langs)
    task_opts = "".join(f'<option value="{html.escape(t)}">{html.escape(t)}</option>' for t in tasks)

    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Composite Translation Quality</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 1.5rem; color: #1c1c1c; }}
  h1 {{ margin-bottom: .25rem; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; margin: 1rem 0; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
  th, td {{ border: 1px solid #ddd; padding: 4px 6px; text-align: left; vertical-align: top; }}
  th {{ background: #f4f4f4; position: sticky; top: 0; cursor: pointer; }}
  td.reasons {{ color: #8a1f1f; }}
  td.sig {{ font-family: ui-monospace, monospace; font-size: 11px; color: #333; }}
  tr.tier-likely_bad {{ background: #fdecec; }}
  tr.tier-review {{ background: #fff7e6; }}
  tr.tier-ok {{ background: #f1faf1; }}
  tr.tier-unknown {{ background: #f0f0f0; }}
  img {{ max-width: 120px; max-height: 90px; }}
  .controls {{ margin: 1rem 0; display: flex; gap: 1rem; flex-wrap: wrap; align-items: center; }}
  select, input {{ padding: 4px; }}
</style></head><body>
<h1>Composite Translation Quality</h1>
<p>{summary['records_total']} item-language records. Sorted worst-first. Score in 0..1 (higher = better).</p>
{_summary_tables_html(summary)}
<div class="controls">
  <label>Tier
    <select id="tierFilter"><option value="">all</option><option>likely_bad</option><option>review</option><option>ok</option><option>unknown</option></select>
  </label>
  <label>Language <select id="langFilter"><option value="">all</option>{lang_opts}</select></label>
  <label>Task <select id="taskFilter"><option value="">all</option>{task_opts}</select></label>
  <label>Search <input id="search" type="search" placeholder="item / text"></label>
</div>
<table id="main">
<thead><tr>
<th>tier</th><th>score</th><th>conf</th><th>item_id</th><th>lang</th><th>task</th>
<th>source</th><th>target</th><th>signals</th><th>reasons</th><th>shot</th>
</tr></thead>
<tbody>
{''.join(body_rows)}
</tbody></table>
<script>
const rows = Array.from(document.querySelectorAll('#main tbody tr'));
const tierF = document.getElementById('tierFilter');
const langF = document.getElementById('langFilter');
const taskF = document.getElementById('taskFilter');
const search = document.getElementById('search');
function apply() {{
  const t = tierF.value, l = langF.value, k = taskF.value, q = search.value.toLowerCase();
  rows.forEach(r => {{
    const ok = (!t || r.dataset.tier === t) && (!l || r.dataset.lang === l) &&
               (!k || r.dataset.task === k) && (!q || r.textContent.toLowerCase().includes(q));
    r.style.display = ok ? '' : 'none';
  }});
}}
[tierF, langF, taskF].forEach(e => e.addEventListener('change', apply));
search.addEventListener('input', apply);
document.querySelectorAll('#main thead th').forEach((th, i) => th.addEventListener('click', () => {{
  const body = document.querySelector('#main tbody');
  const sorted = Array.from(body.querySelectorAll('tr')).sort((a, b) => {{
    const x = a.children[i].textContent.trim(), y = b.children[i].textContent.trim();
    const nx = parseFloat(x), ny = parseFloat(y);
    if (!isNaN(nx) && !isNaN(ny)) return nx - ny;
    return x.localeCompare(y);
  }});
  sorted.forEach(r => body.appendChild(r));
}}));
</script>
</body></html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(doc, encoding="utf-8")


_SIGNAL_LABELS = {
    "embedding_consistency": "Embedding consistency",
    "embedding_baseline": "Embedding baseline",
    "comet": "COMET QE",
    "gemini_judge": "Gemini judge",
    "backtranslation": "Backtranslation",
    "backtranslation_embed": "Back-translation similarity",
    "vlm": "VLM QA",
    "oracle": "Oracle QA",
}


def _signal_detail_text(fam: str, payload: Dict) -> str:
    """Human-readable one-liner describing a signal's contribution to the card.

    This is the composite-metric replacement for the old per-item embedding-delta
    and backtranslation prose in the cloned review dashboard."""
    detail = payload.get("detail", {}) or {}
    q = payload.get("quality")
    qtxt = f"{q:.2f}" if isinstance(q, (int, float)) else "-"
    if fam == "comet":
        raw = payload.get("raw")
        rawtxt = f", raw {raw:.3f}" if isinstance(raw, (int, float)) else ""
        return f"q {qtxt}{rawtxt}"
    if fam == "backtranslation_embed":
        raw = payload.get("raw")
        rawtxt = f", cosine {raw:.3f}" if isinstance(raw, (int, float)) else ""
        return f"q {qtxt}{rawtxt}"
    if fam in {"gemini_judge", "backtranslation"}:
        sev = str(detail.get("severity", "") or "none")
        raw = payload.get("raw")
        rawtxt = f"{raw:.0f}/5 " if isinstance(raw, (int, float)) else ""
        return f"q {qtxt} ({rawtxt}severity: {sev})"
    if fam == "vlm":
        bits = ["correct" if detail.get("vlm_correct") == 1 else "incorrect"]
        if detail.get("vlm_lang_outlier"):
            bits.append("cross-language outlier")
        chosen = detail.get("chosen")
        keyed = detail.get("keyed")
        if chosen and keyed:
            bits.append(f"chose '{chosen}' vs key '{keyed}'")
        return f"q {qtxt} (" + "; ".join(str(b) for b in bits) + ")"
    if fam == "oracle":
        return f"q {qtxt} (" + ("correct" if detail.get("oracle_correct") == 1 else "incorrect") + ")"
    return f"q {qtxt}"


def write_dashboard(records: List[cq.CompositeRecord], path: Path, screenshot_dir: Path,
                    include_ok: bool = False) -> None:
    """Card-based review dashboard, cloned from the NL human-review layout but
    driven by the synthesized composite metric instead of embedding-delta +
    backtranslation prose."""
    summary = cq.summarize(records)
    screenshot_index = _build_screenshot_index(screenshot_dir)
    queue = [r for r in records if include_ok or r.flag_tier in {"likely_bad", "review"}]
    queue.sort(key=lambda r: (
        {"likely_bad": 0, "review": 1, "unknown": 2, "ok": 3}.get(r.flag_tier, 4),
        r.quality_score if r.quality_score is not None else 1.0,
        -r.confidence,
    ))

    cards = []
    for r in queue:
        score = "-" if r.quality_score is None else f"{r.quality_score:.3f}"
        sig_lines = []
        for fam in cq.SIGNAL_FAMILIES:
            payload = r.signals.get(fam)
            if not payload:
                continue
            sig_lines.append(
                f"<li><b>{html.escape(_SIGNAL_LABELS.get(fam, fam))}:</b> "
                f"{html.escape(_signal_detail_text(fam, payload))}</li>"
            )
        shot = _screenshot_for(r.item_id, screenshot_index)
        shot_html = f'<div><img loading="lazy" src="file://{html.escape(shot)}"></div>' if shot else ""
        reasons = "; ".join(r.reasons)
        cards.append(
            f'<div class="item tier-{html.escape(r.flag_tier)}" data-tier="{html.escape(r.flag_tier)}" '
            f'data-lang="{html.escape(r.target_lang)}" data-task="{html.escape(r.task)}">'
            f"<h2><code>{html.escape(r.item_id)}</code> &mdash; {html.escape(r.task or 'unknown')} "
            f'&mdash; <span class="lang">{html.escape(r.target_lang)}</span> '
            f'<span class="badge badge-{html.escape(r.flag_tier)}">{html.escape(r.flag_tier)}</span></h2>'
            f'<p class="composite"><b>Composite quality:</b> {score} '
            f"&nbsp;|&nbsp; confidence {r.confidence:.2f} &nbsp;|&nbsp; coverage {r.coverage:.2f} "
            f"&nbsp;|&nbsp; {len(r.signals)} signals</p>"
            + (f'<p class="bad">Reasons: {html.escape(reasons)}</p>' if reasons else "")
            + (f'<div class="explain"><b>Auto explanation</b> '
               f'<span class="conf conf-{html.escape(r.flag_confidence or "na")}">'
               f'{html.escape((r.flag_confidence or "n/a"))} confidence</span>'
               f'<p>{html.escape(r.explanation)}</p>'
               + (f'<p><b>Suggested fix:</b> {html.escape(r.suggested_fix)}</p>' if r.suggested_fix else "")
               + "</div>" if r.explanation else "")
            + f"<p><b>English:</b> {html.escape(r.source_text)}</p>"
            + f"<p><b>{html.escape(r.target_lang)}:</b> {html.escape(r.target_text)}</p>"
            + f'<p><b>Signal breakdown:</b></p><ul class="signals">{"".join(sig_lines)}</ul>'
            + shot_html
            + "</div>"
        )

    langs = sorted({r.target_lang for r in queue})
    tasks = sorted({r.task for r in queue if r.task})
    lang_opts = "".join(f"<option>{html.escape(l)}</option>" for l in langs)
    task_opts = "".join(f"<option>{html.escape(t)}</option>" for t in tasks)
    tiers = summary["flag_tiers"]

    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Composite Translation Quality Review</title>
<style>
  body {{ font-family: Arial, sans-serif; max-width: 1100px; margin: 24px auto; line-height: 1.35; color: #1c1c1c; }}
  h1 {{ margin-bottom: .25rem; }}
  .sub {{ color: #555; margin-bottom: 1rem; }}
  .item {{ border: 1px solid #ddd; border-radius: 8px; padding: 12px; margin: 12px 0; }}
  .item.tier-likely_bad {{ border-left: 6px solid #c0392b; }}
  .item.tier-review {{ border-left: 6px solid #e0a800; }}
  .item.tier-ok {{ border-left: 6px solid #2e7d32; }}
  .bad {{ color: #9b1c1c; font-weight: 700; }}
  .composite {{ background: #f4f7ff; padding: 6px 8px; border-radius: 6px; }}
  .explain {{ background: #fffdf5; border: 1px solid #f0e6c8; border-radius: 6px; padding: 6px 8px; margin: 6px 0; }}
  .conf {{ font-size: 11px; padding: 1px 6px; border-radius: 8px; color: #fff; }}
  .conf-high {{ background: #c0392b; }} .conf-medium {{ background: #e0a800; }}
  .conf-low {{ background: #6c757d; }} .conf-na {{ background: #999; }}
  ul.signals {{ margin: 4px 0 8px 1.2rem; }}
  ul.signals li {{ font-size: 13px; }}
  code {{ background: #f4f4f4; padding: 2px 4px; border-radius: 4px; }}
  img {{ max-width: 220px; max-height: 160px; border: 1px solid #ccc; margin-top: 8px; }}
  .badge {{ font-size: 11px; padding: 2px 8px; border-radius: 10px; color: #fff; vertical-align: middle; }}
  .badge-likely_bad {{ background: #c0392b; }}
  .badge-review {{ background: #e0a800; }}
  .badge-ok {{ background: #2e7d32; }}
  .badge-unknown {{ background: #777; }}
  .lang {{ color: #34495e; font-weight: 600; }}
  .controls {{ position: sticky; top: 0; background: #fff; padding: 10px 0; border-bottom: 1px solid #eee;
              display: flex; gap: 1rem; flex-wrap: wrap; align-items: center; z-index: 5; }}
  select, input {{ padding: 4px; }}
</style></head><body>
<h1>Composite Translation Quality Review</h1>
<p class="sub">Review queue driven by the synthesized composite metric (embedding consistency + baseline,
COMET QE, Gemini judge, backtranslation, per-language VLM QA, and oracle QA) &mdash;
replacing the standalone embedding-delta and backtranslation views.
Showing <b>{len(queue)}</b> flagged item-language records of {summary['records_total']} total
(likely_bad {tiers['likely_bad']}, review {tiers['review']}, ok {tiers['ok']}).</p>
<div class="controls">
  <label>Tier <select id="tierFilter"><option value="">all flagged</option><option>likely_bad</option><option>review</option>{'<option>ok</option>' if include_ok else ''}</select></label>
  <label>Language <select id="langFilter"><option value="">all</option>{lang_opts}</select></label>
  <label>Task <select id="taskFilter"><option value="">all</option>{task_opts}</select></label>
  <label>Search <input id="search" type="search" placeholder="item / text"></label>
  <span id="count"></span>
</div>
<div id="cards">
{''.join(cards)}
</div>
<script>
const cards = Array.from(document.querySelectorAll('#cards .item'));
const tierF = document.getElementById('tierFilter');
const langF = document.getElementById('langFilter');
const taskF = document.getElementById('taskFilter');
const search = document.getElementById('search');
const count = document.getElementById('count');
function apply() {{
  const t = tierF.value, l = langF.value, k = taskF.value, q = search.value.toLowerCase();
  let shown = 0;
  cards.forEach(c => {{
    const ok = (!t || c.dataset.tier === t) && (!l || c.dataset.lang === l) &&
               (!k || c.dataset.task === k) && (!q || c.textContent.toLowerCase().includes(q));
    c.style.display = ok ? '' : 'none';
    if (ok) shown++;
  }});
  count.textContent = shown + ' shown';
}}
[tierF, langF, taskF].forEach(e => e.addEventListener('change', apply));
search.addEventListener('input', apply);
apply();
</script>
</body></html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(doc, encoding="utf-8")


def main() -> int:
    args = parse_args()
    out_dir = Path(args.output_dir)
    translations_path = Path(args.translations_csv)
    if translations_path.exists():
        item_index = cq.ItemIndex.from_translations_csv(translations_path)
        print(f"[idmap] translations backbone: {len(item_index.item_meta)} items, "
              f"{sum(len(v) for v in item_index.translations.values())} translation pairs "
              f"({translations_path})")
    else:
        item_index = cq.ItemIndex.from_item_bank(Path(args.item_bank), args.item_bank_source_col)
        print(f"[idmap] item bank entries: {len(item_index.item_meta)} "
              f"(no translations backbone found at {translations_path})")

    adapter_records = gather_records(args, item_index)
    oracle_map = cq.load_oracle_logs(Path(args.oracle_logs))
    if oracle_map:
        print(f"[oracle] (task, keyed) entries: {len(oracle_map)}")

    merged = cq.merge_records(adapter_records, oracle_map=oracle_map, item_index=item_index)
    attach_backtranslation_similarity(merged, Path(args.backtranslation_similarity))
    weights = {**cq.DEFAULT_WEIGHTS, **parse_weight_overrides(args.weight)}
    scored = cq.score_records(merged, weights=weights)
    print(f"[score] composite records: {len(scored)}")

    egma_baseline = cq.load_egma_oracle_baseline(Path(args.oracle_logs), item_index)
    if egma_baseline:
        n = 0
        for r in scored:
            if cq.is_math_task(r.task) and r.item_id in egma_baseline:
                r.oracle_solvable = "yes" if egma_baseline[r.item_id] else "no"
                n += 1
        print(f"[oracle] math solvability baseline attached to {n} records "
              f"({len(egma_baseline)} items)")

    attach_explanations(scored, Path(args.explanations))
    attach_backtranslations(scored, Path(args.backtranslations))
    if not args.no_adjudicate:
        adjudicate(scored, args.adjudicate_target)

    exclude_langs = {cq.normalize_lang_code(l) for l in str(args.exclude_langs).split(",") if l.strip()}
    if exclude_langs:
        before = len(scored)
        scored = [r for r in scored if cq.normalize_lang_code(r.target_lang) not in exclude_langs]
        dropped = before - len(scored)
        if dropped:
            print(f"[clean] dropped {dropped} records in excluded langs {sorted(exclude_langs)} "
                  f"(English reference variants, not translations)")

    if not args.keep_textless:
        before = len(scored)
        scored = [r for r in scored if (r.source_text or "").strip() or (r.target_text or "").strip()]
        dropped = before - len(scored)
        if dropped:
            print(f"[clean] dropped {dropped} textless records (no source and no translation)")

    out_csv = out_dir / args.out_csv
    out_json = out_dir / args.out_json
    out_html = out_dir / args.out_html
    out_dashboard = out_dir / args.out_dashboard
    write_csv(scored, out_csv)
    write_json(scored, out_json)
    write_html(scored, out_html, Path(args.screenshot_dir))
    write_dashboard(scored, out_dashboard, Path(args.screenshot_dir),
                    include_ok=args.dashboard_include_ok)
    if args.out_web_json:
        shot_dirs = [Path(d.strip()) for d in str(args.screenshot_dirs).split(",") if d.strip()]
        vocab_dirs = [Path(d.strip()) for d in str(args.vocab_image_dirs).split(",") if d.strip()]
        attach_screenshots(scored, shot_dirs, Path(args.out_web_json), vocab_dirs=vocab_dirs,
                           artifact_path=Path(args.screenshot_artifact))
        write_web_json(scored, Path(args.out_web_json))
        print(f"  WEB JSON : {args.out_web_json}")

    summary = cq.summarize(scored)
    tiers = summary["flag_tiers"]
    print(f"[done] tiers: likely_bad={tiers['likely_bad']} review={tiers['review']} "
          f"ok={tiers['ok']} unknown={tiers['unknown']}")
    print(f"  CSV      : {out_csv}")
    print(f"  JSON     : {out_json}")
    print(f"  HTML     : {out_html}")
    print(f"  DASHBOARD: {out_dashboard}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
