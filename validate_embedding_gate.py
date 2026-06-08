import argparse
import io
import random
import re
import sys
import warnings
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

CSV_PATH = "translation_text/item_bank_translations.csv"
CROWDIN_PROJECT_ID = "756721"
CROWDIN_CACHE_ZIP = "translation_grading/output/.embedding-gate-crowdin-approved-cache.zip"
MODEL_NAME = "sentence-transformers/LaBSE"
OUTPUT_CSV = "embedding_gate_validation.csv"
OUTPUT_PNG = "embedding_gate_validation.png"
THRESHOLD_RANGE = np.arange(0.05, 0.60, 0.005)

ID_COL_CANDIDATES = ["identifier", "item_id"]
SOURCE_COL_CANDIDATES = ["en", "en-US"]
PREFERRED_LANG_COLS = ["en", "en-US", "es-CO", "de", "de-DE", "fr-CA", "nl", "es-AR", "ar-IL", "he-IL"]
MISSING_MARKERS = {"", "NO APPROVED TRANSLATION"}
MIN_APPROVED_ROWS = 50


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a multilingual embedding gate using real or corrupted translations.")
    parser.add_argument("--input-source", choices=["crowdin-api", "csv"], default="crowdin-api")
    parser.add_argument("--csv-path", default=CSV_PATH)
    parser.add_argument("--crowdin-project-id", default=CROWDIN_PROJECT_ID)
    parser.add_argument("--crowdin-cache-zip", default=CROWDIN_CACHE_ZIP)
    parser.add_argument("--refresh-crowdin-cache", action="store_true")
    parser.add_argument("--langs", default="en,es-CO,de,fr-CA,nl", help="Comma-separated language columns to require, if available.")
    parser.add_argument("--schema-only", action="store_true")
    return parser.parse_args()


def is_language_col(col: str) -> bool:
    return bool(re.fullmatch(r"[a-z]{2}(?:-[A-Z]{2})?", str(col)))


def csv_list(raw: str) -> list[str]:
    return [part.strip() for part in str(raw or "").split(",") if part.strip()]


def choose_id_col(columns: list[str]) -> str:
    for col in ID_COL_CANDIDATES:
        if col in columns:
            return col
    raise KeyError(f"Missing identifier column. Expected one of: {ID_COL_CANDIDATES}")


def choose_language_cols(df: pd.DataFrame, requested_cols: list[str] | None = None) -> tuple[list[str], list[tuple[str, int]]]:
    language_cols = [col for col in df.columns if is_language_col(col)]
    if requested_cols:
        ordered = [col for col in requested_cols if col in language_cols]
        missing_requested = [col for col in requested_cols if col not in language_cols]
    else:
        ordered = [col for col in PREFERRED_LANG_COLS if col in language_cols]
        missing_requested = []
        ordered += [col for col in language_cols if col not in ordered and col in PREFERRED_LANG_COLS]
    usable = []
    skipped = [(col, 0) for col in missing_requested]
    for col in ordered:
        approved_count = df[col].notna().sum()
        if approved_count >= MIN_APPROVED_ROWS:
            usable.append(col)
        else:
            skipped.append((col, int(approved_count)))
    if len(usable) < 3:
        raise RuntimeError(f"Need at least 3 usable language columns, found {usable}. Skipped: {skipped}")
    return usable, skipped


def choose_source_lang(lang_cols: list[str]) -> str:
    for col in SOURCE_COL_CANDIDATES:
        if col in lang_cols:
            return col
    return lang_cols[0]


def choose_corruptions(lang_cols: list[str], source_lang: str) -> dict[str, str]:
    non_source = [col for col in lang_cols if col != source_lang]
    if len(non_source) < 3:
        raise RuntimeError(f"Need at least 3 non-source language columns for validation, found {non_source}")

    def first_available(candidates: list[str], fallback_index: int) -> str:
        for col in candidates:
            if col in non_source:
                return col
        return non_source[fallback_index]

    swap_lang = first_available(["de", "de-DE"], 0)
    back_lang = first_available(["es-CO", "es-AR"], min(1, len(non_source) - 1))
    shuffle_candidates = [col for col in ["fr-CA", "nl", "pt-BR", "es-AR", "de-DE", "es-CO"] if col in non_source and col not in {swap_lang, back_lang}]
    shuffle_lang = shuffle_candidates[0] if shuffle_candidates else next(col for col in non_source if col not in {swap_lang, back_lang})
    return {"A_SWAP": swap_lang, "B_BACK": back_lang, "C_SHUFFLE": shuffle_lang}


def fetch_crowdin_zip(project_id: str, cache_path: Path, refresh: bool = False) -> bytes:
    if cache_path.exists() and not refresh:
        try:
            with zipfile.ZipFile(cache_path):
                print(f"Using cached Crowdin approved export: {cache_path}")
                return cache_path.read_bytes()
        except zipfile.BadZipFile:
            print(f"Ignoring invalid Crowdin cache file: {cache_path}")
    from translation_grading import pipeline

    payload = pipeline.fetch_crowdin_project_zip(project_id)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(payload)
    print(f"Cached Crowdin approved export: {cache_path}")
    return payload


