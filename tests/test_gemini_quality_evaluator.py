#!/usr/bin/env python3
"""Non-network smoke tests for the task-aware Gemini quality evaluator."""

import csv
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from translation_grading import gemini_quality_evaluator as evaluator


def test_template_selection() -> bool:
    cases = [
        ("general", "next", "FEEDBACK_TRANSITION"),
        ("hearts-and-flowers", "instruct", "INSTRUCTION_SPATIAL_EXACT"),
        ("same-different-selection", "same_instruct_1", "INSTRUCTION_GENERAL"),
        ("same-different-selection", "same_trial_1", "SPATIAL_RELATIONAL"),
        ("trog", "trog_prompt_1", "INSTRUCTION_GENERAL"),
        ("trog", "trog_item_1", "OBJECT_NAMING_GRAMMAR"),
        ("theory-of-mind", "happy", "OBJECT_NAMING"),
        ("theory-of-mind", "tom_intro", "INSTRUCTION_GENERAL"),
        ("theory-of-mind", "false_belief_q", "AMBIGUOUS_COMPREHENSION"),
        ("hostile-attribution", "story_instruct1", "INSTRUCTION_NARRATIVE_AMBIGUOUS"),
        ("hostile-attribution", "story_q1", "AMBIGUOUS_COMPREHENSION"),
        ("hostile-attribution", "story_q2", "INSTRUCTION_GENERAL"),
        ("survey", "school_q", "SURVEY"),
    ]
    for label, identifier, expected in cases:
        actual = evaluator.select_template(label, identifier)
        assert actual == expected, f"{label}/{identifier}: expected {expected}, got {actual}"
    return True


def test_load_items_and_write_results() -> bool:
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "complete_translations.csv"
        output_path = Path(tmpdir) / "translation_quality_results.csv"
        with input_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["identifier", "labels", "en", "es-CO", "de", "fr-CA", "nl", "context"])
            writer.writeheader()
            writer.writerow(
                {
                    "identifier": "happy",
                    "labels": "theory-of-mind",
                    "en": "happy",
                    "es-CO": "feliz",
                    "de": "gluecklich",
                    "fr-CA": "content",
                    "nl": "blij",
                    "context": "",
                }
            )
            writer.writerow(
                {
                    "identifier": "story_q1",
                    "labels": "hostile-attribution",
                    "en": "Why did she do that?",
                    "es-CO": "Por que hizo eso?",
                    "de": "Warum hat sie das gemacht?",
                    "fr-CA": "Pourquoi elle a fait ca?",
                    "nl": "Waarom deed ze dat?",
                    "context": "",
                }
            )

        items = evaluator.load_items(input_path, "en", ["es-CO", "de"], 0)
        assert len(items) == 4
        assert items[0].template_key == "OBJECT_NAMING"
        assert items[-1].template_key == "AMBIGUOUS_COMPREHENSION"

        rows = [
            evaluator.result_row(items[0], {"score": 5, "errors": [], "notes": "ok"}),
            evaluator.result_row(
                items[-1],
                {"score": 3, "errors": [{"severity": "critical", "description": "resolved ambiguity"}], "notes": "review"},
            ),
        ]
        evaluator.write_results(output_path, rows)
        output_text = output_path.read_text(encoding="utf-8")
        assert "identifier,language,score,errors_json,notes,template_used,human_review" in output_text
        assert "yes" in output_text
    return True


def main() -> int:
    try:
        test_template_selection()
        test_load_items_and_write_results()
    except AssertionError as exc:
        print(f"FAIL: {exc}")
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1
    print("PASS: Gemini quality evaluator smoke tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
