#!/usr/bin/env python3
"""Run and analyze Vocab VLM benchmarks across approved Crowdin languages."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QA_DIR = ROOT.parent / "levante-qa"
DEFAULT_OUTPUT_DIR = ROOT / "translation_grading" / "output"
DEFAULT_DB = DEFAULT_OUTPUT_DIR / "vocab_vlm_language_runs.sqlite"
DEFAULT_CROWDIN_CACHE = DEFAULT_OUTPUT_DIR / ".dashboard-approved-cache.zip"
DEFAULT_LANGUAGES = ["de", "en-GB", "en-US", "es-AR", "es-CO", "fr-CA", "nl", "pt-PT"]
DEFAULT_PROVIDER = "gemini"
DEFAULT_FIRESTORE_PROJECT = "hs-levante-admin-dev"
DEFAULT_FIRESTORE_DATABASE = "levante-tools-data"
DEFAULT_FIRESTORE_COLLECTION = "vocabVlmLanguageRuns"


@dataclass
class RunResult:
    language: str
    provider: str
    run_id: str
    started_at: str
    finished_at: str
    duration_ms: int
    exit_code: int
    command: str
    log_path: Path | None
    stdout_tail: str
    stderr_tail: str
    accuracy: float | None
    n_records: int
    n_scored: int
    n_correct: int
    n_incorrect: int
    n_with_audio: int
    audio_sources: dict[str, int]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--languages", default=",".join(DEFAULT_LANGUAGES))
    parser.add_argument("--provider", default=DEFAULT_PROVIDER)
    parser.add_argument("--qa-dir", default=str(DEFAULT_QA_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--db-path", default=str(DEFAULT_DB))
    parser.add_argument("--crowdin-cache-path", default=str(DEFAULT_CROWDIN_CACHE))
    parser.add_argument("--audio-fallback-language", default="en-US")
    parser.add_argument("--run", action="store_true", help="Launch Cypress runs before analyzing.")
    parser.add_argument("--analyze", action="store_true", help="Generate summary outputs from SQLite.")
    parser.add_argument("--backfill-firestore", action="store_true", help="Write latest SQLite runs to Firestore without rerunning Cypress.")
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--stop-on-failure", action="store_true")
    parser.add_argument("--firestore-shadow", action="store_true", help="Also write runs to the named Firestore database.")
    parser.add_argument("--firestore-strict", action="store_true", help="Fail if the Firestore shadow write fails.")
    parser.add_argument("--firestore-project", default=DEFAULT_FIRESTORE_PROJECT)
    parser.add_argument("--firestore-database", default=DEFAULT_FIRESTORE_DATABASE)
    parser.add_argument("--firestore-collection", default=DEFAULT_FIRESTORE_COLLECTION)
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def csv_list(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def tail(text: str, max_chars: int = 8000) -> str:
    return text[-max_chars:] if len(text) > max_chars else text


def tail_file(path: Path, max_chars: int = 8000) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return tail(text, max_chars)


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS runs (
          run_id TEXT PRIMARY KEY,
          language TEXT NOT NULL,
          provider TEXT NOT NULL,
          task TEXT NOT NULL,
          started_at TEXT NOT NULL,
          finished_at TEXT NOT NULL,
          duration_ms INTEGER NOT NULL,
          exit_code INTEGER NOT NULL,
          command TEXT NOT NULL,
          log_path TEXT,
          stdout_tail TEXT,
          stderr_tail TEXT,
          accuracy REAL,
          n_records INTEGER NOT NULL,
          n_scored INTEGER NOT NULL,
          n_correct INTEGER NOT NULL,
          n_incorrect INTEGER NOT NULL,
          n_with_audio INTEGER NOT NULL,
          audio_sources_json TEXT NOT NULL,
          translations_source TEXT NOT NULL,
          audio_fallback_language TEXT
        );

        CREATE TABLE IF NOT EXISTS trials (
          run_id TEXT NOT NULL,
          language TEXT NOT NULL,
          step INTEGER NOT NULL,
          item_type TEXT,
          prompt_text TEXT,
          target_word TEXT,
          choices_json TEXT NOT NULL,
          chosen_index INTEGER,
          chosen_value TEXT,
          keyed_index INTEGER,
          keyed_value TEXT,
          correct INTEGER,
          rt_ms REAL,
          latency_ms REAL,
          timed_out INTEGER,
          audio_transcript TEXT,
          audio_source TEXT,
          model_raw TEXT,
          record_json TEXT NOT NULL,
          PRIMARY KEY (run_id, step),
          FOREIGN KEY (run_id) REFERENCES runs(run_id)
        );

        CREATE INDEX IF NOT EXISTS idx_trials_language_keyed_value ON trials(language, keyed_value);
        CREATE INDEX IF NOT EXISTS idx_trials_correct ON trials(correct);
        """
    )
    conn.commit()


