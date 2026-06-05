#!/usr/bin/env python3
"""
Smoke test for translation_grading/pipeline.py.

This test uses a tiny synthetic CSV so it can run quickly without external APIs
or heavyweight ML model downloads.
"""

import csv
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

# Add repo root to import path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from translation_grading import pipeline


def make_args(input_csv: str, output_dir: str) -> SimpleNamespace:
    """Build a minimal args object compatible with pipeline helpers."""
    return SimpleNamespace(
        input_mode="csv",
        input_csv=input_csv,
        crowdin_zip="",
        crowdin_project_id="756721",
        dashboard_base_url="https://levante-cockpit.vercel.app",
        item_id_col="item_id",
        source_col="en",
        target_cols="de,es-CO",
        ignore_cols="",
        ambiguity_col="",
        max_pairs=0,
        strip_html=False,
        embedding_model="sentence-transformers/LaBSE",
        embedding_device="auto",
        embedding_batch_size=8,
        consistency_threshold=0.78,
        run_comet=False,
        comet_model="Unbabel/wmt22-cometkiwi-da",
        comet_batch_size=8,
        comet_threshold=0.62,
        run_llm_judge=False,
        gemini_api_key_env="GEMINI_API_KEY",
        gemini_model="gemini-2.5-pro",
        gemini_threshold=75.0,
        llm_only_flagged=False,
        llm_max_calls=0,
        output_csv=str(Path(output_dir) / "translation-grading-report.csv"),
        summary_json=str(Path(output_dir) / "translation-grading-summary.json"),
        report_md=str(Path(output_dir) / "translation-grading-flag-report.md"),
    )


def write_fixture_csv(path: str) -> None:
    """Create a small fixture with two items and two target languages."""
    rows = [
        {
            "item_id": "item-1",
            "en": "The child reads a short story.",
            "de": "Das Kind liest eine kurze Geschichte.",
            "es-CO": "El nino lee una historia corta.",
        },
        {
            "item_id": "item-2",
            "en": "Count the circles in the image.",
            "de": "Zaehle die Kreise im Bild.",
            "es-CO": "Cuenta los circulos en la imagen.",
        },
    ]
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["item_id", "en", "de", "es-CO"])
        writer.writeheader()
        writer.writerows(rows)


def test_translation_grading_pipeline_smoke() -> bool:
    """
    End-to-end smoke test over core pipeline helpers.

    We manually attach consistency scores to avoid model downloads while still
    validating the flagging and output/report behavior.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "fixture.csv"
        write_fixture_csv(str(csv_path))

        args = make_args(str(csv_path), tmpdir)
        pairs, target_cols = pipeline.materialize_pairs(args)

        # 2 items * 2 languages = 4 source-target pairs
        assert len(pairs) == 4, f"Expected 4 pairs, got {len(pairs)}"
        assert target_cols == ["de", "es-CO"], f"Unexpected target columns: {target_cols}"

        # Simulate grading outcomes: one low consistency score should be flagged
        scripted_scores = [0.93, 0.91, 0.74, 0.88]
        for row, score in zip(pairs, scripted_scores):
            row.scores["consistency"] = score
            if score < args.consistency_threshold:
                row.needs_review = True
                row.review_reasons.append(f"consistency<{args.consistency_threshold:.2f}")

        summary = pipeline.summarize(pairs)
        assert summary["rows_total"] == 4
        assert summary["rows_flagged"] == 1
        assert summary["by_language"]["de"]["total"] == 2
        assert summary["by_language"]["es-CO"]["total"] == 2

        pipeline.write_outputs(pairs, args)

        csv_out = Path(args.output_csv)
        json_out = Path(args.summary_json)
        md_out = Path(args.report_md)
        assert csv_out.exists(), f"Missing output CSV: {csv_out}"
        assert json_out.exists(), f"Missing summary JSON: {json_out}"
        assert md_out.exists(), f"Missing markdown report: {md_out}"

        csv_text = csv_out.read_text(encoding="utf-8")
        assert "consistency_score" in csv_text
        assert "yes" in csv_text  # one row flagged

        md_text = md_out.read_text(encoding="utf-8")
        assert "Translation Grading Flag Report" in md_text
        assert "consistency<0.78" in md_text

    return True


def main() -> int:
    print("Running translation grading smoke test...")
    try:
        ok = test_translation_grading_pipeline_smoke()
    except AssertionError as exc:
        print(f"FAIL: {exc}")
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1
    if ok:
        print("PASS: translation grading pipeline smoke test")
        return 0
    print("FAIL: unknown test failure")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
