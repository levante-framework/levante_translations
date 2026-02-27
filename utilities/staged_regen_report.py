#!/usr/bin/env python3
"""
Generate a regeneration report from staged XLIFF rows.

This script is intended to run after staged import:
  utilities/itembank_by_task_regen_report.py --import-staged ...

It compares items_staged against items_current and emits:
  - Markdown summary (human-readable)
  - CSV details
  - JSON details
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import textwrap
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Dict, List, Tuple

# Ensure repo root is on sys.path so `utilities` resolves to package.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _expected_audio_path(audio_base_dir: str, lang: str, item_id: str) -> str:
    return str(Path(audio_base_dir) / lang / f"{item_id}.mp3")


def _write_basic_pdf_report(
    pdf_path: Path,
    report_rows: List[Dict[str, str]],
    counts: Dict[str, int],
    by_lang: Dict[str, int],
    by_task: Dict[str, int],
) -> None:
    def pdf_escape(s: str) -> str:
        s = s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        return s.encode("latin-1", "replace").decode("latin-1")

    lines: List[str] = []
    lines.append("Staged Regen Report")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"Total rows: {len(report_rows)}")
    lines.append("")
    lines.append("Counts by reason")
    for reason, n in sorted(counts.items()):
        lines.append(f"- {reason}: {n}")
    lines.append("")
    lines.append("Counts by language")
    for lang, n in sorted(by_lang.items()):
        lines.append(f"- {lang}: {n}")
    lines.append("")
    lines.append("Counts by task")
    for task, n in sorted(by_task.items()):
        lines.append(f"- {task}: {n}")
    lines.append("")
    lines.append("All proposed regeneration items")
    for idx, row in enumerate(report_rows, 1):
        lines.extend(textwrap.wrap(f"{idx}. {row.get('item_id','')} | {row.get('lang','')} | {row.get('task','')} | {row.get('reasons','')}", width=95))
        lines.extend(textwrap.wrap(f"audio_path: {row.get('audio_path','')}", width=95))
        lines.extend(textwrap.wrap(f"source_file: {row.get('source_file','')}", width=95))
        lines.extend(textwrap.wrap(f"target_text: {row.get('target_text','')}", width=95))
        lines.append("")

    lines_per_page = 48
    pages = [lines[i:i + lines_per_page] for i in range(0, len(lines), lines_per_page)] or [[]]

    objects: Dict[int, bytes] = {}
    obj_id = 1
    catalog_id = obj_id
    obj_id += 1
    pages_id = obj_id
    obj_id += 1
    font_id = obj_id
    obj_id += 1

    page_ids: List[int] = []
    content_ids: List[int] = []
    for _ in pages:
        page_ids.append(obj_id)
        obj_id += 1
        content_ids.append(obj_id)
        obj_id += 1

    objects[font_id] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    for idx, page_lines in enumerate(pages):
        content_parts = ["BT", "/F1 10 Tf", "40 760 Td"]
        first = True
        for line in page_lines:
            safe = pdf_escape(line)
            if first:
                content_parts.append(f"({safe}) Tj")
                first = False
            else:
                content_parts.append("0 -14 Td")
                content_parts.append(f"({safe}) Tj")
        content_parts.append("ET")
        content_stream = "\n".join(content_parts).encode("latin-1", "replace")
        content_obj = b"<< /Length " + str(len(content_stream)).encode("ascii") + b" >>\nstream\n" + content_stream + b"\nendstream"
        objects[content_ids[idx]] = content_obj
        page_obj = (
            f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_ids[idx]} 0 R >>"
        ).encode("ascii")
        objects[page_ids[idx]] = page_obj

    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects[pages_id] = f"<< /Type /Pages /Kids [ {kids} ] /Count {len(page_ids)} >>".encode("ascii")
    objects[catalog_id] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("ascii")

    out = bytearray()
    out.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: Dict[int, int] = {}
    for oid in sorted(objects.keys()):
        offsets[oid] = len(out)
        out.extend(f"{oid} 0 obj\n".encode("ascii"))
        out.extend(objects[oid])
        out.extend(b"\nendobj\n")

    xref_pos = len(out)
    max_id = max(objects.keys())
    out.extend(f"xref\n0 {max_id + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for oid in range(1, max_id + 1):
        off = offsets.get(oid, 0)
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        (
            "trailer\n"
            f"<< /Size {max_id + 1} /Root {catalog_id} 0 R >>\n"
            "startxref\n"
            f"{xref_pos}\n"
            "%%EOF\n"
        ).encode("ascii")
    )
    pdf_path.write_bytes(bytes(out))


def _write_html_report(
    html_path: Path,
    report_rows: List[Dict[str, str]],
    counts: Dict[str, int],
    by_lang: Dict[str, int],
    by_task: Dict[str, int],
) -> None:
    html_lines: List[str] = []
    html_lines.append("<!doctype html>")
    html_lines.append("<html><head><meta charset='utf-8'>")
    html_lines.append("<title>Staged Regen Report</title>")
    html_lines.append(
        "<style>"
        "body{font-family:Arial,sans-serif;margin:24px;line-height:1.4;color:#1f2937}"
        "h1{margin:0 0 6px 0;font-size:26px}"
        ".muted{color:#6b7280}"
        ".grid{display:grid;grid-template-columns:repeat(3,minmax(220px,1fr));gap:12px;margin:18px 0}"
        ".card{border:1px solid #e5e7eb;border-radius:8px;padding:10px 12px;background:#fff}"
        ".card h3{margin:0 0 8px 0;font-size:14px}"
        ".card ul{margin:0;padding-left:16px}"
        "table{border-collapse:collapse;width:100%;font-size:12px;table-layout:fixed}"
        "th,td{border:1px solid #e5e7eb;padding:6px;vertical-align:top;word-wrap:break-word}"
        "th{background:#f9fafb;position:sticky;top:0}"
        "tr:nth-child(even){background:#fcfcfd}"
        ".small{font-size:11px;color:#4b5563}"
        "</style>"
    )
    html_lines.append("</head><body>")
    html_lines.append("<h1>Staged Regen Report</h1>")
    html_lines.append(f"<div class='muted'>Generated: {escape(datetime.now(timezone.utc).isoformat())}</div>")
    html_lines.append(f"<div><strong>Total proposed regenerations:</strong> {len(report_rows)}</div>")
    if report_rows:
        html_lines.append("<div class='grid'>")
        html_lines.append("<div class='card'><h3>Counts by reason</h3><ul>")
        for reason, n in sorted(counts.items()):
            html_lines.append(f"<li>{escape(reason)}: {n}</li>")
        html_lines.append("</ul></div>")
        html_lines.append("<div class='card'><h3>Counts by language</h3><ul>")
        for lang, n in sorted(by_lang.items()):
            html_lines.append(f"<li>{escape(lang)}: {n}</li>")
        html_lines.append("</ul></div>")
        html_lines.append("<div class='card'><h3>Counts by task</h3><ul>")
        for task, n in sorted(by_task.items()):
            html_lines.append(f"<li>{escape(task)}: {n}</li>")
        html_lines.append("</ul></div>")
        html_lines.append("</div>")
        html_lines.append("<h2>All Proposed Regeneration Items</h2>")
        html_lines.append("<table><thead><tr>")
        for col in ["item_id", "lang", "task", "reasons", "audio_path", "source_file", "source_text", "target_text"]:
            html_lines.append(f"<th>{escape(col)}</th>")
        html_lines.append("</tr></thead><tbody>")
        for row in report_rows:
            html_lines.append("<tr>")
            for col in ["item_id", "lang", "task", "reasons", "audio_path", "source_file", "source_text", "target_text"]:
                html_lines.append(f"<td>{escape(str(row.get(col, '')))}</td>")
            html_lines.append("</tr>")
        html_lines.append("</tbody></table>")
    else:
        html_lines.append("<h2>No changes detected</h2>")
        html_lines.append("<p>No staged items require regeneration.</p>")
    html_lines.append("</body></html>")
    html_path.write_text("\n".join(html_lines), encoding="utf-8")


def _write_pdf_via_chrome(pdf_path: Path, html_path: Path) -> bool:
    browser = None
    for cand in ("google-chrome", "chromium", "chromium-browser", "chrome"):
        path = shutil.which(cand)
        if path:
            browser = path
            break
    if not browser:
        return False

    cmd = [
        browser,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        f"--print-to-pdf={str(pdf_path)}",
        str(html_path.resolve().as_uri()),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0 and pdf_path.exists()


def _load_current_by_item_lang(conn: sqlite3.Connection) -> Dict[Tuple[str, str], Dict[str, str]]:
    rows = conn.execute(
        """
        SELECT item_id, lang, task, text_hash, COALESCE(voice, ''), COALESCE(service, '')
        FROM items_current
        """
    ).fetchall()
    merged: Dict[Tuple[str, str], Dict[str, str]] = {}
    for item_id, lang, task, text_hash, voice, service in rows:
        key = (item_id, lang)
        val = {"task": task or "", "text_hash": text_hash or "", "voice": voice or "", "service": service or ""}
        if key not in merged:
            merged[key] = val
            continue
        if merged[key].get("task") == "*" and val.get("task") != "*":
            merged[key] = val
    return merged


def _normalize_lang_candidates(lang: str) -> List[str]:
    base = (lang or "").split("-")[0]
    candidates = [lang]
    if base and base != lang:
        candidates.append(base)
    # Common mapping in this project.
    if lang == "de-DE":
        candidates.append("de")
    if lang == "en-US":
        candidates.append("en")
    if lang == "es-CO":
        candidates.append("es")
    return candidates


def _load_expected_voice_service_from_local_config() -> Dict[str, Dict[str, str]]:
    expected: Dict[str, Dict[str, str]] = {}
    try:
        import utilities.config as conf  # type: ignore
        langs = conf.get_languages()
    except Exception:
        return expected
    for lang_cfg in langs.values():
        code = str(lang_cfg.get("lang_code") or "").strip()
        if not code:
            continue
        expected[code] = {
            "voice": str(lang_cfg.get("voice") or "").strip(),
            "service": str(lang_cfg.get("service") or "").strip(),
        }
    return expected


def _load_expected_voice_service_from_dashboard_config(config_js_path: str) -> Dict[str, Dict[str, str]]:
    cfg_path = Path(config_js_path)
    if not cfg_path.exists():
        return {}
    node_script = (
        "const p=process.argv[1];"
        "const m=require(p);"
        "const root=(m&&m.CONFIG&&m.CONFIG.languages)?m.CONFIG.languages:((m&&m.languages)?m.languages:{});"
        "console.log(JSON.stringify(root));"
    )
    try:
        result = subprocess.run(
            ["node", "-e", node_script, str(cfg_path)],
            capture_output=True,
            text=True,
            check=True,
        )
        raw = json.loads(result.stdout.strip() or "{}")
    except Exception:
        return {}

    expected: Dict[str, Dict[str, str]] = {}
    for _name, data in raw.items():
        if not isinstance(data, dict):
            continue
        code = str(data.get("lang_code") or "").strip()
        if not code:
            continue
        expected[code] = {
            "voice": str(data.get("voice") or "").strip(),
            "service": str(data.get("service") or "").strip(),
        }
    return expected


def _load_expected_voice_service_from_dashboard_api(api_url: str) -> Dict[str, Dict[str, str]]:
    try:
        with urllib.request.urlopen(api_url, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {}

    raw = payload.get("languages") if isinstance(payload, dict) else None
    if not isinstance(raw, dict):
        return {}

    expected: Dict[str, Dict[str, str]] = {}
    for _name, data in raw.items():
        if not isinstance(data, dict):
            continue
        code = str(data.get("lang_code") or "").strip()
        if not code:
            continue
        expected[code] = {
            "voice": str(data.get("voice") or "").strip(),
            "service": str(data.get("service") or "").strip(),
        }
    return expected


def _load_expected_voice_service_from_bucket_url(bucket_url: str) -> Dict[str, Dict[str, str]]:
    try:
        with urllib.request.urlopen(bucket_url, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {}

    raw = payload.get("languages") if isinstance(payload, dict) else None
    if not isinstance(raw, dict):
        return {}

    expected: Dict[str, Dict[str, str]] = {}
    for _name, data in raw.items():
        if not isinstance(data, dict):
            continue
        code = str(data.get("lang_code") or "").strip()
        if not code:
            continue
        expected[code] = {
            "voice": str(data.get("voice") or "").strip(),
            "service": str(data.get("service") or "").strip(),
        }
    return expected


def _expected_for_lang(expected_map: Dict[str, Dict[str, str]], lang: str) -> Dict[str, str]:
    for candidate in _normalize_lang_candidates(lang):
        if candidate in expected_map:
            return expected_map[candidate]
    return {"voice": "", "service": ""}


def _default_dashboard_config_path() -> str:
    candidates = [
        REPO_ROOT / "levante-web-dashboard" / "config.js",
        REPO_ROOT / "web-dashboard" / "config.js",
        REPO_ROOT.parent / "levante-web-dashboard" / "config.js",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return str(candidates[0])


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate report of items requiring audio regeneration from items_staged.")
    parser.add_argument("--db-path", default="tmp/itembank_by_task_regen.sqlite")
    parser.add_argument("--report-dir", default="tmp/itembank_by_task_reports")
    parser.add_argument("--audio-base-dir", default="audio_files")
    parser.add_argument("--langs", nargs="+", default=["all"], help='Language codes to include or "all".')
    parser.add_argument("--voice-config-source", choices=["local", "dashboard", "dashboard_api"], default="local",
                        help="Source of expected voice/service config for VOICE_CHANGED checks.")
    parser.add_argument("--dashboard-config-path", default=_default_dashboard_config_path(),
                        help="Path to sibling dashboard config.js when --voice-config-source=dashboard.")
    parser.add_argument("--dashboard-api-url", default="https://levante-pitwall.vercel.app/api/language-config",
                        help="Dashboard language-config API URL when --voice-config-source=dashboard_api.")
    parser.add_argument("--language-config-bucket-url",
                        default=os.getenv("LANGUAGE_CONFIG_BUCKET_URL", "https://storage.googleapis.com/levante-audio-dev/language_config.json"),
                        help="Public bucket URL for language_config.json fallback.")
    args = parser.parse_args()

    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"❌ DB not found: {db_path}")
        return 1

    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        staged = conn.execute(
            """
            SELECT item_id, lang, task, source_text, target_text, text_hash, source_file
            FROM items_staged
            """
        ).fetchall()
        current_exact_rows = conn.execute(
            """
            SELECT item_id, lang, task, text_hash, COALESCE(voice, ''), COALESCE(service, '')
            FROM items_current
            """
        ).fetchall()
    finally:
        conn.close()

    if not staged:
        print("⚠️  No rows in items_staged. Run staged import first.")
        return 1

    langs_filter = set(args.langs)
    if "all" in langs_filter:
        langs_filter = set()

    current_exact = {
        (r[0], r[1], r[2]): {"text_hash": (r[3] or ""), "voice": (r[4] or ""), "service": (r[5] or "")}
        for r in current_exact_rows
    }

    if args.voice_config_source == "dashboard":
        expected_map = _load_expected_voice_service_from_dashboard_config(args.dashboard_config_path)
    elif args.voice_config_source == "dashboard_api":
        expected_map = _load_expected_voice_service_from_dashboard_api(args.dashboard_api_url)
        if not expected_map:
            expected_map = _load_expected_voice_service_from_bucket_url(args.language_config_bucket_url)
        if not expected_map:
            expected_map = _load_expected_voice_service_from_local_config()
    else:
        expected_map = _load_expected_voice_service_from_local_config()

    # Build fallback map from exact rows to avoid another DB call.
    current_by_item_lang: Dict[Tuple[str, str], Dict[str, str]] = {}
    for item_id, lang, task, text_hash, voice, service in current_exact_rows:
        key = (item_id, lang)
        val = {"task": task or "", "text_hash": text_hash or "", "voice": voice or "", "service": service or ""}
        if key not in current_by_item_lang or (current_by_item_lang[key].get("task") == "*" and val["task"] != "*"):
            current_by_item_lang[key] = val

    report_rows: List[Dict[str, str]] = []
    counts = defaultdict(int)

    for item_id, lang, task, source_text, target_text, text_hash, source_file in staged:
        if langs_filter and lang not in langs_filter:
            continue

        staged_hash = text_hash or ""
        exact_state = current_exact.get((item_id, lang, task))
        effective_state = exact_state
        if effective_state is None:
            fallback = current_by_item_lang.get((item_id, lang))
            effective_state = fallback if fallback else None

        reasons: List[str] = []
        if effective_state is None:
            reasons.append("NEW_ITEM")
        else:
            effective_hash = effective_state.get("text_hash", "")
            if staged_hash != (effective_hash or ""):
                reasons.append("TEXT_CHANGED")

            expected = _expected_for_lang(expected_map, lang)
            expected_voice = expected.get("voice", "")
            expected_service = expected.get("service", "")
            current_voice = effective_state.get("voice", "")
            current_service = effective_state.get("service", "")
            if expected_voice and current_voice and current_voice != expected_voice:
                reasons.append("VOICE_CHANGED")
            if expected_service and current_service and current_service != expected_service:
                reasons.append("SERVICE_CHANGED")

        audio_path = _expected_audio_path(args.audio_base_dir, lang, item_id)
        if target_text and not os.path.exists(audio_path):
            reasons.append("MISSING_AUDIO")

        if reasons:
            reason_set = ",".join(sorted(set(reasons)))
            report_rows.append(
                {
                    "item_id": item_id,
                    "lang": lang,
                    "task": task,
                    "reasons": reason_set,
                    "audio_path": audio_path,
                    "source_file": source_file or "",
                    "source_text": source_text or "",
                    "target_text": target_text or "",
                }
            )
            for reason in set(reasons):
                counts[reason] += 1

    ts = _now_ts()
    csv_path = report_dir / f"staged_regen_report_{ts}.csv"
    json_path = report_dir / f"staged_regen_report_{ts}.json"
    md_path = report_dir / f"staged_regen_report_{ts}.md"
    html_path = report_dir / f"staged_regen_report_{ts}.html"
    pdf_path = report_dir / f"staged_regen_report_{ts}.pdf"

    if report_rows:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=report_rows[0].keys())
            writer.writeheader()
            writer.writerows(report_rows)
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(report_rows, f, ensure_ascii=False, indent=2)

    by_reason = defaultdict(list)
    by_lang = defaultdict(int)
    by_task = defaultdict(int)
    for row in report_rows:
        for reason in row.get("reasons", "").split(","):
            if reason:
                by_reason[reason].append(row)
        by_lang[row["lang"]] += 1
        by_task[row["task"]] += 1

    lines: List[str] = []
    lines.append("# Staged Regen Report")
    lines.append("")
    lines.append(f"- Generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"- Total rows: {len(report_rows)}")
    lines.append("")
    if report_rows:
        lines.append("## Counts by reason")
        for reason, n in sorted(counts.items()):
            lines.append(f"- {reason}: {n}")
        lines.append("")
        lines.append("## Counts by language")
        for lang, n in sorted(by_lang.items()):
            lines.append(f"- {lang}: {n}")
        lines.append("")
        lines.append("## Counts by task")
        for task, n in sorted(by_task.items()):
            lines.append(f"- {task}: {n}")
        lines.append("")
        for reason, items in sorted(by_reason.items()):
            lines.append(f"## All items: {reason}")
            lines.append("")
            for row in items:
                lines.append(
                    f"- `{row['task']}` `{row['item_id']}` ({row['lang']}) — {row['target_text'][:120]}"
                )
            lines.append("")
    else:
        lines.append("## No changes detected")
        lines.append("")
        lines.append("No staged items require regeneration.")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    _write_html_report(
        html_path=html_path,
        report_rows=report_rows,
        counts=dict(counts),
        by_lang=dict(by_lang),
        by_task=dict(by_task),
    )

    rendered = _write_pdf_via_chrome(pdf_path=pdf_path, html_path=html_path)
    if not rendered:
        _write_basic_pdf_report(
            pdf_path=pdf_path,
            report_rows=report_rows,
            counts=dict(counts),
            by_lang=dict(by_lang),
            by_task=dict(by_task),
        )

    # Keep outputs focused on requested format.
    if html_path.exists():
        try:
            html_path.unlink()
        except OSError:
            pass

    print("✅ Staged regeneration report complete.")
    print(f"Report rows: {len(report_rows)}")
    for reason, n in sorted(counts.items()):
        print(f"  - {reason}: {n}")
    if report_rows:
        print(f"CSV: {csv_path}")
        print(f"JSON: {json_path}")
    print(f"MD: {md_path}")
    print(f"PDF: {pdf_path} ({'html-rendered' if rendered else 'basic-fallback'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