def infer_lang_from_path(zip_path: str) -> str:
    first = str(zip_path or "").replace("\\", "/").split("/", 1)[0]
    return first if is_language_col(first) else ""


def canonical_path_for_lang_file(zip_path: str, lang: str) -> str:
    prefix = f"{lang}/"
    return zip_path[len(prefix) :] if lang and zip_path.startswith(prefix) else zip_path


def parse_xliff_units(payload: bytes) -> list[tuple[str, str, str]]:
    try:
        root = ET.fromstring(payload)
    except Exception:
        return []
    units = []
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
        if unit_id and (source or target):
            units.append((unit_id, source, target))
    return units


def load_crowdin_dataframe(project_id: str, cache_zip: str, refresh: bool = False) -> pd.DataFrame:
    zip_bytes = fetch_crowdin_zip(project_id, Path(cache_zip), refresh)
    merged: dict[str, dict] = {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for info in zf.infolist():
            name = str(info.filename or "")
            lower = name.lower()
            if info.is_dir() or "/archive/" in lower or not lower.endswith((".xlf", ".xliff")):
                continue
            lang = infer_lang_from_path(name)
            if not lang:
                continue
            canonical_path = canonical_path_for_lang_file(name, lang)
            for unit_id, source, target in parse_xliff_units(zf.read(info)):
                key = f"{canonical_path}::{unit_id}"
                row = merged.setdefault(key, {"item_id": key, "en": source})
                if source and not row.get("en"):
                    row["en"] = source
                if target:
                    row[lang] = target
    return pd.DataFrame(merged.values())


args = parse_args()
if args.input_source == "crowdin-api":
    print("Loading approved translations from Crowdin...")
    df = load_crowdin_dataframe(args.crowdin_project_id, args.crowdin_cache_zip, args.refresh_crowdin_cache)
else:
    print("Loading CSV...")
    df = pd.read_csv(args.csv_path)
id_col = choose_id_col(list(df.columns))
for col in [c for c in df.columns if is_language_col(c)]:
    df[col] = df[col].astype("string").str.strip().replace(list(MISSING_MARKERS), pd.NA)

LANG_COLS, skipped_langs = choose_language_cols(df, csv_list(args.langs))
SOURCE_LANG = choose_source_lang(LANG_COLS)
CORRUPT_LANG = choose_corruptions(LANG_COLS, SOURCE_LANG)

print(f"Identifier column: {id_col}")
print(f"Input source: {args.input_source}")
print(f"Language columns in input: {[c for c in df.columns if is_language_col(c)]}")
print(f"Using language columns: {LANG_COLS}")
if skipped_langs:
    print(f"Skipping sparse/unapproved language columns (<{MIN_APPROVED_ROWS} approved rows): {skipped_langs}")
print(f"Source language for back-translation corruption: {SOURCE_LANG}")
print(f"Corruption language map: {CORRUPT_LANG}")

df = df.dropna(subset=LANG_COLS).reset_index(drop=True)
print(f"Rows after dropping missing translations across usable languages: {len(df)}")
if len(df) < 2:
    raise RuntimeError("Not enough complete rows after filtering to run validation.")
if args.schema_only:
    print("Schema check complete; exiting before loading embedding model.")
    raise SystemExit(0)

from sentence_transformers import SentenceTransformer

print("Loading model...")
model = SentenceTransformer(MODEL_NAME)

print("Encoding all translations...")
embeddings = {}
for lang in LANG_COLS:
    texts = df[lang].astype(str).tolist()
    embeddings[lang] = model.encode(texts, batch_size=64, show_progress_bar=True, normalize_embeddings=True)

emb_matrix = np.stack([embeddings[l] for l in LANG_COLS], axis=1)


def centroid_distances(emb_mat):
    centroid = emb_mat.mean(axis=1, keepdims=True)
    dists = 1 - (emb_mat * centroid).sum(axis=2)
    return dists


baseline_dists = centroid_distances(emb_matrix)
lang_to_idx = {l: i for i, l in enumerate(LANG_COLS)}
results = []


def run_corruption(corruption_type, corrupt_lang, corrupt_fn):
    print(f"Running corruption: {corruption_type} ({corrupt_lang})...")
    corrupt_idx = lang_to_idx[corrupt_lang]
    corrupt_dists_list = []
    candidate_indices = list(range(len(df)))

    for i in range(len(df)):
        corrupted = emb_matrix[i].copy()
        corrupted[corrupt_idx] = corrupt_fn(i, corrupt_lang, candidate_indices)
        centroid = corrupted.mean(axis=0, keepdims=True)
        dists = 1 - (corrupted * centroid).sum(axis=1)
        outlier_idx = np.argmax(dists)
        corrupt_dists_list.append(dists[corrupt_idx])
        hit = int(outlier_idx == corrupt_idx)
        results.append(
            {
                "identifier": df[id_col].iloc[i],
                "corruption": corruption_type,
                "corrupt_lang": corrupt_lang,
                "corrupt_dist": dists[corrupt_idx],
                "baseline_dist": baseline_dists[i, corrupt_idx],
                "outlier_detected": hit,
            }
        )
    return np.array(corrupt_dists_list)


def swap_fn(i, lang, candidate_indices):
    j = random.choice([x for x in candidate_indices if x != i])
    return embeddings[lang][j]


def back_fn(i, lang, candidate_indices):
    return embeddings[SOURCE_LANG][i]


def shuffle_fn(i, lang, candidate_indices):
    text = str(df[lang].iloc[i])
    words = text.split()
    if len(words) > 1:
        random.shuffle(words)
    shuffled = " ".join(words)
    return model.encode([shuffled], normalize_embeddings=True)[0]


corrupt_fns = {"A_SWAP": swap_fn, "B_BACK": back_fn, "C_SHUFFLE": shuffle_fn}
corrupt_dists = {}
for ctype in ["A_SWAP", "B_BACK", "C_SHUFFLE"]:
    corrupt_dists[ctype] = run_corruption(ctype, CORRUPT_LANG[ctype], corrupt_fns[ctype])

results_df = pd.DataFrame(results)
results_df.to_csv(OUTPUT_CSV, index=False)

print("\nOptimal thresholds by F1:")
summary_rows = []
for ctype in ["A_SWAP", "B_BACK", "C_SHUFFLE"]:
    sub = results_df[results_df["corruption"] == ctype]
    best_f1, best_thresh, best_prec, best_rec = 0, 0, 0, 0
    for t in THRESHOLD_RANGE:
        predicted = (sub["corrupt_dist"] > t).astype(int)
        tp = ((predicted == 1) & (sub["outlier_detected"] == 1)).sum()
        fp = ((predicted == 1) & (sub["outlier_detected"] == 0)).sum()
        fn = ((predicted == 0) & (sub["outlier_detected"] == 1)).sum()
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0
        if f1 > best_f1:
            best_f1, best_thresh, best_prec, best_rec = f1, t, prec, rec
    hits = sub["outlier_detected"].sum()
    n = len(sub)
    summary_rows.append(
        {
            "corruption_type": ctype,
            "corrupt_lang": CORRUPT_LANG[ctype],
            "n_tested": n,
            "hits": hits,
            "misses": n - hits,
            "best_threshold": round(best_thresh, 3),
            "precision": round(best_prec, 3),
            "recall": round(best_rec, 3),
            "F1": round(best_f1, 3),
        }
    )
    print(f"  {ctype} ({CORRUPT_LANG[ctype]}): threshold={best_thresh:.3f}  P={best_prec:.3f}  R={best_rec:.3f}  F1={best_f1:.3f}")

summary_df = pd.DataFrame(summary_rows)
print("\nSummary table:")
print(summary_df.to_string(index=False))

recommended_threshold = round(float(np.mean([r["best_threshold"] for r in summary_rows])), 3)
print(f"\nRecommended gate threshold: {recommended_threshold}")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

fig, axes = plt.subplots(1, 3, figsize=(15, 5))
fig.suptitle("Embedding Gate Validation: Baseline vs. Corrupted Cosine Distances", fontsize=13)

colors = {"A_SWAP": "#e05c5c", "B_BACK": "#e09c3a", "C_SHUFFLE": "#5c8de0"}
labels = {
    "A_SWAP": f"A: SWAP (wrong-meaning {CORRUPT_LANG['A_SWAP']})",
    "B_BACK": f"B: BACK ({SOURCE_LANG} as {CORRUPT_LANG['B_BACK']})",
    "C_SHUFFLE": f"C: SHUFFLE (shuffled {CORRUPT_LANG['C_SHUFFLE']})",
}

for ax, ctype in zip(axes, ["A_SWAP", "B_BACK", "C_SHUFFLE"]):
    clang = CORRUPT_LANG[ctype]
    cidx = lang_to_idx[clang]
    base = baseline_dists[:, cidx]
    corr = corrupt_dists[ctype]
    best_t = summary_rows[["A_SWAP", "B_BACK", "C_SHUFFLE"].index(ctype)]["best_threshold"]
    bins = np.linspace(0, max(base.max(), corr.max()) * 1.05, 50)
    ax.hist(base, bins=bins, alpha=0.55, color="#888", label="Baseline", density=True)
    ax.hist(corr, bins=bins, alpha=0.65, color=colors[ctype], label="Corrupted", density=True)
    ax.axvline(best_t, color="black", linestyle="--", linewidth=1.5, label=f"Threshold={best_t:.3f}")
    ax.set_title(labels[ctype], fontsize=10)
    ax.set_xlabel("Cosine distance from centroid")
    ax.set_ylabel("Density")
    ax.legend(fontsize=8)
    f1 = summary_rows[["A_SWAP", "B_BACK", "C_SHUFFLE"].index(ctype)]["F1"]
    ax.text(
        0.97,
        0.97,
        f"F1={f1:.3f}",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=10,
        fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
    )

plt.tight_layout()
plt.savefig(OUTPUT_PNG, dpi=150, bbox_inches="tight")
print(f"\nPlot saved to {OUTPUT_PNG}")
print(f"Full results saved to {OUTPUT_CSV}")
print(f"\nDone. Use threshold={recommended_threshold} in the main evaluator.")
