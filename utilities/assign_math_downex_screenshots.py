#!/usr/bin/env python3
"""Attach math downward-extension pictures to their Crowdin strings.

Each picture item becomes one screenshot, tagged to the Crowdin string whose
identifier is that item's audio file. Choice items show the correct picture
first, then the other cards. Counting items show the stimulus picture.

Items come from the Airtable corpus item table when LEVANTE_AT_PAT,
LEVANTE_AT_BASEID, and LEVANTE_CORPUSITEMTABLE are set. Pass --corpus to use a
CSV instead.

Usage:
  python utilities/assign_math_downex_screenshots.py
  python utilities/assign_math_downex_screenshots.py --items counting-6-blocks --upload
  python utilities/assign_math_downex_screenshots.py --corpus math-item-bank.csv --upload
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import urllib.request
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROJECT_ID = os.environ.get("CROWDIN_PROJECT_ID", "756721")
ASSET_BUCKET = "levante-assets-dev"
ASSET_PREFIX = "visual/egma-math/"
MATH_FILE_NAME = "math.xliff"
PICTURE_TRIALS = {
    "Non-symbolic Number Identification",
    "Non-symbolic Number Comparison",
    "Counting",
    "Counting AFC",
}
CARD_HEIGHT = 360
GAP = 16
MARGIN = 16


def get_token() -> str:
    token = os.environ.get("CROWDIN_API_TOKEN", "").strip() or os.environ.get("CROWDIN_TOKEN", "").strip()
    if token:
        return token
    token_path = Path.home() / ".crowdin_api_token"
    if token_path.exists():
        return token_path.read_text(encoding="utf-8").strip()
    raise RuntimeError("Crowdin token not found. Set CROWDIN_API_TOKEN or create ~/.crowdin_api_token.")


def crowdin_client(project_id: str):
    from crowdin_api import CrowdinClient

    return CrowdinClient(token=get_token(), project_id=int(project_id))


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        parts = [_text(item) for item in value]
        return next((part for part in parts if part), "")
    if isinstance(value, dict):
        if value.get("name"):
            return str(value["name"])
        linked = value.get("valuesByLinkedRecordId") or {}
        for entry in linked.values():
            text = _text(entry)
            if text:
                return text
        return ""
    return str(value).strip()


def is_downex(value: object) -> bool:
    if value is True:
        return True
    return _text(value).lower() in {"true", "1", "yes", "checked"}


def image_keys(trial_type: str, item: str, answer: str, alternatives: Sequence[str]) -> list[str]:
    if "Counting" in trial_type:
        key = item.replace(" ", "")
        return [key] if key else []
    keys = []
    if answer:
        keys.append(answer)
    keys.extend(part.strip() for part in alternatives if part.strip())
    return [key.replace(" ", "") for key in keys]


def picture_items(rows: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    items = []
    seen = set()
    for row in rows:
        item_id = _text(row.get("item_id"))
        trial_type = _text(row.get("trial_type"))
        task = _text(row.get("task"))
        if not item_id or item_id in seen or not is_downex(row.get("downex")):
            continue
        if task and task != "math":
            continue
        if trial_type not in PICTURE_TRIALS:
            continue
        alternatives = [part.strip() for part in _text(row.get("response_alternatives")).split(",") if part.strip()]
        seen.add(item_id)
        items.append(
            {
                "item_id": item_id,
                "audio": _text(row.get("audio_file")),
                "trial_type": trial_type,
                "item": _text(row.get("item")),
                "answer": _text(row.get("answer")),
                "alternatives": alternatives,
            }
        )
    return items


def load_csv(path: Path) -> list[dict[str, object]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def load_airtable() -> list[dict[str, object]]:
    from pyairtable import Api

    missing = [
        name
        for name in ("LEVANTE_AT_PAT", "LEVANTE_AT_BASEID", "LEVANTE_CORPUSITEMTABLE")
        if not os.environ.get(name, "").strip()
    ]
    if missing:
        raise RuntimeError(
            "Missing Airtable configuration: "
            + ", ".join(missing)
            + ". Pass --corpus or set those variables."
        )
    table = Api(os.environ["LEVANTE_AT_PAT"]).table(
        os.environ["LEVANTE_AT_BASEID"],
        os.environ["LEVANTE_CORPUSITEMTABLE"],
    )
    fields = ["item_id", "audio_file", "item", "answer", "response_alternatives", "trial_type", "downex", "task"]
    records = table.all(formula="AND({downex}, FIND('math', ARRAYJOIN({task})))", fields=fields)
    return [record.get("fields") or {} for record in records]


def download_image(name: str, bucket: str) -> Image.Image:
    url = f"https://storage.googleapis.com/{bucket}/{ASSET_PREFIX}{urllib_quote(name)}.webp"
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read()
    return Image.open(io.BytesIO(data)).convert("RGBA")


def urllib_quote(name: str) -> str:
    from urllib.parse import quote

    return quote(name)


def compose(images: Sequence[Image.Image]) -> Image.Image:
    cards = []
    for image in images:
        ratio = CARD_HEIGHT / image.height
        cards.append(image.resize((max(1, round(image.width * ratio)), CARD_HEIGHT), Image.Resampling.LANCZOS))
    width = MARGIN * 2 + sum(card.width for card in cards) + GAP * max(0, len(cards) - 1)
    canvas = Image.new("RGB", (width, CARD_HEIGHT + MARGIN * 2), (255, 255, 255))
    x = MARGIN
    for card in cards:
        canvas.paste(card, (x, MARGIN), card)
        x += card.width + GAP
    return canvas


def _rows(payload: dict) -> list[dict]:
    rows = []
    for row in payload.get("data") or []:
        if isinstance(row, dict) and isinstance(row.get("data"), dict):
            rows.append(row["data"])
        elif isinstance(row, dict):
            rows.append(row)
    return rows


def _pages(fetch) -> Iterable[dict]:
    offset = 0
    while True:
        rows = _rows(fetch(offset))
        if not rows:
            break
        yield from rows
        if len(rows) < 500:
            break
        offset += 500


def math_file_id(client) -> int:
    for row in _pages(lambda offset: client.source_files.list_files(limit=500, offset=offset)):
        if str(row.get("name") or "") == MATH_FILE_NAME:
            return int(row["id"])
    raise RuntimeError(f"Crowdin file {MATH_FILE_NAME} was not found")


def string_ids(client, file_id: int) -> dict[str, int]:
    mapping = {}
    for row in _pages(lambda offset: client.source_strings.list_strings(fileId=file_id, limit=500, offset=offset)):
        identifier = str(row.get("identifier") or "")
        if identifier:
            mapping[identifier] = int(row["id"])
    return mapping


def existing_names(client, string_id: int) -> set[str]:
    payload = client.screenshots.list_screenshots(stringIds=[string_id], limit=100, offset=0)
    return {str(row.get("name") or "") for row in _rows(payload)}


def upload_screenshot(client, string_id: int, name: str, image: Image.Image) -> int:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    buffer.name = name
    stored = client.storages.add_storage(buffer)
    created = client.screenshots.add_screenshot(storageId=int(stored["data"]["id"]), name=name)
    screenshot = created.get("data") or created
    screenshot_id = int(screenshot["id"])
    client.screenshots.add_tag(
        screenshotId=screenshot_id,
        data=[
            {
                "stringId": string_id,
                "position": {"x": 0, "y": 0, "width": image.width, "height": image.height},
            }
        ],
    )
    return screenshot_id


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Attach math downward-extension pictures to Crowdin strings")
    parser.add_argument("--project", default=DEFAULT_PROJECT_ID, help="Crowdin project id (default 756721)")
    parser.add_argument("--corpus", type=Path, help="Math item-bank CSV. Airtable is used when this is omitted")
    parser.add_argument("--bucket", default=ASSET_BUCKET, help="GCS bucket that holds visual/egma-math images")
    parser.add_argument("--items", default="", help="Comma-separated item ids to process")
    parser.add_argument("--limit", type=int, default=0, help="Max items to process (0 means all)")
    parser.add_argument("--upload", action="store_true", help="Create the Crowdin screenshots")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    rows = load_csv(args.corpus) if args.corpus else load_airtable()
    items = picture_items(rows)
    wanted = {item.strip() for item in args.items.split(",") if item.strip()}
    if wanted:
        items = [item for item in items if item["item_id"] in wanted]
    if args.limit > 0:
        items = items[: args.limit]
    if not items:
        print("No downward-extension picture items to process.")
        return 0
    client = crowdin_client(args.project) if args.upload else None
    identifiers = string_ids(client, math_file_id(client)) if client else {}
    uploaded = 0
    skipped = 0
    errors = 0
    for item in items:
        keys = image_keys(item["trial_type"], item["item"], item["answer"], item["alternatives"])
        name = f"{item['item_id']}.png"
        if not keys or not item["audio"]:
            errors += 1
            print(f"skip {item['item_id']}: missing audio file or image name")
            continue
        if not args.upload:
            print(f"would upload {name} -> {item['audio']} images={','.join(keys)}")
            continue
        string_id = identifiers.get(item["audio"])
        if string_id is None:
            errors += 1
            print(f"skip {item['item_id']}: no Crowdin string {item['audio']}")
            continue
        if name in existing_names(client, string_id):
            skipped += 1
            print(f"skip {name}: already attached to {item['audio']}")
            continue
        try:
            image = compose([download_image(key, args.bucket) for key in keys])
            screenshot_id = upload_screenshot(client, string_id, name, image)
        except Exception as exc:
            errors += 1
            print(f"error {item['item_id']}: {exc}")
            continue
        uploaded += 1
        print(f"uploaded {screenshot_id} {name} -> {item['audio']} images={','.join(keys)}")
    if args.upload:
        print(f"{uploaded} uploaded, {skipped} already present, {errors} errors.")
    else:
        print(f"{len(items) - errors} ready, {errors} errors. Pass --upload to create screenshots.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
