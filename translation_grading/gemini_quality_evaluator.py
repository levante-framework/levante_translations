#!/usr/bin/env python3
"""Task-aware Gemini translation quality evaluator for LEVANTE prompts."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import mimetypes
import os
import re
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


SOURCE_LANG = "English"
DEFAULT_TARGET_LANGS = ["es-CO", "de", "fr-CA", "nl"]
DEFAULT_MODEL = "gemini-2.5-flash"
FALLBACK_MODEL = "gemini-flash-latest"
BATCH_SIZE = 20
CROWDIN_API_BASE = "https://api.crowdin.com/api/v2"
DEFAULT_CROWDIN_PROJECT_ID = "756721"
DEFAULT_SCREENSHOT_TASK_LABELS = [
    "vocab",
    "theory-of-mind",
    "hostile-attribution",
    "matrix-reasoning",
    "mental-rotation",
    "same-different-selection",
]


SYSTEM_PROMPT = """You are an expert translation evaluator for the LEVANTE project (Learning Variability Network Exchange), a multi-site international study measuring cognitive development in children ages 5–12 across language, mathematics, reasoning, executive function, and social cognition. You are evaluating human translations of task strings originally developed in English and professionally translated via: AI pre-translation → professional translator review → native-speaker researcher review. Your role is to catch residual construct-critical errors that earlier review steps may have missed — not to re-do basic QA.

General rules:
- These strings contain NO technical terminology. Evaluate for natural, child-appropriate spoken language only.
- Proper names (people, characters, places) may be translated, transliterated, or kept as-is - all are acceptable.
- Strings are intentionally short and simple because they are spoken, not read by children.
- These prompts are read aloud to children ages 5–12 (or 2–4 for downward extension items).
- For school-age children (5–12), natural sentence complexity and some multi-clause instructions are acceptable.
- Do NOT penalize a translation for being natural and idiomatic rather than word-for-word literal.
- Do NOT penalize a translation for minor structural differences from the source if the meaning is preserved.
- Always use informal/familiar address forms (tu, du, jij/je) - never formal forms (vous, Sie, u).
- Output your evaluation as JSON: {"score": <1-5>, "errors": [{"severity": "minor|major|critical", "description": "..."}], "notes": "..."}

These translations have already been reviewed by a professional translator and a native-speaker researcher. Your role is to catch RESIDUAL issues: subtle meaning shifts, ambiguity collapse, register problems, dialect-specific choices that may not generalize, and construct-critical errors that a general reviewer might miss without task-specific knowledge. Do not flag trivial or obvious issues — focus on errors that could affect child responses or psychometric validity.

Scoring rubric:
5 - Excellent: accurate, natural, age-appropriate, preserves all intended properties
4 - Good: minor wording issues that do not affect child comprehension
3 - Acceptable: noticeable issues but core meaning is preserved
2 - Poor: meaning is partially lost or phrasing is unnatural enough to confuse a child
1 - Unacceptable: critical errors, meaning changed, or ambiguity incorrectly resolved"""


TEMPLATES: Dict[str, str] = {
    "FEEDBACK_TRANSITION": """Source language: {source_lang}
Target language: {target_lang}
Source text: "{source}"
Translation: "{hypothesis}"

This is a short motivational or transitional phrase spoken to a child between tasks.
Evaluate:
1. Does it convey the same emotional tone (encouraging, neutral, celebratory)?
2. Is it age-appropriate and warm in {target_lang}?
3. Is it approximately the same length? (These are timed presentations - very long expansions are a minor error.)
Very minor wording differences are acceptable if tone and meaning are preserved.
Think step by step before giving your score.""",
    "INSTRUCTION_GENERAL": """Source language: {source_lang}
Target language: {target_lang}
Source text: "{source}"
Translation: "{hypothesis}"

This is a task instruction or setup string read aloud to a child.
Evaluate:
1. Is the intended action or concept clearly conveyed?
2. Does it sound natural when spoken aloud to a child in {target_lang}?
3. Are there any omissions or additions that change what the child is being asked to do?
Think step by step before giving your score.""",
    "INSTRUCTION_SPATIAL_EXACT": """Source language: {source_lang}
Target language: {target_lang}
Source text: "{source}"
Translation: "{hypothesis}"

This is a task instruction where directional and spatial terms (left, right, same side) are critical - the child's motor response depends on them being unambiguous.
Evaluate:
1. Are all directional/spatial terms (left, right, same side, opposite) preserved exactly and unambiguously?
2. Does it sound natural when spoken aloud to a child in {target_lang}?
3. Any directional error or ambiguity is a CRITICAL error.
Think step by step before giving your score.""",
    "SPATIAL_RELATIONAL": """Source language: {source_lang}
Target language: {target_lang}
Source text: "{source}"
Translation: "{hypothesis}"

