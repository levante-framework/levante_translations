#!/usr/bin/env python3
"""
Generate a regeneration report from Crowdin XLIFF exports in itembank_by_task/.

This script:
1) Downloads itembank_by_task XLIFFs from Crowdin (unless --skip-download).
2) Parses translations per item/language.
3) Stores a local SQLite snapshot.
4) Emits a report of items needing audio regeneration.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
import xml.etree.ElementTree as ET

# Ensure repo root is on sys.path so `utilities` resolves to package.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from utilities.crowdin_xliff_manager import (
    get_crowdin_token,
    list_project_files,
    list_project_languages,
    download_xliff_file,
)
import utilities.config as conf
from utilities.audio_validation import read_audio_metadata
from utilities.utilities import read_id3_tags, write_id3_tags

def _load_env() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        return
    load_dotenv()

def _strip_env_vars(keys: Iterable[str]) -> None:
    for key in keys:
        val = os.getenv(key)
        if val is None:
            continue
        os.environ[key] = val.strip()


def _init_gcs_client():
    try:
        from google.cloud import storage  # type: ignore
        from google.oauth2 import service_account  # type: ignore
    except Exception:
        return None

    credentials_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    if credentials_json:
        try:
            import json

            credentials_dict = json.loads(credentials_json)
            credentials = service_account.Credentials.from_service_account_info(credentials_dict)
            return storage.Client(credentials=credentials, project=credentials_dict.get("project_id"))
        except Exception:
            pass

    try:
        return storage.Client()
    except Exception:
        return None


def _gcs_pull_db(client, bucket_name: str, blob_path: str, local_path: Path) -> Optional[int]:
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    if not blob.exists():
        return None
    local_path.parent.mkdir(parents=True, exist_ok=True)
    blob.download_to_filename(str(local_path))
    return blob.generation


def _gcs_push_db(client, bucket_name: str, blob_path: str, local_path: Path, *, generation: Optional[int]) -> None:
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    if generation is None:
        blob.upload_from_filename(str(local_path), content_type="application/x-sqlite3")
    else:
        blob.upload_from_filename(
            str(local_path),
            content_type="application/x-sqlite3",
            if_generation_match=generation,
        )


def _normalize_prefix(prefix: str) -> str:
    prefix = prefix.strip()
    if prefix.startswith("/"):
        prefix = prefix[1:]
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    return prefix


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extract_text(elem: Optional[ET.Element]) -> str:
    if elem is None:
        return ""
    parts: List[str] = []
    if elem.text:
        parts.append(elem.text)
    for child in list(elem):
        if child.text:
            parts.append(child.text)
        if child.tail:
            parts.append(child.tail)
    return "".join(parts).strip()


def _local_tag(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _iter_trans_units(root: ET.Element) -> Iterable[ET.Element]:
    for elem in root.iter():
        if _local_tag(elem.tag) == "trans-unit":
            yield elem


def parse_xliff_file(path: Path) -> List[Dict[str, str]]:
    try:
        root = ET.parse(path).getroot()
    except Exception as exc:
        raise RuntimeError(f"Failed to parse XLIFF: {path}") from exc

    rows: List[Dict[str, str]] = []
    for tu in _iter_trans_units(root):
        item_id = tu.attrib.get("resname") or tu.attrib.get("id") or ""
        if not item_id:
            continue
        source_el = None
        target_el = None
        for child in list(tu):
            tag = _local_tag(child.tag)
            if tag == "source":
                source_el = child
            elif tag == "target":
                target_el = child
        rows.append(
            {
                "item_id": item_id,
                "source_text": _extract_text(source_el),
                "target_text": _extract_text(target_el),
            }
        )
    return rows


def ensure_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_ts TEXT NOT NULL,
            source TEXT NOT NULL,
            project_id TEXT NOT NULL,
            file_prefix TEXT NOT NULL,
            langs TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS items_current (
            item_id TEXT NOT NULL,
            lang TEXT NOT NULL,
            task TEXT NOT NULL,
            source_text TEXT,
            target_text TEXT,
            text_hash TEXT NOT NULL,
            voice TEXT,
            service TEXT,
            source_file TEXT,
            run_id INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (item_id, lang, task)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS item_versions (
            version_id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id TEXT NOT NULL,
            lang TEXT NOT NULL,
            task TEXT NOT NULL,
            source_text TEXT,
            target_text TEXT,
            text_hash TEXT NOT NULL,
            voice TEXT,
            service TEXT,
            source_file TEXT,
            run_id INTEGER NOT NULL,
            change_type TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_item_versions_key ON item_versions(item_id, lang, task)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_item_versions_run ON item_versions(run_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_item_versions_hash ON item_versions(text_hash)")
    conn.commit()


def drop_legacy_tables(conn: sqlite3.Connection) -> None:
    # Legacy table from pre-versioned schema.
    conn.execute("DROP TABLE IF EXISTS items")
    conn.commit()


def reset_versioned_tables(conn: sqlite3.Connection) -> None:
    # Start clean while preserving schema definitions.
    conn.execute("DELETE FROM item_versions")
    conn.execute("DELETE FROM items_current")
    conn.execute("DELETE FROM runs")
    conn.commit()


def load_existing_state(conn: sqlite3.Connection) -> Dict[Tuple[str, str, str], Dict[str, str]]:
    rows = conn.execute(
        "SELECT item_id, lang, task, text_hash, COALESCE(voice, ''), COALESCE(service, '') FROM items_current"
    ).fetchall()
    return {
        (r[0], r[1], r[2]): {"text_hash": (r[3] or ""), "voice": (r[4] or ""), "service": (r[5] or "")}
        for r in rows
    }


def seed_from_translation_master(
    conn: sqlite3.Connection,
    master_path: Path,
    run_id: int,
) -> int:
    if not master_path.exists():
        print(f"⚠️  translation_master.csv not found at {master_path}. Skipping baseline seed.")
        return 0

    try:
        import pandas as pd  # type: ignore
    except Exception as exc:
        print(f"❌ pandas is required to read {master_path}: {exc}")
        return 0

    df = pd.read_csv(master_path)
    if "item_id" not in df.columns:
        print(f"⚠️  Missing item_id column in {master_path}. Skipping baseline seed.")
        return 0

    ignore_cols = {"item_id", "labels", "context", "isHidden"}
    lang_cols = [c for c in df.columns if c not in ignore_cols]

    seeded = 0
    for _, row in df.iterrows():
        item_id = str(row["item_id"])
        for lang in lang_cols:
            text_val = row.get(lang)
            if text_val is None or (isinstance(text_val, float) and str(text_val) == "nan"):
                continue
            text = str(text_val).strip()
            if not text:
                continue
            upsert_item(
                conn,
                item_id=item_id,
                lang=lang,
                task="*",
                source_text="",
                target_text=text,
                text_hash=_sha256(text),
                voice="",
                service="",
                source_file="translation_master.csv",
                run_id=run_id,
            )
            append_item_version(
                conn,
                item_id=item_id,
                lang=lang,
                task="*",
                source_text="",
                target_text=text,
                text_hash=_sha256(text),
                voice="",
                service="",
                source_file="translation_master.csv",
                run_id=run_id,
                change_type="BASELINE_SEED",
            )
            seeded += 1
    conn.commit()
    return seeded


def write_run(conn: sqlite3.Connection, project_id: str, prefix: str, langs: List[str]) -> int:
    run_ts = datetime.now(timezone.utc).isoformat()
    langs_csv = ",".join(langs)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO runs (run_ts, source, project_id, file_prefix, langs) VALUES (?, ?, ?, ?, ?)",
        (run_ts, "crowdin", project_id, prefix, langs_csv),
    )
    conn.commit()
    return int(cur.lastrowid)


def upsert_item(
    conn: sqlite3.Connection,
    *,
    item_id: str,
    lang: str,
    task: str,
    source_text: str,
    target_text: str,
    text_hash: str,
    voice: str,
    service: str,
    source_file: str,
    run_id: int,
) -> None:
    conn.execute(
        """
        INSERT INTO items_current (item_id, lang, task, source_text, target_text, text_hash, voice, service, source_file, run_id, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(item_id, lang, task)
        DO UPDATE SET
            source_text=excluded.source_text,
            target_text=excluded.target_text,
            text_hash=excluded.text_hash,
            voice=excluded.voice,
            service=excluded.service,
            source_file=excluded.source_file,
            run_id=excluded.run_id,
            updated_at=excluded.updated_at
        """,
        (
            item_id,
            lang,
            task,
            source_text,
            target_text,
            text_hash,
            voice,
            service,
            source_file,
            run_id,
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def append_item_version(
    conn: sqlite3.Connection,
    *,
    item_id: str,
    lang: str,
    task: str,
    source_text: str,
    target_text: str,
    text_hash: str,
    voice: str,
    service: str,
    source_file: str,
    run_id: int,
    change_type: str,
) -> None:
    conn.execute(
        """
        INSERT INTO item_versions (
            item_id, lang, task, source_text, target_text, text_hash,
            voice, service, source_file, run_id, change_type, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item_id,
            lang,
            task,
            source_text,
            target_text,
            text_hash,
            voice,
            service,
            source_file,
            run_id,
            change_type,
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def resolve_voice_service(language_map: Dict[str, Dict[str, str]], lang_code: str) -> Tuple[str, str]:
    for cfg in language_map.values():
        if cfg.get("lang_code") == lang_code:
            return cfg.get("voice", ""), cfg.get("service", "")

    # Fallback to base-language match (e.g., es-AR -> es-CO)
    base = (lang_code or "").split("-")[0]
    for cfg in language_map.values():
        cfg_code = cfg.get("lang_code", "")
        if cfg_code.split("-")[0] == base:
            return cfg.get("voice", ""), cfg.get("service", "")

    return "", ""


def load_item_task_map(csv_path: Path) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    if not csv_path.exists():
        return mapping
    try:
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                item_id = str(row.get("item_id") or row.get("identifier") or "").strip()
                task = str(row.get("labels") or row.get("task") or "").strip()
                if item_id and task:
                    mapping[item_id] = task
    except Exception:
        return {}
    return mapping


def seed_from_audio_directory(
    conn: sqlite3.Connection,
    *,
    audio_base_dir: Path,
    lang_code: str,
    run_id: int,
    item_task_map: Optional[Dict[str, str]] = None,
    backfill_task_tag: bool = False,
) -> Dict[str, int]:
    audio_dir = audio_base_dir / lang_code
    stats = {
        "scanned": 0,
        "seeded": 0,
        "missing_metadata": 0,
        "missing_text": 0,
        "task_backfilled": 0,
        "task_backfill_failed": 0,
    }
    if not audio_dir.exists():
        return stats

    for mp3 in sorted(audio_dir.glob("*.mp3")):
        stats["scanned"] += 1
        meta = read_audio_metadata(str(mp3))
        if not meta:
            stats["missing_metadata"] += 1
            continue

        item_id = str(meta.get("title") or mp3.stem).strip()
        mapped_task = (item_task_map or {}).get(item_id, "")
        task = str(meta.get("task") or meta.get("album") or mapped_task or "*").strip() or "*"
        target_text = str(meta.get("text") or "").strip()
        voice = str(meta.get("voice") or "").strip()
        service = str(meta.get("service") or "").strip()
        stored_lang = str(meta.get("lang_code") or "").strip()
        # Prefer explicit target folder language when metadata is generic (e.g., "en")
        # or missing region while requested lang_code is regional (e.g., "en-US").
        if not stored_lang:
            stored_lang = lang_code
        elif "-" in lang_code and stored_lang.split("-")[0] == lang_code.split("-")[0]:
            stored_lang = lang_code
        if not target_text:
            stats["missing_text"] += 1
            continue
        if backfill_task_tag and mapped_task and not str(meta.get("task") or "").strip():
            tags = read_id3_tags(str(mp3))
            tags["task"] = mapped_task
            if write_id3_tags(str(mp3), tags):
                stats["task_backfilled"] += 1
            else:
                stats["task_backfill_failed"] += 1

        text_hash = _sha256(target_text)
        upsert_item(
            conn,
            item_id=item_id,
            lang=stored_lang,
            task=task,
            source_text="",
            target_text=target_text,
            text_hash=text_hash,
            voice=voice,
            service=service,
            source_file=mp3.name,
            run_id=run_id,
        )
        append_item_version(
            conn,
            item_id=item_id,
            lang=stored_lang,
            task=task,
            source_text="",
            target_text=target_text,
            text_hash=text_hash,
            voice=voice,
            service=service,
            source_file=mp3.name,
            run_id=run_id,
            change_type="AUDIO_BASELINE_SEED",
        )
        stats["seeded"] += 1
    conn.commit()
    return stats


def expected_audio_path(audio_base_dir: str, lang: str, item_id: str) -> str:
    return str(Path(audio_base_dir) / lang / f"{item_id}.mp3")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate regeneration report from itembank_by_task XLIFF files.")
    parser.add_argument("--project-id", default=os.getenv("CROWDIN_PROJECT_ID") or os.getenv("CROWDIN_LEVANTE_PID"))
    parser.add_argument("--langs", nargs="+", default=["all"], help='Language codes or "all"')
    parser.add_argument("--crowdin-prefix", default="itembank_by_task/")
    parser.add_argument("--output-dir", default="tmp/itembank_by_task_xliff")
    parser.add_argument("--db-path", default="tmp/itembank_by_task_regen.sqlite")
    parser.add_argument("--report-dir", default="tmp/itembank_by_task_reports")
    parser.add_argument("--audio-base-dir", default="audio_files")
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--skip-audio-check", action="store_true")
    parser.add_argument("--no-update-db", action="store_true")
    parser.add_argument("--baseline-from", choices=["none", "master"], default="none")
    parser.add_argument("--master-path", default="translation_master.csv")
    parser.add_argument("--gcs-sync", action="store_true", help="Sync SQLite baseline to GCS (download before run, upload after).")
    parser.add_argument("--gcs-bucket", default=os.getenv("GCS_BASELINE_BUCKET", "levante-assets-draft"))
    parser.add_argument("--gcs-path", default=os.getenv("GCS_BASELINE_PATH", "baselines/itembank_by_task_regen.sqlite"))
    parser.add_argument("--reset-db", action="store_true", help="Delete current runs/snapshots and start clean with versioned tables.")
    parser.add_argument("--seed-audio-lang", nargs="+", default=[], help="Seed baseline from local audio_files metadata for these language codes (e.g. en-US).")
    parser.add_argument("--seed-audio-dir", default="audio_files", help="Base directory that contains per-language audio folders.")
    parser.add_argument("--audio-seed-only", action="store_true", help="Only seed DB from local audio metadata; skip Crowdin download/parse.")
    parser.add_argument("--task-map-csv", default=conf.item_bank_translations, help="CSV path used to map item_id -> task (labels) during audio seeding.")
    parser.add_argument("--backfill-task-tag", action="store_true", help="When audio metadata lacks task, write ID3 task tag using --task-map-csv.")
    parser.add_argument("--verbose", action="store_true")

    args = parser.parse_args()
    _load_env()
    _strip_env_vars(["CROWDIN_API_TOKEN", "CROWDIN_PROJECT_ID", "CROWDIN_LEVANTE_PID"])

    if not args.project_id:
        args.project_id = os.getenv("CROWDIN_PROJECT_ID") or os.getenv("CROWDIN_LEVANTE_PID")
    if not args.project_id and not args.audio_seed_only:
        print("❌ Missing project id. Set --project-id or CROWDIN_PROJECT_ID/CROWDIN_LEVANTE_PID.")
        return 1

    prefix = _normalize_prefix(args.crowdin_prefix)
    output_dir = Path(args.output_dir)
    report_dir = Path(args.report_dir)
    db_path = Path(args.db_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    matched: List[Dict[str, str]] = []
    langs: List[str] = []
    if not args.audio_seed_only:
        token = get_crowdin_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        files = list_project_files(args.project_id, headers)
        for file_data in files:
            data = file_data["data"]
            path = data.get("path", "").lstrip("/")
            if path.startswith(prefix):
                matched.append(data)

        if not matched:
            print(f"❌ No Crowdin files found under '{prefix}'")
            return 1

        langs = args.langs
        if len(langs) == 1 and langs[0] == "all":
            lang_rows = list_project_languages(args.project_id, headers)
            langs = [row["data"]["id"] for row in lang_rows]
        langs = [lang.strip() for lang in langs if lang.strip()]

        if not langs:
            print("❌ No languages selected.")
            return 1

        if not args.skip_download:
            for file_info in matched:
                file_id = file_info["id"]
                base_name = os.path.splitext(os.path.basename(file_info["path"]))[0]
                for lang in langs:
                    out_path = output_dir / f"{base_name}-{lang}.xliff"
                    ok = download_xliff_file(args.project_id, headers, file_id, lang, str(out_path), format="xliff")
                    if not ok:
                        print(f"⚠️  Failed download: {file_info['path']} ({lang})")
    else:
        langs = [lang.strip() for lang in args.seed_audio_lang if lang.strip()]
        if not langs:
            print("❌ --audio-seed-only requires at least one --seed-audio-lang value.")
            return 1

    gcs_generation = None
    if args.gcs_sync:
        client = _init_gcs_client()
        if client is None:
            print("❌ google-cloud-storage not available or credentials missing; cannot use --gcs-sync.")
            return 1
        gcs_generation = _gcs_pull_db(client, args.gcs_bucket, args.gcs_path, Path(args.db_path))

    conn = sqlite3.connect(db_path)
    ensure_db(conn)
    drop_legacy_tables(conn)
    if args.reset_db:
        print("🧹 Resetting versioned SQLite tables (--reset-db)")
        reset_versioned_tables(conn)
    run_id = write_run(conn, args.project_id or "audio-seed", prefix or "audio-seed/", langs)
    try:
        language_dict = conf.get_languages()
    except Exception:
        language_dict = {}
    if args.baseline_from == "master":
        seeded = seed_from_translation_master(conn, Path(args.master_path), run_id)
        print(f"Seeded baseline rows from translation_master.csv: {seeded}")
    if args.seed_audio_lang:
        if args.no_update_db:
            print("⚠️  --seed-audio-lang ignored because --no-update-db is set.")
        else:
            item_task_map = load_item_task_map(Path(args.task_map_csv))
            if item_task_map:
                print(f"Loaded task map entries: {len(item_task_map)} from {args.task_map_csv}")
            for audio_lang in args.seed_audio_lang:
                stats = seed_from_audio_directory(
                    conn,
                    audio_base_dir=Path(args.seed_audio_dir),
                    lang_code=audio_lang,
                    run_id=run_id,
                    item_task_map=item_task_map,
                    backfill_task_tag=args.backfill_task_tag,
                )
                print(
                    f"Seeded audio metadata for {audio_lang}: "
                    f"scanned={stats['scanned']}, seeded={stats['seeded']}, "
                    f"missing_metadata={stats['missing_metadata']}, missing_text={stats['missing_text']}, "
                    f"task_backfilled={stats['task_backfilled']}, task_backfill_failed={stats['task_backfill_failed']}"
                )
    if args.audio_seed_only:
        conn.close()
        print("✅ Audio metadata seeding complete.")
        print(f"SQLite: {db_path}")
        return 0
    existing_state = load_existing_state(conn)

    report_rows: List[Dict[str, str]] = []
    change_counts: Dict[str, int] = {}

    for xliff_path in sorted(output_dir.glob("*.xliff")):
        name = xliff_path.stem
        if "-" not in name:
            continue
        base, lang = name.rsplit("-", 1)
        task = base
        if lang not in langs:
            continue

        rows = parse_xliff_file(xliff_path)
        if args.verbose:
            print(f"Parsed {len(rows)} items from {xliff_path.name}")

        for row in rows:
            item_id = row["item_id"]
            target_text = row["target_text"]
            source_text = row["source_text"]
            key = (item_id, lang, task)
            new_hash = _sha256(target_text or "")
            voice, service = resolve_voice_service(language_dict, lang)
            old_state = existing_state.get(key)
            if not old_state:
                old_state = existing_state.get((item_id, lang, "*"))
            old_hash = (old_state or {}).get("text_hash", "")
            old_voice = (old_state or {}).get("voice", "")
            old_service = (old_state or {}).get("service", "")

            reasons: List[str] = []
            if not target_text:
                reasons.append("MISSING_TRANSLATION")
            if not old_hash:
                reasons.append("NEW_ITEM")
            elif new_hash != old_hash:
                reasons.append("TEXT_CHANGED")
            if old_hash and voice and old_voice and voice != old_voice:
                reasons.append("VOICE_CHANGED")
            if old_hash and service and old_service and service != old_service:
                reasons.append("SERVICE_CHANGED")

            audio_path = expected_audio_path(args.audio_base_dir, lang, item_id)
            if not args.skip_audio_check and target_text and not os.path.exists(audio_path):
                reasons.append("MISSING_AUDIO")

            if reasons:
                for r in reasons:
                    change_counts[r] = change_counts.get(r, 0) + 1
                report_rows.append(
                    {
                        "item_id": item_id,
                        "lang": lang,
                        "task": task,
                        "reasons": ",".join(sorted(set(reasons))),
                        "audio_path": audio_path,
                        "source_file": xliff_path.name,
                        "source_text": source_text,
                        "target_text": target_text,
                    }
                )

            if not args.no_update_db:
                change_types = [r for r in reasons if r in {"NEW_ITEM", "TEXT_CHANGED", "VOICE_CHANGED", "SERVICE_CHANGED"}]
                upsert_item(
                    conn,
                    item_id=item_id,
                    lang=lang,
                    task=task,
                    source_text=source_text,
                    target_text=target_text,
                    text_hash=new_hash,
                    voice=voice,
                    service=service,
                    source_file=xliff_path.name,
                    run_id=run_id,
                )
                existing_state[key] = {"text_hash": new_hash, "voice": voice, "service": service}
                for change_type in change_types:
                    append_item_version(
                        conn,
                        item_id=item_id,
                        lang=lang,
                        task=task,
                        source_text=source_text,
                        target_text=target_text,
                        text_hash=new_hash,
                        voice=voice,
                        service=service,
                        source_file=xliff_path.name,
                        run_id=run_id,
                        change_type=change_type,
                    )

    if not args.no_update_db:
        conn.commit()
    conn.close()

    if args.gcs_sync:
        try:
            _gcs_push_db(client, args.gcs_bucket, args.gcs_path, Path(args.db_path), generation=gcs_generation)
            print(f"✅ GCS baseline synced: gs://{args.gcs_bucket}/{args.gcs_path}")
        except Exception as exc:
            print(f"⚠️  Failed to sync GCS baseline: {exc}")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_csv = report_dir / f"regen_report_{timestamp}.csv"
    report_json = report_dir / f"regen_report_{timestamp}.json"
    report_md = report_dir / f"regen_report_{timestamp}.md"

    if report_rows:
        import csv
        import json

        with open(report_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=report_rows[0].keys())
            writer.writeheader()
            writer.writerows(report_rows)

        with open(report_json, "w", encoding="utf-8") as f:
            json.dump(report_rows, f, ensure_ascii=False, indent=2)
    
    # Human-readable report (always emit)
    def _write_markdown_report(rows: List[Dict[str, str]]) -> None:
        from collections import defaultdict

        by_reason = defaultdict(list)
        by_lang = defaultdict(int)
        by_task = defaultdict(int)
        for row in rows:
            reasons = row.get("reasons", "")
            for reason in reasons.split(","):
                if reason:
                    by_reason[reason].append(row)
            by_lang[row.get("lang", "")] += 1
            by_task[row.get("task", "")] += 1

        def _top_items(items: List[Dict[str, str]], limit: int = 20) -> List[Dict[str, str]]:
            return items[:limit]

        lines: List[str] = []
        lines.append("# Itembank Regen Report")
        lines.append("")
        lines.append(f"- Generated: {datetime.now(timezone.utc).isoformat()}")
        lines.append(f"- Total rows: {len(rows)}")
        if rows:
            lines.append("")
            lines.append("## Counts by reason")
            for reason, items in sorted(by_reason.items()):
                lines.append(f"- {reason}: {len(items)}")
            lines.append("")
            lines.append("## Counts by language")
            for lang, count in sorted(by_lang.items()):
                if lang:
                    lines.append(f"- {lang}: {count}")
            lines.append("")
            lines.append("## Counts by task")
            for task, count in sorted(by_task.items()):
                if task:
                    lines.append(f"- {task}: {count}")
            lines.append("")
            for reason, items in sorted(by_reason.items()):
                lines.append(f"## Sample items: {reason}")
                lines.append("")
                for row in _top_items(items):
                    lines.append(
                        f"- `{row.get('task','')}` `{row.get('item_id','')}` "
                        f"({row.get('lang','')}) — {row.get('target_text','')[:120]}"
                    )
                lines.append("")
        else:
            lines.append("")
            lines.append("## No changes detected")
            lines.append("")
            lines.append("No items require regeneration based on the current snapshot.")

        report_md.write_text("\n".join(lines), encoding="utf-8")

    _write_markdown_report(report_rows)

    print("✅ Regeneration report complete.")
    print(f"Report rows: {len(report_rows)}")
    for reason, count in sorted(change_counts.items()):
        print(f"  - {reason}: {count}")
    if report_rows:
        print(f"CSV: {report_csv}")
        print(f"JSON: {report_json}")
    print(f"MD: {report_md}")
    print(f"SQLite: {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
