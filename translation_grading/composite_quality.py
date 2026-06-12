#!/usr/bin/env python3
"""Composite translation quality scoring engine and signal adapters.

This module fuses every available translation quality signal into a single
per-``(item_id, target_lang)`` composite score plus a confidence estimate and a
flag tier. It is deliberately dependency-light (stdlib only) so the fusion layer
can run anywhere the cached artifacts live, even without the heavy embedding /
COMET / Gemini stacks installed.

Signal families fused (each normalized to a 0..1 "quality" direction):
  - embedding_consistency : LaBSE target-centroid cosine (pipeline.py)
  - embedding_baseline    : persistent .npz item / item-lang centroid sims
  - comet                 : reference-free QE (COMET-Kiwi / xCOMET)
  - gemini_judge          : Gemini direct 1-5 score + MQM severity
  - backtranslation       : Gemini round-trip 1-5 score + severity
  - vlm                   : per-language VLM QA correctness + cross-lang outlier
  - oracle                : deterministic oracle QA agent correctness

The signals live in two identifier namespaces:
  * Crowdin ``item_id``           -> embeddings, COMET, Gemini, backtranslation
  * behavioral answer-key items   -> VLM, oracle
For the vocab task the two are bridged via the English source text. For stories
(theory-of-mind) and trog the behavioral items are keyed by ordinal and kept in
a synthetic ``<task>::<ordinal>`` id namespace; this is recorded per record via
``join_status`` so downstream consumers know coverage is partial.
"""

from __future__ import annotations

import csv
import json
import math
import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


# --------------------------------------------------------------------------- #
# Signal configuration
# --------------------------------------------------------------------------- #

# Default fusion weights. Behavioral ground truth (oracle, VLM) is trusted most,
# cheap embedding priors least. All weights are configurable via score_records().
DEFAULT_WEIGHTS: Dict[str, float] = {
    "embedding_consistency": 0.5,
    "embedding_baseline": 0.5,
    "comet": 1.0,
    "backtranslation": 1.5,
    "backtranslation_embed": 1.5,
    "gemini_judge": 2.0,
    "vlm": 3.0,
    "oracle": 4.0,
}

SIGNAL_FAMILIES: Tuple[str, ...] = tuple(DEFAULT_WEIGHTS.keys())

# Calibration anchors reused from the existing per-stage thresholds so the
# composite stays comparable with the legacy single-signal gates.
CALIBRATION = {
    "embedding_consistency": {"center": 0.78, "slope": 14.0},
    "embedding_baseline_item": {"center": 0.78, "slope": 14.0},
    "embedding_baseline_item_lang": {"center": 0.82, "slope": 14.0},
    "comet": {"center": 0.62, "slope": 10.0},
    # Round-trip: cosine between the English source and the Gemini back-translation
    # (both English). Faithful translations round-trip high; meaning drift is low.
    "backtranslation_embed": {"center": 0.70, "slope": 15.0},
}

# Flag-tier bands on the composite quality score.
TIER_OK_MIN = 0.72
TIER_REVIEW_MIN = 0.50

# A single present signal below this quality forces at least a "review".
SINGLE_SIGNAL_REVIEW_FLOOR = 0.35

SEVERITY_QUALITY = {"none": 1.0, "minor": 0.75, "major": 0.4, "critical": 0.0}

# Tasks where the VLM / oracle QA agent is NOT a valid solver: the question has
# no objective visual answer (mental-state inference, social attribution, or
# self-report). For these, a VLM "incorrect" / cross-language outlier reflects
# the agent's inability to answer a subjective prompt, not a translation defect,
# so the behavioral signal is neutralized and never drives a flag.
VLM_INVALID_TASKS = {
    "theory-of-mind",
    "hostile-attribution",
    "survey",
    "child-survey",
}


def vlm_valid_for_task(task: object) -> bool:
    return str(task or "").strip().lower() not in VLM_INVALID_TASKS


# Math tasks have objective numeric answers; used for locale number-format rules.
MATH_TASKS = {"math", "egma-math", "egma"}


def is_math_task(task: object) -> bool:
    return str(task or "").strip().lower() in MATH_TASKS


# Spanish number words (accent-stripped). In es-CO, math number prompts are
# sometimes written with commas *between number words* as a spoken-pronunciation
# aid (e.g. "doscientos, cuarenta y cinco"); those commas are intentional and
# must not be penalized. Commas elsewhere (after a verb/article) are real errors.
_ES_NUMBER_WORDS = {
    "cero", "un", "uno", "una", "dos", "tres", "cuatro", "cinco", "seis", "siete",
    "ocho", "nueve", "diez", "once", "doce", "trece", "catorce", "quince",
    "dieciseis", "diecisiete", "dieciocho", "diecinueve", "veinte", "veintiuno",
    "veintidos", "veintitres", "veinticuatro", "veinticinco", "veintiseis",
    "veintisiete", "veintiocho", "veintinueve", "treinta", "cuarenta", "cincuenta",
    "sesenta", "setenta", "ochenta", "noventa", "cien", "ciento", "cientos",
    "doscientos", "trescientos", "cuatrocientos", "quinientos", "seiscientos",
    "setecientos", "ochocientos", "novecientos", "mil", "millon", "millones", "y",
}


def _strip_accents(text: str) -> str:
    table = str.maketrans("áéíóúüñ", "aeiouun")
    return text.lower().translate(table)