This prompt asks a child to judge a spatial or relational property (position, size, quantity, color, pattern, orientation).
Spatial and relational vocabulary varies across languages - evaluate whether the translation uses the most natural and precise term in {target_lang} for the concept expressed, not necessarily the most literal word.
Evaluate:
1. Is the spatial/relational concept correctly and unambiguously conveyed?
2. Is it clear WHICH dimension (size, color, count, pattern) the child is being asked to attend to?
3. Is the phrasing natural for a young child?
Think step by step before giving your score.""",
    "SPATIAL_RELATIONAL_ROTATION": """Source language: {source_lang}
Target language: {target_lang}
Source text: "{source}"
Translation: "{hypothesis}"

This prompt is part of a mental rotation task. The phrase "goes with" means "matches by rotation" - i.e., is the same shape seen from a different angle.
Evaluate:
1. Does the translated phrase convey matching/fitting by rotation, not merely adjacency, similarity, or belonging together in another sense?
2. If the translated phrase could be misread as a different spatial relationship (e.g., next to, similar to), flag this as a major error.
3. Is the phrasing natural for a young child?
Think step by step before giving your score.""",
    "MEMORY_RECALL": """Source language: {source_lang}
Target language: {target_lang}
Source text: "{source}"
Translation: "{hypothesis}"

This prompt asks a child to remember or recall a sequence they just saw.
Evaluate:
1. Is it clear what the child is being asked to recall?
2. Is sequence language ("same order", "in order") unambiguous in {target_lang}? Any ambiguity here is a major error.
3. Is tense and phrasing natural in {target_lang} for a spoken prompt?
4. Does it preserve the same level of specificity as the source?
Think step by step before giving your score.""",
    "OBJECT_NAMING": """Source language: {source_lang}
Target language: {target_lang}
Source text: "{source}"
Translation: "{hypothesis}"

This is a short label for an object, image, or concept shown to a child.
Evaluate:
1. Is this the most natural, everyday word a {target_lang}-speaking child would know for this object?
2. Prefer common child-vocabulary terms over formal, scientific, or adult equivalents.
3. Proper names and animal names that vary by region should use the most broadly understood variant.
Think step by step before giving your score.""",
    "OBJECT_NAMING_GRAMMAR": """Source language: {source_lang}
Target language: {target_lang}
Source text: "{source}"
Translation: "{hypothesis}"

This string is a TROG (Test for Reception of Grammar) item. It tests grammatical comprehension - the exact syntactic structure (modifier placement, relative clauses, plurals, prepositions) is what is being assessed and MUST be preserved.
Evaluate:
1. Is the syntactic structure (e.g., "the big dog chasing the cat" vs. "the dog chasing the big cat") faithfully preserved?
2. Do NOT accept simplifications or restructuring even if they sound more natural - grammatical fidelity is critical here.
3. Is the vocabulary child-appropriate?
Any syntactic simplification or restructuring is a CRITICAL error.
Think step by step before giving your score.""",
    "AMBIGUOUS_COMPREHENSION": """Source language: {source_lang}
Target language: {target_lang}
Source text: "{source}"
Translation: "{hypothesis}"

IMPORTANT: This string is intentionally ambiguous - it is designed to be interpretable in more than one way by a native speaker. This is deliberate and is the core purpose of the item.

Evaluate:
1. AMBIGUITY PRESERVATION (critical): Does the translation remain genuinely ambiguous in the same way for a native {target_lang} speaker? If the translation resolves the ambiguity or nudges toward one interpretation, this is a CRITICAL error.
2. NATURALNESS: Does it sound like something a {target_lang}-speaking adult would say to a child?
3. ACCURACY: Are the core words and grammar correct?

Do NOT penalize the translation for being ambiguous or "unclear" - that is intentional.
Think step by step before giving your score.""",
    "INSTRUCTION_NARRATIVE_AMBIGUOUS": """Source language: {source_lang}
Target language: {target_lang}
Source text: "{source}"
Translation: "{hypothesis}"

This is a scene-setting narrative for a social cognition task that measures how children interpret ambiguous social situations.
Evaluate:
1. Does the narrative preserve the ambiguity of the actor's intent - i.e., it should be equally plausible that the action was on purpose OR accidental? Any translation that makes the intent seem more deliberate or more accidental than in the English source is a MAJOR error.
2. Is the vocabulary and tone appropriate for a child listener (ages 8-12)?
3. Are the events described accurately and completely?
Think step by step before giving your score.""",
    "CHILD_SURVEY": """Source language: {source_lang}
Target language: {target_lang}
Source text: "{source}"
Translation: "{hypothesis}"

This is a survey question (or a response option) answered BY THE CHILD participant (ages 5-12) about themselves - their feelings, their friends, school, family, or class. The child is BOTH the respondent and the subject: "you" refers to the child. Do NOT assume an adult respondent and do NOT treat "you" as referring to a caregiver or teacher.
Evaluate:
1. Is the meaning accurate and complete for a child answering about their own experience?
2. Does it sound natural and age-appropriate when read to/by a child in {target_lang}, using informal/familiar address (tu, du, jij/je, vos)?
3. For response options (e.g. "Definitely true", "Somewhat false"), is the option's polarity and degree preserved exactly?
A literal, child-directed translation of "you/your" is CORRECT here - do not flag it as a subject shift.
Think step by step before giving your score.""",
    "SURVEY": """{survey_audience}

