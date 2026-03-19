#!/usr/bin/env python3
"""
Build partner-audio-dashboard.json from items_current (XLIFF / itembank SQLite).

Same row shape as the legacy item-bank CSV pivot: item_id, labels, per-lang columns,
plus `text` and `en` for English source (partner UI).

Usage:
  python utilities/partner_itembank_export.py --db-path tmp/itembank_by_task_regen.sqlite \\
      --output tmp/partner_itembank_audio_dashboard.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import utilities.config as conf
import utilities.utilities as u


def load_items_from_sqlite(db_path: Path, language_dict: Optional[Dict] = None) -> List[Dict[str, Any]]:
    """Mirror generate_speech._load_translation_data_from_sqlite row shape (dict records)."""
    if not db_path.is_file():
        raise FileNotFoundError(str(db_path))

    conn = sqlite3.connect(str(db_path))
    try:
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            ("items_current",),
        ).fetchone()
        if not table_exists:
            raise ValueError("SQLite DB is missing table items_current")
        rows = conn.execute(
            "SELECT item_id, task, lang, source_text, target_text FROM items_current"
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return []

    items: Dict[str, Dict[str, Any]] = {}
    for item_id, task, lang, source_text, target_text in rows:
        if item_id is None or lang is None:
            continue
        sid = str(item_id).strip()
        item = items.setdefault(sid, {"item_id": sid})
        if task and not item.get("labels"):
            item["labels"] = str(task).strip()
        text_val = target_text if target_text not in (None, "") else source_text
        if text_val not in (None, ""):
            item[str(lang)] = str(text_val)

    df = pd.DataFrame(list(items.values()))
    if df.empty:
        return []
    df = u.normalize_language_columns(df)

    lang_cfg = language_dict or {}
    for lang_key in lang_cfg.values():
        lang_code = lang_key.get("lang_code")
        if lang_code and lang_code not in df.columns:
            df[lang_code] = None

    df = df.fillna("")
    records = df.to_dict(orient="records")

    for rec in records:
        iid = rec.get("item_id")
        if iid is not None:
            rec["item_id"] = str(iid).strip()
        en_text = (
            rec.get("en-US")
            or rec.get("en-GB")
            or rec.get("en-GH")
            or rec.get("en")
            or ""
        )
        if isinstance(en_text, str):
            en_text = en_text.strip()
        else:
            en_text = str(en_text or "").strip()
        rec["text"] = en_text
        rec["en"] = en_text

    return records


def build_payload(db_path: Path, language_dict: Optional[Dict] = None) -> Dict[str, Any]:
    items = load_items_from_sqlite(db_path, language_dict=language_dict)
    return {
        "version": 1,
        "source": "itembank_sqlite_xliff",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "item_count": len(items),
        "items": items,
    }


def write_json(payload: Dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))


def upload_to_gcs(local_path: Path, bucket: str, object_path: str) -> None:
    from google.cloud import storage  # type: ignore
    from google.oauth2 import service_account  # type: ignore

    import os

    credentials_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

    if credentials_json:
        credentials_dict = json.loads(credentials_json)
        creds = service_account.Credentials.from_service_account_info(credentials_dict)
        client = storage.Client(credentials=creds, project=credentials_dict.get("project_id"))
    elif creds_path and Path(creds_path).is_file():
        creds = service_account.Credentials.from_service_account_file(creds_path)
        client = storage.Client(credentials=creds)
    else:
        # Application Default Credentials (e.g. gcloud auth application-default login)
        client = storage.Client()
    bucket_ref = client.bucket(bucket)
    blob = bucket_ref.blob(object_path)
    blob.upload_from_filename(
        str(local_path),
        content_type="application/json; charset=utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Export partner audio dashboard JSON from itembank SQLite.")
    parser.add_argument("--db-path", default="tmp/itembank_by_task_regen.sqlite")
    parser.add_argument("--output", default="tmp/partner_itembank_audio_dashboard.json")
    parser.add_argument("--upload-gcs", action="store_true", help="Upload JSON to GCS after write")
    parser.add_argument("--gcs-bucket", default=None, help="Default: GCS_BASELINE_BUCKET or levante-assets-draft")
    parser.add_argument(
        "--gcs-object",
        default="translations/partner-itembank-audio-dashboard.json",
        help="Object path inside bucket",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path)
    out_path = Path(args.output)

    try:
        language_dict = conf.get_languages()
    except Exception:
        language_dict = {}

    payload = build_payload(db_path, language_dict=language_dict or None)
    write_json(payload, out_path)
    print(f"✅ Wrote {payload['item_count']} items → {out_path.resolve()}")

    if args.upload_gcs:
        import os

        bucket = args.gcs_bucket or os.getenv("GCS_BASELINE_BUCKET", "levante-assets-draft")
        upload_to_gcs(out_path, bucket, args.gcs_object)
        print(f"✅ Uploaded gs://{bucket}/{args.gcs_object}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