def _is_es_number_word(token: str) -> bool:
    return _strip_accents(token).strip() in _ES_NUMBER_WORDS


def es_comma_number_status(text: str) -> str:
    """Classify the commas in a Spanish string.

    Returns ``"none"`` (no commas), ``"all_number"`` (every comma sits between
    two Spanish number words -> intentional pronunciation aid), or ``"mixed"``
    (at least one comma is not number-internal -> a real formatting error)."""
    parts = re.findall(r"[0-9A-Za-zÀ-ÿ]+|,", str(text or ""))
    commas = [i for i, p in enumerate(parts) if p == ","]
    if not commas:
        return "none"
    for i in commas:
        prev = parts[i - 1] if i - 1 >= 0 else ""
        nxt = parts[i + 1] if i + 1 < len(parts) else ""
        if not (_is_es_number_word(prev) and _is_es_number_word(nxt)):
            return "mixed"
    return "all_number"


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def logistic_quality(value: float, center: float, slope: float) -> float:
    return clamp01(_sigmoid(slope * (value - center)))


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def to_float(value: object) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.lower() in {"na", "nan", "none", "null"}:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def normalize_lang_code(value: str) -> str:
    raw = str(value or "").strip().replace("_", "-")
    if not raw:
        return ""
    aliases = {
        "de-de": "de",
        "nl-nl": "nl",
        "en-us": "en-US",
        "en-gb": "en-GB",
        "en-gh": "en-GH",
        "es-co": "es-CO",
        "es-ar": "es-AR",
        "fr-ca": "fr-CA",
        "pt-br": "pt-BR",
        "pt-pt": "pt-PT",
        "de-ch": "de-CH",
    }
    return aliases.get(raw.lower(), raw)


_SPACE_RE = re.compile(r"\s+")
_ARTICLE_RE = re.compile(r"^(the|a|an)\s+", re.IGNORECASE)


def normalize_text_key(value: str) -> str:
    text = _SPACE_RE.sub(" ", str(value or "").strip().lower())
    text = _ARTICLE_RE.sub("", text)
    return text.strip()


def truthy_correct(value: object) -> Optional[bool]:
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "correct"}:
        return True
    if text in {"0", "false", "no", "n", "incorrect", "wrong"}:
        return False
    f = to_float(text)
    if f is None:
        return None
    return f >= 0.5


# --------------------------------------------------------------------------- #
# Adapter record model
# --------------------------------------------------------------------------- #

@dataclass
class AdapterRecord:
    """A single signal observation contributed by one adapter."""

    item_id: str
    target_lang: str
    signal: str
    raw: Optional[float] = None
    task: str = ""
    source_text: str = ""
    target_text: str = ""
    detail: Dict[str, object] = field(default_factory=dict)
    keyed_value: str = ""  # behavioral answer key, used to bridge oracle <-> vlm


# --------------------------------------------------------------------------- #
# Identifier reconciliation
# --------------------------------------------------------------------------- #

class ItemIndex:
    """Bridges English source text / answer keys to canonical Crowdin item ids."""

    def __init__(self) -> None:
        self.item_meta: Dict[str, Dict[str, str]] = {}
        self._en_to_id: Dict[str, str] = {}
        # item_id -> {normalized_lang: translation_text}
        self.translations: Dict[str, Dict[str, str]] = {}

    @classmethod
    def from_translations_csv(cls, csv_path: Path, source_col: str = "en",
                              id_col: str = "identifier", label_col: str = "labels",
                              non_lang_cols: Optional[Sequence[str]] = None) -> "ItemIndex":
        """Build the index from the wide complete-translations export.

        This is the authoritative backbone: it supplies task labels, the English
        source, and per-language target text for every item-language pair so the
        fused records never show a blank source or translation."""
        index = cls()
        path = Path(csv_path)
        if not path.exists():
            return index
        skip = {id_col, "item_id", label_col, source_col, *(non_lang_cols or ())}
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            cols = reader.fieldnames or []
            lang_cols = [c for c in cols if c not in skip]
            for row in reader:
                item_id = str(row.get(id_col, "") or row.get("item_id", "") or "").strip()
                if not item_id:
                    continue
                task = str(row.get(label_col, "") or "").strip()
                en_text = str(row.get(source_col, "") or "").strip()
                index.item_meta[item_id] = {"task": task, "en_text": en_text}
                key = normalize_text_key(en_text)
                if key and key not in index._en_to_id:
                    index._en_to_id[key] = item_id
                lang_map: Dict[str, str] = {}
                for col in lang_cols:
                    val = str(row.get(col, "") or "").strip()
                    if val:
                        lang_map[normalize_lang_code(col)] = val
                if lang_map:
                    index.translations[item_id] = lang_map
        return index

    @classmethod
    def from_item_bank(cls, csv_path: Path, source_col: str = "en-US") -> "ItemIndex":
        index = cls()
        path = Path(csv_path)
        if not path.exists():
            return index
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            cols = reader.fieldnames or []
            if source_col not in cols:
                source_col = next((c for c in cols if c.lower() in {"en-us", "en"}), source_col)
            for row in reader:
                item_id = str(row.get("item_id", "") or "").strip()
                if not item_id:
                    continue
                task = str(row.get("task", "") or row.get("labels", "") or "").strip()
                en_text = str(row.get(source_col, "") or "").strip()
                index.item_meta[item_id] = {"task": task, "en_text": en_text}
                key = normalize_text_key(en_text)
                if key and key not in index._en_to_id:
                    index._en_to_id[key] = item_id
        return index

    def resolve_english(self, english_text: str) -> Optional[str]:
        return self._en_to_id.get(normalize_text_key(english_text))

    def task_for(self, item_id: str) -> str:
        return self.item_meta.get(item_id, {}).get("task", "")

    def source_for(self, item_id: str) -> str:
        return self.item_meta.get(item_id, {}).get("en_text", "")

    def translation_for(self, item_id: str, lang: str) -> str:
        return self.translations.get(item_id, {}).get(normalize_lang_code(lang), "")


