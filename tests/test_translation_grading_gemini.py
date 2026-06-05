#!/usr/bin/env python3
"""
Live Gemini smoke test for translation_grading/pipeline.py.

This test calls the real Gemini judge stage on a tiny in-memory fixture so we
can verify end-to-end behavior of the new grading path.
"""

import os
import sys
from pathlib import Path
from types import SimpleNamespace

# Add repo root to import path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from translation_grading import pipeline


def _read_key_from_dotenv(repo_root: Path) -> str:
    env_path = repo_root / ".env"
    if not env_path.exists():
        return ""
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "GEMINI_API_KEY":
            return value.strip().strip('"').strip("'")
    return ""


def _resolve_gemini_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key
    repo_root = Path(__file__).resolve().parent.parent
    return _read_key_from_dotenv(repo_root).strip()


def test_translation_grading_gemini_live() -> bool:
    """
    Runs the LLM-judge stage on one flagged row.

    We keep this tiny (max 1 call) to make it fast and cheap while still
    validating the real Gemini integration path.
    """
    gemini_key = _resolve_gemini_key()
    if not gemini_key:
        raise AssertionError("GEMINI_API_KEY not found in environment or .env")

    # Ensure pipeline reads the key from the configured env var.
    os.environ["GEMINI_API_KEY"] = gemini_key

    rows = [
        pipeline.RowTranslation(
            item_id="gemini-test-good",
            row_index=2,
            source_text="The student solved the puzzle quickly.",
            target_lang="es-CO",
            target_text="El estudiante resolvio el rompecabezas rapidamente.",
        ),
        pipeline.RowTranslation(
            item_id="gemini-test-flagged",
            row_index=3,
            source_text="Please count the circles in the image.",
            target_lang="es-CO",
            target_text="El cielo es azul y la manana es tranquila.",
            needs_review=True,
            review_reasons=["seeded_for_llm_test"],
        ),
    ]

    args = SimpleNamespace(
        run_llm_judge=True,
        gemini_api_key_env="GEMINI_API_KEY",
        gemini_model="gemini-2.5-pro",
        gemini_threshold=75.0,
        llm_only_flagged=True,
        llm_max_calls=1,
    )

    pipeline.run_llm_judge_stage(rows, args)

    judged_rows = [r for r in rows if isinstance(r.metadata.get("llm"), dict)]
    assert len(judged_rows) == 1, f"Expected exactly one judged row, got {len(judged_rows)}"
    judged = judged_rows[0]
    assert judged.item_id == "gemini-test-flagged", "Expected only flagged row to be judged"

    llm_payload = judged.metadata["llm"]
    assert isinstance(llm_payload, dict), "Gemini payload must be a JSON object"
    assert "final_score" in llm_payload, "Gemini response missing final_score"
    assert "severity" in llm_payload, "Gemini response missing severity"
    assert "llm_final" in judged.scores, "Pipeline did not record llm_final score"

    print("Judged row:", judged.item_id)
    print("LLM final score:", judged.scores.get("llm_final"))
    print("LLM severity:", llm_payload.get("severity"))
    print("Review reasons:", sorted(set(judged.review_reasons)))
    return True


def main() -> int:
    print("Running translation grading Gemini live smoke test...")
    try:
        ok = test_translation_grading_gemini_live()
    except AssertionError as exc:
        print(f"FAIL: {exc}")
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1
    if ok:
        print("PASS: translation grading Gemini live smoke test")
        return 0
    print("FAIL: unknown test failure")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
