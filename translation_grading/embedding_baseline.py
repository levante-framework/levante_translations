#!/usr/bin/env python3
"""
Persistent embedding baseline + outlier detection for translation monitoring.

Two workflows:
1) Build/update baseline embeddings from a CSV.
2) Detect outliers for a new CSV by comparing against the baseline.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

import numpy as np


DEFAULT_MODEL = "sentence-transformers/LaBSE"


@dataclass
class Pair:
    item_id: str
    source_text: str
    target_lang: str
    target_text: str
    source_path: str = ""


def parse_csv_list(raw: str) -> List[str]:
    return [x.strip() for x in str(raw or "").split(",") if x.strip()]


def normalize_text(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def text_hash(value: str) -> str:
    return hashlib.sha256(normalize_text(value).encode("utf-8")).hexdigest()


def auto_target_cols(fieldnames: Iterable[str], source_col: str, id_col: str, ignore_cols: Sequence[str]) -> List[str]:
    ignored = {source_col, id_col, *ignore_cols}
    ignored = {x for x in ignored if x}
    out: List[str] = []
    for name in fieldnames:
        n = str(name or "").strip()
        if not n or n in ignored or n.startswith("_"):
            continue
        if len(n) >= 2 and n[0].isalpha() and any(ch == "-" for ch in n) or n.isalpha():
            out.append(n)
    return out


def load_pairs_from_csv(
    csv_path: Path,
    item_id_col: str,
    source_col: str,
    target_cols_raw: str,
    ignore_cols_raw: str,
) -> List[Pair]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return []
    fieldnames = list(rows[0].keys())
    target_cols = parse_csv_list(target_cols_raw) or auto_target_cols(
        fieldnames=fieldnames,
        source_col=source_col,
        id_col=item_id_col,
        ignore_cols=parse_csv_list(ignore_cols_raw) + ["labels", "context", "task", "_path"],
    )
    pairs: List[Pair] = []
    for idx, row in enumerate(rows, start=2):
        item_id = normalize_text(row.get(item_id_col, "")) or f"row-{idx}"
        source_text = normalize_text(row.get(source_col, ""))
        source_path = normalize_text(row.get("_path", ""))
        if not source_text:
            continue
        for lang in target_cols:
            target_text = normalize_text(row.get(lang, ""))
            if not target_text:
                continue
            pairs.append(
                Pair(
                    item_id=item_id,
                    source_text=source_text,
                    target_lang=lang,
                    target_text=target_text,
                    source_path=source_path,
                )
            )
    return pairs


def maybe_prefix_e5(model_name: str, texts: Sequence[str], prefix: str) -> List[str]:
    if "e5" not in str(model_name or "").lower():
        return list(texts)
    return [f"{prefix}: {text}" for text in texts]


def load_model(model_name: str, device: str):
    from sentence_transformers import SentenceTransformer

    resolved_device = None if device == "auto" else device
    return SentenceTransformer(model_name, device=resolved_device)


def encode_texts(model, model_name: str, texts: Sequence[str], batch_size: int, prefix: str) -> np.ndarray:
    inputs = maybe_prefix_e5(model_name, texts, prefix)
    emb = model.encode(
        inputs,
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    return np.asarray(emb, dtype=np.float32)


def cosine(u: np.ndarray, v: np.ndarray) -> float:
    denom = float(np.linalg.norm(u) * np.linalg.norm(v))
    if denom == 0.0:
        return 0.0
    return float(np.dot(u, v) / denom)


def save_baseline(
    path: Path,
    model_name: str,
    source_csv: str,
    pairs: Sequence[Pair],
    embeddings: np.ndarray,
) -> None:
    payload = {
        "model_name": model_name,
        "source_csv": source_csv,
        "size": len(pairs),
    }
    np.savez_compressed(
        str(path),
        embeddings=np.asarray(embeddings, dtype=np.float32),
        item_id=np.array([p.item_id for p in pairs], dtype=object),
        target_lang=np.array([p.target_lang for p in pairs], dtype=object),
        target_text=np.array([p.target_text for p in pairs], dtype=object),
        text_hash=np.array([text_hash(p.target_text) for p in pairs], dtype=object),
        source_text=np.array([p.source_text for p in pairs], dtype=object),
        source_path=np.array([p.source_path for p in pairs], dtype=object),
        meta=np.array([json.dumps(payload)], dtype=object),
    )


def load_baseline(path: Path) -> Dict[str, np.ndarray]:
    data = np.load(str(path), allow_pickle=True)
    return {
        "embeddings": np.asarray(data["embeddings"], dtype=np.float32),
        "item_id": np.asarray(data["item_id"], dtype=object),
        "target_lang": np.asarray(data["target_lang"], dtype=object),
        "target_text": np.asarray(data["target_text"], dtype=object),
        "text_hash": np.asarray(data["text_hash"], dtype=object),
        "source_text": np.asarray(data["source_text"], dtype=object),
        "source_path": np.asarray(data["source_path"], dtype=object),
        "meta": np.asarray(data["meta"], dtype=object),
    }


def build_index(values: Sequence[str]) -> Dict[str, List[int]]:
    idx: Dict[str, List[int]] = {}
    for i, value in enumerate(values):
        idx.setdefault(str(value), []).append(i)
    return idx


def cmd_build(args: argparse.Namespace) -> int:
    csv_path = Path(args.input_csv).expanduser()
    pairs = load_pairs_from_csv(
        csv_path=csv_path,
        item_id_col=args.item_id_col,
        source_col=args.source_col,
        target_cols_raw=args.target_cols,
        ignore_cols_raw=args.ignore_cols,
    )
    if not pairs:
        print("No source-target pairs found.")
        return 1
    model = load_model(args.embedding_model, args.embedding_device)
    emb = encode_texts(
        model=model,
        model_name=args.embedding_model,
        texts=[p.target_text for p in pairs],
        batch_size=args.embedding_batch_size,
        prefix="passage",
    )
    out_path = Path(args.baseline_out).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    save_baseline(out_path, args.embedding_model, str(csv_path), pairs, emb)
    print(f"Baseline saved: {out_path}")
    print(f"Rows: {len(pairs)}")
    return 0


def cmd_detect(args: argparse.Namespace) -> int:
    baseline_path = Path(args.baseline).expanduser()
    baseline = load_baseline(baseline_path)
    baseline_emb = baseline["embeddings"]
    baseline_item_id = baseline["item_id"].astype(str)
    baseline_target_lang = baseline["target_lang"].astype(str)

    pairs = load_pairs_from_csv(
        csv_path=Path(args.input_csv).expanduser(),
        item_id_col=args.item_id_col,
        source_col=args.source_col,
        target_cols_raw=args.target_cols,
        ignore_cols_raw=args.ignore_cols,
    )
    if not pairs:
        print("No source-target pairs found.")
        return 1

    model = load_model(args.embedding_model, args.embedding_device)
    cand_emb = encode_texts(
        model=model,
        model_name=args.embedding_model,
        texts=[p.target_text for p in pairs],
        batch_size=args.embedding_batch_size,
        prefix="passage",
    )

    by_item = build_index(baseline_item_id)
    by_item_lang = build_index([f"{iid}|{lang}" for iid, lang in zip(baseline_item_id, baseline_target_lang)])
    by_lang = build_index(baseline_target_lang)

    out_rows: List[dict] = []
    flagged = 0
    for i, pair in enumerate(pairs):
        vec = cand_emb[i]
        key_item = pair.item_id
        key_item_lang = f"{pair.item_id}|{pair.target_lang}"
        same_item_idx = by_item.get(key_item, [])
        same_item_lang_idx = by_item_lang.get(key_item_lang, [])
        same_lang_idx = by_lang.get(pair.target_lang, [])

        same_item_centroid_sim = None
        same_item_lang_max_sim = None
        lang_centroid_sim = None

        if same_item_idx:
            centroid = np.mean(baseline_emb[same_item_idx], axis=0)
            same_item_centroid_sim = cosine(vec, centroid)
        if same_item_lang_idx:
            sims = [cosine(vec, baseline_emb[j]) for j in same_item_lang_idx]
            same_item_lang_max_sim = max(sims) if sims else None
        if same_lang_idx:
            lang_centroid = np.mean(baseline_emb[same_lang_idx], axis=0)
            lang_centroid_sim = cosine(vec, lang_centroid)

        reasons: List[str] = []
        if (
            args.item_centroid_threshold > 0
            and same_item_centroid_sim is not None
            and same_item_centroid_sim < args.item_centroid_threshold
        ):
            reasons.append(f"item_centroid<{args.item_centroid_threshold:.2f}")
        if (
            args.item_lang_threshold > 0
            and same_item_lang_max_sim is not None
            and same_item_lang_max_sim < args.item_lang_threshold
        ):
            reasons.append(f"item_lang<{args.item_lang_threshold:.2f}")
        if (
            args.lang_centroid_threshold > 0
            and lang_centroid_sim is not None
            and lang_centroid_sim < args.lang_centroid_threshold
        ):
            reasons.append(f"lang_centroid<{args.lang_centroid_threshold:.2f}")
        is_outlier = bool(reasons)
        if is_outlier:
            flagged += 1

        out_rows.append(
            {
                "item_id": pair.item_id,
                "target_lang": pair.target_lang,
                "source_text": pair.source_text,
                "target_text": pair.target_text,
                "same_item_centroid_sim": "" if same_item_centroid_sim is None else f"{same_item_centroid_sim:.6f}",
                "same_item_lang_max_sim": "" if same_item_lang_max_sim is None else f"{same_item_lang_max_sim:.6f}",
                "lang_centroid_sim": "" if lang_centroid_sim is None else f"{lang_centroid_sim:.6f}",
                "is_outlier": "yes" if is_outlier else "no",
                "outlier_reasons": ";".join(reasons),
            }
        )

    out_csv = Path(args.output_csv).expanduser()
    out_json = Path(args.summary_json).expanduser()
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)

    fields = list(out_rows[0].keys()) if out_rows else []
    with out_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out_rows)

    summary = {
        "baseline": str(baseline_path),
        "rows_total": len(out_rows),
        "rows_flagged": flagged,
        "flag_rate": round((flagged / len(out_rows)) if out_rows else 0.0, 4),
        "thresholds": {
            "item_centroid_threshold": args.item_centroid_threshold,
            "item_lang_threshold": args.item_lang_threshold,
            "lang_centroid_threshold": args.lang_centroid_threshold,
        },
    }
    out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Outlier report CSV: {out_csv}")
    print(f"Summary JSON: {out_json}")
    print(f"Flagged: {flagged} / {len(out_rows)} ({(100 * flagged / max(1, len(out_rows))):.1f}%)")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Persistent embedding baseline workflow.")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="Build and save baseline embeddings.")
    build.add_argument("--input-csv", required=True)
    build.add_argument("--item-id-col", default="item_id")
    build.add_argument("--source-col", default="en")
    build.add_argument("--target-cols", default="")
    build.add_argument("--ignore-cols", default="")
    build.add_argument("--embedding-model", default=DEFAULT_MODEL)
    build.add_argument("--embedding-device", default="auto", choices=["auto", "cpu", "cuda"])
    build.add_argument("--embedding-batch-size", type=int, default=128)
    build.add_argument("--baseline-out", default="translation_grading/output/embedding_baseline.npz")

    detect = sub.add_parser("detect", help="Compare a new CSV against a baseline.")
    detect.add_argument("--baseline", default="translation_grading/output/embedding_baseline.npz")
    detect.add_argument("--input-csv", required=True)
    detect.add_argument("--item-id-col", default="item_id")
    detect.add_argument("--source-col", default="en")
    detect.add_argument("--target-cols", default="")
    detect.add_argument("--ignore-cols", default="")
    detect.add_argument("--embedding-model", default=DEFAULT_MODEL)
    detect.add_argument("--embedding-device", default="auto", choices=["auto", "cpu", "cuda"])
    detect.add_argument("--embedding-batch-size", type=int, default=128)
    detect.add_argument("--item-centroid-threshold", type=float, default=0.78)
    detect.add_argument("--item-lang-threshold", type=float, default=0.82)
    detect.add_argument(
        "--lang-centroid-threshold",
        type=float,
        default=0.0,
        help="Set >0 to enable language-centroid filtering (0 disables).",
    )
    detect.add_argument("--output-csv", default="translation_grading/output/embedding_outlier_report.csv")
    detect.add_argument("--summary-json", default="translation_grading/output/embedding_outlier_summary.json")

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "build":
        return cmd_build(args)
    if args.command == "detect":
        return cmd_detect(args)
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