# --------------------------------------------------------------------------- #
# Signal adapters (graceful absence: every adapter returns [] if input missing)
# --------------------------------------------------------------------------- #

def _read_csv(path: Path) -> List[dict]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_grading_report(path: Path) -> List[AdapterRecord]:
    """Embedding consistency + baseline + (optionally) COMET/Gemini from the
    pipeline.py CSV report when it has already been produced."""
    out: List[AdapterRecord] = []
    for row in _read_csv(path):
        item_id = str(row.get("item_id", "") or "").strip()
        lang = normalize_lang_code(row.get("target_lang", ""))
        if not item_id or not lang:
            continue
        source_text = str(row.get("source_text", "") or "")
        target_text = str(row.get("target_text", "") or "")
        consistency = to_float(row.get("consistency_score"))
        if consistency is not None:
            out.append(AdapterRecord(item_id, lang, "embedding_consistency", consistency,
                                     source_text=source_text, target_text=target_text))
        item_centroid = to_float(row.get("baseline_item_centroid_score"))
        item_lang = to_float(row.get("baseline_item_lang_max_score"))
        if item_centroid is not None or item_lang is not None:
            out.append(AdapterRecord(item_id, lang, "embedding_baseline", None,
                                     source_text=source_text, target_text=target_text,
                                     detail={"item_centroid": item_centroid, "item_lang_max": item_lang}))
        comet = to_float(row.get("comet_score"))
        if comet is not None:
            out.append(AdapterRecord(item_id, lang, "comet", comet,
                                     source_text=source_text, target_text=target_text))
        llm = to_float(row.get("llm_final_score"))
        if llm is not None:
            # pipeline emits final_score on a 0-100 scale; convert to shared 1-5.
            out.append(AdapterRecord(item_id, lang, "gemini_judge", _scale_llm_100(llm),
                                     source_text=source_text, target_text=target_text,
                                     detail={"severity": str(row.get("llm_severity", "") or "").lower(),
                                             "scale": "1-5"}))
    return out


def _scale_llm_100(value: float) -> float:
    # Convert a 0-100 pipeline score to the shared 1-5 raw scale used elsewhere.
    return 1.0 + clamp01(value / 100.0) * 4.0


def load_embedding_records(rows: Sequence["object"]) -> List[AdapterRecord]:
    """Convert in-memory pipeline RowTranslation objects (live embedding run)
    into adapter records. Accepts duck-typed objects exposing item_id,
    target_lang, source_text, target_text, scores, metadata."""
    out: List[AdapterRecord] = []
    for row in rows:
        item_id = str(getattr(row, "item_id", "") or "").strip()
        lang = normalize_lang_code(getattr(row, "target_lang", ""))
        if not item_id or not lang:
            continue
        scores = getattr(row, "scores", {}) or {}
        meta = getattr(row, "metadata", {}) or {}
        source_text = str(getattr(row, "source_text", "") or "")
        target_text = str(getattr(row, "target_text", "") or "")
        task = str(meta.get("labels", "") or "")
        if "consistency" in scores:
            out.append(AdapterRecord(item_id, lang, "embedding_consistency", float(scores["consistency"]),
                                     task=task, source_text=source_text, target_text=target_text))
        item_centroid = scores.get("baseline_item_centroid")
        item_lang = scores.get("baseline_item_lang_max")
        if item_centroid is not None or item_lang is not None:
            out.append(AdapterRecord(item_id, lang, "embedding_baseline", None, task=task,
                                     source_text=source_text, target_text=target_text,
                                     detail={"item_centroid": item_centroid, "item_lang_max": item_lang}))
        if "comet" in scores:
            out.append(AdapterRecord(item_id, lang, "comet", float(scores["comet"]), task=task,
                                     source_text=source_text, target_text=target_text))
    return out


def load_comet_dir(comet_output_dir: Path) -> List[AdapterRecord]:
    """Reference-free QE from xcomet/output/<lang>/segment_scores.csv."""
    out: List[AdapterRecord] = []
    base = Path(comet_output_dir)
    if not base.exists():
        return out
    for lang_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        lang = normalize_lang_code(lang_dir.name)
        if lang.lower() == "labels":
            continue
        for row in _read_csv(lang_dir / "segment_scores.csv"):
            item_id = str(row.get("item_id", "") or "").strip()
            score = to_float(row.get("score"))
            if not item_id or score is None:
                continue
            out.append(AdapterRecord(item_id, lang, "comet", score,
                                     source_text=str(row.get("source", "") or ""),
                                     target_text=str(row.get("translation", "") or "")))
    return out


