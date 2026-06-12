#!/usr/bin/env python3
"""Embedding similarity between the English source and the Gemini back-translation.

This turns the (display-only) back-translations produced by ``backtranslate.py``
into a deterministic, cross-language round-trip quality signal: it embeds the
English source and the English back-translation with the same LaBSE model the
pipeline uses and records their cosine similarity. A faithful translation
round-trips to a back-translation that is semantically close to the source; a
meaning drift shows up as a low cosine.

Output: JSON keyed ``item_id\\tlang`` -> cosine similarity (0..1).

Usage (from repo root):
    python translation_grading/backtranslation_similarity.py \
        --report translation_grading/output/composite-quality-report.csv \
        --out translation_grading/output/backtranslation_similarity.json
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path
from typing import Dict, List, Tuple


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report", default="translation_grading/output/composite-quality-report.csv")
    p.add_argument("--out", default="translation_grading/output/backtranslation_similarity.json")
    p.add_argument("--model", default="sentence-transformers/all-MiniLM-L6-v2",
                   help="Both source and back-translation are English, so a small "
                        "English sentence model is sufficient and fast.")
    p.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    p.add_argument("--batch-size", type=int, default=128)
    args = p.parse_args()

    import numpy as np
    from sentence_transformers import SentenceTransformer

    keys: List[Tuple[str, str]] = []
    sources: List[str] = []
    backs: List[str] = []
    with Path(args.report).open("r", encoding="utf-8-sig", newline="") as handle:
        for r in csv.DictReader(handle):
            src = (r.get("source_text") or "").strip()
            bt = (r.get("back_translation") or "").strip()
            if not src or not bt:
                continue
            keys.append((r["item_id"], r["target_lang"]))
            sources.append(src)
            backs.append(bt)

    if not keys:
        print("[bt-sim] no records with both source and back-translation; nothing to do")
        return 0

    device = None if args.device == "auto" else args.device
    model = SentenceTransformer(args.model, device=device)
    src_emb = model.encode(sources, batch_size=args.batch_size, convert_to_numpy=True,
                           normalize_embeddings=True, show_progress_bar=True)
    bt_emb = model.encode(backs, batch_size=args.batch_size, convert_to_numpy=True,
                          normalize_embeddings=True, show_progress_bar=True)
    cos = np.sum(src_emb * bt_emb, axis=1)  # normalized -> dot == cosine

    out: Dict[str, float] = {}
    for (item_id, lang), c in zip(keys, cos):
        out[f"{item_id}\t{lang}"] = round(float(c), 4)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")

    vals = sorted(out.values())
    def pct(q: float) -> float:
        return vals[min(len(vals) - 1, int(q * len(vals)))]
    print(f"[bt-sim] wrote {len(out)} similarities -> {args.out}")
    print(f"[bt-sim] min={vals[0]:.3f} p05={pct(0.05):.3f} p10={pct(0.10):.3f} "
          f"p25={pct(0.25):.3f} median={statistics.median(vals):.3f} "
          f"mean={statistics.mean(vals):.3f} max={vals[-1]:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
