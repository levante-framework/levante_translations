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
        assert "identifier,language,score,errors_json,notes,template_used,human_review,screenshot_names" in output_text
        assert "yes" in output_text
    return True


def test_prompt_updates_include_construct_context() -> bool:
    math_item = evaluator.EvaluationItem(
        identifier="math_instruct",
        labels="math",
        source="What is 1.5 plus 2?",
        target_lang="fr-CA",
        hypothesis="Combien font 1,5 plus 2?",
        template_key=evaluator.select_template("math", "math_instruct"),
    )
    math_prompt = evaluator.build_prompt(math_item)
    assert "LEVANTE project (Learning Variability Network Exchange)" in math_prompt
    assert "RESIDUAL issues" in math_prompt
    assert "ages 5–12 (or 2–4 for downward extension items)" in math_prompt
    assert "standard notation for the target locale" in math_prompt

    same_different_item = evaluator.EvaluationItem(
        identifier="same_trial_1",
        labels="same-different-selection",
        source="Find one that is the same in a different way.",
        target_lang="nl",
        hypothesis="Vind er een die op een andere manier hetzelfde is.",
        template_key=evaluator.select_template("same-different-selection", "same_trial_1"),
    )
    same_different_prompt = evaluator.build_prompt(same_different_item)
    assert "same in a different way" in same_different_prompt
    assert "single-dimension match" in same_different_prompt
    return True


def test_screenshot_prompt_and_image_part() -> bool:
    with tempfile.TemporaryDirectory() as tmpdir:
        image_path = Path(tmpdir) / "item.png"
        image_path.write_bytes(b"not-a-real-png-but-encoded-for-request-shape")
        item = evaluator.EvaluationItem(
            identifier="vocab-item-001",
            labels="vocab",
            source="the apple",
            target_lang="nl",
            hypothesis="de appel",
            template_key=evaluator.select_template("vocab", "vocab-item-001"),
            screenshots=[
                evaluator.ScreenshotAttachment(
                    path=image_path,
                    screenshot_id=123,
                    name="vocab-item-001.png",
                    position={"x": 1, "y": 2, "width": 3, "height": 4},
                )
            ],
        )
        prompt = evaluator.build_prompt(item)
        assert "Crowdin screenshot context is attached as image input" in prompt
        row = evaluator.result_row(item, {"score": 5, "errors": [], "notes": "ok"})
        assert row["screenshot_names"] == "vocab-item-001.png"
        part = evaluator.image_part(image_path)
        assert part["inlineData"]["mimeType"] == "image/png"
        assert part["inlineData"]["data"]
    return True


def test_backtranslation_with_screenshot_support() -> bool:
    with tempfile.TemporaryDirectory() as tmpdir:
        image_path = Path(tmpdir) / "item.png"
        image_path.write_bytes(b"fake-image")
        item = evaluator.EvaluationItem(
            identifier="vocab-item-002",
            labels="vocab",
            source="the sink",
            target_lang="nl",
            hypothesis="de gootsteen",
            template_key=evaluator.select_template("vocab", "vocab-item-002"),
            screenshots=[
                evaluator.ScreenshotAttachment(
                    path=image_path,
                    screenshot_id=55,
                    name="vocab-item-002.png",
                    position=None,
                )
            ],
        )
        prompt = evaluator.build_backtranslation_prompt(item)
        assert "Crowdin screenshot context is attached as image input" in prompt

        parsed = evaluator.parse_backtranslation_evaluation(
            '{"backtranslation":"the kitchen sink","score":2,"severity":"major","notes":"context mismatch"}'
        )
        assert parsed["backtranslation"] == "the kitchen sink"
        assert parsed["score"] == 2
        assert parsed["severity"] == "major"
    return True


def test_survey_prompt_audience_context() -> bool:
    caregiver_item = evaluator.EvaluationItem(
        identifier="main/xliff-out/parent_survey_family/file.xliff::q1",
        labels="survey",
        source="How often do you read with your child?",
        target_lang="nl",
        hypothesis="Hoe vaak leest u met uw kind?",
        template_key=evaluator.select_template("survey", "q1"),
    )
    caregiver_prompt = evaluator.build_prompt(caregiver_item)
    assert "CAREGIVER survey" in caregiver_prompt
    assert "ADULT respondent" in caregiver_prompt

    teacher_item = evaluator.EvaluationItem(
        identifier="main/xliff-out/teacher_survey_classroom/file.xliff::q2",
        labels="survey",
        source="How often does this child participate in class discussions?",
        target_lang="nl",
        hypothesis="Hoe vaak neemt dit kind deel aan klassikale discussies?",
        template_key=evaluator.select_template("survey", "q2"),
    )
    teacher_prompt = evaluator.build_prompt(teacher_item)
    assert "TEACHER survey" in teacher_prompt
    return True


def main() -> int:
    try:
        test_template_selection()
        test_load_items_and_write_results()
        test_prompt_updates_include_construct_context()
        test_screenshot_prompt_and_image_part()
        test_backtranslation_with_screenshot_support()
        test_survey_prompt_audience_context()
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