def load_gemini_results(path: Path) -> List[AdapterRecord]:
    """Gemini direct judge from gemini_quality_evaluator output
    (columns: identifier, language, score [1-5], errors_json, ...)."""
    out: List[AdapterRecord] = []
    for row in _read_csv(path):
        item_id = str(row.get("identifier", "") or row.get("item_id", "") or "").strip()
        lang = normalize_lang_code(row.get("language", ""))
        score = to_float(row.get("score"))
        if not item_id or not lang or score is None:
            continue
        severity = _max_severity_from_errors(row.get("errors_json", ""))
        out.append(AdapterRecord(item_id, lang, "gemini_judge", score,
                                 detail={"severity": severity, "scale": "1-5",
                                         "notes": str(row.get("notes", "") or "")}))
    return out


def _max_severity_from_errors(errors_json: str) -> str:
    order = {"none": 0, "minor": 1, "major": 2, "critical": 3}
    worst = "none"
    try:
        errors = json.loads(errors_json or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        return worst
    if not isinstance(errors, list):
        return worst
    for err in errors:
        if not isinstance(err, dict):
            continue
        sev = str(err.get("severity", "") or "").strip().lower()
        if order.get(sev, 0) > order.get(worst, 0):
            worst = sev
    return worst


def load_nl_auto_review(path: Path) -> List[AdapterRecord]:
    """Gemini judge + backtranslation from the NL all-tasks auto-review CSV.

    The NL workflow stored its hypotheses in language columns and the Gemini /
    backtranslation verdicts for the Dutch (nl) column only."""
    out: List[AdapterRecord] = []
    for row in _read_csv(path):
        # Prefer the bare identifier so NL rows share the item_id namespace used
        # by COMET / VLM / item bank (item_id here is path-prefixed, e.g.
        # "main/...stories.xliff::ToM-scene-10-q1").
        item_id = str(row.get("identifier", "") or row.get("item_id", "") or "").strip()
        if "::" in item_id:
            item_id = item_id.split("::", 1)[-1]
        if not item_id:
            continue
        task = str(row.get("task_label", "") or "")
        source_text = str(row.get("en", "") or "")
        target_text = str(row.get("nl", "") or "")
        gemini_score = to_float(row.get("gemini_score"))
        if gemini_score is not None:
            out.append(AdapterRecord(item_id, "nl", "gemini_judge", gemini_score, task=task,
                                     source_text=source_text, target_text=target_text,
                                     detail={"severity": str(row.get("gemini_severity", "") or "").lower(),
                                             "scale": "1-5", "notes": str(row.get("gemini_notes", "") or "")}))
        bt_score = to_float(row.get("backtranslation_score"))
        if bt_score is not None:
            out.append(AdapterRecord(item_id, "nl", "backtranslation", bt_score, task=task,
                                     source_text=source_text, target_text=target_text,
                                     detail={"severity": str(row.get("backtranslation_severity", "") or "").lower(),
                                             "scale": "1-5",
                                             "backtranslation": str(row.get("backtranslation", "") or "")}))
    return out


# VLM matrices: per task the item-key column and namespace differ.
_VLM_TASK_CONFIG = {
    "vocab": {"key_col": "item_key", "task": "vocab", "english_col": "english_reference"},
    "stories": {"key_col": "question_ordinal", "task": "theory-of-mind", "english_col": None},
    "trog": {"key_col": "item_ordinal", "task": "trog", "english_col": None},
}


def load_vlm_task(task: str, matrix_path: Path, outliers_path: Path,
                  item_index: ItemIndex) -> List[AdapterRecord]:
    cfg = _VLM_TASK_CONFIG.get(task)
    if cfg is None:
        return []
    matrix_rows = _read_csv(matrix_path)
    if not matrix_rows:
        return []
    key_col = cfg["key_col"]
    english_col = cfg["english_col"]
    fieldnames = list(matrix_rows[0].keys())
    langs = sorted({m.group(1) for col in fieldnames
                    if (m := re.match(r"(.+)_correct$", col))})

    # Pre-index the outlier file: (lang, key) -> outlier score.
    outlier_by_key: Dict[Tuple[str, str], dict] = {}
    for row in _read_csv(outliers_path):
        lang = normalize_lang_code(row.get("language", ""))
        okey = str(row.get("item") or row.get("question_ordinal") or row.get("item_ordinal") or "").strip()
        if not lang or not okey:
            continue
        outlier_by_key[(lang, okey)] = {
            "other_correct": to_float(row.get("other_correct")),
            "other_total": to_float(row.get("other_total")),
            "score": to_float(row.get("score")),
        }

    out: List[AdapterRecord] = []
    for row in matrix_rows:
        raw_key = str(row.get(key_col, "") or "").strip()
        if not raw_key:
            continue
        english_ref = str(row.get(english_col, "") or "") if english_col else ""
        # Fall back to the English prompt column so behavioral-only items (stories,
        # trog) that lack an english_reference still carry a source string.
        if not english_ref:
            english_ref = (str(row.get("en-US_prompt", "") or "").strip()
                           or str(row.get("en-GB_prompt", "") or "").strip())
        item_id, join_status = _resolve_vlm_item(task, raw_key, english_ref, item_index)
        # English baseline solvability for this item. The VLM "incorrect" signal
        # only implicates the *translation* when the simulated child could solve
        # the item in English; if it fails in English too (or there is no English
        # baseline), a wrong answer reflects item/VLM difficulty, not translation.
        baseline_correct = truthy_correct(row.get("en-US_correct"))
        if baseline_correct is None:
            baseline_correct = truthy_correct(row.get("en-GB_correct"))
        for lang_raw in langs:
            lang = normalize_lang_code(lang_raw)
            correct = truthy_correct(row.get(f"{lang_raw}_correct"))
            if correct is None:
                continue
            keyed = str(row.get(f"{lang_raw}_keyed", "") or "").strip()
            chosen = str(row.get(f"{lang_raw}_chosen", "") or "").strip()
            prompt = str(row.get(f"{lang_raw}_prompt", "") or "").strip()
            outlier = outlier_by_key.get((lang, raw_key))
            is_outlier = bool(outlier) and correct is False
            out.append(AdapterRecord(
                item_id, lang, "vlm", 1.0 if correct else 0.0, task=cfg["task"],
                source_text=english_ref, target_text=prompt, keyed_value=keyed,
                detail={
                    "vlm_correct": int(correct),
                    "vlm_lang_outlier": is_outlier,
                    "vlm_baseline_correct": baseline_correct,
                    "outlier_score": (outlier or {}).get("score"),
                    "chosen": chosen, "keyed": keyed, "prompt": prompt,
                    "join_status": join_status, "vlm_item_key": raw_key,
                },
            ))
    return out


def _resolve_vlm_item(task: str, raw_key: str, english_ref: str,
                      item_index: ItemIndex) -> Tuple[str, str]:
    if task == "vocab":
        resolved = item_index.resolve_english(english_ref) or item_index.resolve_english(raw_key)
        if resolved:
            return resolved, "matched"
        return f"vocab::{raw_key}", "synthetic"
    # stories / trog are keyed by ordinal, but the matrix now carries the English
    # prompt; bridge to the Crowdin item_id via the English source so the
    # behavioral signal merges with the text-based signals (Gemini/COMET/embedding)
    # instead of stranding the item in a synthetic-ordinal namespace. Fall back to
    # the ordinal namespace only when no source match exists.
    cfg = _VLM_TASK_CONFIG[task]
    resolved = item_index.resolve_english(english_ref) if english_ref else None
    if resolved:
        return resolved, "matched"
    return f"{cfg['task']}::ord{raw_key}", "synthetic-ordinal"


def load_egma_oracle_baseline(logs_dir: Path, item_index: "ItemIndex") -> Dict[str, bool]:
    """Math (egma) deterministic-oracle solvability baseline.

    The egma oracle is a deterministic solver (it reads the answer from task
    state, ~100% correct) so it is NOT a translation-quality signal; it confirms
    an item is mechanically solvable. Records are keyed by English ``promptText``
    only, so we bridge to the Crowdin item id via the translations backbone.
    Returns ``item_id -> solvable`` for math items."""
    out: Dict[str, bool] = {}
    base = Path(logs_dir)
    if not base.exists() or item_index is None:
        return out
    paths = list(base.glob("*egma*oracle*.jsonl")) + list(base.glob("_egma_oracle*.jsonl"))
    for log_path in sorted(set(paths)):
        try:
            text = log_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(rec, dict) or str(rec.get("task", "")).lower() != "egma-math":
                continue
            correct = rec.get("correct")
            if not isinstance(correct, bool):
                continue
            item_id = item_index.resolve_english(str(rec.get("promptText", "") or ""))
            if not item_id:
                continue
            out[item_id] = out.get(item_id, True) and correct
    return out


def load_oracle_logs(logs_dir: Path) -> Dict[Tuple[str, str], bool]:
    """Best-effort deterministic oracle ground truth.

    Oracle runs are single-language (source-text driven) and keyed by the answer
    key, not by item_id or target language. We therefore build a
    ``(task, normalized_keyed_value) -> correct`` map that is later applied as a
    task-solvability prior to every language of an item whose behavioral answer
    key matches (resolved through the VLM ``keyed`` value)."""
    out: Dict[Tuple[str, str], bool] = {}
    base = Path(logs_dir)
    if not base.exists():
        return out
    for log_path in sorted(base.glob("*oracle*.jsonl")):
        try:
            text = log_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(rec, dict) or rec.get("itemType") != "item":
                continue
            correct = rec.get("correct")
            if not isinstance(correct, bool):
                continue
            task = str(rec.get("task", "") or "").strip().lower()
            keyed = normalize_text_key(rec.get("keyedValue") or rec.get("keyedIndex") or "")
            if not task or not keyed:
                continue
            # Latest record wins; oracle is deterministic so this is idempotent.
            out[(task, keyed)] = correct
    return out


# --------------------------------------------------------------------------- #
# Fusion engine
# --------------------------------------------------------------------------- #

@dataclass
class CompositeRecord:
    item_id: str
    target_lang: str
    task: str = ""
    source_text: str = ""
    target_text: str = ""
    signals: Dict[str, dict] = field(default_factory=dict)
    quality_score: Optional[float] = None
    confidence: float = 0.0
    coverage: float = 0.0
    agreement: float = 0.0
    flag_tier: str = "unknown"
    reasons: List[str] = field(default_factory=list)
    join_status: str = ""
    explanation: str = ""
    suggested_fix: str = ""
    flag_confidence: str = ""
    verdict: str = ""
    screenshot: str = ""
    oracle_solvable: str = ""
    back_translation: str = ""


def _calibrate(family: str, raw: Optional[float], detail: Dict[str, object]) -> Optional[float]:
    """Map a raw signal to a 0..1 quality value. Returns None if not derivable."""
    if family == "embedding_consistency":
        if raw is None:
            return None
        cal = CALIBRATION["embedding_consistency"]
        return logistic_quality(raw, cal["center"], cal["slope"])
    if family == "embedding_baseline":
        parts: List[float] = []
        ic = to_float(detail.get("item_centroid"))
        il = to_float(detail.get("item_lang_max"))
        if ic is not None:
            cal = CALIBRATION["embedding_baseline_item"]
            parts.append(logistic_quality(ic, cal["center"], cal["slope"]))
        if il is not None:
            cal = CALIBRATION["embedding_baseline_item_lang"]
            parts.append(logistic_quality(il, cal["center"], cal["slope"]))
        return sum(parts) / len(parts) if parts else None
    if family == "comet":
        if raw is None:
            return None
        cal = CALIBRATION["comet"]
        return logistic_quality(raw, cal["center"], cal["slope"])
    if family == "backtranslation_embed":
        if raw is None:
            return None
        cal = CALIBRATION["backtranslation_embed"]
        return logistic_quality(raw, cal["center"], cal["slope"])
    if family in {"gemini_judge", "backtranslation"}:
        if raw is None:
            return None
        scale = str(detail.get("scale", "1-5"))
        if scale == "0-100":
            base = clamp01(raw / 100.0)
        else:
            base = clamp01((raw - 1.0) / 4.0)
        severity = str(detail.get("severity", "") or "none").strip().lower()
        if severity in SEVERITY_QUALITY:
            # Blend rubric score with severity-implied quality (severity dominates).
            base = min(base, 0.5 * base + 0.5 * SEVERITY_QUALITY[severity])
        return clamp01(base)
    if family == "vlm":
        if raw is None:
            return None
        # The VLM is not a valid solver for subjective / non-visual tasks.
        if not vlm_valid_for_task(detail.get("_task")):
            return None
        # Neutralize an "incorrect" VLM answer unless it is translation-relevant:
        # the item must be solvable in English (baseline correct) or the failure
        # must be a cross-language outlier. Otherwise it reflects item difficulty.
        if raw <= 0.0 and detail.get("vlm_baseline_correct") is not True \
                and not detail.get("vlm_lang_outlier"):
            return None
        return clamp01(raw)
    if family == "oracle":
        if raw is None:
            return None
        # The oracle QA agent shares the VLM's premise; invalid for the same tasks.
        if not vlm_valid_for_task(detail.get("_task")):
            return None
        return clamp01(raw)
    return None


def merge_records(adapter_records: Iterable[AdapterRecord],
                  oracle_map: Optional[Dict[Tuple[str, str], bool]] = None,
                  item_index: Optional[ItemIndex] = None) -> List[CompositeRecord]:
    grouped: Dict[Tuple[str, str], CompositeRecord] = {}
    for rec in adapter_records:
        key = (rec.item_id, rec.target_lang)
        comp = grouped.get(key)
        if comp is None:
            comp = CompositeRecord(item_id=rec.item_id, target_lang=rec.target_lang)
            grouped[key] = comp
        if rec.task and not comp.task:
            comp.task = rec.task
        if rec.source_text and not comp.source_text:
            comp.source_text = rec.source_text
        if rec.target_text and not comp.target_text:
            comp.target_text = rec.target_text
        payload = {"raw": rec.raw, "detail": dict(rec.detail)}
        if rec.keyed_value:
            payload["keyed_value"] = rec.keyed_value
        # If the family already exists, keep the most informative (prefer one
        # with a non-null raw / richer detail).
        existing = comp.signals.get(rec.signal)
        if existing is None or (existing.get("raw") is None and rec.raw is not None):
            comp.signals[rec.signal] = payload
        else:
            existing["detail"].update(payload["detail"])

    # The translations backbone (Crowdin approved export) is authoritative for the
    # displayed source / target text: it is the exact string the Gemini judge
    # evaluated. Other adapters (e.g. COMET) may carry a normalized digit variant
    # that disagrees with the judged string, which would make a legitimate flag
    # look like a false positive on the card. Prefer the backbone string when it
    # exists; fall back to adapter text otherwise.
    if item_index is not None:
        for comp in grouped.values():
            if not comp.task:
                comp.task = item_index.task_for(comp.item_id)
            bb_source = item_index.source_for(comp.item_id)
            if bb_source:
                comp.source_text = bb_source
            bb_target = item_index.translation_for(comp.item_id, comp.target_lang)
            if bb_target:
                comp.target_text = bb_target

    # Apply oracle as a task-solvability prior via each record's VLM keyed value.
    if oracle_map:
        for comp in grouped.values():
            if "oracle" in comp.signals:
                continue
            vlm = comp.signals.get("vlm")
            keyed = ""
            if vlm:
                keyed = str(vlm.get("keyed_value") or vlm.get("detail", {}).get("keyed") or "")
            keyed_norm = normalize_text_key(keyed)
            task = str(comp.task or "").strip().lower()
            # theory-of-mind logs use task "theory-of-mind"; stories config maps to it.
            oracle_correct = None
            for candidate_task in {task, task.replace("theory-of-mind", "theory-of-mind")}:
                if (candidate_task, keyed_norm) in oracle_map:
                    oracle_correct = oracle_map[(candidate_task, keyed_norm)]
                    break
            if oracle_correct is not None:
                comp.signals["oracle"] = {"raw": 1.0 if oracle_correct else 0.0,
                                          "detail": {"oracle_correct": int(oracle_correct),
                                                     "source": "task-key-prior"}}

    return list(grouped.values())


def score_records(records: Sequence[CompositeRecord],
                  weights: Optional[Dict[str, float]] = None) -> List[CompositeRecord]:
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    for comp in records:
        rule_notes = _apply_locale_number_rules(comp)
        qualities: Dict[str, float] = {}
        weighted_sum = 0.0
        weight_total = 0.0
        for family in SIGNAL_FAMILIES:
            payload = comp.signals.get(family)
            if not payload:
                continue
            detail = payload.setdefault("detail", {})
            detail["_task"] = comp.task
            quality = _calibrate(family, payload.get("raw"), detail)
            if quality is None:
                continue
            payload["quality"] = round(quality, 4)
            payload["weight"] = weights.get(family, 0.0)
            qualities[family] = quality
            weighted_sum += weights.get(family, 0.0) * quality
            weight_total += weights.get(family, 0.0)

        if weight_total > 0:
            comp.quality_score = round(weighted_sum / weight_total, 4)
        else:
            comp.quality_score = None

        present = list(qualities.values())
        comp.coverage = round(min(1.0, len(present) / 3.0), 4)
        if len(present) >= 2:
            comp.agreement = round(clamp01(1.0 - 2.0 * statistics.pstdev(present)), 4)
        elif len(present) == 1:
            comp.agreement = 0.5
        else:
            comp.agreement = 0.0
        comp.confidence = round(comp.coverage * comp.agreement, 4)

        comp.flag_tier, comp.reasons = _decide_tier(comp, qualities)
        comp.reasons.extend(rule_notes)
        comp.join_status = _join_status(comp)
    return list(records)


def _apply_locale_number_rules(comp: "CompositeRecord") -> List[str]:
    """Locale-specific number-format normalization applied before scoring.

    es-CO math: a Gemini penalty driven solely by commas placed *between number
    words* is a false positive (those commas are an intentional spoken-number
    pronunciation aid). When every comma in the translation is number-internal,
    drop the Gemini signal so it no longer drags the score; commas placed
    elsewhere (e.g. "Escoge, el, 66") are left flagged."""
    notes: List[str] = []
    if normalize_lang_code(comp.target_lang) == "es-CO" and is_math_task(comp.task):
        if "gemini_judge" in comp.signals and es_comma_number_status(comp.target_text) == "all_number":
            comp.signals.pop("gemini_judge", None)
            notes.append("es-CO:number-comma-ignored")
    return notes


def _decide_tier(comp: CompositeRecord, qualities: Dict[str, float]) -> Tuple[str, List[str]]:
    reasons: List[str] = []
    score = comp.quality_score

    # Hard overrides -> likely_bad.
    gem = comp.signals.get("gemini_judge", {}).get("detail", {})
    if str(gem.get("severity", "")).lower() == "critical":
        reasons.append("gemini:critical")
    bt = comp.signals.get("backtranslation", {}).get("detail", {})
    if str(bt.get("severity", "")).lower() == "critical":
        reasons.append("backtranslation:critical")
    task_vlm_valid = vlm_valid_for_task(comp.task)
    vlm = comp.signals.get("vlm", {}).get("detail", {})
    vlm_informative = (vlm.get("vlm_baseline_correct") is True) or bool(vlm.get("vlm_lang_outlier"))
    if task_vlm_valid and vlm.get("vlm_lang_outlier"):
        reasons.append("vlm:cross_lang_outlier")
    elif task_vlm_valid and vlm.get("vlm_correct") == 0 and vlm_informative:
        reasons.append("vlm:incorrect")
    oracle = comp.signals.get("oracle", {}).get("detail", {})
    if task_vlm_valid and oracle.get("oracle_correct") == 0:
        reasons.append("oracle:incorrect")

    if score is None:
        return "unknown", reasons or ["no_signals"]

    # Behavioral ground truth (cross-language VLM outlier / oracle incorrect) is
    # always a hard fail. An LLM "critical" (Gemini or backtranslation) only
    # forces likely_bad when corroborated; a lone, uncorroborated LLM critical
    # is routed to human review instead of being auto-condemned to a flat 0.
    behavioral_bad = ("vlm:cross_lang_outlier" in reasons) or ("oracle:incorrect" in reasons)
    llm_crit = int("gemini:critical" in reasons) + int("backtranslation:critical" in reasons)
    other_low = any(q < TIER_REVIEW_MIN for fam, q in qualities.items()
                    if fam not in {"gemini_judge", "backtranslation"})
    corroborated = behavioral_bad or llm_crit >= 2 or other_low

    if behavioral_bad or (llm_crit >= 1 and corroborated):
        return "likely_bad", reasons
    if llm_crit >= 1:
        reasons.append("uncorroborated_critical")
        return "review", reasons

    # Score-band tier.
    if score >= TIER_OK_MIN:
        tier = "ok"
    elif score >= TIER_REVIEW_MIN:
        tier = "review"
    else:
        tier = "likely_bad"

    # Single weak signal floor.
    low = [f for f, q in qualities.items() if q < SINGLE_SIGNAL_REVIEW_FLOOR]
    if low and tier == "ok":
        tier = "review"
        reasons.append("weak_signal:" + ",".join(sorted(low)))
    elif low:
        reasons.append("weak_signal:" + ",".join(sorted(low)))

    if tier != "ok" and not reasons:
        reasons.append(f"score={score:.2f}")
    return tier, reasons


def _join_status(comp: CompositeRecord) -> str:
    statuses = {
        str(payload.get("detail", {}).get("join_status", ""))
        for payload in comp.signals.values()
        if payload.get("detail", {}).get("join_status")
    }
    statuses.discard("")
    if not statuses:
        return "id"
    if "synthetic-ordinal" in statuses or "synthetic" in statuses:
        return "behavioral-only" if comp.item_id.split("::")[0] in {"vocab", "trog", "theory-of-mind"} else "mixed"
    return "matched"


# --------------------------------------------------------------------------- #
# Rollups
# --------------------------------------------------------------------------- #

def _dist(values: Sequence[float]) -> Dict[str, float]:
    vals = [v for v in values if v is not None]
    if not vals:
        return {"count": 0}
    vals_sorted = sorted(vals)
    return {
        "count": len(vals),
        "mean": round(statistics.mean(vals), 4),
        "median": round(statistics.median(vals), 4),
        "min": round(min(vals), 4),
        "max": round(max(vals), 4),
        "p10": round(vals_sorted[max(0, int(0.10 * (len(vals) - 1)))], 4),
        "p90": round(vals_sorted[min(len(vals) - 1, int(0.90 * (len(vals) - 1)))], 4),
    }


def summarize(records: Sequence[CompositeRecord]) -> Dict[str, object]:
    tiers = {"ok": 0, "review": 0, "likely_bad": 0, "unknown": 0}
    by_language: Dict[str, Dict[str, int]] = {}
    by_task: Dict[str, Dict[str, int]] = {}
    signal_coverage: Dict[str, int] = {fam: 0 for fam in SIGNAL_FAMILIES}
    scores: List[float] = []

    for comp in records:
        tiers[comp.flag_tier] = tiers.get(comp.flag_tier, 0) + 1
        if comp.quality_score is not None:
            scores.append(comp.quality_score)
        lang_bucket = by_language.setdefault(comp.target_lang, {"total": 0, "review": 0, "likely_bad": 0})
        lang_bucket["total"] += 1
        if comp.flag_tier in {"review", "likely_bad"}:
            lang_bucket[comp.flag_tier] += 1
        task_bucket = by_task.setdefault(comp.task or "unknown", {"total": 0, "review": 0, "likely_bad": 0})
        task_bucket["total"] += 1
        if comp.flag_tier in {"review", "likely_bad"}:
            task_bucket[comp.flag_tier] += 1
        for fam in comp.signals:
            if fam in signal_coverage:
                signal_coverage[fam] += 1

    return {
        "records_total": len(records),
        "flag_tiers": tiers,
        "quality_score": _dist(scores),
        "signal_coverage": signal_coverage,
        "by_language": by_language,
        "by_task": by_task,
    }


def record_to_row(comp: CompositeRecord) -> Dict[str, object]:
    def q(name: str) -> str:
        payload = comp.signals.get(name)
        if not payload:
            return ""
        val = payload.get("quality")
        return "" if val is None else f"{val:.4f}"

    def raw(name: str) -> str:
        payload = comp.signals.get(name)
        if not payload or payload.get("raw") is None:
            return ""
        return f"{payload['raw']:.4f}"

    vlm_detail = comp.signals.get("vlm", {}).get("detail", {})
    gem_detail = comp.signals.get("gemini_judge", {}).get("detail", {})
    return {
        "item_id": comp.item_id,
        "target_lang": comp.target_lang,
        "task": comp.task,
        "join_status": comp.join_status,
        "quality_score": "" if comp.quality_score is None else f"{comp.quality_score:.4f}",
        "confidence": f"{comp.confidence:.4f}",
        "coverage": f"{comp.coverage:.4f}",
        "agreement": f"{comp.agreement:.4f}",
        "flag_tier": comp.flag_tier,
        "n_signals": len(comp.signals),
        "embedding_consistency_q": q("embedding_consistency"),
        "embedding_baseline_q": q("embedding_baseline"),
        "comet_q": q("comet"),
        "comet_raw": raw("comet"),
        "gemini_judge_q": q("gemini_judge"),
        "gemini_severity": str(gem_detail.get("severity", "") or ""),
        "backtranslation_q": q("backtranslation"),
        "backtranslation_embed_q": q("backtranslation_embed"),
        "backtranslation_embed_cos": raw("backtranslation_embed"),
        "vlm_q": q("vlm"),
        "vlm_correct": vlm_detail.get("vlm_correct", ""),
        "vlm_lang_outlier": "yes" if vlm_detail.get("vlm_lang_outlier") else "",
        "oracle_q": q("oracle"),
        "reasons": ";".join(comp.reasons),
        "source_text": comp.source_text,
        "target_text": comp.target_text,
        "explanation": comp.explanation,
        "suggested_fix": comp.suggested_fix,
        "flag_confidence": comp.flag_confidence,
        "verdict": comp.verdict,
        "screenshot": comp.screenshot,
        "oracle_solvable": comp.oracle_solvable,
        "back_translation": comp.back_translation,
    }


CSV_FIELDS = list(record_to_row(CompositeRecord("_", "_")).keys())