def vocab_logs(qa_dir: Path) -> set[Path]:
    logs_dir = qa_dir / "cypress" / "logs"
    return set(logs_dir.glob("vlm_vocab_*.jsonl"))


def newest_vocab_log(qa_dir: Path, since: float, existing_logs: set[Path]) -> Path | None:
    logs_dir = qa_dir / "cypress" / "logs"
    candidates = [
        path
        for path in logs_dir.glob("vlm_vocab_*.jsonl")
        if path.is_file() and path not in existing_logs and path.stat().st_mtime >= since - 2
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def summarize_records(records: list[dict]) -> tuple[float | None, int, int, int, int, dict[str, int]]:
    scored = [row for row in records if isinstance(row.get("correct"), bool)]
    n_correct = sum(1 for row in scored if row.get("correct") is True)
    n_incorrect = len(scored) - n_correct
    n_with_audio = sum(1 for row in records if row.get("audioTranscript"))
    sources: dict[str, int] = {}
    for row in records:
        source = row.get("audioSource")
        if source:
            sources[str(source)] = sources.get(str(source), 0) + 1
    accuracy = n_correct / len(scored) if scored else None
    return accuracy, n_correct, n_incorrect, n_with_audio, len(scored), sources


def run_document(result: RunResult, translations_source: str, audio_fallback_language: str) -> dict:
    return {
        "runId": result.run_id,
        "language": result.language,
        "provider": result.provider,
        "task": "vocab",
        "startedAt": result.started_at,
        "finishedAt": result.finished_at,
        "durationMs": result.duration_ms,
        "exitCode": result.exit_code,
        "command": result.command,
        "logPath": str(result.log_path) if result.log_path else None,
        "stdoutTail": result.stdout_tail,
        "stderrTail": result.stderr_tail,
        "accuracy": result.accuracy,
        "nRecords": result.n_records,
        "nScored": result.n_scored,
        "nCorrect": result.n_correct,
        "nIncorrect": result.n_incorrect,
        "nWithAudio": result.n_with_audio,
        "audioSources": result.audio_sources,
        "translationsSource": translations_source,
        "audioFallbackLanguage": audio_fallback_language or None,
        "shadowSource": "translation_grading/vocab_vlm_language_benchmark.py",
        "updatedAt": utc_now(),
    }


def trial_document(result: RunResult, row: dict) -> dict:
    return {
        "runId": result.run_id,
        "language": result.language,
        "task": "vocab",
        "step": int(row.get("step") or 0),
        "itemType": row.get("itemType"),
        "promptText": row.get("promptText"),
        "targetWord": row.get("targetWord"),
        "choices": row.get("choices") or [],
        "chosenIndex": row.get("chosenIndex"),
        "chosenValue": row.get("chosenValue"),
        "keyedIndex": row.get("keyedIndex"),
        "keyedValue": row.get("keyedValue"),
        "correct": row.get("correct"),
        "rtMs": row.get("rtMs"),
        "latencyMs": row.get("latencyMs"),
        "timedOut": row.get("timedOut"),
        "audioTranscript": row.get("audioTranscript"),
        "audioSource": row.get("audioSource"),
        "provider": row.get("provider"),
        "modelRaw": row.get("modelRaw"),
        "timestamp": row.get("timestamp"),
    }


def write_firestore_shadow(
    args: argparse.Namespace,
    result: RunResult,
    records: list[dict],
    translations_source: str,
    audio_fallback_language: str,
) -> None:
    if not args.firestore_shadow:
        return
    try:
        from google.cloud import firestore

        db = firestore.Client(project=args.firestore_project, database=args.firestore_database)
        run_ref = db.collection(args.firestore_collection).document(result.run_id)
        run_ref.set(run_document(result, translations_source, audio_fallback_language))
        trials = run_ref.collection("trials")
        for start in range(0, len(records), 450):
            batch = db.batch()
            for row in records[start : start + 450]:
                step = int(row.get("step") or 0)
                batch.set(trials.document(f"{step:04d}"), trial_document(result, row))
            batch.commit()
        print(
            f"[firestore] shadow wrote {result.run_id} to "
            f"{args.firestore_project}/{args.firestore_database}/{args.firestore_collection}",
            flush=True,
        )
    except Exception as exc:
        message = f"[firestore] shadow write failed for {result.run_id}: {exc}"
        if args.firestore_strict:
            raise RuntimeError(message) from exc
        print(message, flush=True)


def store_run(conn: sqlite3.Connection, result: RunResult, records: list[dict], translations_source: str, audio_fallback_language: str) -> None:
    with conn:
        conn.execute("DELETE FROM trials WHERE run_id = ?", (result.run_id,))
        conn.execute("DELETE FROM runs WHERE run_id = ?", (result.run_id,))
        conn.execute(
            """
            INSERT INTO runs (
              run_id, language, provider, task, started_at, finished_at, duration_ms,
              exit_code, command, log_path, stdout_tail, stderr_tail, accuracy,
              n_records, n_scored, n_correct, n_incorrect, n_with_audio,
              audio_sources_json, translations_source, audio_fallback_language
            ) VALUES (?, ?, ?, 'vocab', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.run_id,
                result.language,
                result.provider,
                result.started_at,
                result.finished_at,
                result.duration_ms,
                result.exit_code,
                result.command,
                str(result.log_path) if result.log_path else "",
                result.stdout_tail,
                result.stderr_tail,
                result.accuracy,
                result.n_records,
                result.n_scored,
                result.n_correct,
                result.n_incorrect,
                result.n_with_audio,
                json.dumps(result.audio_sources, ensure_ascii=False, sort_keys=True),
                translations_source,
                audio_fallback_language,
            ),
        )
        for row in records:
            conn.execute(
                """
                INSERT INTO trials (
                  run_id, language, step, item_type, prompt_text, target_word,
                  choices_json, chosen_index, chosen_value, keyed_index, keyed_value,
                  correct, rt_ms, latency_ms, timed_out, audio_transcript, audio_source,
                  model_raw, record_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.run_id,
                    result.language,
                    int(row.get("step") or 0),
                    row.get("itemType"),
                    row.get("promptText"),
                    row.get("targetWord"),
                    json.dumps(row.get("choices") or [], ensure_ascii=False),
                    row.get("chosenIndex"),
                    row.get("chosenValue"),
                    row.get("keyedIndex"),
                    row.get("keyedValue"),
                    None if row.get("correct") is None else int(bool(row.get("correct"))),
                    row.get("rtMs"),
                    row.get("latencyMs"),
                    None if row.get("timedOut") is None else int(bool(row.get("timedOut"))),
                    row.get("audioTranscript"),
                    row.get("audioSource"),
                    row.get("modelRaw"),
                    json.dumps(row, ensure_ascii=False),
                ),
            )


def run_language(args: argparse.Namespace, conn: sqlite3.Connection, language: str) -> RunResult:
    qa_dir = Path(args.qa_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    started_at = utc_now()
    env = os.environ.copy()
    env.update(
        {
            "QA_LANGUAGE": language,
            "QA_TRANSLATIONS_SOURCE": "crowdin-approved",
            "QA_CROWDIN_CACHE_PATH": str(Path(args.crowdin_cache_path).expanduser().resolve()),
            "QA_AUDIO_FALLBACK_LANGUAGE": args.audio_fallback_language,
            "VLM_PROVIDER": args.provider,
        }
    )
    env.pop("ELECTRON_RUN_AS_NODE", None)
    env.pop("CYPRESS_CACHE_FOLDER", None)
    command = ["npm", "run", "cy:run:vocab:vlm", "--", "--env", f"provider={args.provider}"]
    process_log = output_dir / f"vocab_vlm_process_{language}_{int(started)}.log"
    existing_logs = vocab_logs(qa_dir)
    print(f"[run] {language}: {' '.join(command)}", flush=True)
    timed_out = False
    with process_log.open("w", encoding="utf-8") as handle:
        try:
            proc = subprocess.run(
                command,
                cwd=qa_dir,
                env=env,
                stdout=handle,
                stderr=subprocess.STDOUT,
                timeout=args.timeout_seconds,
                check=False,
            )
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            exit_code = 124
            handle.write(f"\n[TIMEOUT] exceeded {args.timeout_seconds} seconds\n")
    finished_at = utc_now()
    duration_ms = int((time.time() - started) * 1000)
    log_path = newest_vocab_log(qa_dir, started, existing_logs)
    records = read_jsonl(log_path) if log_path else []
    accuracy, n_correct, n_incorrect, n_with_audio, n_scored, sources = summarize_records(records)
    run_id = f"{language}__{log_path.stem if log_path else int(started)}"
    result = RunResult(
        language=language,
        provider=args.provider,
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        exit_code=exit_code,
        command=" ".join(command),
        log_path=log_path,
        stdout_tail=tail_file(process_log),
        stderr_tail="[timeout]" if timed_out else "",
        accuracy=accuracy,
        n_records=len(records),
        n_scored=n_scored,
        n_correct=n_correct,
        n_incorrect=n_incorrect,
        n_with_audio=n_with_audio,
        audio_sources=sources,
    )
    store_run(conn, result, records, "crowdin-approved", args.audio_fallback_language)
    write_firestore_shadow(args, result, records, "crowdin-approved", args.audio_fallback_language)
    print(
        f"[run] {language}: exit={result.exit_code} scored={result.n_scored} "
        f"correct={result.n_correct} accuracy={result.accuracy if result.accuracy is not None else 'n/a'} "
        f"log={result.log_path}",
        flush=True,
    )
    return result


def latest_runs(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return list(
        conn.execute(
            """
            SELECT r.*
            FROM runs r
            JOIN (
              SELECT language, MAX(started_at) AS started_at
              FROM runs
              WHERE task = 'vocab'
              GROUP BY language
            ) latest
            ON latest.language = r.language AND latest.started_at = r.started_at
            ORDER BY r.language
            """
        )
    )


def load_trials_for_run(conn: sqlite3.Connection, run_id: str) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return list(conn.execute("SELECT * FROM trials WHERE run_id = ? ORDER BY step", (run_id,)))


def row_to_run_result(row: sqlite3.Row) -> RunResult:
    return RunResult(
        language=row["language"],
        provider=row["provider"],
        run_id=row["run_id"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        duration_ms=row["duration_ms"],
        exit_code=row["exit_code"],
        command=row["command"],
        log_path=Path(row["log_path"]) if row["log_path"] else None,
        stdout_tail=row["stdout_tail"] or "",
        stderr_tail=row["stderr_tail"] or "",
        accuracy=row["accuracy"],
        n_records=row["n_records"],
        n_scored=row["n_scored"],
        n_correct=row["n_correct"],
        n_incorrect=row["n_incorrect"],
        n_with_audio=row["n_with_audio"],
        audio_sources=json.loads(row["audio_sources_json"] or "{}"),
    )


def trial_row_to_record(row: sqlite3.Row) -> dict:
    return {
        "timestamp": None,
        "task": "vocab",
        "step": row["step"],
        "itemType": row["item_type"],
        "promptText": row["prompt_text"],
        "targetWord": row["target_word"],
        "choices": json.loads(row["choices_json"] or "[]"),
        "chosenIndex": row["chosen_index"],
        "chosenValue": row["chosen_value"],
        "keyedIndex": row["keyed_index"],
        "keyedValue": row["keyed_value"],
        "correct": None if row["correct"] is None else bool(row["correct"]),
        "rtMs": row["rt_ms"],
        "latencyMs": row["latency_ms"],
        "timedOut": None if row["timed_out"] is None else bool(row["timed_out"]),
        "audioTranscript": row["audio_transcript"],
        "audioSource": row["audio_source"],
        "modelRaw": row["model_raw"],
    }


def backfill_firestore(args: argparse.Namespace, conn: sqlite3.Connection) -> None:
    if not args.firestore_shadow:
        raise ValueError("--backfill-firestore requires --firestore-shadow")
    for run in latest_runs(conn):
        result = row_to_run_result(run)
        records = [trial_row_to_record(row) for row in load_trials_for_run(conn, result.run_id)]
        write_firestore_shadow(
            args,
            result,
            records,
            run["translations_source"],
            run["audio_fallback_language"] or "",
        )


def write_summary_outputs(conn: sqlite3.Connection, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    runs = latest_runs(conn)
    summary_csv = output_dir / "vocab_vlm_language_summary.csv"
    with summary_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "language",
                "run_id",
                "provider",
                "exit_code",
                "accuracy",
                "n_records",
                "n_scored",
                "n_correct",
                "n_incorrect",
                "n_with_audio",
                "audio_sources",
                "log_path",
            ],
        )
        writer.writeheader()
        for run in runs:
            writer.writerow(
                {
                    "language": run["language"],
                    "run_id": run["run_id"],
                    "provider": run["provider"],
                    "exit_code": run["exit_code"],
                    "accuracy": "" if run["accuracy"] is None else round(float(run["accuracy"]), 4),
                    "n_records": run["n_records"],
                    "n_scored": run["n_scored"],
                    "n_correct": run["n_correct"],
                    "n_incorrect": run["n_incorrect"],
                    "n_with_audio": run["n_with_audio"],
                    "audio_sources": run["audio_sources_json"],
                    "log_path": run["log_path"],
                }
            )

    item_rows: dict[str, dict[str, object]] = {}
    for run in runs:
        for trial in load_trials_for_run(conn, run["run_id"]):
            if trial["item_type"] != "word":
                continue
            item_key = trial["keyed_value"] or trial["target_word"] or trial["audio_transcript"] or f"step-{trial['step']}"
            row = item_rows.setdefault(
                str(item_key),
                {
                    "item_key": item_key,
                    "english_reference": "",
                },
            )
            lang = run["language"]
            row[f"{lang}_prompt"] = trial["prompt_text"]
            row[f"{lang}_chosen"] = trial["chosen_value"]
            row[f"{lang}_keyed"] = trial["keyed_value"]
            row[f"{lang}_correct"] = trial["correct"]
            if lang == "en-US":
                row["english_reference"] = trial["prompt_text"]

    languages = [run["language"] for run in runs]
    matrix_csv = output_dir / "vocab_vlm_item_matrix.csv"
    fields = ["item_key", "english_reference"]
    for lang in languages:
        fields.extend([f"{lang}_prompt", f"{lang}_chosen", f"{lang}_keyed", f"{lang}_correct"])
    with matrix_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for key in sorted(item_rows):
            writer.writerow({field: item_rows[key].get(field, "") for field in fields})

    suspicious = []
    for row in item_rows.values():
        english_ok = all(row.get(f"{lang}_correct") == 1 for lang in ("en-US", "en-GB") if f"{lang}_correct" in row)
        failing_langs = [lang for lang in languages if lang not in {"en-US", "en-GB"} and row.get(f"{lang}_correct") == 0]
        if english_ok and failing_langs:
            suspicious.append((row, failing_langs))

    md = [
        "# Vocab VLM Language Benchmark",
        "",
        "## Run Summary",
        "",
        "| Language | Accuracy | Correct | Scored | Audio source | Log |",
        "| --- | ---: | ---: | ---: | --- | --- |",
    ]
    for run in runs:
        accuracy = "" if run["accuracy"] is None else f"{float(run['accuracy']) * 100:.1f}%"
        md.append(
            f"| {run['language']} | {accuracy} | {run['n_correct']} | {run['n_scored']} | "
            f"`{run['audio_sources_json']}` | `{run['log_path']}` |"
        )
    md.extend(
        [
            "",
            "## Cross-Language Flags",
            "",
            "Items below passed the English baseline(s) but failed in at least one translated language. Treat these as review-priority signals, not final translation judgments.",
            "",
        ]
    )
    if not suspicious:
        md.append("No items met the English-pass / translation-fail heuristic.")
    else:
        for row, failing_langs in suspicious[:50]:
            md.append(f"### `{row['item_key']}`")
            md.append(f"- English reference: {row.get('english_reference') or ''}")
            md.append(f"- Failing languages: {', '.join(failing_langs)}")
            for lang in failing_langs:
                md.append(
                    f"- {lang}: prompt `{row.get(f'{lang}_prompt', '')}`, "
                    f"chose `{row.get(f'{lang}_chosen', '')}`, key `{row.get(f'{lang}_keyed', '')}`"
                )
            md.append("")

    md_path = output_dir / "vocab_vlm_language_summary.md"
    md_path.write_text("\n".join(md), encoding="utf-8")
    print(f"[analyze] wrote {summary_csv}", flush=True)
    print(f"[analyze] wrote {matrix_csv}", flush=True)
    print(f"[analyze] wrote {md_path}", flush=True)


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).expanduser().resolve()
    db_path = Path(args.db_path).expanduser().resolve()
    languages = csv_list(args.languages)
    conn = connect(db_path)
    if not args.run and not args.analyze and not args.backfill_firestore:
        args.run = True
        args.analyze = True
    if args.run:
        for language in languages:
            result = run_language(args, conn, language)
            if args.stop_on_failure and result.exit_code != 0:
                return result.exit_code
    if args.analyze:
        write_summary_outputs(conn, output_dir)
    if args.backfill_firestore:
        backfill_firestore(args, conn)
    print(f"[done] database: {db_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