Source language: {source_lang}
Target language: {target_lang}
Source text: "{source}"
Translation: "{hypothesis}"

This is a survey question answered by an ADULT respondent.
Evaluate:
1. Is the meaning accurate and complete, including who is being referred to (the child participant, caregiver, or teacher/classroom context)?
2. Does it sound natural and respectful for an adult survey respondent in {target_lang}?
3. If the source is teacher-facing, preserve teacher/classroom framing; if caregiver-facing, preserve parent/caregiver framing.
4. Avoid child-directed wording that would sound unnatural for an adult respondent.
Think step by step before giving your score.""",
}


CONSTRUCT_CONTEXTS: Dict[str, str] = {
    "INSTRUCTION_SPATIAL_EXACT": "This task measures inhibitory control and cognitive flexibility. The critical rule is that hearts require a response on the SAME side, flowers require a response on the OPPOSITE side. Correct directional mapping is the entire construct being measured.",
    "MEMORY_RECALL": "This task measures visuospatial working memory (Corsi Block task). Sequence language — same order vs. backwards order — is the core distinction between the two task blocks and must be preserved exactly.",
    "SPATIAL_RELATIONAL_ROTATION": "This task measures spatial rotation ability. The correct item 'matches when rotated' — not 'looks similar' or 'goes with' in a generic sense. The concept of rotational matching must be unambiguous.",
    "OBJECT_NAMING_GRAMMAR": "This task measures receptive grammatical comprehension. Each sentence targets a specific grammatical structure (e.g., passive voice, relative clauses, negation, coordination). The grammatical structure is the item — syntactic simplification is a critical error even if the meaning is technically preserved.",
    "INSTRUCTION_NARRATIVE_AMBIGUOUS": "This task measures hostile attribution bias. Scenarios are constructed so that a social harm is genuinely ambiguous — equally plausible as accidental or intentional. Any translation that makes the scenario feel more intentional or more accidental than the English source introduces systematic measurement bias.",
}

LABEL_CONSTRUCT_CONTEXTS: Dict[str, str] = {
    "math": "This is a math task with an objective numeric answer; judge whether the translated instruction conveys the same number and operation. Mathematical symbols and operations must use the standard notation for the target locale (e.g., comma vs. period as decimal separator; local names for arithmetic operations). Numbers may legitimately be written out in words, and in some locales (notably es-CO) a comma is placed BETWEEN number words as an intentional spoken-pronunciation aid (e.g. 'doscientos, cuarenta y cinco' for 245) — do NOT penalize commas that fall between number words. Only flag punctuation that actually breaks the sentence or changes the number, such as commas after a verb or article ('Escoge, el, 66') or doubled/stray commas.",
    "matrix-reasoning": "This task measures general reasoning ability. The word 'pattern' must be translated as a visual/logical regularity, not a decorative pattern.",
    "same-different-selection": "This task measures cognitive flexibility. Children identify cards that are 'the same in some way' across dimensions like shape, color, size, and number. The multi-dimensional framing ('same in a different way') is critical — translations must not collapse this to a single-dimension match.",
    "vocab": "This task is a receptive picture vocabulary task. Children hear a target word and must identify the matching picture among semantically close distractors (e.g., 'acorn' with distractor 'coconut'). A more specific or formal translation could make a correct answer appear wrong — always prefer the most common child-vocabulary term.",
    "theory-of-mind": "This task measures theory of mind: true beliefs, false beliefs, deception, and moral reasoning. Questions often hinge on the distinction between what a character knows vs. what is actually true. Any translation that blurs a character's epistemic state (what they know/think/believe) is a critical error.",
    "hostile-attribution": "This task measures hostile attribution bias. Scenarios are constructed so that a social harm is genuinely ambiguous — equally plausible as accidental or intentional. Any translation that makes the scenario feel more intentional or more accidental than the English source introduces systematic measurement bias.",
}


LABEL_TEMPLATES = {
    "general": "FEEDBACK_TRANSITION",
    "hearts-and-flowers": "INSTRUCTION_SPATIAL_EXACT",
    "math": "INSTRUCTION_GENERAL",
    "matrix-reasoning": "SPATIAL_RELATIONAL",
    "memory-game": "MEMORY_RECALL",
    "mental-rotation": "SPATIAL_RELATIONAL_ROTATION",
    "vocab": "OBJECT_NAMING",
    "survey": "SURVEY",
}


STATE_LABELS = {
    "afraid",
    "angry",
    "bored",
    "calm",
    "confused",
    "disappointed",
    "disgusted",
    "embarrassed",
    "excited",
    "frustrated",
    "happy",
    "lonely",
    "mad",
    "neutral",
    "proud",
    "sad",
    "scared",
    "surprised",
    "tired",
    "upset",
    "worried",
}


@dataclass
class ScreenshotAttachment:
    path: Path
    screenshot_id: int
    name: str
    position: dict | None = None


@dataclass
class EvaluationItem:
    identifier: str
    labels: str
    source: str
    target_lang: str
    hypothesis: str
    template_key: str
    screenshots: List[ScreenshotAttachment] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate LEVANTE translations with task-aware Gemini prompts.")
    parser.add_argument("--input-csv", default="complete_translations.csv")
    parser.add_argument("--output-csv", default="translation_quality_results.csv")
    parser.add_argument("--source-col", default="en")
    parser.add_argument("--target-cols", default=",".join(DEFAULT_TARGET_LANGS))
    parser.add_argument("--api-key-env", default="GEMINI_API_KEY")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--fallback-model", default=FALLBACK_MODEL)
    parser.add_argument("--limit", type=int, default=0, help="Limit evaluated source rows, for smoke runs.")
    parser.add_argument("--sleep-seconds", type=float, default=0.0, help="Optional delay between Gemini calls.")
    parser.add_argument("--use-crowdin-screenshots", action="store_true", help="Attach tagged Crowdin screenshots for visual-context tasks.")
    parser.add_argument("--crowdin-project-id", default=DEFAULT_CROWDIN_PROJECT_ID)
    parser.add_argument("--crowdin-api-key-env", default="CROWDIN_API_TOKEN")
    parser.add_argument("--screenshot-cache-dir", default="translation_grading/output/crowdin_screenshots")
    parser.add_argument(
        "--screenshot-task-labels",
        default=",".join(DEFAULT_SCREENSHOT_TASK_LABELS),
        help="Comma-separated task labels eligible for screenshot attachment.",
    )
    parser.add_argument("--max-screenshots-per-item", type=int, default=1)
    return parser.parse_args()


def csv_list(raw: str) -> List[str]:
    return [part.strip() for part in str(raw or "").split(",") if part.strip()]


def normalize_label(labels: str) -> str:
    return str(labels or "").strip().lower()


def identifier_tokens(identifier: str) -> List[str]:
    return [token for token in re.split(r"[^a-zA-Z]+", str(identifier or "").lower()) if token]


def is_short_state_label(identifier: str) -> bool:
    tokens = identifier_tokens(identifier)
    if not tokens:
        return False
    if len(tokens) == 1 and tokens[0] in STATE_LABELS:
        return True
    return len(tokens) <= 3 and tokens[-1] in STATE_LABELS


def select_template(labels: str, identifier: str) -> str:
    label = normalize_label(labels)
    ident = str(identifier or "").strip().lower()
    if label == "child-survey":
        return "CHILD_SURVEY"
    if label == "same-different-selection":
        return "INSTRUCTION_GENERAL" if "instruct" in ident else "SPATIAL_RELATIONAL"
    if label == "trog":
        return "INSTRUCTION_GENERAL" if ("instruct" in ident or "prompt" in ident) else "OBJECT_NAMING_GRAMMAR"
    if label == "theory-of-mind":
        if is_short_state_label(ident):
            return "OBJECT_NAMING"
        if "intro" in ident or "transition" in ident:
            return "INSTRUCTION_GENERAL"
        return "AMBIGUOUS_COMPREHENSION"
    if label == "hostile-attribution":
        if ident.endswith("instruct1") or ident.endswith("instruct2"):
            return "INSTRUCTION_NARRATIVE_AMBIGUOUS"
        if ident.endswith("q1"):
            return "AMBIGUOUS_COMPREHENSION"
        return "INSTRUCTION_GENERAL"
    return LABEL_TEMPLATES.get(label, "INSTRUCTION_GENERAL")


def construct_context_for(labels: str, template_key: str) -> str:
    label = normalize_label(labels)
    if label in LABEL_CONSTRUCT_CONTEXTS:
        return LABEL_CONSTRUCT_CONTEXTS[label]
    return CONSTRUCT_CONTEXTS.get(template_key, "")


def survey_audience_for(identifier: str, labels: str) -> str:
    if normalize_label(labels) != "survey":
        return ""
    ident = str(identifier or "").lower()
    if any(token in ident for token in ["teacher_survey", "teacher", "classroom"]):
        return (
            "Audience context: This item is from a TEACHER survey for a teacher who has a participating child in their classroom. "
            "Use natural adult-professional register and preserve classroom/teacher framing."
        )
    if any(token in ident for token in ["parent_survey", "caregiver", "parent", "family"]):
        return (
            "Audience context: This item is from a CAREGIVER survey for a parent or other caregiver of a participating child. "
            "Use natural adult-caregiver register and preserve caregiver/child framing."
        )
    return (
        "Audience context: This item is from an ADULT survey completed by either a caregiver or a teacher of a participating child. "
        "Use natural adult register and preserve respondent framing."
    )


def build_task_prompt(
    *,
    template_key: str,
    labels: str,
    identifier: str = "",
    source_lang: str,
    target_lang: str,
    source: str,
    hypothesis: str,
) -> str:
    task_prompt = TEMPLATES[template_key].format(
        source_lang=source_lang,
        target_lang=target_lang,
        source=source,
        hypothesis=hypothesis,
        survey_audience=survey_audience_for(identifier, labels),
    )
    construct_context = construct_context_for(labels, template_key)
    if construct_context:
        return f"{construct_context}\n\n{task_prompt}"
    return task_prompt


def build_prompt(item: EvaluationItem, *, json_only: bool = False) -> str:
    task_prompt = build_task_prompt(
        template_key=item.template_key,
        labels=item.labels,
        identifier=item.identifier,
        source_lang=SOURCE_LANG,
        target_lang=item.target_lang,
        source=item.source,
        hypothesis=item.hypothesis,
    )
    if item.screenshots:
        task_prompt += (
            "\n\nCrowdin screenshot context is attached as image input. Use it only to disambiguate the visual object, "
            "scene, or UI context for this exact string; do not penalize the translation for visual details that are not relevant to the string."
        )
    suffix = "\n\nOutput ONLY valid JSON, no other text." if json_only else ""
    return f"{SYSTEM_PROMPT}\n\n{task_prompt}{suffix}"


def build_backtranslation_prompt(item: EvaluationItem, *, json_only: bool = False) -> str:
    prompt = (
        "You are checking whether a Dutch translation preserves task-relevant meaning for a child-facing cognitive assessment.\n\n"
        f"Source English: \"{item.source}\"\n"
        f"Dutch translation: \"{item.hypothesis}\"\n"
        f"Task label: {item.labels}\n\n"
        "First, backtranslate the Dutch into English as literally as possible. Then judge whether the backtranslation preserves "
        "the task-relevant meaning and ambiguity profile of the source.\n\n"
        "Return JSON with keys: backtranslation, score, severity, notes.\n"
        "Allowed severity values: none, minor, major, critical.\n"
        "Scoring: 5=fully preserved, 4=minor drift, 3=noticeable drift but likely usable, "
        "2=major meaning shift, 1=critical mismatch or unrelated text."
    )
    if item.screenshots:
        prompt += (
            "\n\nCrowdin screenshot context is attached as image input. Use it only to disambiguate the pictured object, "
            "scene, or UI context for this exact string."
        )
    if json_only:
        prompt += "\n\nOutput ONLY valid JSON, no other text."
    return prompt


def build_batch_object_prompt(items: Sequence[EvaluationItem], *, json_only: bool = False) -> str:
    if not items:
        raise ValueError("Cannot build an empty batch prompt.")
    target_lang = items[0].target_lang
    labels = items[0].labels
    construct_context = construct_context_for(labels, "OBJECT_NAMING")
    construct_block = f"{construct_context}\n\n" if construct_context else ""
    numbered = []
    for idx, item in enumerate(items, start=1):
        numbered.extend(
            [
                f"{idx}. Source text: \"{item.source}\"",
                f"   Translation: \"{item.hypothesis}\"",
            ]
        )
    suffix = "\nOutput ONLY valid JSON, no other text." if json_only else ""
    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"Source language: {SOURCE_LANG}\n"
        f"Target language: {target_lang}\n\n"
        f"{construct_block}"
        "These are short labels for objects, images, or concepts shown to children.\n"
        "Evaluate each numbered item independently using the OBJECT_NAMING criteria:\n"
        "1. Is this the most natural, everyday word a child would know?\n"
        "2. Prefer common child-vocabulary terms over formal, scientific, or adult equivalents.\n"
        "3. Proper names and animal names that vary by region should use the most broadly understood variant.\n\n"
        + "\n".join(numbered)
        + "\n\nReturn JSON as: {\"items\": [{\"index\": 1, \"score\": <1-5>, "
        "\"errors\": [{\"severity\": \"minor|major|critical\", \"description\": \"...\"}], "
        "\"notes\": \"...\"}]}."
        + suffix
    )


def extract_json_text(raw: str) -> str:
    text = str(raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_evaluation(raw: str) -> dict:
    payload = json.loads(extract_json_text(raw))
    if not isinstance(payload, dict):
        raise ValueError("Gemini response was not a JSON object.")
    return normalize_evaluation(payload)


def normalize_evaluation(payload: dict) -> dict:
    score = int(payload.get("score", 0) or 0)
    if score < 1 or score > 5:
        raise ValueError(f"Invalid score from Gemini: {score}")
    errors = payload.get("errors", [])
    if not isinstance(errors, list):
        errors = []
    clean_errors = []
    for error in errors:
        if not isinstance(error, dict):
            continue
        severity = str(error.get("severity", "") or "").strip().lower()
        if severity not in {"minor", "major", "critical"}:
            severity = "minor"
        description = str(error.get("description", "") or "").strip()
        clean_errors.append({"severity": severity, "description": description})
    return {"score": score, "errors": clean_errors, "notes": str(payload.get("notes", "") or "").strip()}


def parse_batch_evaluations(raw: str, expected_count: int) -> List[dict]:
    payload = json.loads(extract_json_text(raw))
    items = payload.get("items") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise ValueError("Gemini batch response missing items list.")
    by_index = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        idx = int(item.get("index", 0) or 0)
        if 1 <= idx <= expected_count:
            by_index[idx] = normalize_evaluation(item)
    missing = [idx for idx in range(1, expected_count + 1) if idx not in by_index]
    if missing:
        raise ValueError(f"Gemini batch response missing item indexes: {missing}")
    return [by_index[idx] for idx in range(1, expected_count + 1)]


def parse_backtranslation_evaluation(raw: str) -> dict:
    payload = json.loads(extract_json_text(raw))
    if not isinstance(payload, dict):
        raise ValueError("Backtranslation response was not a JSON object.")
    score = int(payload.get("score", 0) or 0)
    if score < 1 or score > 5:
        raise ValueError(f"Invalid backtranslation score from Gemini: {score}")
    severity = str(payload.get("severity", "none") or "none").strip().lower()
    if severity not in {"none", "minor", "major", "critical"}:
        severity = "minor"
    return {
        "backtranslation": str(payload.get("backtranslation", "") or "").strip(),
        "score": score,
        "severity": severity,
        "notes": str(payload.get("notes", "") or "").strip(),
    }


def image_part(path: Path) -> dict:
    mime_type = mimetypes.guess_type(str(path))[0] or "image/png"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return {"inlineData": {"mimeType": mime_type, "data": data}}


def call_gemini_text(prompt: str, model: str, api_key: str, image_paths: Sequence[Path] | None = None) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    parts = [{"text": prompt}]
    for path in image_paths or []:
        parts.append(image_part(path))
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            # Disable "thinking" on 2.5+ flash models: ~3-5x faster and cheaper
            # for this short structured-judgement task (ignored by older models).
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["candidates"][0]["content"]["parts"][0]["text"]


def should_fallback(exc: Exception) -> bool:
    if not isinstance(exc, urllib.error.HTTPError):
        return False
    return exc.code in {400, 404, 429, 503}


def call_gemini(prompt: str, api_key: str, model: str, fallback_model: str, image_paths: Sequence[Path] | None = None) -> str:
    try:
        return call_gemini_text(prompt, model, api_key, image_paths)
    except Exception as exc:
        if fallback_model and fallback_model != model and should_fallback(exc):
            return call_gemini_text(prompt, fallback_model, api_key, image_paths)
        raise


def evaluate_single(item: EvaluationItem, api_key: str, model: str, fallback_model: str) -> dict:
    image_paths = [attachment.path for attachment in item.screenshots]
    raw = call_gemini(build_prompt(item), api_key, model, fallback_model, image_paths)
    try:
        return parse_evaluation(raw)
    except Exception:
        retry_raw = call_gemini(build_prompt(item, json_only=True), api_key, model, fallback_model, image_paths)
        return parse_evaluation(retry_raw)


def evaluate_object_batch(items: Sequence[EvaluationItem], api_key: str, model: str, fallback_model: str) -> List[dict]:
    raw = call_gemini(build_batch_object_prompt(items), api_key, model, fallback_model)
    try:
        return parse_batch_evaluations(raw, len(items))
    except Exception:
        retry_raw = call_gemini(build_batch_object_prompt(items, json_only=True), api_key, model, fallback_model)
        return parse_batch_evaluations(retry_raw, len(items))


def evaluate_backtranslation(item: EvaluationItem, api_key: str, model: str, fallback_model: str) -> dict:
    image_paths = [attachment.path for attachment in item.screenshots]
    raw = call_gemini(build_backtranslation_prompt(item), api_key, model, fallback_model, image_paths)
    try:
        return parse_backtranslation_evaluation(raw)
    except Exception:
        retry_raw = call_gemini(build_backtranslation_prompt(item, json_only=True), api_key, model, fallback_model, image_paths)
        return parse_backtranslation_evaluation(retry_raw)


def load_items(input_csv: Path, source_col: str, target_cols: Sequence[str], limit: int = 0) -> List[EvaluationItem]:
    items: List[EvaluationItem] = []
    with input_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"identifier", "labels", source_col, *target_cols}
        missing = sorted(col for col in required if col not in (reader.fieldnames or []))
        if missing:
            raise ValueError(f"Input CSV missing required columns: {', '.join(missing)}")
        for row_index, row in enumerate(reader, start=1):
            if limit > 0 and row_index > limit:
                break
            source = str(row.get(source_col, "") or "").strip()
            if not source:
                continue
            identifier = str(row.get("identifier", "") or "").strip()
            labels = str(row.get("labels", "") or "").strip()
            template_key = select_template(labels, identifier)
            for target_lang in target_cols:
                hypothesis = str(row.get(target_lang, "") or "").strip()
                if not hypothesis:
                    continue
                items.append(
                    EvaluationItem(
                        identifier=identifier,
                        labels=labels,
                        source=source,
                        target_lang=target_lang,
                        hypothesis=hypothesis,
                        template_key=template_key,
                    )
                )
    return items


def get_crowdin_token(api_key_env: str) -> str:
    token = os.environ.get(api_key_env, "").strip() or os.environ.get("CROWDIN_TOKEN", "").strip()
    if token:
        return token
    token_path = Path.home() / ".crowdin_api_token"
    if token_path.exists():
        return token_path.read_text(encoding="utf-8").strip()
    raise RuntimeError(f"Crowdin token not found. Set {api_key_env}, CROWDIN_TOKEN, or create ~/.crowdin_api_token.")


def fetch_crowdin_json(path: str, token: str, params: Dict[str, object] | None = None) -> dict:
    query = ""
    if params:
        query = "?" + urllib.parse.urlencode({k: str(v) for k, v in params.items()})
    req = urllib.request.Request(
        f"{CROWDIN_API_BASE}{path}{query}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Crowdin HTTP {exc.code} for {path}: {details}") from exc


def iter_crowdin_pages(path: str, token: str, *, limit: int = 500) -> Iterable[dict]:
    offset = 0
    while True:
        payload = fetch_crowdin_json(path, token, {"limit": limit, "offset": offset})
        items = payload.get("data", [])
        for item in items:
            yield item.get("data", item)
        if len(items) < limit:
            break
        offset += limit


def crowdin_identifier_for(item: EvaluationItem) -> str:
    return str(item.identifier or "").split("::", 1)[-1]


def safe_cache_name(screenshot_id: int, name: str, url: str) -> str:
    suffix = Path(str(name or "")).suffix.lower() or ".png"
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        suffix = ".png"
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(str(name or f'screenshot-{screenshot_id}')).stem).strip("_")
    return f"{screenshot_id}_{stem}_{digest}{suffix}"


def download_screenshot(url: str, cache_dir: Path, screenshot_id: int, name: str) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    out_path = cache_dir / safe_cache_name(screenshot_id, name, url)
    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path
    with urllib.request.urlopen(url, timeout=90) as resp:
        out_path.write_bytes(resp.read())
    return out_path


def attach_crowdin_screenshots(
    items: Sequence[EvaluationItem],
    *,
    project_id: str,
    api_key_env: str,
    cache_dir: Path,
    eligible_labels: Sequence[str],
    max_screenshots_per_item: int = 1,
) -> Dict[str, int]:
    eligible = {normalize_label(label) for label in eligible_labels if normalize_label(label)}
    wanted_items = [item for item in items if normalize_label(item.labels) in eligible]
    wanted_identifiers = {crowdin_identifier_for(item) for item in wanted_items}
    if not wanted_identifiers:
        return {"eligible_items": 0, "items_with_screenshots": 0, "screenshots_downloaded": 0}

    token = get_crowdin_token(api_key_env)
    strings_by_identifier: Dict[str, List[int]] = {identifier: [] for identifier in wanted_identifiers}
    for string_data in iter_crowdin_pages(f"/projects/{project_id}/strings", token):
        identifier = str(string_data.get("identifier") or "")
        if identifier in strings_by_identifier:
            strings_by_identifier[identifier].append(int(string_data["id"]))
    identifier_by_string_id = {
        string_id: identifier
        for identifier, string_ids in strings_by_identifier.items()
        for string_id in string_ids
    }

    screenshots_by_identifier: Dict[str, List[dict]] = {identifier: [] for identifier in wanted_identifiers}
    for screenshot in iter_crowdin_pages(f"/projects/{project_id}/screenshots", token):
        screenshot_id = int(screenshot.get("id") or 0)
        url = str(screenshot.get("url") or "").strip()
        name = str(screenshot.get("name") or f"screenshot-{screenshot_id}")
        if not screenshot_id or not url:
            continue
        seen_in_screenshot = set()
        for tag in screenshot.get("tags") or []:
            identifier = identifier_by_string_id.get(tag.get("stringId"))
            if not identifier or identifier in seen_in_screenshot:
                continue
            seen_in_screenshot.add(identifier)
            screenshots_by_identifier[identifier].append(
                {
                    "screenshot_id": screenshot_id,
                    "name": name,
                    "url": url,
                    "position": tag.get("position"),
                }
            )

    screenshots_downloaded = 0
    items_with_screenshots = 0
    for item in wanted_items:
        identifier = crowdin_identifier_for(item)
        candidates = screenshots_by_identifier.get(identifier, [])
        candidates.sort(key=lambda shot: (crowdin_identifier_for(item).lower() not in str(shot["name"]).lower(), int(shot["screenshot_id"])))
        attachments: List[ScreenshotAttachment] = []
        for shot in candidates[: max(0, max_screenshots_per_item)]:
            path = download_screenshot(str(shot["url"]), cache_dir, int(shot["screenshot_id"]), str(shot["name"]))
            screenshots_downloaded += 1
            attachments.append(
                ScreenshotAttachment(
                    path=path,
                    screenshot_id=int(shot["screenshot_id"]),
                    name=str(shot["name"]),
                    position=shot.get("position"),
                )
            )
        item.screenshots = attachments
        if attachments:
            items_with_screenshots += 1
    return {
        "eligible_items": len(wanted_items),
        "items_with_screenshots": items_with_screenshots,
        "screenshots_downloaded": screenshots_downloaded,
        "matched_identifiers": sum(1 for ids in strings_by_identifier.values() if ids),
    }


def has_critical_error(evaluation: dict) -> bool:
    return any(error.get("severity") == "critical" for error in evaluation.get("errors", []))


def result_row(item: EvaluationItem, evaluation: dict) -> dict:
    human_review = evaluation["score"] <= 3 or has_critical_error(evaluation)
    return {
        "identifier": item.identifier,
        "language": item.target_lang,
        "score": evaluation["score"],
        "errors_json": json.dumps(evaluation["errors"], ensure_ascii=False),
        "notes": evaluation["notes"],
        "template_used": item.template_key,
        "human_review": "yes" if human_review else "no",
        "screenshot_names": "|".join(attachment.name for attachment in item.screenshots),
    }


def write_results(path: Path, rows: Sequence[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["identifier", "language", "score", "errors_json", "notes", "template_used", "human_review", "screenshot_names"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def chunks(items: Sequence[EvaluationItem], size: int) -> Iterable[Sequence[EvaluationItem]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def evaluate_items(items: Sequence[EvaluationItem], api_key: str, model: str, fallback_model: str, sleep_seconds: float) -> List[dict]:
    results: List[dict] = []
    object_items = [item for item in items if item.template_key == "OBJECT_NAMING" and not item.screenshots]
    object_ids = {id(item) for item in object_items}

    object_items_by_group: Dict[Tuple[str, str], List[EvaluationItem]] = {}
    for item in object_items:
        object_items_by_group.setdefault((item.target_lang, construct_context_for(item.labels, item.template_key)), []).append(item)

    for group in sorted(object_items_by_group):
        for batch in chunks(object_items_by_group[group], BATCH_SIZE):
            evaluations = evaluate_object_batch(batch, api_key, model, fallback_model)
            results.extend(result_row(item, evaluation) for item, evaluation in zip(batch, evaluations))
            if sleep_seconds:
                time.sleep(sleep_seconds)

    for item in items:
        if id(item) in object_ids:
            continue
        evaluation = evaluate_single(item, api_key, model, fallback_model)
        results.append(result_row(item, evaluation))
        if sleep_seconds:
            time.sleep(sleep_seconds)
    return results


def mean_score(rows: Sequence[dict]) -> float:
    scores = [float(row["score"]) for row in rows if row.get("score") not in {"", None}]
    return statistics.mean(scores) if scores else 0.0


def print_summary(rows: Sequence[dict]) -> None:
    print("\nPer-task mean scores")
    print("template_used,count,mean_score")
    for template in sorted({row["template_used"] for row in rows}):
        bucket = [row for row in rows if row["template_used"] == template]
        print(f"{template},{len(bucket)},{mean_score(bucket):.2f}")

    print("\nPer-language mean scores")
    print("language,count,mean_score")
    for language in sorted({row["language"] for row in rows}):
        bucket = [row for row in rows if row["language"] == language]
        print(f"{language},{len(bucket)},{mean_score(bucket):.2f}")

    review_count = sum(1 for row in rows if row.get("human_review") == "yes")
    print(f"\nHuman review flags: {review_count} / {len(rows)}")


def main() -> int:
    args = parse_args()
    api_key = os.environ.get(args.api_key_env, "").strip()
    if not api_key:
        raise RuntimeError(f"{args.api_key_env} is not set.")

    items = load_items(Path(args.input_csv), args.source_col, csv_list(args.target_cols), args.limit)
    if args.use_crowdin_screenshots:
        screenshot_stats = attach_crowdin_screenshots(
            items,
            project_id=args.crowdin_project_id,
            api_key_env=args.crowdin_api_key_env,
            cache_dir=Path(args.screenshot_cache_dir),
            eligible_labels=csv_list(args.screenshot_task_labels),
            max_screenshots_per_item=args.max_screenshots_per_item,
        )
        print(
            "[screenshots] "
            f"eligible={screenshot_stats['eligible_items']} "
            f"with_screenshots={screenshot_stats['items_with_screenshots']} "
            f"matched_identifiers={screenshot_stats.get('matched_identifiers', 0)} "
            f"downloaded={screenshot_stats['screenshots_downloaded']}"
        )
    rows = evaluate_items(items, api_key, args.model, args.fallback_model, args.sleep_seconds)
    write_results(Path(args.output_csv), rows)
    print(f"Wrote {len(rows)} evaluations to {args.output_csv}")
    print_summary(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
